"""Registration, password sign-in, one-time codes, phone verification and password reset."""

import logging
import re
import secrets
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from mrcourt.config import get_settings
from mrcourt.db.base import utcnow
from mrcourt.models import OtpChallenge, User, UserSettings
from mrcourt.schemas.auth import RegisterRequest
from mrcourt.services import ratelimit
from mrcourt.services.notify import Message, get_notifier
from mrcourt.services.session import hash_password, verify_password

RESERVED_USERNAMES = frozenset({"admin", "administrator", "root", "support", "mrcourt", "system", "moderator", "staff", "help", "info"})
INVALID_CREDENTIALS = "Invalid email, phone or password"
# Verified against when no account exists so both failures take about the same time.
_DUMMY_HASH = hash_password("not-a-real-password")


def normalize_identifier(value: str) -> tuple[str, str]:
    """Returns (email_or_empty, phone_or_empty) for a typed identifier."""
    value = value.strip()
    if "@" in value:
        return value.lower(), ""
    return "", re.sub(r"[\s-]", "", value)


def find_user(db: Session, identifier: str) -> User | None:
    """An account by email, phone number or username (a username always starts with a letter)."""
    email, phone = normalize_identifier(identifier)
    conditions = []
    if email:
        conditions.append(User.email == email)
    if phone:
        conditions.append(User.phone == phone)
        if phone[:1].isalpha():
            conditions.append(User.username == phone.lower())
    if not conditions:
        return None
    return db.scalars(select(User).where(or_(*conditions))).first()


def register(db: Session, data: RegisterRequest) -> User:
    email = data.email.lower() if data.email else None
    phone = re.sub(r"[\s-]", "", data.phone) if data.phone else None
    username = data.username.lower() if data.username else None
    if username and username in RESERVED_USERNAMES:
        raise HTTPException(status.HTTP_409_CONFLICT, "That username is not available. Please choose another.")
    if username and db.scalars(select(User).where(User.username == username)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "That username is taken. Please choose another.")
    clash = [User.email == email] if email else []
    if phone:
        clash.append(User.phone == phone)
    if clash and db.scalars(select(User).where(or_(*clash))).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with these details already exists")

    bar_number = data.bar_registration_number if data.role == "advocate" else None
    user = User(
        role=data.role,
        full_name=data.full_name.strip(),
        username=username,
        email=email,
        phone=phone,
        password_hash=hash_password(data.password),
        bar_registration_number=bar_number,
        verification_status="pending" if bar_number else "none",
    )
    user.settings = UserSettings()
    db.add(user)
    db.flush()
    return user


def authenticate(db: Session, identifier: str, password: str) -> User:
    ratelimit.hit(
        f"login:{identifier.strip().lower()}",
        limit=get_settings().login_attempts_per_window,
        window_seconds=15 * 60,
    )
    user = find_user(db, identifier)
    if user is None:
        verify_password(_DUMMY_HASH, password)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_CREDENTIALS)
    if not verify_password(user.password_hash, password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_CREDENTIALS)
    if user.status == "suspended":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This account has been suspended. Please contact the administrator.",
        )
    if user.status != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been deactivated")
    return user


CODE_MINUTES = 10  # phone and password-reset codes live this long; sign-in codes use OTP_TTL_SECONDS


def _issue_code(db: Session, user: User, purpose: str, ttl_seconds: int | None = None) -> str:
    """Makes a 6-digit code for one purpose, replacing any earlier unused code for it."""
    for older in db.scalars(
        select(OtpChallenge).where(
            OtpChallenge.user_id == user.id, OtpChallenge.purpose == purpose, OtpChallenge.consumed_at.is_(None)
        )
    ):
        older.consumed_at = utcnow()
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(
        OtpChallenge(
            user_id=user.id,
            purpose=purpose,
            code_hash=hash_password(code),
            expires_at=utcnow() + timedelta(seconds=ttl_seconds or CODE_MINUTES * 60),
        )
    )
    return code


def _check_code(db: Session, user: User, purpose: str, code: str) -> bool:
    """True (and the code is used up) when `code` is the live code for this purpose."""
    challenge = db.scalars(
        select(OtpChallenge)
        .where(OtpChallenge.user_id == user.id, OtpChallenge.purpose == purpose, OtpChallenge.consumed_at.is_(None))
        .order_by(OtpChallenge.created_at.desc())
    ).first()
    if challenge is None or challenge.attempts >= get_settings().otp_max_attempts:
        return False
    expires = challenge.expires_at
    if expires.tzinfo is None:  # SQLite returns naive datetimes; treat them as UTC
        expires = expires.replace(tzinfo=utcnow().tzinfo)
    if expires <= utcnow():
        return False
    challenge.attempts += 1
    if not verify_password(challenge.code_hash, code):
        db.commit()  # keep the failed attempt even though the caller refuses
        return False
    challenge.consumed_at = utcnow()
    return True


def _deliver(message: Message) -> None:
    """Sends a code. A sending failure must not change the reply (it would reveal that the account exists)."""
    try:
        get_notifier().send(message)
    except Exception:  # noqa: BLE001 - the text-message service being down or refusing is not the caller's error
        logging.getLogger(__name__).warning("A code could not be delivered; the person can ask for another")


def request_otp(db: Session, identifier: str) -> None:
    """Sends a sign-in code if the account exists. Callers respond identically either way."""
    ratelimit.hit(f"otp-request:{identifier.strip().lower()}", limit=5, window_seconds=10 * 60)
    user = find_user(db, identifier)
    if user is None or user.status != "active":
        return
    code = _issue_code(db, user, "login", get_settings().otp_ttl_seconds)
    contact = user.phone or user.email or ""
    _deliver(
        Message(contact=contact, text=f"Your MrCourt code is {code}. It expires in 5 minutes.", code=code)
    )


def verify_otp(db: Session, identifier: str, code: str) -> User:
    ratelimit.hit(f"otp-verify:{identifier.strip().lower()}", limit=20, window_seconds=15 * 60)
    user = find_user(db, identifier)
    if user is None or user.status != "active" or not _check_code(db, user, "login", code):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired code")
    return user


# ----- phone verification --------------------------------------------------------------------


def request_phone_code(db: Session, user: User) -> None:
    """Texts a code to the phone on the account. Tells the caller if there is nothing to verify."""
    if not user.phone:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Add a mobile number first")
    if user.phone_verified_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This phone number is already verified")
    ratelimit.hit(f"phone-code:{user.id}", limit=5, window_seconds=60 * 60)
    code = _issue_code(db, user, "phone")
    _deliver(
        Message(
            contact=user.phone,
            text=f"Your MrCourt verification code is {code}. It expires in {CODE_MINUTES} minutes.",
            code=code,
        )
    )


def verify_phone_code(db: Session, user: User, code: str) -> None:
    ratelimit.hit(f"phone-verify:{user.id}", limit=20, window_seconds=60 * 60)
    if not user.phone or not _check_code(db, user, "phone", code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired code")
    user.phone_verified_at = utcnow()


# ----- forgot password -----------------------------------------------------------------------


def forgot_password(db: Session, identifier: str) -> None:
    """Texts a reset code to a verified phone. Callers respond identically whether or not it did."""
    ratelimit.hit(f"forgot:{identifier.strip().lower()}", limit=5, window_seconds=60 * 60)
    user = find_user(db, identifier)
    if user is None or user.status != "active" or not user.phone or user.phone_verified_at is None:
        return
    code = _issue_code(db, user, "reset")
    _deliver(
        Message(
            contact=user.phone,
            text=(
                f"Your MrCourt password reset code is {code}. It expires in {CODE_MINUTES} minutes. "
                "If you did not ask for it, ignore this message."
            ),
            code=code,
        )
    )


def reset_password(db: Session, identifier: str, code: str, new_password: str) -> User:
    ratelimit.hit(f"reset:{identifier.strip().lower()}", limit=20, window_seconds=60 * 60)
    user = find_user(db, identifier)
    if user is None or user.status != "active" or not _check_code(db, user, "reset", code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired code")
    user.password_hash = hash_password(new_password)
    user.session_epoch += 1  # signs this person out everywhere
    return user
