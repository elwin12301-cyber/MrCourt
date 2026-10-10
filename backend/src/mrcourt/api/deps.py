from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from mrcourt.db.base import get_db
from mrcourt.models import User
from mrcourt.services.session import SESSION_COOKIE, read_session_full

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> User:
    session = read_session_full(token)
    user = db.get(User, session[0]) if session else None
    # A suspended or deactivated person, or a cookie older than the last forced sign-out, is refused.
    if user is None or user.status != "active" or session is None or session[1] != user.session_epoch:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_advocate(user: CurrentUser) -> User:
    if user.role != "advocate":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only advocates can do this")
    return user


Advocate = Annotated[User, Depends(require_advocate)]


def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrators only")
    return user


Admin = Annotated[User, Depends(require_admin)]


def require_client(user: CurrentUser) -> User:
    if user.role != "petitioner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This is for clients only")
    return user


Client = Annotated[User, Depends(require_client)]
