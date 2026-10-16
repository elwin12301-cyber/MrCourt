"""Linking a verified number and choosing what is sent over WhatsApp (feature 010).

Everything is off until the person switches it on, one kind at a time. Nothing is sent to a number that is not
verified and linked (the one exception, a code the person has just asked for, is handled by the sender, which
uses SMS when WhatsApp codes are off). Linking, unlinking, consent changes and STOP are written to the audit log
without message content.
"""

import unicodedata
import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from mrcourt.config import get_settings
from mrcourt.db.base import utcnow
from mrcourt.models import MessageConsent, User, WhatsAppLink
from mrcourt.services import audit
from mrcourt.services.notify import to_msisdn

KINDS_BY_ROLE = {
    "petitioner": ("codes", "reminders", "updates"),
    "advocate": ("codes", "reminders", "activity"),
    "admin": ("codes",),
}

DESCRIBES = {
    "codes": "Your sign-in and verification codes.",
    "reminders": "The case title and the date and time of a hearing, 5 days before, 1 day before and on the day.",
    "updates": "A short note that there is news on a case, with the case title only. The detail stays in MrCourt.",
    "activity": "A short note that a client sent a message about a case, with the case title only.",
}

# STOP in English, Hindi and Tamil. Matching ignores case, spaces and punctuation.
STOP_WORDS = frozenset(
    {"stop", "stopall", "stopmessages", "unsubscribe", "optout", "cancel", "रोकें", "रुकें", "बंद", "बंदकरें", "நிறுத்து", "நிறுத்தவும்", "நிறுத்துங்கள்"}
)


def kinds_for(role: str) -> tuple[str, ...]:
    return KINDS_BY_ROLE.get(role, ())


def is_stop(text: str) -> bool:
    # Keep letters, combining marks (vowel signs in Hindi and Tamil) and digits; drop spaces and punctuation.
    cleaned = "".join(ch for ch in (text or "").lower() if unicodedata.category(ch)[0] in "LMN")
    return cleaned in STOP_WORDS


def msisdn_of(user: User) -> str | None:
    """The account's phone number as digits with its country code, or None."""
    return to_msisdn(user.phone or "", get_settings().sms_country_code) if user.phone else None


def mask(msisdn: str | None) -> str | None:
    """+91 ••••• ••172: all but the last three digits hidden."""
    if not msisdn:
        return None
    cc = get_settings().sms_country_code
    rest = msisdn[len(cc):] if msisdn.startswith(cc) and len(msisdn) > len(cc) + 6 else msisdn
    return f"+{cc} ••••• ••{rest[-3:]}" if msisdn.startswith(cc) else f"••••• ••{msisdn[-3:]}"


def get_link(db: Session, user_id: uuid.UUID) -> WhatsAppLink | None:
    """The person's active link, if any."""
    link = db.get(WhatsAppLink, user_id)
    return link if link is not None and link.active else None


def user_for_number(db: Session, msisdn: str) -> User | None:
    """The active account whose verified, linked number this is. Nobody else may use the channel."""
    link = db.scalar(select(WhatsAppLink).where(WhatsAppLink.msisdn == msisdn, WhatsAppLink.unlinked_at.is_(None)))
    if link is None:
        return None
    user = db.get(User, link.user_id)
    if user is None or user.status != "active" or user.phone_verified_at is None or msisdn_of(user) != msisdn:
        return None
    return user


def is_enabled(db: Session, user_id: uuid.UUID, kind: str) -> bool:
    """True only for a person with an active link who switched this kind on."""
    if get_link(db, user_id) is None:
        return False
    row = db.get(MessageConsent, (user_id, kind))
    return bool(row and row.enabled)


def _all_off(db: Session, user_id: uuid.UUID, changed_by: str) -> None:
    now = utcnow()
    for row in db.scalars(select(MessageConsent).where(MessageConsent.user_id == user_id)):
        if row.enabled:
            row.enabled, row.changed_at, row.changed_by = False, now, changed_by


def link(db: Session, user: User) -> WhatsAppLink:
    """Links the account's verified number. Everything stays off until switched on."""
    if not user.phone or user.phone_verified_at is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "phone_not_verified")
    msisdn = msisdn_of(user)
    if msisdn is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "phone_not_verified")
    taken = db.scalar(select(WhatsAppLink).where(WhatsAppLink.msisdn == msisdn, WhatsAppLink.user_id != user.id))
    if taken is not None:
        if taken.active:
            raise HTTPException(status.HTTP_409_CONFLICT, "number_in_use")  # never says whose number it is
        db.delete(taken)  # an old, inactive link of someone who gave the number up
        db.flush()
    row = db.get(WhatsAppLink, user.id)
    if row is None:
        row = WhatsAppLink(user_id=user.id, msisdn=msisdn)
        db.add(row)
    if row.unlinked_at is not None or row.msisdn != msisdn:
        _all_off(db, user.id, "system")
    row.msisdn, row.linked_at, row.unlinked_at = msisdn, utcnow(), None
    audit.record(db, user, "whatsapp.link", "user", user.id)
    db.flush()
    return row


def unlink(db: Session, user: User, changed_by: str = "person") -> None:
    """Stops everything and deactivates the link (the person, or the system when the phone number changed)."""
    row = db.get(WhatsAppLink, user.id)
    if row is None or row.unlinked_at is not None:
        return
    row.unlinked_at = utcnow()
    _all_off(db, user.id, changed_by)
    audit.record(db, user, "whatsapp.unlink", "user", user.id, by=changed_by)
    db.flush()


def set_consent(db: Session, user: User, kind: str, enabled: bool) -> None:
    if kind not in kinds_for(user.role):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    if get_link(db, user.id) is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "not_linked")
    row = db.get(MessageConsent, (user.id, kind))
    if row is None:
        row = MessageConsent(user_id=user.id, kind=kind, enabled=enabled, changed_at=utcnow(), changed_by="person")
        db.add(row)
    elif row.enabled != enabled:
        row.enabled, row.changed_at, row.changed_by = enabled, utcnow(), "person"
    else:
        return
    audit.record(db, user, "whatsapp.consent", "user", user.id, kind=kind, enabled=enabled)
    db.flush()


def stop_all(db: Session, user: User) -> None:
    """The person replied STOP: every kind off at once. Switching back on is done in Settings."""
    _all_off(db, user.id, "stop")
    audit.record(db, user, "whatsapp.stop", "user", user.id)
    db.flush()


def view(db: Session, user: User) -> dict[str, object]:
    """What the Settings screen shows."""
    from mrcourt.services.whatsapp.channel import is_configured

    row = get_link(db, user.id)
    consents = {c.kind: c for c in db.scalars(select(MessageConsent).where(MessageConsent.user_id == user.id))}
    kinds = []
    for kind in kinds_for(user.role):
        c = consents.get(kind)
        changed: datetime | None = c.changed_at if c else None
        kinds.append({"kind": kind, "enabled": bool(c and c.enabled and row), "changed_at": changed, "describes": DESCRIBES[kind]})
    return {
        "available": is_configured(),
        "linked": row is not None,
        "number": mask(row.msisdn) if row else None,
        "can_link": user.phone_verified_at is not None and bool(user.phone),
        "kinds": kinds,
        "last_sent_at": row.last_sent_at if row else None,
    }
