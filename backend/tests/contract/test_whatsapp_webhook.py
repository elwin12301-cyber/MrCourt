"""The public WhatsApp webhook: refuses what is not signed, ignores repeats, never says who has an account."""
import pytest
from helpers_whatsapp import (
    NUMBER,
    OTHER_NUMBER,
    VERIFY_TOKEN,
    WEBHOOK_PATH,
    dev_request,
    meta_request,
    twilio_request,
    use_meta,
    use_twilio,
)
from sqlalchemy import select

from mrcourt.config import get_settings
from mrcourt.models import InboundMessage


def _rows(db):
    db.expire_all()
    return list(db.scalars(select(InboundMessage)))


def test_an_unsigned_or_wrongly_signed_call_is_refused_and_nothing_is_stored(client, db, monkeypatch) -> None:
    use_meta(monkeypatch)
    body, _ = meta_request()
    assert client.post(WEBHOOK_PATH, content=body).status_code == 403
    assert client.post(WEBHOOK_PATH, content=body, headers={"X-Hub-Signature-256": "sha256=" + "0" * 64}).status_code == 403
    bad_body, headers = meta_request(secret="not-our-secret")
    assert client.post(WEBHOOK_PATH, content=bad_body, headers=headers).status_code == 403
    assert _rows(db) == []


def test_a_signed_message_is_kept_handled_and_leaves_no_text_behind(client, db, monkeypatch) -> None:
    use_meta(monkeypatch)
    body, headers = meta_request(text="What is Section 138?", id="wamid.ONE")
    response = client.post(WEBHOOK_PATH, content=body, headers=headers)
    assert response.status_code == 200 and response.json() == {}
    (row,) = _rows(db)
    assert (row.provider, row.provider_message_id, row.status, row.kind) == ("meta", "wamid.ONE", "processed", "unknown_sender")
    assert row.payload is None  # the text is cleared once handled
    assert row.sender_hash != NUMBER and NUMBER not in row.sender_hash  # only a hash of the number


def test_the_same_message_twice_is_one_message(client, db, monkeypatch) -> None:
    use_meta(monkeypatch)
    body, headers = meta_request(id="wamid.SAME")
    assert client.post(WEBHOOK_PATH, content=body, headers=headers).status_code == 200
    assert client.post(WEBHOOK_PATH, content=body, headers=headers).status_code == 200
    assert len(_rows(db)) == 1


def test_twilio_calls_are_checked_the_same_way(client, db, monkeypatch) -> None:
    use_twilio(monkeypatch)
    body, headers = twilio_request(id="SM42")
    assert client.post(WEBHOOK_PATH, content=body, headers=headers).status_code == 200
    assert [r.provider for r in _rows(db)] == ["twilio"]
    body, headers = twilio_request(token="wrong", id="SM43")
    assert client.post(WEBHOOK_PATH, content=body, headers=headers).status_code == 403
    assert len(_rows(db)) == 1


def test_meta_setup_challenge_is_answered_only_with_the_right_token(client, monkeypatch) -> None:
    use_meta(monkeypatch)
    ok = client.get(WEBHOOK_PATH, params={"hub.mode": "subscribe", "hub.verify_token": VERIFY_TOKEN, "hub.challenge": "12345"})
    assert (ok.status_code, ok.text) == (200, "12345")
    assert client.get(WEBHOOK_PATH, params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "1"}).status_code == 403
    assert client.get(WEBHOOK_PATH, params={"hub.mode": "subscribe", "hub.challenge": "1"}).status_code == 403
    monkeypatch.setattr(get_settings(), "whatsapp_verify_token", "")
    assert client.get(WEBHOOK_PATH, params={"hub.mode": "subscribe", "hub.verify_token": "", "hub.challenge": "1"}).status_code == 403


def test_a_call_without_an_origin_passes_the_cross_site_check_and_a_foreign_origin_does_not(client, monkeypatch) -> None:
    use_meta(monkeypatch)
    body, headers = meta_request()
    assert client.post(WEBHOOK_PATH, content=body, headers=headers).status_code == 200  # providers send no Origin
    body, headers = meta_request(id="wamid.TWO")
    assert client.post(WEBHOOK_PATH, content=body, headers={**headers, "Origin": "https://evil.example"}).status_code == 403


def test_a_huge_body_is_refused(client, monkeypatch) -> None:
    use_meta(monkeypatch)
    big = b"x" * (1024 * 1024 + 1)
    assert client.post(WEBHOOK_PATH, content=big, headers={"X-Hub-Signature-256": "sha256=00"}).status_code == 413


def test_the_reply_is_the_same_whether_or_not_the_number_has_an_account(client, monkeypatch) -> None:
    use_meta(monkeypatch)
    answers = []
    for number, id_ in ((NUMBER, "wamid.A"), (OTHER_NUMBER, "wamid.B")):
        body, headers = meta_request(sender=number, id=id_)
        r = client.post(WEBHOOK_PATH, content=body, headers=headers)
        answers.append((r.status_code, r.text))
    assert answers[0] == answers[1] == (200, "{}")


def test_with_no_provider_the_webhook_is_closed_in_production(client, monkeypatch) -> None:
    body, headers = dev_request()  # signed while still in development mode
    monkeypatch.setattr(get_settings(), "whatsapp_provider", "none")
    monkeypatch.setattr(get_settings(), "environment", "production")
    assert client.post(WEBHOOK_PATH, content=body, headers=headers).status_code == 403


def test_the_development_channel_accepts_only_calls_signed_with_the_development_secret(client, db) -> None:
    body, headers = dev_request(id="dev-9")
    assert client.post(WEBHOOK_PATH, content=body, headers=headers).status_code == 200
    assert [r.provider for r in _rows(db)] == ["development"]
    assert client.post(WEBHOOK_PATH, content=body.replace(b"dev-9", b"dev-10"), headers=headers).status_code == 403
