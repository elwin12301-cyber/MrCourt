"""Sending over WhatsApp with proof of delivery, and falling back once to SMS (feature 010).

Every message becomes a record (kind, status, time, person; never the words). WhatsApp is used only for a person
with a verified, linked number who switched that kind on. Delivery reports from the provider move the status
forward only; a failure starts one SMS with the same short words. A login code cannot be rebuilt later, so its SMS
fallback happens only when WhatsApp refuses the message at once.
"""

import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mrcourt.config import get_settings
from mrcourt.db.base import utcnow
from mrcourt.models import Case, Hearing, User
from mrcourt.models import Message as MessageRow
from mrcourt.models.whatsapp import STATUS_ORDER
from mrcourt.services.cases import aware
from mrcourt.services.notify import Message as TextMessage
from mrcourt.services.notify import get_notifier
from mrcourt.services.whatsapp import consent
from mrcourt.services.whatsapp.channel import (
    DeliveryReport,
    SendError,
    get_channel,
    render_template,
)

logger = logging.getLogger(__name__)

CONSENT_FOR = {"code": "codes", "reminder": "reminders", "update": "updates", "activity": "activity"}


def text_messages_allowed(user: User) -> bool:
    """The person's SMS is allowed: a verified phone and the "text message reminders" switch on."""
    settings = user.settings
    return bool(user.phone) and user.phone_verified_at is not None and (settings is None or settings.whatsapp_reminders)


def _sent_today(db: Session) -> int:
    midnight = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return db.scalar(
        select(func.count()).select_from(MessageRow).where(
            MessageRow.channel == "whatsapp", MessageRow.created_at >= midnight, MessageRow.provider_message_id.is_not(None)
        )
    ) or 0


def _record(db: Session, user: User, kind: str, channel: str, **fields: object) -> MessageRow:
    row = MessageRow(user_id=user.id, kind=kind, channel=channel, status="queued", created_at=utcnow(), **fields)  # type: ignore[arg-type]
    db.add(row)
    db.flush()
    return row


def _whatsapp(
    db: Session, user: User, kind: str, variables: list[str], *, case_id: uuid.UUID | None = None,
    hearing_id: uuid.UUID | None = None, row: MessageRow | None = None,
) -> MessageRow:
    """One WhatsApp template message to a linked person. Returns its record (status sent or failed).
    A message that was waiting in the queue passes its own record."""
    channel = get_channel()
    link = consent.get_link(db, user.id)
    if row is None:
        row = _record(db, user, kind, "whatsapp", provider=channel.name, case_id=case_id, hearing_id=hearing_id)
    row.provider, row.send_after = channel.name, None
    if link is None:
        row.status, row.failure_reason = "failed", "not_linked"
        return row
    if _sent_today(db) >= get_settings().whatsapp_daily_send_cap:
        row.status, row.failure_reason = "failed", "cap_reached"
        return row
    try:
        row.provider_message_id = channel.send_template(link.msisdn, kind, variables)
        row.status = "sent"
        link.last_sent_at = utcnow()
    except SendError as error:
        row.status, row.failure_reason = "failed", error.reason
    except Exception as error:  # noqa: BLE001 - a provider problem must not break the caller
        logger.warning("A WhatsApp message could not be sent (%s)", type(error).__name__)
        row.status, row.failure_reason = "failed", "provider_error"
    db.flush()
    return row


def _sms(
    db: Session, user: User, kind: str, text: str, *, code: str | None = None, case_id: uuid.UUID | None = None,
    hearing_id: uuid.UUID | None = None, fallback_of: uuid.UUID | None = None, variables: dict[str, str] | None = None,
) -> MessageRow:
    """One text message through the SMS sender. Returns its record (status sent or failed). Never raises."""
    notifier = get_notifier()
    row = _record(db, user, kind, "sms", provider=type(notifier).__name__.removesuffix("Notifier").lower(),
                  case_id=case_id, hearing_id=hearing_id, fallback_of=fallback_of)
    try:
        notifier.send(TextMessage(contact=user.phone or user.email or "", text=text, code=code, kind=kind, variables=variables or {}))
        row.status = "sent"
    except Exception as error:  # noqa: BLE001 - the SMS service being down or refusing is not the caller's error
        logger.warning("A text message could not be sent (%s)", type(error).__name__)
        row.status, row.failure_reason = "failed", "provider_error"
    db.flush()
    return row


# ----- what callers use -----------------------------------------------------------------------------


def send_code(db: Session, user: User, text: str, code: str) -> None:
    """A code the person just asked for. WhatsApp when they chose it (then SMS if WhatsApp refuses at once),
    otherwise SMS. Never raises: a failure must not change the caller's reply, which must not reveal the account."""
    try:
        first: MessageRow | None = None
        if consent.is_enabled(db, user.id, "codes"):
            first = _whatsapp(db, user, "code", [code])
            if first.status != "failed":
                return
        _sms(db, user, "code", text, code=code, fallback_of=first.id if first else None)
    except Exception:  # noqa: BLE001
        logger.warning("A code could not be delivered; the person can ask for another", exc_info=False)


def send_reminder(db: Session, user: User, case: Case, hearing: Hearing, when: datetime, now: datetime) -> bool:
    """A hearing reminder: WhatsApp for a person who opted in (SMS if that fails and texts are allowed), else SMS
    for a person who keeps text reminders on. True when a message was handed to a provider."""
    from mrcourt.services.reminders import when_text

    variables = [case.title, when_text(when, now)]
    words = render_template("reminder", variables)
    sms_vars = {"case": variables[0], "when": variables[1]}
    first: MessageRow | None = None
    if consent.is_enabled(db, user.id, "reminders"):
        first = _whatsapp(db, user, "reminder", variables, case_id=case.id, hearing_id=hearing.id)
        if first.status != "failed":
            return True
    if text_messages_allowed(user):
        row = _sms(db, user, "reminder", words, case_id=case.id, hearing_id=hearing.id,
                   fallback_of=first.id if first else None, variables=sms_vars)
        return row.status != "failed"
    return False


def eligible_for_reminders(db: Session, user: User) -> bool:
    """Someone who can receive a reminder on at least one channel."""
    if user.status != "active" or not user.phone or user.phone_verified_at is None:
        return False
    return text_messages_allowed(user) or consent.is_enabled(db, user.id, "reminders")


# ----- delivery reports and the SMS fallback ---------------------------------------------------------


def variables_for(db: Session, row: MessageRow) -> list[str] | None:
    """The template variables of a message, rebuilt from its case and hearing (the record keeps no words).
    None when it cannot or should not be rebuilt: a login code, or a reminder for a hearing that has passed."""
    from mrcourt.services.reminders import when_text

    case = db.get(Case, row.case_id) if row.case_id else None
    if case is None:
        return None
    if row.kind == "reminder":
        hearing = db.get(Hearing, row.hearing_id) if row.hearing_id else None
        if hearing is None or aware(hearing.scheduled_at) <= utcnow():
            return None  # the hearing has gone or passed: a late reminder would only confuse
        return [case.title, when_text(aware(hearing.scheduled_at), utcnow())]
    if row.kind in ("update", "activity"):
        return [case.title]
    return None


def _fallback_words(db: Session, row: MessageRow) -> tuple[str, dict[str, str]] | None:
    """The short words and SMS template fields for a failed message, rebuilt from the case and hearing."""
    variables = variables_for(db, row)
    if variables is None:
        return None
    sms = {"case": variables[0], "when": variables[1]} if row.kind == "reminder" else {"case": variables[0]}
    return render_template(row.kind, variables), sms


def fallback(db: Session, row: MessageRow) -> MessageRow | None:
    """One SMS for a WhatsApp message that failed, when the person allows texts. Never twice."""
    if row.channel != "whatsapp" or row.kind == "code":
        return None
    if db.scalar(select(MessageRow.id).where(MessageRow.fallback_of == row.id)) is not None:
        return None
    user = db.get(User, row.user_id)
    if user is None or user.status != "active" or not text_messages_allowed(user):
        return None
    words = _fallback_words(db, row)
    if words is None:
        return None
    text, variables = words
    return _sms(db, user, row.kind, text, case_id=row.case_id, hearing_id=row.hearing_id, fallback_of=row.id, variables=variables)


def _latest_to(db: Session, report: DeliveryReport) -> MessageRow | None:
    """The newest message of this provider sent to the report's recipient in the last 3 days that has not failed.
    Used only when the report's own id matches nothing; with two messages in flight to one number it is a best guess."""
    from mrcourt.config import get_settings as settings
    from mrcourt.models import WhatsAppLink
    from mrcourt.services.notify import to_msisdn

    number = to_msisdn(report.recipient or "", settings().sms_country_code)
    link = db.scalar(select(WhatsAppLink).where(WhatsAppLink.msisdn == number)) if number else None
    if link is None:
        return None
    return db.scalar(
        select(MessageRow)
        .where(
            MessageRow.user_id == link.user_id, MessageRow.provider == report.provider, MessageRow.channel == "whatsapp",
            MessageRow.status.in_(("sent", "delivered")), MessageRow.created_at >= utcnow() - timedelta(days=3),
        )
        .order_by(MessageRow.created_at.desc())
    )


def apply_report(db: Session, report: DeliveryReport) -> None:
    """A delivery report from the provider. The status only moves forward; failed is final unless the message
    was already delivered; a failure starts the SMS fallback."""
    row = db.scalar(
        select(MessageRow).where(
            MessageRow.provider == report.provider, MessageRow.provider_message_id == report.provider_message_id
        )
    )
    if row is None and report.recipient:
        row = _latest_to(db, report)  # a provider whose report may not carry the id we stored
    if row is None:
        return
    if report.status == "failed":
        if row.status in ("delivered", "read") or row.status == "failed":
            return
        row.status, row.failure_reason = "failed", report.reason or "provider_error"
        fallback(db, row)
        return
    if row.status == "failed" or report.status not in STATUS_ORDER:
        return
    if STATUS_ORDER[report.status] > STATUS_ORDER.get(row.status, 0):
        row.status = report.status


# ----- short "there is news" messages, held a few minutes so close changes merge into one --------------

NUDGE_KINDS = ("update", "activity")


def queue_nudge(db: Session, user: User, kind: str, case: Case) -> MessageRow | None:
    """Queues one "news on <case>" message for a person who opted in. A second change while one is already
    waiting is merged into it. Never raises: a nudge is never worth failing the change that caused it."""
    try:
        if user.status != "active" or not consent.is_enabled(db, user.id, CONSENT_FOR[kind]):
            return None
        waiting = db.scalar(
            select(MessageRow.id).where(
                MessageRow.user_id == user.id, MessageRow.case_id == case.id, MessageRow.kind == kind, MessageRow.status == "queued"
            )
        )
        if waiting is not None:
            return None
        delay = timedelta(seconds=get_settings().whatsapp_nudge_delay_seconds)
        return _record(db, user, kind, "whatsapp", case_id=case.id, send_after=utcnow() + delay)
    except Exception:  # noqa: BLE001
        logger.warning("A WhatsApp nudge could not be queued", exc_info=False)
        return None


def _nudge_still_wanted(db: Session, row: MessageRow, user: User | None, case: Case | None) -> bool:
    """The person is still active, still opted in, and still allowed to hear about the case."""
    from mrcourt.models import CaseInvitation

    if user is None or case is None or user.status != "active":
        return False
    if not consent.is_enabled(db, user.id, CONSENT_FOR[row.kind]):
        return False
    if row.kind == "activity":
        return case.owner_id == user.id
    return db.scalar(
        select(CaseInvitation.id).where(
            CaseInvitation.case_id == case.id, CaseInvitation.invitee_user_id == user.id, CaseInvitation.status == "accepted"
        )
    ) is not None


def flush_due(db: Session, now: datetime | None = None) -> int:
    """Sends the nudges whose wait is over. One that is no longer wanted, or that a reminder for the same case
    already covers, is dropped without a trace. Returns how many were handed to the provider."""
    now = now or utcnow()
    delay = timedelta(seconds=get_settings().whatsapp_nudge_delay_seconds)
    due = list(
        db.scalars(
            select(MessageRow).where(
                MessageRow.status == "queued", MessageRow.channel == "whatsapp",
                MessageRow.kind.in_(NUDGE_KINDS), MessageRow.send_after <= now,
            )
        )
    )
    sent = 0
    for row in due:
        user, case = db.get(User, row.user_id), db.get(Case, row.case_id) if row.case_id else None
        covered = db.scalar(
            select(MessageRow.id).where(
                MessageRow.user_id == row.user_id, MessageRow.case_id == row.case_id, MessageRow.kind == "reminder",
                MessageRow.created_at >= aware(row.created_at) - delay,
            )
        )
        if covered is not None or not _nudge_still_wanted(db, row, user, case):
            db.delete(row)
            continue
        assert user is not None and case is not None
        done = _whatsapp(db, user, row.kind, [case.title], case_id=case.id, row=row)
        if done.status == "failed":
            fallback(db, done)
        else:
            sent += 1
    db.flush()
    return sent
