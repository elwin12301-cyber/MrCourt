"""A short "there is news on <case>" message for people who opted in: merged, minimal, and never to anyone else."""
from datetime import timedelta

import pytest
from helpers_whatsapp import NUMBER, linked
from sqlalchemy import select

from mrcourt.config import get_settings
from mrcourt.db.base import utcnow
from mrcourt.models import Case, CaseInvitation, ClientQuestion, Message, User
from mrcourt.services import client_questions, client_status, notify
from mrcourt.services.whatsapp import consent, jobs, outbox

ROHAN = "rohan.sharma@example.com"
ANITA = "anita.sharma@example.com"
RAVI = "ravi.mehta@example.com"
FIRST = "Sharma v. Verma Traders"
ADVOCATE_NUMBER = "919000000005"


@pytest.fixture
def case(db):
    return db.scalars(select(Case).where(Case.title == FIRST)).one()


def later(seconds=None):
    return utcnow() + timedelta(seconds=(seconds if seconds is not None else get_settings().whatsapp_nudge_delay_seconds + 1))


def change_status(db, case):
    new = "awaiting_order" if case.client_status != "awaiting_order" else "notice_stage"
    client_status.set_client_status(db, case, case.owner_id, new)
    db.commit()
    return client_status.STATUS_LABELS[new]


def queued(db, **where):
    db.expire_all()
    return list(db.scalars(select(Message).filter_by(**where)))


def test_only_a_client_who_opted_in_gets_a_nudge_and_it_names_only_the_case(db, case, fake_channel) -> None:
    anita = linked(db, ANITA, "updates")
    label = change_status(db, case)
    assert [m.user_id for m in queued(db, status="queued")] == [anita.id]  # Ravi did not opt in
    assert outbox.flush_due(db, later()) == 1
    db.commit()
    assert fake_channel.templates_to(NUMBER) == [("update", [FIRST])]
    words = fake_channel.words_to(NUMBER)[0]
    assert words == f"MrCourt: there is a new update on {FIRST}. Open MrCourt to read it." and label not in words
    assert [(m.channel, m.status, m.kind) for m in queued(db, user_id=anita.id)] == [("whatsapp", "sent", "update")]


def test_nothing_is_sent_before_the_wait_is_over(db, case, fake_channel) -> None:
    linked(db, ANITA, "updates")
    change_status(db, case)
    assert outbox.flush_due(db, later(30)) == 0
    assert fake_channel.sent == []
    assert len(queued(db, status="queued")) == 1


def test_changes_close_together_become_one_message(db, case, fake_channel) -> None:
    linked(db, ANITA, "updates")
    change_status(db, case)
    change_status(db, case)
    change_status(db, case)
    assert len(queued(db, status="queued")) == 1
    assert outbox.flush_due(db, later()) == 1
    assert len(fake_channel.templates_to(NUMBER)) == 1


def test_a_reminder_for_the_same_case_makes_the_nudge_unnecessary(db, case, fake_channel) -> None:
    anita = linked(db, ANITA, "updates", "reminders")
    change_status(db, case)
    db.add(Message(user_id=anita.id, case_id=case.id, kind="reminder", channel="whatsapp", status="sent", created_at=utcnow()))
    db.commit()
    assert outbox.flush_due(db, later()) == 0
    db.commit()
    assert fake_channel.sent == []
    assert [m.kind for m in queued(db)] == ["reminder"]  # the nudge left no trace


def test_a_person_who_opts_out_or_unlinks_before_it_is_sent_gets_nothing(db, case, fake_channel) -> None:
    anita = linked(db, ANITA, "updates")
    change_status(db, case)
    consent.set_consent(db, anita, "updates", False)
    db.commit()
    assert outbox.flush_due(db, later()) == 0
    assert fake_channel.sent == [] and queued(db) == []


def test_a_removed_invitation_stops_the_nudge(db, case, fake_channel) -> None:
    anita = linked(db, ANITA, "updates")
    change_status(db, case)
    invitation = db.scalars(select(CaseInvitation).where(CaseInvitation.invitee_user_id == anita.id)).one()
    invitation.status = "removed"
    db.commit()
    assert outbox.flush_due(db, later()) == 0
    assert fake_channel.sent == [] and queued(db) == []


def test_no_nudge_is_queued_for_someone_who_never_linked(db, case, fake_channel) -> None:
    change_status(db, case)
    assert queued(db) == []
    assert outbox.flush_due(db, later()) == 0


def test_when_whatsapp_fails_the_nudge_falls_back_to_one_sms(db, case, fake_channel) -> None:
    anita = linked(db, ANITA, "updates")
    change_status(db, case)
    fake_channel.fail_with = "not_on_whatsapp"
    assert outbox.flush_due(db, later()) == 0
    db.commit()
    texts = [m.text for m in notify.OUTBOX if m.channel == "sms"]
    assert texts == [f"MrCourt: there is a new update on {FIRST}. Open MrCourt to read it."]
    whatsapp, sms = queued(db, user_id=anita.id)
    assert (whatsapp.status, whatsapp.failure_reason, sms.channel, sms.fallback_of) == ("failed", "not_on_whatsapp", "sms", whatsapp.id)


def test_an_advocate_who_opted_in_hears_that_a_client_wrote(db, case, fake_channel) -> None:
    rohan = linked(db, ROHAN, "activity", phone="9000000005")
    anita = db.scalar(select(User).where(User.email == ANITA))
    client_questions.ask(db, anita, case, "question", "What happens at the next hearing?")
    db.commit()
    assert [(m.user_id, m.kind) for m in queued(db, status="queued")] == [(rohan.id, "activity")]
    outbox.flush_due(db, later())
    assert fake_channel.templates_to(ADVOCATE_NUMBER) == [("activity", [FIRST])]
    assert "What happens" not in " ".join(fake_channel.words_to(ADVOCATE_NUMBER))  # the question itself is not sent


def test_an_advocate_who_did_not_opt_in_is_not_messaged(db, case, fake_channel) -> None:
    anita = db.scalar(select(User).where(User.email == ANITA))
    client_questions.ask(db, anita, case, "update_request", None)
    db.commit()
    assert queued(db) == []


def test_the_advocates_reply_nudges_only_the_client_who_asked(db, case, fake_channel) -> None:
    anita = linked(db, ANITA, "updates")
    linked(db, RAVI, "updates", phone="9000000008")
    advocate = db.get(User, case.owner_id)
    question = client_questions.ask(db, anita, case, "question", "When is my next date?")
    db.commit()
    stored = db.get(ClientQuestion, question.id)
    client_questions.reply(db, advocate, stored, "It is on the 15th at 4 pm, please bring ID.")
    db.commit()
    assert [m.user_id for m in queued(db, status="queued")] == [anita.id]
    outbox.flush_due(db, later())
    assert "15th" not in " ".join(fake_channel.words_to(NUMBER))  # the reply stays in the app


def test_the_housekeeping_run_sends_due_nudges_too(db, case, fake_channel) -> None:
    linked(db, ANITA, "updates")
    change_status(db, case)
    counts = jobs.flush(db, later())
    assert counts["nudges"] == 1
