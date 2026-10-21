"""Housekeeping for the WhatsApp channel. Run on a schedule: `python -m mrcourt.services.whatsapp.jobs`.

Also run by the in-app loop (see main.py). Delivery records and incoming-message rows are kept 90 days; an
expired "choose a case" list is removed.
"""

import logging
import threading
import time
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from mrcourt.db.base import get_sessionmaker, utcnow
from mrcourt.models import ConversationState, InboundMessage, Message

logger = logging.getLogger(__name__)

RETENTION_DAYS = 90


def purge(db: Session, now: datetime | None = None) -> dict[str, int]:
    """Deletes delivery records and incoming-message rows older than 90 days and expired conversation state."""
    now = now or utcnow()
    cutoff = now - timedelta(days=RETENTION_DAYS)
    counts = {
        "messages": db.execute(delete(Message).where(Message.created_at < cutoff)).rowcount or 0,
        "inbound": db.execute(delete(InboundMessage).where(InboundMessage.created_at < cutoff)).rowcount or 0,
        "state": db.execute(delete(ConversationState).where(ConversationState.expires_at < now)).rowcount or 0,
    }
    return counts


MAX_ATTEMPTS = 3
STUCK_AFTER = timedelta(minutes=1)  # a message still "received" this long after arriving was not finished


def retry_unfinished(db: Session, now: datetime | None = None) -> dict[str, int]:
    """Handles messages left unfinished (for example by a restart) a few times, then gives up on them."""
    from mrcourt.services.whatsapp import inbound

    now = now or utcnow()
    stuck = list(
        db.scalars(
            select(InboundMessage).where(InboundMessage.status == "received", InboundMessage.created_at < now - STUCK_AFTER)
        )
    )
    retried = gave_up = 0
    for row in stuck:
        if row.attempts >= MAX_ATTEMPTS:
            row.status, row.payload = "failed", None
            gave_up += 1
            continue
        try:
            with db.begin_nested():
                inbound.process(db, row.id)
            retried += 1
        except Exception as error:  # noqa: BLE001 - tried again next time, up to the limit
            logger.warning("A stuck WhatsApp message could not be handled (%s)", type(error).__name__)
    return {"retried": retried, "gave_up": gave_up}


def flush(db: Session, now: datetime | None = None) -> dict[str, int]:
    """What should happen within a minute: unfinished messages retried and waiting nudges sent."""
    from mrcourt.services.whatsapp import outbox

    counts = retry_unfinished(db, now)
    counts["nudges"] = outbox.flush_due(db, now)
    counts["polled"] = poll_delivery(db, now)
    return counts


POLL_AFTER = timedelta(seconds=20)
POLL_UNTIL = timedelta(days=2)
POLL_BATCH = 50


def poll_delivery(db: Session, now: datetime | None = None) -> int:
    """Asks Fast2SMS about template messages still "queued" or "sent" (it can reach us by webhook only on a public
    address). Reports apply the same way as webhook ones: the status only moves forward and a failure starts the SMS
    fallback. Returns how many messages were checked."""
    from mrcourt.services.whatsapp import outbox
    from mrcourt.services.whatsapp.channel import get_channel, provider_name

    if provider_name() != "fast2sms":
        return 0
    channel = get_channel()
    fetch = getattr(channel, "fetch_report", None)
    if fetch is None:
        return 0
    now = now or utcnow()
    rows = list(
        db.scalars(
            select(Message)
            .where(
                Message.channel == "whatsapp", Message.provider == "fast2sms", Message.status.in_(("queued", "sent")),
                Message.provider_message_id.is_not(None), Message.created_at < now - POLL_AFTER, Message.created_at > now - POLL_UNTIL,
            )
            .order_by(Message.created_at)
            .limit(POLL_BATCH)
        )
    )
    checked = 0
    for row in rows:
        if not row.provider_message_id or row.provider_message_id.startswith(("session-", "f2s-")):
            continue  # replies and ids we made up have nothing to look up
        report = fetch(row.provider_message_id)
        checked += 1
        if report is not None:
            with db.begin_nested():
                outbox.apply_report(db, report)
    return checked


def run_once(db: Session, now: datetime | None = None) -> dict[str, int]:
    """Everything that is due, for a scheduler that runs this every minute or so."""
    counts = flush(db, now)
    counts.update(purge(db, now))
    return counts


def flush_loop(stop: threading.Event, seconds: int = 60) -> None:
    """For hosts without a scheduler: flush every minute and purge once an hour (started by main.py)."""
    last_purge = 0.0
    while not stop.is_set():
        session = get_sessionmaker()()
        try:
            counts = flush(session)
            if time.monotonic() - last_purge >= 3600:
                counts.update(purge(session))
                last_purge = time.monotonic()
            session.commit()
            if any(counts.values()):
                logger.info("WhatsApp housekeeping: %s", counts)
        except Exception:  # noqa: BLE001 - tried again in a minute
            session.rollback()
            logger.warning("WhatsApp housekeeping failed", exc_info=True)
        finally:
            session.close()
        stop.wait(seconds)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    with get_sessionmaker()() as db:
        counts = run_once(db)
        db.commit()
    logger.info("WhatsApp housekeeping done: %s", counts)


if __name__ == "__main__":
    main()
