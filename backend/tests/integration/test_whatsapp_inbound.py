"""Asking on WhatsApp: the same cited answer as the website, in short form, with every safety rule kept."""
import pytest
from helpers import make_document
from helpers_whatsapp import NUMBER, OTHER_NUMBER, linked, send
from sqlalchemy import select

from mrcourt.config import get_settings
from mrcourt.models import InboundMessage, LegalSource, Question, User
from mrcourt.services.advice_guard import CASE_SPECIFIC_NOTICE, LAWYER_REMINDER
from mrcourt.services.answering import DISCLAIMER, NO_SOURCE_MESSAGE
from mrcourt.services.whatsapp import inbound

ANITA = "anita.sharma@example.com"
ROHAN = "rohan.sharma@example.com"
UNKNOWN_REPLY = inbound.REPLIES["unknown"]


@pytest.fixture
def law(db):
    """A statute passage that is section 138 and some notes about cheque dishonour (shared by everyone)."""
    exact = make_document(db, title="Negotiable Instruments Act, 1881", citation="NI Act s.138", kind="act_section",
                          passages=["Dishonour of cheque for insufficiency of funds in the account."])
    make_document(db, title="Negotiable Instruments notes", citation="NI notes", kind="act_section",
                  passages=["Cheque dishonour: when a cheque is dishonoured the payee may sue; cheque dishonour notice."])
    db.flush()
    db.scalars(select(LegalSource).where(LegalSource.document_id == exact.id)).first().section = "138"
    db.commit()


def reply_to(fake, number=NUMBER):
    return fake.texts_to(number)


def test_a_question_gets_a_short_cited_answer_with_the_disclaimer_and_a_link(client, db, law, fake_channel) -> None:
    linked(db, ROHAN)
    send(client, text="What does Section 138 NI Act say about cheque dishonour?")
    (text,) = reply_to(fake_channel)
    assert "Sources:" in text and "NI Act s.138" in text and DISCLAIMER in text and "Read more: http" in text
    assert "Dishonour of cheque" in text and len(text) < 2200
    db.expire_all()
    (question,) = db.scalars(select(Question))
    assert (question.channel, question.input_method, question.user_id) == ("whatsapp", "typed", db.scalar(select(User).where(User.email == ROHAN)).id)
    assert question.answer.outcome == "cited" and question.answer.citations
    (row,) = db.scalars(select(InboundMessage))
    assert (row.kind, row.status, row.question_id, row.payload) == ("question", "processed", question.id, None)


def test_no_reliable_source_is_said_plainly(client, db, law, fake_channel) -> None:
    linked(db, ROHAN)
    send(client, text="What is the GST rate on gold jewellery?")
    (text,) = reply_to(fake_channel)
    assert NO_SOURCE_MESSAGE in text and DISCLAIMER in text and "Sources:" not in text


def test_a_section_that_is_not_in_the_sources_is_reported_not_replaced(client, db, law, fake_channel) -> None:
    linked(db, ROHAN)
    send(client, text="What does Section 999 of the NI Act say about cheque dishonour?")
    (text,) = reply_to(fake_channel)
    assert "Not found in the sources: Section 999 NI" in text


def test_a_client_gets_the_general_information_rule(client, db, law, fake_channel) -> None:
    linked(db, ANITA)
    send(client, text="Should I accept the settlement in my case about cheque dishonour?")
    (text,) = reply_to(fake_channel)
    assert CASE_SPECIFIC_NOTICE in text and LAWYER_REMINDER in text and DISCLAIMER in text


def test_an_advocate_does_not_get_the_client_reminder(client, db, law, fake_channel) -> None:
    linked(db, ROHAN)
    send(client, text="What does Section 138 NI Act say about cheque dishonour?")
    assert LAWYER_REMINDER not in reply_to(fake_channel)[0]


def test_a_number_that_is_not_linked_gets_only_the_fixed_reply_a_couple_of_times(client, db, fake_channel) -> None:
    for n in range(5):
        send(client, sender="919123456780", text=f"What is bail? {n}", id=f"s{n}")
    texts = reply_to(fake_channel, "919123456780")
    assert texts == [UNKNOWN_REPLY, UNKNOWN_REPLY]
    assert db.scalars(select(Question)).all() == []  # nothing was answered or stored for a stranger


def test_the_reply_to_a_stranger_does_not_depend_on_whether_the_number_has_an_account(client, db, fake_channel) -> None:
    from helpers_whatsapp import verified

    verified(db, ANITA, "9000000009")  # an account with a verified phone, but never linked to WhatsApp
    send(client, sender="919000000009", text="hello", id="a")
    send(client, sender="919888888888", text="hello", id="b")
    assert reply_to(fake_channel, "919000000009") == reply_to(fake_channel, "919888888888") == [UNKNOWN_REPLY]


def test_too_many_messages_get_one_polite_reply_then_silence(client, db, law, fake_channel, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "whatsapp_questions_per_minute", 2)
    linked(db, ROHAN)
    for n in range(5):
        send(client, text="What does Section 138 NI Act say about cheque dishonour?", id=f"q{n}")
    texts = reply_to(fake_channel)
    assert len(texts) == 3 and texts[2] == inbound.REPLIES["limit"]
    assert len(db.scalars(select(Question)).all()) == 2


def test_stop_still_works_when_the_limit_is_reached(client, db, law, fake_channel, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "whatsapp_questions_per_minute", 1)
    user = linked(db, ROHAN, "reminders")
    for n in range(3):
        send(client, text="What does Section 138 NI Act say about cheque dishonour?", id=f"q{n}")
    send(client, text="STOP", id="stop")
    from mrcourt.services.whatsapp import consent

    db.expire_all()
    assert not consent.is_enabled(db, user.id, "reminders")
    assert reply_to(fake_channel)[-1] == inbound.REPLIES["stop"]


def test_when_the_answer_cannot_be_made_the_person_is_asked_to_try_again(client, db, law, fake_channel, monkeypatch) -> None:
    def broken(*args, **kwargs):
        raise RuntimeError("the answer service fell over")

    monkeypatch.setattr(inbound.ask, "ask", broken)
    linked(db, ROHAN)
    send(client, text="What does Section 138 NI Act say about cheque dishonour?")
    assert reply_to(fake_channel) == [inbound.REPLIES["busy"]]
    db.expire_all()
    (row,) = db.scalars(select(InboundMessage))
    assert (row.status, row.payload) == ("failed", None)
    assert db.scalars(select(Question)).all() == []


def test_an_advocates_private_document_is_never_quoted_on_whatsapp(client, db, law, fake_channel) -> None:
    rohan = linked(db, ROHAN)
    make_document(db, title="Rohan note", citation="Rohan note", kind="note", owner=rohan,
                  passages=["Zanzibar clause: the zanzibar limitation is eleven months."])
    db.commit()
    send(client, text="What is the zanzibar limitation clause?")
    (text,) = reply_to(fake_channel)
    assert "eleven months" not in text and NO_SOURCE_MESSAGE in text


def test_a_message_delivered_twice_is_answered_once(client, db, law, fake_channel) -> None:
    linked(db, ROHAN)
    for _ in range(2):
        send(client, text="What does Section 138 NI Act say about cheque dishonour?", id="same")
    assert len(reply_to(fake_channel)) == 1
    assert len(db.scalars(select(Question)).all()) == 1


def test_a_picture_or_document_gets_the_supported_content_reply(client, db, fake_channel) -> None:
    linked(db, ROHAN)
    send(client, kind="other", text="", id="img")
    assert reply_to(fake_channel) == [inbound.REPLIES["unsupported"]]
    assert db.scalars(select(Question)).all() == []


def test_no_message_text_is_left_in_the_incoming_rows_afterwards(client, db, law, fake_channel) -> None:
    linked(db, ROHAN)
    send(client, text="What does Section 138 NI Act say about cheque dishonour?")
    send(client, sender=OTHER_NUMBER, text="a stranger's words", id="x")
    db.expire_all()
    assert all(row.payload is None for row in db.scalars(select(InboundMessage)))


def test_a_question_asked_on_whatsapp_is_marked_in_the_persons_history(client, db, law, fake_channel) -> None:
    from helpers import sign_in

    linked(db, ANITA)
    send(client, text="What does Section 138 NI Act say about cheque dishonour?")
    sign_in(client, ANITA)
    items = client.get("/api/v1/history").json()["items"]
    assert [(i["channel"], i["input_method"]) for i in items] == [("whatsapp", "typed")]
    client.post("/api/v1/questions", json={"text": "What is cheque dishonour?"})
    assert sorted(i["channel"] for i in client.get("/api/v1/history").json()["items"]) == ["app", "whatsapp"]


def test_unfinished_messages_are_retried_a_few_times_and_then_given_up(db, law, fake_channel) -> None:
    from datetime import timedelta

    from mrcourt.db.base import utcnow
    from mrcourt.services.whatsapp import jobs

    linked(db, ROHAN)
    old = utcnow() - timedelta(minutes=5)
    stuck = InboundMessage(provider="fake", provider_message_id="stuck", sender_hash="h", kind="text", created_at=old,
                           payload={"sender": NUMBER, "text": "What does Section 138 NI Act say about cheque dishonour?"})
    fresh = InboundMessage(provider="fake", provider_message_id="fresh", sender_hash="h2", kind="text", created_at=utcnow(),
                           payload={"sender": NUMBER, "text": "hello"})
    gave_up = InboundMessage(provider="fake", provider_message_id="gaveup", sender_hash="h3", kind="text", created_at=old, attempts=3,
                             payload={"sender": NUMBER, "text": "never"})
    db.add_all([stuck, fresh, gave_up])
    db.commit()
    jobs.run_once(db)
    db.commit()
    db.expire_all()
    states = {r.provider_message_id: (r.status, r.payload) for r in db.scalars(select(InboundMessage))}
    assert states["stuck"] == ("processed", None) and len(fake_channel.texts_to(NUMBER)) == 1
    assert states["fresh"][0] == "received"  # too recent: the live handler may still be working on it
    assert states["gaveup"] == ("failed", None)
