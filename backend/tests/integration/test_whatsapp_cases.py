"""Next hearing, status and today over WhatsApp: a client sees only invited cases and shared items."""
from datetime import timedelta

import pytest
from helpers_whatsapp import NUMBER, OTHER_NUMBER, linked, send
from sqlalchemy import select

from mrcourt.config import get_settings
from mrcourt.db.base import utcnow
from mrcourt.models import Case, CaseInvitation, ConversationState, InboundMessage, Question, User
from mrcourt.services.whatsapp import intents

ROHAN = "rohan.sharma@example.com"
ANITA = "anita.sharma@example.com"
RAVI = "ravi.mehta@example.com"
FIRST = "Sharma v. Verma Traders"
SECOND = "State v. Imran Khan"


@pytest.fixture(autouse=True)
def _roomy_limits(monkeypatch):
    monkeypatch.setattr(get_settings(), "whatsapp_questions_per_minute", 100)


def case_named(db, title):
    return db.scalars(select(Case).where(Case.title == title)).one()


def invite(db, email, title):
    user = db.scalar(select(User).where(User.email == email))
    case = case_named(db, title)
    db.add(CaseInvitation(case_id=case.id, invitee_user_id=user.id, status="accepted", invited_by=case.owner_id, accepted_at=utcnow()))
    db.commit()


def last(fake, number=NUMBER):
    return fake.texts_to(number)[-1]


def test_a_client_with_one_case_gets_its_next_hearing_and_its_shared_status(client, db, fake_channel) -> None:
    linked(db, ANITA)
    send(client, text="next hearing")
    reply = last(fake_channel)
    assert reply.startswith(f"Next hearing in {FIRST}:") and "Saket District Court" in reply
    send(client, text="status", id="m2")
    assert last(fake_channel).startswith(f"Status of {FIRST}: ")


def test_a_client_never_hears_of_a_case_they_were_not_invited_to(client, db, fake_channel) -> None:
    linked(db, ANITA)
    for n, text in enumerate(["next hearing", "status", "today", "help"]):
        send(client, text=text, id=f"m{n}")
    assert SECOND not in " ".join(fake_channel.texts_to(NUMBER))
    send(client, text=f"next hearing in {SECOND}", id="by-name")  # asking by name is just a question: nothing about the case
    assert "Imran" not in last(fake_channel) and SECOND not in last(fake_channel)


def test_a_client_with_several_cases_is_asked_to_pick_one(client, db, fake_channel) -> None:
    linked(db, ANITA)
    invite(db, ANITA, SECOND)
    send(client, text="next hearing")
    menu = last(fake_channel)
    assert menu.startswith("Which case? Reply with its number.") and f"1. {FIRST}" in menu and f"2. {SECOND}" in menu
    send(client, text="2", id="pick")
    assert last(fake_channel).startswith(f"Next hearing in {SECOND}:")
    assert db.scalars(select(ConversationState)).all() == []  # the list is used up


def test_a_pick_works_for_status_too_and_a_wrong_number_asks_again(client, db, fake_channel) -> None:
    linked(db, ANITA)
    invite(db, ANITA, SECOND)
    send(client, text="status")
    send(client, text="7", id="bad")
    assert last(fake_channel) == "Please reply with a number from 1 to 2."
    send(client, text="2", id="good")
    assert last(fake_channel).startswith(f"Status of {SECOND}: ")


def test_an_expired_list_is_forgotten_and_the_number_is_just_a_message(client, db, fake_channel) -> None:
    user = linked(db, ANITA)
    invite(db, ANITA, SECOND)
    send(client, text="status")
    state = db.get(ConversationState, user.id)
    state.expires_at = utcnow() - timedelta(minutes=1)
    db.commit()
    send(client, text="1", id="late")
    assert "Which case?" not in last(fake_channel)
    assert db.scalars(select(Question).where(Question.channel == "whatsapp")).all()  # treated as a question


def test_a_removed_invitation_hides_the_case(client, db, fake_channel) -> None:
    linked(db, ANITA)
    invitation = db.scalars(select(CaseInvitation).where(CaseInvitation.invitee_user_id == db.scalar(select(User.id).where(User.email == ANITA)))).first()
    invitation.status = "removed"
    db.commit()
    send(client, text="next hearing")
    assert last(fake_channel) == "You have no cases shared with you on MrCourt yet. Ask your advocate to invite you."


def test_a_client_sees_only_the_shared_status_not_the_advocates_notes(client, db, fake_channel) -> None:
    linked(db, ANITA)
    case = case_named(db, FIRST)
    case.notes, case.client_status = "PRIVATE ADVOCATE NOTE about strategy", "awaiting_order"
    db.commit()
    send(client, text="status")
    reply = last(fake_channel)
    assert "Awaiting order" in reply and "PRIVATE" not in reply and "strategy" not in reply


def test_a_status_that_was_never_shared_is_said_plainly(client, db, fake_channel) -> None:
    linked(db, ANITA)
    case_named(db, FIRST).client_status = None
    db.commit()
    send(client, text="status")
    assert last(fake_channel).startswith(f"Your advocate has not shared a status for {FIRST} yet.")


def test_an_advocate_sees_their_next_hearings_and_todays(client, db, fake_channel) -> None:
    linked(db, ROHAN)
    send(client, text="next hearing")
    reply = last(fake_channel)
    assert reply.startswith("Your next hearings:") and "1. " in reply and "2. " in reply
    send(client, text="status", id="s")
    assert last(fake_channel).startswith("You have ") and "open case(s)" in last(fake_channel)
    send(client, text="today", id="t")
    assert last(fake_channel) in ("You have no hearings today.",) or last(fake_channel).startswith("Your hearings today:")


def test_help_lists_what_can_be_asked(client, db, fake_channel) -> None:
    linked(db, ROHAN)
    send(client, text="help")
    assert "next hearing" in last(fake_channel) and "STOP" in last(fake_channel)


def test_another_persons_number_cannot_read_a_case(client, db, fake_channel) -> None:
    linked(db, RAVI, phone="9000000002")  # a different client on the same case
    send(client, sender=OTHER_NUMBER, text="status")
    assert last(fake_channel, OTHER_NUMBER).startswith(f"Status of {FIRST}")
    assert fake_channel.texts_to(NUMBER) == []  # nothing for anyone else


def test_short_requests_are_not_stored_as_questions(client, db, fake_channel) -> None:
    linked(db, ANITA)
    send(client, text="next hearing")
    db.expire_all()
    assert db.scalars(select(Question)).all() == []
    (row,) = db.scalars(select(InboundMessage))
    assert row.kind == "status" and row.payload is None


def test_the_parser_is_used_before_the_question_path(db) -> None:
    assert intents.parse("next hearing") == "next_hearing"
