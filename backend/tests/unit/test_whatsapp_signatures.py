"""The providers' webhook signatures and the messages and delivery reports read from sample payloads."""
import hmac
import json

import pytest
from helpers_whatsapp import (
    META_SECRET,
    NUMBER,
    TWILIO_TOKEN,
    WEBHOOK_URL,
    meta_body,
    meta_request,
    meta_signature,
    twilio_body,
    twilio_request,
    twilio_signature,
    use_meta,
    use_twilio,
)

from mrcourt.services.whatsapp import meta as meta_module
from mrcourt.services.whatsapp.channel import SignatureError
from mrcourt.services.whatsapp.meta import MetaChannel
from mrcourt.services.whatsapp.twilio_sandbox import TwilioChannel


@pytest.fixture
def meta(monkeypatch):
    use_meta(monkeypatch)
    return MetaChannel()


@pytest.fixture
def twilio(monkeypatch):
    use_twilio(monkeypatch)
    return TwilioChannel()


def test_a_genuine_meta_text_message_is_read(meta) -> None:
    body, headers = meta_request(text="What is Section 138?", id="wamid.A")
    parsed = meta.verify_and_parse(headers, body, WEBHOOK_URL)
    assert [(m.provider, m.provider_message_id, m.sender, m.kind, m.text) for m in parsed.messages] == [
        ("meta", "wamid.A", NUMBER, "text", "What is Section 138?")
    ]


def test_a_meta_voice_note_and_other_content_are_recognised(meta) -> None:
    body, headers = meta_request("meta_audio")
    message = meta.verify_and_parse(headers, body, WEBHOOK_URL).messages[0]
    assert (message.kind, message.media_ref, message.media_type) == ("audio", "MEDIA1", "audio/ogg; codecs=opus")
    other = json.loads(meta_body()) 
    other["entry"][0]["changes"][0]["value"]["messages"][0]["type"] = "image"
    raw = json.dumps(other).encode()
    assert meta.verify_and_parse(meta_signature(raw), raw, WEBHOOK_URL).messages[0].kind == "other"


def test_meta_delivery_reports_are_read_with_a_plain_reason(meta) -> None:
    body, headers = meta_request("meta_status_delivered", id="wamid.OUT", status="read")
    assert [(r.provider_message_id, r.status, r.reason) for r in meta.verify_and_parse(headers, body, WEBHOOK_URL).reports] == [
        ("wamid.OUT", "read", None)
    ]
    body, headers = meta_request("meta_status_failed", id="wamid.OUT")
    report = meta.verify_and_parse(headers, body, WEBHOOK_URL).reports[0]
    assert (report.status, report.reason) == ("failed", "not_on_whatsapp")


def test_a_meta_call_with_a_bad_signature_is_refused(meta) -> None:
    body, headers = meta_request()
    for bad in (
        {},  # missing
        {"X-Hub-Signature-256": "sha256=" + "0" * 64},  # wrong
        {"X-Hub-Signature-256": "0" * 64},  # no prefix
        meta_signature(body, "another-secret"),  # signed with another secret
        meta_signature(body + b" ", META_SECRET),  # body changed after signing
    ):
        with pytest.raises(SignatureError):
            meta.verify_and_parse(bad, body, WEBHOOK_URL)


def test_meta_with_no_secret_configured_refuses_everything(meta, monkeypatch) -> None:
    from mrcourt.config import get_settings

    monkeypatch.setattr(get_settings(), "whatsapp_app_secret", "")
    body, headers = meta_request()
    with pytest.raises(SignatureError):
        meta.verify_and_parse(headers, body, WEBHOOK_URL)


def test_nothing_is_read_before_the_signature_is_checked_and_the_comparison_is_constant_time(meta, monkeypatch) -> None:
    def explode(*args, **kwargs):
        raise AssertionError("the body was read before the signature was checked")

    body, _ = meta_request()
    monkeypatch.setattr(meta_module.json, "loads", explode)
    with pytest.raises(SignatureError):
        meta.verify_and_parse({"X-Hub-Signature-256": "sha256=" + "1" * 64}, body, WEBHOOK_URL)

    calls = []
    real = hmac.compare_digest
    monkeypatch.setattr(meta_module.hmac, "compare_digest", lambda a, b: calls.append(1) or real(a, b))
    with pytest.raises(SignatureError):
        meta.verify_and_parse({"X-Hub-Signature-256": "sha256=" + "2" * 64}, body, WEBHOOK_URL)
    assert calls


def test_a_genuine_twilio_message_and_reports_are_read(twilio) -> None:
    body, headers = twilio_request(text="Next hearing please", id="SMIN")
    message = twilio.verify_and_parse(headers, body, WEBHOOK_URL).messages[0]
    assert (message.sender, message.kind, message.text, message.provider_message_id) == (NUMBER, "text", "Next hearing please", "SMIN")
    body, headers = twilio_request("twilio_status", id="SMOUT", status="delivered")
    assert twilio.verify_and_parse(headers, body, WEBHOOK_URL).reports[0].status == "delivered"
    body, headers = twilio_request("twilio_status", id="SMOUT", status="undelivered", error="63015")
    report = twilio.verify_and_parse(headers, body, WEBHOOK_URL).reports[0]
    assert (report.status, report.reason) == ("failed", "not_on_whatsapp")


def test_twilio_progress_statuses_are_ignored(twilio) -> None:
    body, headers = twilio_request("twilio_status", status="queued")
    parsed = twilio.verify_and_parse(headers, body, WEBHOOK_URL)
    assert parsed.reports == [] and parsed.messages == []


def test_a_twilio_call_with_a_bad_signature_is_refused(twilio) -> None:
    body = twilio_body()
    for bad in (
        {},
        twilio_signature(body, "another-token"),
        twilio_signature(body, TWILIO_TOKEN, "https://elsewhere.example/api/v1/whatsapp/webhook"),  # signed for another address
        twilio_signature(body + b"&Extra=1"),  # fields changed after signing is checked against the old body below
    ):
        with pytest.raises(SignatureError):
            twilio.verify_and_parse(bad, body, WEBHOOK_URL)
