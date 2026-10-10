"""Password hashing and signed session cookies."""

import uuid

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from itsdangerous import BadSignature, URLSafeTimedSerializer

from mrcourt.config import get_settings

SESSION_COOKIE = "mrcourt_session"
# Automated test runs hash with a small, fast setting so many parallel sign-ins do not starve the
# machine. Every other environment, including development, uses the library's standard cost.
# Verification reads the cost from each stored hash, so the two kinds still verify either way.
_hasher = (
    PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
    if get_settings().environment == "test"
    else PasswordHasher()
)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    """Constant-shape check: returns False for missing hashes instead of raising."""
    if not password_hash:
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def _serializer() -> URLSafeTimedSerializer:
    settings = get_settings()
    secret = settings.session_secret
    if not secret:
        if settings.environment == "production":
            raise RuntimeError("SESSION_SECRET must be set in production")
        secret = "dev-only-insecure-secret"
    return URLSafeTimedSerializer(secret, salt="mrcourt-session")


def issue_session(user_id: uuid.UUID, epoch: int = 0) -> str:
    return _serializer().dumps(f"{user_id}:{epoch}")


def read_session_full(token: str | None) -> tuple[uuid.UUID, int] | None:
    """The person and the session epoch the cookie was issued under, or None if it is not valid."""
    if not token:
        return None
    try:
        value = _serializer().loads(token, max_age=get_settings().session_max_age_seconds)
        user_part, _, epoch_part = str(value).partition(":")
        return uuid.UUID(user_part), int(epoch_part or 0)
    except (BadSignature, ValueError):
        return None


def read_session(token: str | None) -> uuid.UUID | None:
    full = read_session_full(token)
    return full[0] if full else None
