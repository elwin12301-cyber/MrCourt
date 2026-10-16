"""What administrators see of the WhatsApp channel: counts, failures and whether it works (feature 010).

Built only from the delivery records (kind, channel, status, time, person). There is no message text anywhere
to show: not in the records, and not in what this returns.
"""

import uuid
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from mrcourt.db.base import utcnow
from mrcourt.models import Message, User
from mrcourt.schemas.whatsapp import FailureRow, FailuresPage, MessageTotal, ServiceHealth, SummaryOut
from mrcourt.services import audit
from mrcourt.services.cases import aware
from mrcourt.services.whatsapp import consent, outbox
from mrcourt.services.whatsapp.channel import get_channel, is_configured, provider_name

STATUSES = ("queued", "sent", "delivered", "read", "failed")
OUTAGE_REASONS = ("provider_down", "provider_error", "not_configured")
STREAK = 3  # this many recent WhatsApp messages in a row refused for provider reasons: the service looks down


def health(db: Session, now: datetime) -> ServiceHealth:
    provider = get_channel().name if is_configured() else provider_name()
    if not is_configured():
        return ServiceHealth(provider=provider, configured=False, healthy=None, last_ok_at=None)
    recent = list(
        db.scalars(
            select(Message).where(Message.channel == "whatsapp", Message.status != "queued").order_by(Message.created_at.desc()).limit(STREAK)
        )
    )
    last_ok = db.scalar(
        select(func.max(Message.created_at)).where(Message.channel == "whatsapp", Message.status.in_(("sent", "delivered", "read")))
    )
    down = len(recent) == STREAK and all(m.status == "failed" and m.failure_reason in OUTAGE_REASONS for m in recent)
    return ServiceHealth(provider=provider, configured=True, healthy=not down, last_ok_at=aware(last_ok) if last_ok else None)


def summary(db: Session, days: int, now: datetime | None = None) -> SummaryOut:
    now = now or utcnow()
    rows = db.execute(
        select(Message.kind, Message.channel, Message.status, func.count())
        .where(Message.created_at >= now - timedelta(days=days))
        .group_by(Message.kind, Message.channel, Message.status)
    ).all()
    table: dict[tuple[str, str], dict[str, int]] = {}
    for kind, channel, state, count in rows:
        table.setdefault((kind, channel), {s: 0 for s in STATUSES})[state] = count
    totals = [MessageTotal(kind=k, channel=c, **counts) for (k, c), counts in sorted(table.items())]
    return SummaryOut(days=days, service=health(db, now), totals=totals)


def failures(db: Session, admin: User, days: int, limit: int, before: tuple[datetime, uuid.UUID] | None) -> FailuresPage:
    """WhatsApp messages that failed, newest first: who, what kind, why (a plain code) and whether an SMS replaced
    it. Never the words, never the phone number."""
    now = utcnow()
    query = (
        select(Message, User.full_name)
        .join(User, User.id == Message.user_id)
        .where(Message.channel == "whatsapp", Message.status == "failed", Message.created_at >= now - timedelta(days=days))
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(limit + 1)
    )
    if before is not None:
        stamp, ident = before
        query = query.where(or_(Message.created_at < stamp, and_(Message.created_at == stamp, Message.id < ident)))
    found = db.execute(query).all()
    page = found[:limit]
    covered = set(
        db.scalars(
            select(Message.fallback_of).where(
                Message.fallback_of.in_([m.id for m, _ in page] or [uuid.uuid4()]), Message.channel == "sms", Message.status == "sent"
            )
        )
    )
    items = [
        FailureRow(
            id=m.id, time=aware(m.created_at), kind=m.kind, person=name, reason=m.failure_reason or "provider_error",
            fell_back_to_sms=m.id in covered, can_resend=_resendable(db, m),
        )
        for m, name in page
    ]
    cursor = f"{aware(page[-1][0].created_at).isoformat()}|{page[-1][0].id}" if len(found) > limit and page else None
    audit.record(db, admin, "whatsapp.admin.failures.view", "workspace", None, shown=len(items))  # a count, never the rows
    return FailuresPage(items=items, next_before=cursor)


def _resendable(db: Session, row: Message) -> bool:
    """A failed reminder, update or activity message for someone still linked, opted in and not already reached."""
    if row.kind == "code" or row.status != "failed" or row.channel != "whatsapp":
        return False
    user = db.get(User, row.user_id)
    if user is None or user.status != "active" or not consent.is_enabled(db, user.id, outbox.CONSENT_FOR[row.kind]):
        return False
    if outbox.variables_for(db, row) is None:
        return False
    reached = db.scalar(
        select(Message.id).where(
            Message.user_id == row.user_id, Message.case_id == row.case_id, Message.kind == row.kind,
            Message.channel == "whatsapp", Message.status.in_(("sent", "delivered", "read")), Message.created_at > row.created_at,
        )
    )
    return reached is None


def resend(db: Session, admin: User, message_id: uuid.UUID) -> Message:
    """Sends a failed message again as a new record. Audited without the words."""
    row = db.get(Message, message_id)
    if row is None or not _resendable(db, row):
        raise HTTPException(status.HTTP_409_CONFLICT, "cannot_resend")
    user = db.get(User, row.user_id)
    variables = outbox.variables_for(db, row)
    assert user is not None and variables is not None
    new = outbox._whatsapp(db, user, row.kind, variables, case_id=row.case_id, hearing_id=row.hearing_id)  # noqa: SLF001
    if new.status == "failed":
        outbox.fallback(db, new)
    audit.record(db, admin, "whatsapp.admin.resend", "message", row.id, kind=row.kind, result=new.status)
    return new
