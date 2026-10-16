"""Reminders and codes over WhatsApp: only to people who opted in, with a status, and one SMS fallback."""
import json
from datetime import datetime, timedelta, timezone

import pytest
from helpers_whatsapp import WEBHOOK_PATH
from sqlalchemy import select

from mrcourt.config import get_settings
from mrcourt.db.base import utcnow
from mrcourt.models import Case, Message, ReminderLog, User
from mrcourt.services import auth, notify
from mrcourt.services.cases import aware
from mrcourt.services.reminders import IST, forget_reminders, send_due_reminders
from mrcourt.services.whatsapp import consent

ADVOCATE = "rohan.sharma@example.com"
CLIENT = "anita.sharma@example.com"
CLIENT_TWO = "ravi.mehta@example.com"
HEARING = datetime(2026, 10, 20, 16, 0, tzinfo=IST)
NUMBERS = {ADVOCATE: "919810000001", CLIENT: "919810000002", CLIENT_TWO: "919810000003"}
FIVE_DAYS = "in 5 days, on 20 Oct 2026, at 04:00 PM"


def at(day: int, hour: int) -> datetime:
    return datetime(2026, 10, day, hour, 0, tzinfo=IST).astimezone(timezone.utc)


@pytest.fixture
def world(db):
    """The advocate and both clients with verified phones, one open case with one hearing."""
    people = {u.email: u for u in db.scalars(select(User))}
    for email, number in NUMBERS.items():
        people[email].phone, people[email].phone_verified_at = f"+{number}", utcnow()
    first = db.scalars(select(Case).where(Case.title == "Sharma v. Verma Traders")).one()
    for case in db.scalars(select(Case)):
        if case.id != first.id:
            case.status = "closed"
    hearing = min(first.hearings, key=lambda h: aware(h.scheduled_at))
    hearing.scheduled_at = HEARING.astimezone(timezone.utc)
    for other in first.hearings:
        if other.id != hearing.id:
            other.scheduled_at = HEARING.astimezone(timezone.utc) - timedelta(days=100)
    db.commit()
    notify.OUTBOX.clear()
    return people, first, hearing


def opt_in(db, person, *kinds):
    consent.link(db, person)
    for kind in kinds:
        consent.set_consent(db, person, kind, True)
    db.commit()


def sms_to(person):
    return [m.text for m in notify.OUTBOX if m.contact == person.phone and m.channel == "sms"]


def rows(db, **where):
    db.expire_all()
    return list(db.scalars(select(Message).filter_by(**where).order_by(Message.created_at, Message.id)))


def test_opted_in_people_get_one_whatsapp_reminder_at_each_step_and_no_sms(db, world, fake_channel) -> None:
    people, case, _ = world
    for email in (ADVOCATE, CLIENT):
        opt_in(db, people[email], "reminders")
    assert send_due_reminders(db, now=at(15, 9)) == 3  # the advocate and Anita by WhatsApp, Ravi by text
    assert fake_channel.templates_to(NUMBERS[ADVOCATE]) == [("reminder", [case.title, FIVE_DAYS])]
    assert fake_channel.words_to(NUMBERS[CLIENT]) == [f"Announcement from MrCourt: your hearing in {case.title} is {FIVE_DAYS}."]
    assert sms_to(people[ADVOCATE]) == [] and sms_to(people[CLIENT]) == []
    assert len(sms_to(people[CLIENT_TWO])) == 1  # Ravi never opted in: the existing text reminder, as before
    kept = {(m.channel, m.status, m.provider) for m in rows(db, kind="reminder") if m.user_id != people[CLIENT_TWO].id}
    assert kept == {("whatsapp", "sent", "fake")}
    assert send_due_reminders(db, now=at(15, 12)) == 0  # once per person per hearing
    send_due_reminders(db, now=at(19, 9))
    send_due_reminders(db, now=at(20, 8))
    assert len(fake_channel.templates_to(NUMBERS[ADVOCATE])) == 3


def test_a_reminder_names_only_the_case_and_the_time(db, world, fake_channel) -> None:
    people, case, _ = world
    opt_in(db, people[CLIENT], "reminders")
    send_due_reminders(db, now=at(20, 8))
    ((kind, variables),) = fake_channel.templates_to(NUMBERS[CLIENT])
    assert kind == "reminder" and variables == [case.title, "today at 04:00 PM"]


def test_nothing_goes_by_whatsapp_to_people_who_did_not_opt_in_or_unlinked_or_left(db, world, fake_channel) -> None:
    people, _, _ = world
    opt_in(db, people[ADVOCATE], "codes")  # linked, but reminders not switched on
    opt_in(db, people[CLIENT], "reminders")
    consent.unlink(db, people[CLIENT])  # unlinked again
    people[CLIENT_TWO].status = "deactivated"
    db.commit()
    send_due_reminders(db, now=at(15, 9))
    assert fake_channel.sent == []
    assert len(sms_to(people[ADVOCATE])) == 1 and len(sms_to(people[CLIENT])) == 1  # their text reminders, as before
    assert sms_to(people[CLIENT_TWO]) == []


def test_a_person_with_text_reminders_off_and_no_whatsapp_gets_nothing(db, world, fake_channel) -> None:
    people, _, _ = world
    people[CLIENT].settings.whatsapp_reminders = False
    db.commit()
    send_due_reminders(db, now=at(15, 9))
    assert fake_channel.sent == [] and sms_to(people[CLIENT]) == []


def test_when_whatsapp_refuses_at_once_one_sms_with_the_same_words_goes_instead(db, world, fake_channel) -> None:
    people, case, _ = world
    opt_in(db, people[CLIENT], "reminders")
    fake_channel.fail_with = "not_on_whatsapp"
    send_due_reminders(db, now=at(15, 9))
    first, second = rows(db, user_id=people[CLIENT].id)
    assert (first.channel, first.status, first.failure_reason) == ("whatsapp", "failed", "not_on_whatsapp")
    assert (second.channel, second.status, second.fallback_of) == ("sms", "sent", first.id)
    assert sms_to(people[CLIENT]) == [f"Announcement from MrCourt: your hearing in {case.title} is {FIVE_DAYS}."]
    assert send_due_reminders(db, now=at(15, 10)) == 0  # handled: not sent a third time


def test_when_whatsapp_reports_failure_later_the_sms_goes_once(client, db, world, fake_channel) -> None:
    people, _, _ = world
    opt_in(db, people[CLIENT], "reminders")
    send_due_reminders(db, now=at(15, 9))
    (sent,) = rows(db, user_id=people[CLIENT].id)
    assert sent.status == "sent" and sms_to(people[CLIENT]) == []
    body = json.dumps({"report": {"id": sent.provider_message_id, "status": "failed", "reason": "not_on_whatsapp"}}).encode()
    for _ in range(2):  # the provider repeats itself
        assert client.post(WEBHOOK_PATH, content=body).status_code == 200
    assert len(sms_to(people[CLIENT])) == 1
    first, second = rows(db, user_id=people[CLIENT].id)
    assert (first.status, first.failure_reason, second.channel, second.fallback_of) == ("failed", "not_on_whatsapp", "sms", first.id)


def test_a_delivery_report_moves_the_status_forward_through_the_webhook(client, db, world, fake_channel) -> None:
    people, _, _ = world
    opt_in(db, people[CLIENT], "reminders")
    send_due_reminders(db, now=at(15, 9))
    (sent,) = rows(db, user_id=people[CLIENT].id)
    for status in ("delivered", "read"):
        body = json.dumps({"report": {"id": sent.provider_message_id, "status": status}}).encode()
        client.post(WEBHOOK_PATH, content=body)
    assert rows(db, user_id=people[CLIENT].id)[0].status == "read"


def test_with_text_reminders_off_a_failed_whatsapp_reminder_is_not_texted_and_is_tried_again(db, world, fake_channel) -> None:
    people, _, _ = world
    opt_in(db, people[CLIENT], "reminders")
    people[CLIENT].settings.whatsapp_reminders = False
    db.commit()
    fake_channel.fail_with = "provider_down"
    send_due_reminders(db, now=at(15, 9))
    assert sms_to(people[CLIENT]) == []
    assert db.scalars(select(ReminderLog).where(ReminderLog.user_id == people[CLIENT].id)).all() == []
    fake_channel.fail_with = None
    send_due_reminders(db, now=at(15, 10))
    assert len(fake_channel.templates_to(NUMBERS[CLIENT])) == 1


def test_a_rescheduled_hearing_restarts_the_reminders_on_whatsapp(db, world, fake_channel) -> None:
    people, _, hearing = world
    opt_in(db, people[CLIENT], "reminders")
    send_due_reminders(db, now=at(15, 9))
    forget_reminders(db, hearing)
    db.commit()
    send_due_reminders(db, now=at(15, 10))
    assert len(fake_channel.templates_to(NUMBERS[CLIENT])) == 2


def test_the_daily_send_cap_sends_the_rest_by_sms(db, world, fake_channel, monkeypatch) -> None:
    people, _, _ = world
    for email in (ADVOCATE, CLIENT):
        opt_in(db, people[email], "reminders")
    monkeypatch.setattr(get_settings(), "whatsapp_daily_send_cap", 1)
    send_due_reminders(db, now=at(15, 9))
    assert sum(len(fake_channel.templates_to(n)) for n in NUMBERS.values()) == 1
    capped = [m for m in rows(db, channel="whatsapp") if m.failure_reason == "cap_reached"]
    assert len(capped) == 1 and len([m for m in rows(db, channel="sms") if m.fallback_of == capped[0].id]) == 1


# ----- codes ------------------------------------------------------------------------------------------


def test_a_code_goes_by_text_unless_the_person_chose_whatsapp(db, world, fake_channel) -> None:
    people, _, _ = world
    auth.request_otp(db, CLIENT)
    assert len(sms_to(people[CLIENT])) == 1 and fake_channel.sent == []
    assert [(m.kind, m.channel, m.status) for m in rows(db, user_id=people[CLIENT].id)] == [("code", "sms", "sent")]


def test_a_code_goes_by_whatsapp_for_a_person_who_chose_it_and_the_words_are_not_stored(db, world, fake_channel) -> None:
    people, _, _ = world
    opt_in(db, people[CLIENT], "codes")
    auth.request_otp(db, CLIENT)
    ((kind, variables),) = fake_channel.templates_to(NUMBERS[CLIENT])
    assert kind == "code" and len(variables[0]) == 6 and variables[0].isdigit()
    assert sms_to(people[CLIENT]) == []
    assert all(variables[0] not in json.dumps([m.kind, m.status, m.failure_reason]) for m in rows(db))


def test_a_password_reset_code_can_use_whatsapp_too(db, world, fake_channel) -> None:
    people, _, _ = world
    opt_in(db, people[CLIENT], "codes")
    auth.forgot_password(db, CLIENT)
    assert len(fake_channel.templates_to(NUMBERS[CLIENT])) == 1 and sms_to(people[CLIENT]) == []


def test_if_whatsapp_refuses_a_code_at_once_the_person_gets_it_by_text(db, world, fake_channel) -> None:
    people, _, _ = world
    opt_in(db, people[CLIENT], "codes")
    fake_channel.fail_with = "not_on_whatsapp"
    auth.request_otp(db, CLIENT)
    (text,) = sms_to(people[CLIENT])
    assert "Your MrCourt code is" in text
    whatsapp, sms = rows(db, user_id=people[CLIENT].id)
    assert (whatsapp.status, sms.channel, sms.fallback_of) == ("failed", "sms", whatsapp.id)


def test_asking_for_a_code_gives_the_same_reply_whether_or_not_the_account_exists(client, db, world, fake_channel) -> None:
    replies = [
        client.post("/api/v1/auth/otp/request", json={"identifier": identifier})
        for identifier in (CLIENT, "nobody@example.com")
    ]
    assert (replies[0].status_code, replies[0].json()) == (replies[1].status_code, replies[1].json())
