import re

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from mrcourt.api.deps import CurrentUser, DbSession
from mrcourt.models import User
from mrcourt.schemas.auth import DeactivateRequest, MeOut, MePatch, SettingsOut, SettingsPatch
from mrcourt.services import privacy
from mrcourt.services.session import SESSION_COOKIE

router = APIRouter(prefix="/me", tags=["me"])


def _me(user: User) -> MeOut:
    return MeOut.model_validate(user).model_copy(update={"phone_verified": user.phone_verified_at is not None})


@router.get("", response_model=MeOut)
def get_me(user: CurrentUser) -> MeOut:
    return _me(user)


@router.patch("", response_model=MeOut)
def patch_me(data: MePatch, user: CurrentUser, db: DbSession) -> MeOut:
    if data.full_name is not None:
        user.full_name = data.full_name.strip()
    if data.phone is not None:
        phone = re.sub(r"[\s-]", "", data.phone) or None
        if phone and db.scalars(select(User).where(User.phone == phone, User.id != user.id)).first():
            raise HTTPException(status.HTTP_409_CONFLICT, "That phone number is already in use")
        if phone != user.phone:
            user.phone_verified_at = None  # a new number has to be checked again
        user.phone = phone
    if data.bar_registration_number is not None and user.role == "advocate":
        number = data.bar_registration_number.strip() or None
        if number != user.bar_registration_number:
            # A new or changed number must be (re)confirmed by an administrator.
            user.bar_registration_number = number
            user.verification_status = "pending" if number else "none"
            user.verified_by = None
            user.verified_at = None
    db.commit()
    return _me(user)


@router.patch("/settings", response_model=SettingsOut)
def patch_settings(data: SettingsPatch, user: CurrentUser, db: DbSession) -> SettingsOut:
    for field, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(user.settings, field, value)
    db.commit()
    return SettingsOut.model_validate(user.settings)


@router.get("/data-export")
def data_export(user: CurrentUser, db: DbSession) -> dict[str, object]:
    return privacy.export_data(db, user)


@router.post("/deactivate", status_code=status.HTTP_204_NO_CONTENT)
def deactivate(_: DeactivateRequest, user: CurrentUser, db: DbSession) -> Response:
    if user.role == "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator accounts cannot be deactivated here")
    privacy.deactivate(db, user)
    db.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response
