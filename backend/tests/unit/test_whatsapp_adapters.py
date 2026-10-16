"""The Meta and Twilio adapters' sending side, with a fake HTTP transport (no network)."""
import json

import httpx
import pytest
from helpers_whatsapp import use_meta, use_twilio

from mrcourt.services.whatsapp.channel import SendError
from mrcourt.services.whatsapp.meta import MetaChannel
from mrcourt.services.whatsapp.twilio_sandbox import TwilioChannel


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


# ----- Meta ------------------------------------------------------------------------------------------


def test_meta_sends_a_template_with_its_variables(monkeypatch) -> None:
    use_meta(monkeypatch)
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["auth"], seen["body"] = str(request.url), request.headers["authorization"], json.loads(request.content)
        return httpx.Response(200, json={"messages": [{"id": "wamid.OUT1"}]})

    message_id = MetaChannel(client(handler)).send_template("+91 90000 00001", "reminder", ["Sharma v. Verma", "tomorrow, 20 Oct, at 04:00 PM"])
    assert message_id == "wamid.OUT1"
    assert seen["url"] == "https://graph.facebook.com/v21.0/123456/messages" and seen["auth"] == "Bearer meta-access-token"
    template = seen["body"]["template"]
    assert seen["body"]["to"] == "919000000001" and seen["body"]["type"] == "template"
    assert template["name"] == "mrcourt_hearing_reminder" and template["language"] == {"code": "en"}
    assert template["components"] == [
        {"type": "body", "parameters": [{"type": "text", "text": "Sharma v. Verma"}, {"type": "text", "text": "tomorrow, 20 Oct, at 04:00 PM"}]}
    ]


def test_a_meta_code_template_also_carries_the_code_on_its_button(monkeypatch) -> None:
    use_meta(monkeypatch)
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"messages": [{"id": "x"}]})

    MetaChannel(client(handler)).send_template("919000000001", "code", ["123456"])
    assert seen["template"]["name"] == "mrcourt_code"
    assert {"type": "button", "sub_type": "url", "index": "0", "parameters": [{"type": "text", "text": "123456"}]} in seen["template"]["components"]


def test_meta_sends_a_free_text_reply(monkeypatch) -> None:
    use_meta(monkeypatch)
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"messages": [{"id": "wamid.R"}]})

    assert MetaChannel(client(handler)).send_text("919000000001", "Hello") == "wamid.R"
    assert seen["type"] == "text" and seen["text"] == {"body": "Hello"}


@pytest.mark.parametrize(
    ("status", "body", "reason"),
    [
        (400, {"error": {"code": 131026}}, "not_on_whatsapp"),
        (400, {"error": {"code": 132001}}, "template_missing"),
        (400, {"error": {"code": 131047}}, "window_closed"),
        (400, {"error": {"code": 999999}}, "provider_error"),
        (503, {}, "provider_down"),
        (200, {"unexpected": True}, "provider_error"),
    ],
)
def test_meta_errors_become_plain_reasons(monkeypatch, status, body, reason) -> None:
    use_meta(monkeypatch)
    with pytest.raises(SendError) as error:
        MetaChannel(client(lambda r: httpx.Response(status, json=body))).send_text("919000000001", "x")
    assert error.value.reason == reason


def test_meta_network_trouble_is_provider_down(monkeypatch) -> None:
    use_meta(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("no route", request=request)

    with pytest.raises(SendError) as error:
        MetaChannel(client(handler)).send_text("919000000001", "x")
    assert error.value.reason == "provider_down"


def test_meta_with_no_account_details_sends_nothing(monkeypatch) -> None:
    from mrcourt.config import get_settings

    use_meta(monkeypatch)
    monkeypatch.setattr(get_settings(), "whatsapp_access_token", "")
    with pytest.raises(SendError) as error:
        MetaChannel(client(lambda r: httpx.Response(200))).send_text("919000000001", "x")
    assert error.value.reason == "not_configured"


def test_meta_fetches_a_voice_note_in_two_steps(monkeypatch) -> None:
    use_meta(monkeypatch)
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((str(request.url), request.headers.get("authorization")))
        if str(request.url).endswith("/MEDIA1"):
            return httpx.Response(200, json={"url": "https://lookaside.example/audio", "mime_type": "audio/ogg"})
        return httpx.Response(200, content=b"OggS-audio")

    audio, mime = MetaChannel(client(handler)).fetch_audio("MEDIA1")
    assert (audio, mime) == (b"OggS-audio", "audio/ogg")
    assert calls[0] == ("https://graph.facebook.com/v21.0/MEDIA1", "Bearer meta-access-token") and calls[1][0] == "https://lookaside.example/audio"


def test_meta_audio_that_is_missing_or_too_big_is_refused(monkeypatch) -> None:
    use_meta(monkeypatch)
    with pytest.raises(SendError) as error:
        MetaChannel(client(lambda r: httpx.Response(404))).fetch_audio("MEDIA1")
    assert error.value.reason == "media_unavailable"

    def big(request: httpx.Request) -> httpx.Response:
        if str(request.url).endswith("/MEDIA1"):
            return httpx.Response(200, json={"url": "https://lookaside.example/a", "mime_type": "audio/ogg"})
        return httpx.Response(200, content=b"x" * (10 * 1024 * 1024 + 1))

    with pytest.raises(SendError) as error:
        MetaChannel(client(big)).fetch_audio("MEDIA1")
    assert error.value.reason == "media_too_large"


# ----- Twilio sandbox --------------------------------------------------------------------------------


def test_twilio_sends_a_template_as_plain_words_to_a_whatsapp_address(monkeypatch) -> None:
    use_twilio(monkeypatch)
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["auth"] = str(request.url), request.headers["authorization"]
        seen["form"] = dict(httpx.QueryParams(request.content.decode()))
        return httpx.Response(201, json={"sid": "SM123"})

    assert TwilioChannel(client(handler)).send_template("919000000001", "update", ["Sharma v. Verma"]) == "SM123"
    assert seen["url"] == "https://api.twilio.com/2010-04-01/Accounts/AC00000000000000000000000000000000/Messages.json"
    assert seen["auth"].startswith("Basic ")
    assert seen["form"] == {
        "To": "whatsapp:+919000000001",
        "From": "whatsapp:+14155238886",
        "Body": "MrCourt: there is a new update on Sharma v. Verma. Open MrCourt to read it.",
    }


@pytest.mark.parametrize(("code", "reason"), [(63015, "not_on_whatsapp"), (63016, "window_closed"), (12345, "provider_error")])
def test_twilio_errors_become_plain_reasons(monkeypatch, code, reason) -> None:
    use_twilio(monkeypatch)
    with pytest.raises(SendError) as error:
        TwilioChannel(client(lambda r: httpx.Response(400, json={"code": code}))).send_text("919000000001", "x")
    assert error.value.reason == reason


def test_twilio_only_fetches_media_from_twilio_itself(monkeypatch) -> None:
    use_twilio(monkeypatch)
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, content=b"audio", headers={"content-type": "audio/ogg"})

    channel = TwilioChannel(client(handler))
    assert channel.fetch_audio("https://api.twilio.com/2010-04-01/Accounts/AC1/Messages/MM1/Media/ME1") == (b"audio", "audio/ogg")
    with pytest.raises(SendError):
        channel.fetch_audio("https://evil.example/steal")  # our login is never sent to another address
    assert seen == ["https://api.twilio.com/2010-04-01/Accounts/AC1/Messages/MM1/Media/ME1"]
