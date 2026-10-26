import re

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from mrcourt.api.deps import CurrentUser, DbSession
from mrcourt.db.base import utcnow
from mrcourt.models import User
from mrcourt.schemas.auth import DeactivateRequest, MeOut, MePatch, SettingsOut, SettingsPatch
from mrcourt.schemas.whatsapp import ConsentIn, WhatsAppSettingsOut
from mrcourt.services import audit, privacy
from mrcourt.services.whatsapp import consent as whatsapp_consent
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
            whatsapp_consent.unlink(db, user, changed_by="system")  # and linked and agreed to again
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
    changes = data.model_dump(exclude_unset=True)
    settings = user.settings
    _change_voice(db, user, changes)
    for field, value in changes.items():
        if field.startswith("voice_"):
            continue
        if value is not None:
            setattr(settings, field, value)
    if "voice_language" in changes:
        settings.voice_language = changes["voice_language"]  # None is a real choice: the app default
    db.commit()
    return SettingsOut.model_validate(settings)


def _change_voice(db: DbSession, user: User, changes: dict[str, object]) -> None:
    """Voice control consent and the cloud option. Consent is required for the cloud option, and withdrawing it
    also turns that option off. Each real change is audited, with who and when and never any phrase or audio."""
    settings = user.settings
    consent = changes.get("voice_consent")
    cloud = changes.get("voice_cloud_opt_in")
    wants_consent = settings.voice_consent if consent is None else bool(consent)
    if cloud and not wants_consent:
        raise HTTPException(422, "Agree to voice control first")
    if consent is True and not settings.voice_consent:
        settings.voice_consent_at = utcnow()
        audit.record(db, user, "voice.consent.on", "user", user.id)
    elif consent is False and settings.voice_consent:
        settings.voice_consent_at = None
        audit.record(db, user, "voice.consent.off", "user", user.id)
        if settings.voice_cloud_opt_in:
            settings.voice_cloud_opt_in = False
            audit.record(db, user, "voice.cloud.off", "user", user.id)
    if cloud is not None and bool(cloud) != settings.voice_cloud_opt_in:
        settings.voice_cloud_opt_in = bool(cloud)
        audit.record(db, user, "voice.cloud.on" if cloud else "voice.cloud.off", "user", user.id)


def _whatsapp(db: DbSession, user: User) -> WhatsAppSettingsOut:
    return WhatsAppSettingsOut(**whatsapp_consent.view(db, user))  # type: ignore[arg-type]


@router.get("/whatsapp", response_model=WhatsAppSettingsOut)
def get_whatsapp(user: CurrentUser, db: DbSession) -> WhatsAppSettingsOut:
    return _whatsapp(db, user)


@router.post("/whatsapp/link", response_model=WhatsAppSettingsOut)
def link_whatsapp(user: CurrentUser, db: DbSession) -> WhatsAppSettingsOut:
    whatsapp_consent.link(db, user)
    db.commit()
    return _whatsapp(db, user)


@router.delete("/whatsapp", status_code=status.HTTP_204_NO_CONTENT)
def unlink_whatsapp(user: CurrentUser, db: DbSession) -> Response:
    whatsapp_consent.unlink(db, user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/whatsapp/consents/{kind}", response_model=WhatsAppSettingsOut)
def set_whatsapp_consent(kind: str, data: ConsentIn, user: CurrentUser, db: DbSession) -> WhatsAppSettingsOut:
    whatsapp_consent.set_consent(db, user, kind, data.enabled)
    db.commit()
    return _whatsapp(db, user)


@router.delete("/whatsapp/history", status_code=status.HTTP_204_NO_CONTENT)
def delete_whatsapp_history(user: CurrentUser, db: DbSession) -> Response:
    """Deletes the person's WhatsApp delivery records held by MrCourt."""
    from sqlalchemy import delete

    from mrcourt.models import Message

    db.execute(delete(Message).where(Message.user_id == user.id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
