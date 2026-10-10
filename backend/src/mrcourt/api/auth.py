from fastapi import APIRouter, Response, status

from mrcourt.api.deps import CurrentUser, DbSession
from mrcourt.config import get_settings
from mrcourt.models import User
from mrcourt.schemas.auth import (
    ForgotPassword,
    LoginRequest,
    OtpRequest,
    OtpVerify,
    PhoneCode,
    RegisterRequest,
    ResetPassword,
)
from mrcourt.services import auth as auth_service
from mrcourt.services import invitations as invitation_service
from mrcourt.services import notify
from mrcourt.services.session import SESSION_COOKIE, issue_session

router = APIRouter(prefix="/auth", tags=["auth"])


def _start_session(response: Response, user: User) -> None:
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        issue_session(user.id, user.session_epoch),
        max_age=settings.session_max_age_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, response: Response, db: DbSession) -> dict[str, str]:
    user = auth_service.register(db, data)
    invitation_service.link_pending_for(db, user)
    db.commit()
    _start_session(response, user)
    return {"id": str(user.id)}


@router.post("/login")
def login(data: LoginRequest, response: Response, db: DbSession) -> dict[str, str]:
    user = auth_service.authenticate(db, data.identifier, data.password)
    _start_session(response, user)
    return {"id": str(user.id)}


@router.post("/otp/request", status_code=status.HTTP_202_ACCEPTED)
def otp_request(data: OtpRequest, db: DbSession) -> dict[str, str]:
    auth_service.request_otp(db, data.identifier)
    db.commit()
    # Same response whether or not the account exists, so contacts cannot be probed.
    return {"detail": "If the account exists, a code has been sent."}


@router.post("/otp/verify")
def otp_verify(data: OtpVerify, response: Response, db: DbSession) -> dict[str, str]:
    user = auth_service.verify_otp(db, data.identifier, data.code)
    db.commit()
    _start_session(response, user)
    return {"id": str(user.id)}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def _delivery() -> str:
    """"sms" when a real text-message service sends the code, "development" when it only goes to the outbox."""
    return "sms" if notify.delivers_for_real() else "development"


@router.post("/phone/request", status_code=status.HTTP_202_ACCEPTED)
def phone_request(user: CurrentUser, db: DbSession) -> dict[str, str]:
    auth_service.request_phone_code(db, user)
    db.commit()
    return {"detail": "A code has been sent to your mobile number.", "delivery": _delivery()}


@router.post("/phone/verify")
def phone_verify(data: PhoneCode, user: CurrentUser, db: DbSession) -> dict[str, str]:
    auth_service.verify_phone_code(db, user, data.code)
    db.commit()
    return {"detail": "Your mobile number is verified."}


@router.post("/password/forgot", status_code=status.HTTP_202_ACCEPTED)
def password_forgot(data: ForgotPassword, db: DbSession) -> dict[str, str]:
    auth_service.forgot_password(db, data.identifier)
    db.commit()
    # The same words whether or not an account matches, so this cannot be used to look people up.
    return {"detail": "If an account matches, a code has been sent to its verified mobile number.", "delivery": _delivery()}


@router.post("/password/reset")
def password_reset(data: ResetPassword, db: DbSession) -> dict[str, str]:
    auth_service.reset_password(db, data.identifier, data.code, data.new_password)
    db.commit()
    return {"detail": "Your password has been changed. Please sign in."}
