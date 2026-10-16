"""Fast2SMS end to end through the webhook: the secret check, a question answered by the session call, and delivery
reports matched to our messages (by id, or by recipient when the id differs), with the one SMS fallback."""
import json

import httpx
import pytest
from helpers import make_document
from helpers_whatsapp import NUMBER, WEBHOOK_PATH, f2s_headers, f2s_incoming, f2s_status, linked, use_fast2sms
from sqlalchemy import select

from mrcourt.config import get_settings
from mrcourt.db.base import utcnow
from mrcourt.models import Case, InboundMessage, LegalSource, Message
from mrcourt.services import notify
from mrcourt.services.whatsapp import inbound
from mrcourt.services.whatsapp.fast2sms import Fast2SmsChannel

ROHAN = "rohan.sharma@example.com"
ANITA = "anita.sharma@example.com"
REAL_REPLY = inbound.reply  # captured before the helper stubs it


@pytest.fixture
def outgoing(monkeypatch):
    """Fast2SMS with a fake HTTP side: records what the app sends and answers success."""
    use_fast2sms(monkeypatch)
    monkeypatch.setattr(inbound, "reply", REAL_REPLY)  # these tests want the real reply to be sent (to the fake transport)
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={"status": "success", "return": True, "request_id": "req-1"})

    fake = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(Fast2SmsChannel, "_http", lambda self: fake)
    monkeypatch.setattr(get_settings(), "whatsapp_questions_per_minute", 100)
    return sent


def post(client, body: bytes, headers=None):
    return client.post(WEBHOOK_PATH, content=body, headers=headers or f2s_headers())


def test_a_call_without_the_secret_is_refused_and_nothing_is_stored(client, db, outgoing) -> None:
    assert post(client, f2s_incoming(), {"Content-Type": "application/json"}).status_code == 403
    assert post(client, f2s_incoming(), f2s_headers("wrong")).status_code == 403
    db.expire_all()
    assert db.scalars(select(InboundMessage)).all() == [] and outgoing == []


def test_a_question_is_answered_back_through_the_session_call(client, db, outgoing) -> None:
    linked(db, ROHAN)
    exact = make_document(db, title="Negotiable Instruments Act, 1881", citation="NI Act s.138", kind="act_section",
                          passages=["Dishonour of cheque for insufficiency of funds in the account."])
    db.flush()
    db.scalars(select(LegalSource).where(LegalSource.document_id == exact.id)).first().section = "138"
    db.commit()
    assert post(client, f2s_incoming(body="What does Section 138 NI Act say about cheque dishonour?")).status_code == 200
    (call,) = outgoing
    assert call.method == "POST" and str(call.url).split("?")[0] == "https://www.fast2sms.com/dev/whatsapp-session"
    assert dict(call.url.params) == {"phone_number_id": "1122334455", "to": NUMBER}
    text = json.loads(call.content)["text"]
    assert "Sources:" in text and "NI Act s.138" in text and "Informational only" in text


def test_a_repeated_delivery_of_the_same_message_is_answered_once(client, db, outgoing) -> None:
    linked(db, ROHAN)
    for _ in range(3):  # Fast2SMS retries when it does not get a quick 200
        assert post(client, f2s_incoming(body="help", id="wamid.SAME")).status_code == 200
    assert len(outgoing) == 1


def _sent_message(db, user, *, provider_id="req-9", kind="update"):
    case = db.scalars(select(Case).where(Case.title == "Sharma v. Verma Traders")).one()
    row = Message(user_id=user.id, kind=kind, channel="whatsapp", status="sent", provider="fast2sms", provider_message_id=provider_id,
                  case_id=case.id, created_at=utcnow())
    db.add(row)
    db.commit()
    return row


def test_a_report_with_a_different_id_is_matched_by_the_recipient(client, db, outgoing) -> None:
    user = linked(db, ANITA, "updates")
    row = _sent_message(db, user)
    for status in ("delivered", "read"):
        assert post(client, f2s_status(id="wamid.OTHER-ID", status=status)).status_code == 200
    db.expire_all()
    assert db.get(Message, row.id).status == "read"


def test_a_report_for_a_number_we_did_not_message_changes_nothing(client, db, outgoing) -> None:
    user = linked(db, ANITA, "updates")
    row = _sent_message(db, user)
    assert post(client, f2s_status(id="wamid.X", status="delivered", recipient="919888888888")).status_code == 200
    db.expire_all()
    assert db.get(Message, row.id).status == "sent"


def test_a_reported_failure_sends_one_sms_even_if_the_provider_repeats_itself(client, db, outgoing) -> None:
    user = linked(db, ANITA, "updates")
    row = _sent_message(db, user)
    for _ in range(3):
        post(client, f2s_status(id="wamid.Z", status="failed", error="The number is not on WhatsApp"))
    db.expire_all()
    assert (db.get(Message, row.id).status, db.get(Message, row.id).failure_reason) == ("failed", "not_on_whatsapp")
    texts = [m.text for m in notify.OUTBOX if m.channel == "sms"]
    assert texts == ["MrCourt: there is a new update on Sharma v. Verma Traders. Open MrCourt to read it."]


def test_the_stored_provider_id_is_preferred_when_the_report_carries_it(client, db, outgoing) -> None:
    user = linked(db, ANITA, "updates")
    first = _sent_message(db, user, provider_id="req-A")
    second = _sent_message(db, user, provider_id="req-B")
    post(client, f2s_status(id="req-A", status="delivered"))
    db.expire_all()
    assert (db.get(Message, first.id).status, db.get(Message, second.id).status) == ("delivered", "sent")
