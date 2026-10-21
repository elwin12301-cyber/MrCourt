"""The Fast2SMS WhatsApp adapter, with a fake HTTP transport (no network)."""
import hmac

import httpx
import pytest
from helpers_whatsapp import F2S_SECRET, NUMBER, f2s_headers, f2s_incoming, f2s_status, use_fast2sms

from mrcourt.config import get_settings
from mrcourt.services.whatsapp import fast2sms as module
from mrcourt.services.whatsapp.channel import SendError, SignatureError
from mrcourt.services.whatsapp.fast2sms import Fast2SmsChannel

URL = "http://localhost:5173/api/v1/whatsapp/webhook"


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture
def channel(monkeypatch):
    use_fast2sms(monkeypatch)
    return Fast2SmsChannel()


# ----- sending ---------------------------------------------------------------------------------------


def test_a_template_goes_by_get_with_the_template_id_the_number_and_the_values(monkeypatch) -> None:
    use_fast2sms(monkeypatch)
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["auth"], seen["params"] = str(request.url).split("?")[0], request.headers["authorization"], dict(request.url.params)
        return httpx.Response(200, json={"return": True, "request_id": "req-777", "message": ["WhatsApp message sent"]})

    request_id = Fast2SmsChannel(client(handler)).send_template("919000000001", "reminder", ["Sharma | Verma", "tomorrow at 4 PM"])
    assert request_id == "req-777"
    assert seen["url"] == "https://www.fast2sms.com/dev/whatsapp" and seen["auth"] == "F2S-API-KEY"  # the raw key, no Bearer
    assert seen["params"] == {
        "message_id": "102", "phone_number_id": "1122334455", "numbers": "9000000001",
        "variables_values": "Sharma / Verma|tomorrow at 4 PM",  # a pipe inside a case title cannot split the values
    }


def test_the_number_id_is_optional_for_templates_and_left_out_when_not_set(monkeypatch) -> None:
    use_fast2sms(monkeypatch)
    monkeypatch.setattr(get_settings(), "fast2sms_whatsapp_phone_number_id", "")
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(200, json={"return": True, "request_id": "r"})

    Fast2SmsChannel(client(handler)).send_template("919000000001", "reminder", ["A", "B"])
    assert "phone_number_id" not in seen and seen["message_id"] == "102"


def test_a_reply_still_needs_the_number_id(monkeypatch) -> None:
    use_fast2sms(monkeypatch)
    monkeypatch.setattr(get_settings(), "fast2sms_whatsapp_phone_number_id", "")
    with pytest.raises(SendError) as error:
        Fast2SmsChannel(client(lambda r: httpx.Response(200, json={"status": "success"}))).send_text("919000000001", "x")
    assert error.value.reason == "not_configured"


def test_each_kind_uses_its_own_template(monkeypatch) -> None:
    use_fast2sms(monkeypatch)
    ids = []

    def handler(request: httpx.Request) -> httpx.Response:
        ids.append(request.url.params["message_id"])
        return httpx.Response(200, json={"return": True, "request_id": "r"})

    channel = Fast2SmsChannel(client(handler))
    for kind, variables in (("code", ["123456"]), ("reminder", ["A", "B"]), ("update", ["A"]), ("activity", ["A"])):
        channel.send_template("919000000001", kind, variables)
    assert ids == ["101", "102", "103", "104"]


@pytest.mark.parametrize("missing", ["fast2sms_api_key", "fast2sms_whatsapp_template_reminder"])
def test_missing_details_send_nothing(monkeypatch, missing) -> None:
    use_fast2sms(monkeypatch)
    monkeypatch.setattr(get_settings(), missing, "")
    calls = []
    with pytest.raises(SendError) as error:
        Fast2SmsChannel(client(lambda r: calls.append(r) or httpx.Response(200))).send_template("919000000001", "reminder", ["A", "B"])
    assert error.value.reason == "not_configured" and calls == []


@pytest.mark.parametrize(
    ("status", "body", "reason"),
    [
        (200, {"return": False, "message": ["Template not approved"]}, "template_missing"),
        (200, {"return": False, "message": ["Number is not on WhatsApp"]}, "not_on_whatsapp"),
        (400, {"message": "Invalid API key"}, "provider_error"),
        (503, {}, "provider_down"),
    ],
)
def test_refusals_become_plain_reasons(monkeypatch, status, body, reason) -> None:
    use_fast2sms(monkeypatch)
    with pytest.raises(SendError) as error:
        Fast2SmsChannel(client(lambda r: httpx.Response(status, json=body))).send_template("919000000001", "update", ["A"])
    assert error.value.reason == reason


def test_network_trouble_is_provider_down(monkeypatch) -> None:
    use_fast2sms(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(SendError) as error:
        Fast2SmsChannel(client(handler)).send_text("919000000001", "x")
    assert error.value.reason == "provider_down"


def test_a_reply_goes_by_the_session_call_with_the_full_number(monkeypatch) -> None:
    use_fast2sms(monkeypatch)
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen.update(method=request.method, url=str(request.url).split("?")[0], params=dict(request.url.params), body=json.loads(request.content), auth=request.headers["authorization"])
        return httpx.Response(200, json={"status": "success"})

    Fast2SmsChannel(client(handler)).send_text("919000000001", "Hello there")
    assert seen["method"] == "POST" and seen["url"] == "https://www.fast2sms.com/dev/whatsapp-session"
    assert seen["params"] == {"phone_number_id": "1122334455", "to": "919000000001"}
    assert seen["body"] == {"type": "text", "text": "Hello there"} and seen["auth"] == "F2S-API-KEY"


def test_a_refused_reply_is_an_error(monkeypatch) -> None:
    use_fast2sms(monkeypatch)
    with pytest.raises(SendError):
        Fast2SmsChannel(client(lambda r: httpx.Response(200, json={"status": "failed", "message": "window closed"}))).send_text("919000000001", "x")


# ----- receiving -------------------------------------------------------------------------------------


def test_a_genuine_text_message_is_read(channel) -> None:
    parsed = channel.verify_and_parse(f2s_headers(), f2s_incoming(body="What is Section 138?", id="wamid.A"), URL)
    assert [(m.provider, m.provider_message_id, m.sender, m.kind, m.text) for m in parsed.messages] == [
        ("fast2sms", "wamid.A", NUMBER, "text", "What is Section 138?")
    ]


def test_a_voice_note_and_other_content_are_recognised(channel) -> None:
    audio = channel.verify_and_parse(f2s_headers(), f2s_incoming(message_type="audio", media_url="https://www.fast2sms.com/m/1", mime="audio/ogg"), URL).messages[0]
    assert (audio.kind, audio.media_ref, audio.media_type) == ("audio", "https://www.fast2sms.com/m/1", "audio/ogg")
    assert channel.verify_and_parse(f2s_headers(), f2s_incoming(message_type="image"), URL).messages[0].kind == "other"


def test_a_form_encoded_body_and_a_list_of_events_are_both_read(channel) -> None:
    form = b"webhook_type=incoming_message&from=919000000001&message_id=wamid.FORM&message_type=text&body=hello"
    assert channel.verify_and_parse(f2s_headers(), form, URL).messages[0].text == "hello"
    both = b"[" + f2s_incoming(id="a") + b"," + f2s_status(id="b") + b"]"
    parsed = channel.verify_and_parse(f2s_headers(), both, URL)
    assert len(parsed.messages) == 1 and len(parsed.reports) == 1


def test_status_updates_become_delivery_reports_with_the_recipient(channel) -> None:
    for word, expected in (("sent", "sent"), ("Delivered", "delivered"), ("read", "read")):
        report = channel.verify_and_parse(f2s_headers(), f2s_status(status=word, id="wamid.S"), URL).reports[0]
        assert (report.provider, report.provider_message_id, report.status, report.reason, report.recipient) == ("fast2sms", "wamid.S", expected, None, NUMBER)
    failed = channel.verify_and_parse(f2s_headers(), f2s_status(status="failed", error="The number is not on WhatsApp"), URL).reports[0]
    assert (failed.status, failed.reason) == ("failed", "not_on_whatsapp")
    assert channel.verify_and_parse(f2s_headers(), f2s_status(status="queued"), URL).reports == []  # progress words are ignored


def test_a_live_style_report_matches_by_our_send_id_and_gives_the_held_back_reason(channel) -> None:
    body = (
        b'{"webhook_type":"status_update","status":"failed","fast2sms_request_id":"WN9FP","request_id":"wamid.LONG",'
        b'"recipient_id":919535673788,"status_description":"This message was not delivered to maintain healthy ecosystem '
        b'engagement. (Error: 131049)"}'
    )
    report = channel.verify_and_parse(f2s_headers(), body, URL).reports[0]
    assert (report.provider_message_id, report.status, report.reason, report.recipient) == ("WN9FP", "failed", "not_delivered", "919535673788")


@pytest.mark.parametrize("headers", [{},{"webhook_secret_key": "wrong"}, {"webhook_secret_key": ""}, {"x-other": F2S_SECRET}])
def test_a_call_without_the_right_secret_is_refused(channel, headers) -> None:
    with pytest.raises(SignatureError):
        channel.verify_and_parse(headers, f2s_incoming(), URL)


def test_a_proxy_that_turns_underscores_into_dashes_still_works(channel) -> None:
    assert channel.verify_and_parse({"webhook-secret-key": F2S_SECRET}, f2s_incoming(), URL).messages


def test_with_no_secret_configured_everything_is_refused_and_the_comparison_is_constant_time(channel, monkeypatch) -> None:
    calls = []
    real = hmac.compare_digest
    monkeypatch.setattr(module.hmac, "compare_digest", lambda a, b: calls.append(1) or real(a, b))
    with pytest.raises(SignatureError):
        channel.verify_and_parse({"webhook_secret_key": "nope"}, f2s_incoming(), URL)
    assert calls
    monkeypatch.setattr(get_settings(), "fast2sms_webhook_secret", "")
    with pytest.raises(SignatureError):
        channel.verify_and_parse({"webhook_secret_key": ""}, f2s_incoming(), URL)


def test_an_unreadable_body_with_the_right_secret_is_ignored_not_an_error(channel) -> None:
    parsed = channel.verify_and_parse(f2s_headers(), b"\xff\xfe not text", URL)
    assert parsed.messages == [] and parsed.reports == []


# ----- voice notes -----------------------------------------------------------------------------------


def test_audio_is_fetched_only_from_fast2sms_over_https(monkeypatch) -> None:
    use_fast2sms(monkeypatch)
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((str(request.url), request.headers.get("authorization")))
        return httpx.Response(200, content=b"OggS", headers={"content-type": "audio/ogg"})

    channel = Fast2SmsChannel(client(handler))
    assert channel.fetch_audio("https://www.fast2sms.com/media/1") == (b"OggS", "audio/ogg")
    for bad in ("http://www.fast2sms.com/media/1", "https://evil.example/steal", "https://fast2sms.com.evil.example/x", "http://169.254.169.254/latest"):
        with pytest.raises(SendError):
            channel.fetch_audio(bad)  # our login is never sent elsewhere, and a forged call cannot aim us at another address
    assert seen == [("https://www.fast2sms.com/media/1", "F2S-API-KEY")]


def test_audio_that_is_too_big_or_missing_is_refused(monkeypatch) -> None:
    use_fast2sms(monkeypatch)
    with pytest.raises(SendError) as error:
        Fast2SmsChannel(client(lambda r: httpx.Response(404))).fetch_audio("https://www.fast2sms.com/media/1")
    assert error.value.reason == "media_unavailable"
    with pytest.raises(SendError) as error:
        Fast2SmsChannel(client(lambda r: httpx.Response(200, content=b"x" * (10 * 1024 * 1024 + 1)))).fetch_audio("https://www.fast2sms.com/media/1")
    assert error.value.reason == "media_too_large"
