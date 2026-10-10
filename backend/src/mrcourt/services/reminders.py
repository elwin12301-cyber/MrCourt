"""Hearing reminders by text message. Run every hour on a schedule: `python -m mrcourt.services.reminders`.

For each hearing in an open case, the advocate who owns the case and every client who has accepted the
invitation are texted 5 days before, 1 day before and on the day of the hearing, once each, as long as
their phone number is verified and text reminders are on. A hearing added at short notice sends one
text that says how soon it is, not a text for each missed step. Texts name the case and the time only.
"""

from datetime import datetime, time, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from mrcourt.db.base import get_sessionmaker, utcnow
from mrcourt.models import Case, CaseInvitation, Hearing, ReminderLog, User
from mrcourt.services.cases import aware
from mrcourt.services.notify import Message, get_notifier

import logging

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))
OFFSETS = (5, 1, 0)  # days before the hearing
FROM_TIME = {5: time(8, 0), 1: time(8, 0), 0: time(7, 0)}  # earliest time of day to send each one (IST)


def due_offsets(when: datetime, now: datetime) -> list[int]:
    """The reminder steps whose time has come for a hearing at `when`."""
    local_when, local_now = when.astimezone(IST), now.astimezone(IST)
    due = []
    for offset in OFFSETS:
        start = datetime.combine(local_when.date() - timedelta(days=offset), FROM_TIME[offset], tzinfo=IST)
        if offset == 0:
            start = min(start, local_when - timedelta(hours=1))  # an early hearing still gets its text
        if local_now >= start:
            due.append(offset)
    return due


def when_text(when: datetime, now: datetime) -> str:
    local_when, local_now = when.astimezone(IST), now.astimezone(IST)
    days = (local_when.date() - local_now.date()).days
    clock = f"{local_when:%I:%M %p}"
    if days <= 0:
        return f"today at {clock}"
    if days == 1:
        return f"tomorrow, {local_when:%d %b}, at {clock}"
    return f"in {days} days, on {local_when:%d %b %Y}, at {clock}"


def _recipients(db: Session, case: Case) -> list[User]:
    people = [case.owner] if getattr(case, "owner", None) else []
    if not people:
        owner = db.get(User, case.owner_id)
        people = [owner] if owner else []
    invitations = db.scalars(
        select(CaseInvitation).where(
            CaseInvitation.case_id == case.id,
            CaseInvitation.status == "accepted",
            CaseInvitation.invitee_user_id.is_not(None),
        )
    )
    for invitation in invitations:
        client = db.get(User, invitation.invitee_user_id)
        if client is not None and client not in people:
            people.append(client)
    return people


def _eligible(user: User) -> bool:
    settings = user.settings
    return (
        user.status == "active"
        and bool(user.phone)
        and user.phone_verified_at is not None
        and (settings is None or settings.whatsapp_reminders)  # the "text message reminders" switch
    )


def send_due_reminders(db: Session, now: datetime | None = None) -> int:
    """Sends each due reminder once and records it. Returns how many texts were sent."""
    now = now or utcnow()
    sent = 0
    cases = db.scalars(select(Case).where(Case.status != "closed").options(selectinload(Case.hearings)))
    for case in cases:
        upcoming = [h for h in case.hearings if aware(h.scheduled_at) > now]
        if not upcoming:
            continue
        recipients = [u for u in _recipients(db, case) if _eligible(u)]
        for hearing in upcoming:
            when = aware(hearing.scheduled_at)
            due = due_offsets(when, now)
            if not due:
                continue
            text = f"Announcement from MrCourt: your hearing in {case.title} is {when_text(when, now)}."
            for user in recipients:
                done = set(
                    db.scalars(
                        select(ReminderLog.offset_days).where(
                            ReminderLog.hearing_id == hearing.id, ReminderLog.user_id == user.id
                        )
                    )
                )
                pending = [o for o in due if o not in done]
                if not pending:
                    continue
                try:
                    get_notifier().send(
                        Message(
                            contact=user.phone or "",
                            text=text,
                            kind="reminder",
                            variables={"case": case.title, "when": when_text(when, now)},
                        )
                    )
                except Exception:  # noqa: BLE001 - one failed text must not stop the rest; it is tried again next run
                    logger.warning("A reminder could not be sent; it will be tried again", exc_info=True)
                    continue
                for offset in pending:
                    db.add(ReminderLog(hearing_id=hearing.id, user_id=user.id, offset_days=offset, sent_at=now))
                db.flush()
                sent += 1
    return sent


def forget_reminders(db: Session, hearing: Hearing) -> None:
    """A rescheduled hearing starts its reminder schedule again."""
    db.execute(delete(ReminderLog).where(ReminderLog.hearing_id == hearing.id))
    hearing.reminder_sent_at = None


def main() -> None:
    session = get_sessionmaker()()
    try:
        count = send_due_reminders(session)
        session.commit()
        print(f"Sent {count} reminder(s).")
    finally:
        session.close()


if __name__ == "__main__":
    main()
