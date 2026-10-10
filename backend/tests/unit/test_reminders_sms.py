from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from mrcourt.db.base import utcnow
from mrcourt.models import Case, CaseInvitation, Hearing, ReminderLog, User
from mrcourt.services import notify, reminders
from mrcourt.services.cases import aware
from mrcourt.services.reminders import IST, due_offsets, forget_reminders, send_due_reminders, when_text

ADVOCATE = "rohan.sharma@example.com"
CLIENTS = ("anita.sharma@example.com", "ravi.mehta@example.com")
HEARING = datetime(2026, 10, 20, 16, 0, tzinfo=IST)


def at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=IST)


def test_each_step_becomes_due_at_its_own_time():
    assert due_offsets(HEARING, at(14, 7, 59)) == []
    assert due_offsets(HEARING, at(15, 8, 0)) == [5]
    assert due_offsets(HEARING, at(19, 7, 59)) == [5]
    assert due_offsets(HEARING, at(19, 8, 0)) == [5, 1]
    assert due_offsets(HEARING, at(20, 6, 59)) == [5, 1]
    assert due_offsets(HEARING, at(20, 7, 0)) == [5, 1, 0]


def test_a_very_early_hearing_still_gets_its_day_of_text():
    early = at(20, 6, 0)
    assert 0 in due_offsets(early, at(20, 5, 0))
    assert 0 not in due_offsets(early, at(20, 4, 30))


def test_the_text_says_how_soon_in_plain_words():
    assert when_text(HEARING, at(20, 7)) == "today at 04:00 PM"
    assert when_text(HEARING, at(19, 9)) == "tomorrow, 20 Oct, at 04:00 PM"
    assert when_text(HEARING, at(15, 9)) == "in 5 days, on 20 Oct 2026, at 04:00 PM"


@pytest.fixture
def world(db):
    """The seeded advocate and both clients with verified phones; returns a hearing of the first case."""
    people = {u.email: u for u in db.scalars(select(User))}
    for number, email in enumerate((ADVOCATE, *CLIENTS), start=1):
        people[email].phone = f"+91981000000{number}"
        people[email].phone_verified_at = utcnow()
    first = db.scalars(select(Case).where(Case.title == "Sharma v. Verma Traders")).one()
    for case in db.scalars(select(Case)):
        if case.id != first.id:
            case.status = "closed"  # keep these tests to one case
    hearing = min(first.hearings, key=lambda h: aware(h.scheduled_at))
    hearing.scheduled_at = HEARING.astimezone(timezone.utc)
    for other in first.hearings:
        if other.id != hearing.id:
            other.scheduled_at = HEARING.astimezone(timezone.utc) - timedelta(days=100)
    db.commit()
    notify.OUTBOX.clear()
    return people, first, hearing


def texts_to(person: User) -> list[str]:
    return [m.text for m in notify.OUTBOX if m.contact == person.phone]


def test_the_advocate_and_each_client_get_a_text_at_7_days_1_day_and_on_the_day(db, world):
    people, case, hearing = world
    assert send_due_reminders(db, now=at(14, 12).astimezone(timezone.utc)) == 0
    assert send_due_reminders(db, now=at(15, 9).astimezone(timezone.utc)) == 3  # advocate + two clients
    assert all("in 5 days" in text for person in people.values() for text in texts_to(person))
    assert send_due_reminders(db, now=at(15, 12).astimezone(timezone.utc)) == 0  # never twice

    assert send_due_reminders(db, now=at(19, 9).astimezone(timezone.utc)) == 3
    assert send_due_reminders(db, now=at(20, 8).astimezone(timezone.utc)) == 3
    advocate = people[ADVOCATE]
    assert len(texts_to(advocate)) == 3
    assert "today at 04:00 PM" in texts_to(advocate)[-1]
    assert send_due_reminders(db, now=at(20, 12).astimezone(timezone.utc)) == 0
    assert all(m.kind == "reminder" for m in notify.OUTBOX)


def test_a_hearing_added_at_short_notice_sends_one_text_not_three(db, world):
    people, case, hearing = world
    assert send_due_reminders(db, now=at(20, 9).astimezone(timezone.utc)) == 3
    assert len(texts_to(people[ADVOCATE])) == 1
    assert send_due_reminders(db, now=at(20, 10).astimezone(timezone.utc)) == 0


def test_texts_name_the_case_and_the_time_only(db, world):
    people, case, hearing = world
    send_due_reminders(db, now=at(15, 9).astimezone(timezone.utc))
    text = texts_to(people[ADVOCATE])[0]
    assert text == "Announcement from MrCourt: your hearing in Sharma v. Verma Traders is in 5 days, on 20 Oct 2026, at 04:00 PM."
    assert case.cnr_number not in text and "Saket" not in text


def test_nothing_goes_to_people_who_are_not_eligible(db, world):
    people, case, hearing = world
    people[ADVOCATE].phone_verified_at = None  # phone not checked
    people[CLIENTS[0]].settings.whatsapp_reminders = False  # switched off
    people[CLIENTS[1]].status = "suspended"
    db.commit()
    assert send_due_reminders(db, now=at(15, 9).astimezone(timezone.utc)) == 0
    assert notify.OUTBOX == []


def test_a_client_whose_invitation_is_not_accepted_gets_nothing(db, world):
    people, case, hearing = world
    for invitation in db.scalars(select(CaseInvitation).where(CaseInvitation.case_id == case.id)):
        invitation.status = "pending"
    db.commit()
    assert send_due_reminders(db, now=at(15, 9).astimezone(timezone.utc)) == 1  # only the advocate
    assert texts_to(people[CLIENTS[0]]) == [] and texts_to(people[CLIENTS[1]]) == []


def test_closed_cases_and_past_hearings_send_nothing(db, world):
    people, case, hearing = world
    assert send_due_reminders(db, now=at(21, 9).astimezone(timezone.utc)) == 0  # the hearing has passed
    case.status = "closed"
    db.commit()
    assert send_due_reminders(db, now=at(15, 9).astimezone(timezone.utc)) == 0


def test_a_rescheduled_hearing_starts_its_reminders_again(db, world):
    people, case, hearing = world
    send_due_reminders(db, now=at(15, 9).astimezone(timezone.utc))
    notify.OUTBOX.clear()
    hearing.scheduled_at = at(27, 11).astimezone(timezone.utc)
    forget_reminders(db, hearing)
    db.commit()
    assert db.scalars(select(ReminderLog)).first() is None
    assert send_due_reminders(db, now=at(22, 9).astimezone(timezone.utc)) == 3
    assert "in 5 days" in texts_to(people[ADVOCATE])[0]


def test_a_failed_send_is_tried_again_next_time(db, world):
    people, case, hearing = world

    class Flaky:
        calls = 0

        def send(self, message):
            Flaky.calls += 1
            if Flaky.calls == 1:
                raise RuntimeError("provider down")
            notify.OUTBOX.append(message)

    notify.set_notifier(Flaky())
    try:
        assert send_due_reminders(db, now=at(15, 9).astimezone(timezone.utc)) == 2  # one failed, two went out
        assert send_due_reminders(db, now=at(15, 10).astimezone(timezone.utc)) == 1  # the failed one now goes
    finally:
        notify.set_notifier(None)
    assert len(notify.OUTBOX) == 3


def test_rescheduling_through_the_service_clears_the_log(db, world):
    from mrcourt.schemas.cases import HearingPatch
    from mrcourt.services import hearings

    people, case, hearing = world
    send_due_reminders(db, now=at(15, 9).astimezone(timezone.utc))
    db.commit()
    hearings.reschedule(db, case, hearing.id, HearingPatch(scheduled_at=at(30, 11).astimezone(timezone.utc)), people[ADVOCATE].id)
    db.commit()
    assert db.scalars(select(ReminderLog).where(ReminderLog.hearing_id == hearing.id)).first() is None
    assert reminders.OFFSETS == (5, 1, 0)
