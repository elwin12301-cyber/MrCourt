"""WhatsApp and privacy: STOP through the webhook, strangers, and deletion when an account is deactivated."""
import json

from helpers_whatsapp import NUMBER, OTHER_NUMBER, WEBHOOK_PATH, linked
from sqlalchemy import select

from mrcourt.config import get_settings
from mrcourt.db.base import utcnow
from mrcourt.models import (
    ConversationState,
    InboundMessage,
    Message,
    MessageConsent,
    User,
    WhatsAppLink,
)
from mrcourt.services import privacy
from mrcourt.services.whatsapp import consent

ROHAN = "rohan.sharma@example.com"
ANITA = "anita.sharma@example.com"


def _send(client, *, sender: str, text: str, id: str, kind: str = "text") -> None:  # noqa: A002
    body = json.dumps({"id": id, "from": sender, "text": text, "kind": kind}).encode()
    assert client.post(WEBHOOK_PATH, content=body).status_code == 200


def test_stop_by_a_linked_person_switches_everything_off_and_confirms_once(client, db, fake_channel) -> None:
    user = linked(db, ANITA, "reminders", "updates")
    _send(client, sender=NUMBER, text="STOP", id="m1")
    db.expire_all()
    assert not any(consent.is_enabled(db, user.id, k) for k in consent.kinds_for("petitioner"))
    assert all(c.changed_by == "stop" for c in db.scalars(select(MessageConsent)))
    assert fake_channel.texts_to(NUMBER) == ["You will not get WhatsApp messages from MrCourt. You can switch them on again in Settings."]
    assert [e.action for e in db.scalars(select(__import__("mrcourt.models", fromlist=["AuditEntry"]).AuditEntry)) if e.action == "whatsapp.stop"] == ["whatsapp.stop"]


def test_stop_in_hindi_and_tamil_works_too(client, db, fake_channel) -> None:
    user = linked(db, ROHAN, "reminders")
    _send(client, sender=NUMBER, text="रोकें", id="m1")
    db.expire_all()
    assert not consent.is_enabled(db, user.id, "reminders")
    consent.set_consent(db, user, "reminders", True)
    db.commit()
    _send(client, sender=NUMBER, text="நிறுத்து", id="m2")
    db.expire_all()
    assert not consent.is_enabled(db, user.id, "reminders")


def test_a_strangers_stop_changes_nothing_and_gets_no_reply(client, db, fake_channel) -> None:
    linked(db, ANITA, "reminders")
    _send(client, sender=OTHER_NUMBER, text="STOP", id="m1")
    assert fake_channel.sent == []
    db.expire_all()
    assert all(c.enabled for c in db.scalars(select(MessageConsent)))


def test_a_message_from_a_linked_person_opens_the_free_reply_window(client, db, fake_channel) -> None:
    user = linked(db, ROHAN)
    assert consent.get_link(db, user.id).last_inbound_at is None
    _send(client, sender=NUMBER, text="hello", id="m1")
    db.expire_all()
    assert consent.get_link(db, user.id).last_inbound_at is not None


def test_a_strangers_number_is_never_stored(client, db, fake_channel) -> None:
    _send(client, sender="919123456789", text="hello", id="m1")
    db.expire_all()
    (row,) = db.scalars(select(InboundMessage))
    assert row.user_id is None and row.payload is None
    assert "919123456789" not in json.dumps([row.sender_hash, row.kind, row.status, row.provider_message_id])


def test_deactivating_an_account_removes_the_link_choices_records_and_open_lists(db) -> None:
    user = linked(db, ANITA, "reminders", "updates")
    db.add(Message(user_id=user.id, kind="reminder", channel="whatsapp", status="delivered", created_at=utcnow()))
    db.add(ConversationState(user_id=user.id, awaiting="case_choice", options=["x"], expires_at=utcnow()))
    db.add(InboundMessage(provider="development", provider_message_id="p1", user_id=user.id, sender_hash="h", payload={"text": "secret"}))
    db.commit()
    privacy.deactivate(db, db.get(User, user.id))
    db.commit()
    assert db.scalars(select(WhatsAppLink)).all() == []
    assert db.scalars(select(MessageConsent)).all() == []
    assert db.scalars(select(Message)).all() == []
    assert db.scalars(select(ConversationState)).all() == []
    (row,) = db.scalars(select(InboundMessage))
    assert row.user_id is None and row.payload is None
    assert consent.user_for_number(db, NUMBER) is None


def test_no_words_codes_numbers_or_keys_are_kept_or_logged_outside_the_persons_own_history(client, second_client, db, fake_channel, caplog, monkeypatch) -> None:
    """After questions, a code, a reminder, a nudge, STOP and the administrator's views, the delivery records, incoming
    rows, conversation state, audit log, admin data and the logs hold none of the words, the code, the number or keys."""
    import logging

    from helpers import sign_in
    from helpers_whatsapp import linked
    from sqlalchemy import select

    from mrcourt.models import AuditEntry, Case, ConversationState, Message
    from mrcourt.services import auth
    from mrcourt.services.whatsapp import outbox

    monkeypatch.setattr(get_settings(), "whatsapp_access_token", "SECRET-ACCESS-TOKEN-7731")
    monkeypatch.setattr(get_settings(), "whatsapp_app_secret", "SECRET-APP-SECRET-5520")
    caplog.set_level(logging.DEBUG)
    words = "SENSITIVE-ZEBRA-QUESTION about dishonour of a cheque and my bail"
    user = linked(db, ROHAN, "reminders", "codes", "activity")

    send_text(client, words, "q1")
    auth.request_otp(db, ROHAN)
    db.commit()
    (code,) = [variables[0] for kind, variables in fake_channel.templates_to(NUMBER) if kind == "code"]
    case = db.scalars(select(Case)).first()
    outbox.queue_nudge(db, user, "activity", case)
    send_text(client, "STOP", "stop1")
    db.commit()

    sign_in(second_client, "admin@example.com")
    api = [
        second_client.get("/api/v1/admin/messages/summary").text,
        second_client.get("/api/v1/admin/messages/failures").text,
    ]
    sign_in(client, ROHAN)
    api.append(client.get("/api/v1/me/whatsapp").text)

    def dump(model):
        db.expire_all()
        return json.dumps([{c.name: str(getattr(row, c.name)) for c in model.__table__.columns} for row in db.scalars(select(model))])

    stored = " ".join([dump(Message), dump(InboundMessage), dump(ConversationState), dump(AuditEntry)])
    everywhere = " ".join([stored, *api, caplog.text])
    for secret in ("SENSITIVE-ZEBRA", "dishonour of a cheque", code, "SECRET-ACCESS-TOKEN-7731", "SECRET-APP-SECRET-5520"):
        assert secret not in everywhere, secret
    for number in (NUMBER, NUMBER[2:]):  # the number appears only in the person's own link, never elsewhere
        assert number not in stored and number not in " ".join(api[:2]) and number not in caplog.text, number


def send_text(client, text, id):  # noqa: A002
    from helpers_whatsapp import send

    send(client, text=text, id=id)
