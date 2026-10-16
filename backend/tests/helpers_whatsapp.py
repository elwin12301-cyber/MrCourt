"""Helpers for the WhatsApp tests: signed provider requests built from the sample payloads, and a fake channel."""

import base64
import hashlib
import hmac
import json
import urllib.parse
from pathlib import Path

from mrcourt.services.whatsapp.channel import (
    DeliveryReport,
    InboundMessage,
    ParsedRequest,
    SendError,
    digits,
    render_template,
)

DATA = Path(__file__).parent / "data" / "whatsapp"
META_SECRET = "meta-test-secret"
TWILIO_TOKEN = "twilio-test-token"
VERIFY_TOKEN = "verify-test-token"
WEBHOOK_URL = "http://localhost:5173/api/v1/whatsapp/webhook"  # PUBLIC_APP_URL default + the path
WEBHOOK_PATH = "/api/v1/whatsapp/webhook"

NUMBER = "919000000001"  # fictional
OTHER_NUMBER = "919000000002"


def _no_network_replies(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Tests of the real providers' webhooks read what arrives; a reply must never really be sent."""
    from mrcourt.services.whatsapp import inbound

    monkeypatch.setattr(inbound, "reply", lambda number, text: None)


def use_meta(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from mrcourt.config import get_settings

    _no_network_replies(monkeypatch)
    s = get_settings()
    monkeypatch.setattr(s, "whatsapp_provider", "meta")
    monkeypatch.setattr(s, "whatsapp_app_secret", META_SECRET)
    monkeypatch.setattr(s, "whatsapp_verify_token", VERIFY_TOKEN)
    monkeypatch.setattr(s, "whatsapp_phone_number_id", "123456")
    monkeypatch.setattr(s, "whatsapp_access_token", "meta-access-token")


def use_twilio(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from mrcourt.config import get_settings

    _no_network_replies(monkeypatch)
    s = get_settings()
    monkeypatch.setattr(s, "whatsapp_provider", "twilio")
    monkeypatch.setattr(s, "twilio_account_sid", "AC" + "0" * 32)
    monkeypatch.setattr(s, "twilio_auth_token", TWILIO_TOKEN)
    monkeypatch.setattr(s, "twilio_whatsapp_from", "whatsapp:+14155238886")


F2S_SECRET = "f2s-webhook-secret-40-characters-long-0000"


def use_fast2sms(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from mrcourt.config import get_settings

    from mrcourt.services import notify

    _no_network_replies(monkeypatch)
    notify.set_notifier(notify.ConsoleNotifier())  # the SMS side stays on the development outbox even with the key set
    s = get_settings()
    monkeypatch.setattr(s, "whatsapp_provider", "fast2sms")
    monkeypatch.setattr(s, "fast2sms_api_key", "F2S-API-KEY")
    monkeypatch.setattr(s, "fast2sms_whatsapp_phone_number_id", "1122334455")
    monkeypatch.setattr(s, "fast2sms_webhook_secret", F2S_SECRET)
    for kind, template_id in (("code", "101"), ("reminder", "102"), ("update", "103"), ("activity", "104")):
        monkeypatch.setattr(s, f"fast2sms_whatsapp_template_{kind}", template_id)


def f2s_incoming(*, sender: str = NUMBER, id: str = "wamid.F1", body: str = "hello", message_type: str = "text", media_url: str = "", mime: str = "") -> bytes:  # noqa: A002
    return json.dumps({"webhook_type": "incoming_message", "from": sender, "message_id": id, "message_type": message_type, "body": body, "media_url": media_url, "mime_type": mime}).encode()


def f2s_status(*, id: str = "wamid.F2", status: str = "delivered", recipient: str = NUMBER, error: str = "") -> bytes:  # noqa: A002
    return json.dumps({"webhook_type": "status_update", "status": status, "message_id": id, "recipient_id": recipient, "error_message": error}).encode()


def f2s_headers(secret: str = F2S_SECRET) -> dict[str, str]:
    return {"webhook_secret_key": secret, "Content-Type": "application/json"}


def meta_body(sample: str = "meta_text", *, sender: str = NUMBER, id: str = "wamid.IN1", text: str = "hello", status: str = "delivered") -> bytes:  # noqa: A002
    raw = (DATA / f"{sample}.json").read_text(encoding="utf-8")
    for key, value in {"{FROM}": sender, "{ID}": id, "{STATUS}": status}.items():
        raw = raw.replace(key, value)
    return raw.replace("{TEXT}", text.replace("\\", "\\\\").replace('"', '\\"')).encode()


def meta_signature(body: bytes, secret: str = META_SECRET) -> dict[str, str]:
    return {"X-Hub-Signature-256": "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()}


def meta_request(sample: str = "meta_text", *, secret: str = META_SECRET, **fields) -> tuple[bytes, dict[str, str]]:  # type: ignore[no-untyped-def]
    body = meta_body(sample, **fields)
    return body, meta_signature(body, secret)


def twilio_body(sample: str = "twilio_text", *, sender: str = NUMBER, id: str = "SM1", text: str = "hello", status: str = "delivered", error: str = "") -> bytes:  # noqa: A002
    raw = (DATA / f"{sample}.txt").read_text(encoding="utf-8").strip()
    for key, value in {"{FROM}": sender, "{ID}": id, "{STATUS}": status, "{ERROR}": error, "{TEXT}": urllib.parse.quote(text)}.items():
        raw = raw.replace(key, value)
    return raw.encode()


def twilio_signature(body: bytes, token: str = TWILIO_TOKEN, url: str = WEBHOOK_URL) -> dict[str, str]:
    from mrcourt.services.whatsapp.twilio_sandbox import signature_for

    form = dict(urllib.parse.parse_qsl(body.decode(), keep_blank_values=True))
    return {"X-Twilio-Signature": signature_for(token, url, form)}


def twilio_request(sample: str = "twilio_text", *, token: str = TWILIO_TOKEN, **fields) -> tuple[bytes, dict[str, str]]:  # type: ignore[no-untyped-def]
    body = twilio_body(sample, **fields)
    return body, {**twilio_signature(body, token), "Content-Type": "application/x-www-form-urlencoded"}


def dev_request(*, sender: str = NUMBER, id: str = "dev-1", text: str = "hello", kind: str = "text", media: str | None = None) -> tuple[bytes, dict[str, str]]:  # noqa: A002
    from mrcourt.services.whatsapp.development import SIGNATURE_HEADER, sign

    body = json.dumps({"id": id, "from": sender, "text": text, "kind": kind, "media": media}).encode()
    return body, {SIGNATURE_HEADER: sign(body), "Content-Type": "application/json"}


def dev_report(*, id: str, status: str, reason: str | None = None) -> tuple[bytes, dict[str, str]]:  # noqa: A002
    from mrcourt.services.whatsapp.development import SIGNATURE_HEADER, sign

    body = json.dumps({"report": {"id": id, "status": status, "reason": reason}}).encode()
    return body, {SIGNATURE_HEADER: sign(body), "Content-Type": "application/json"}


class FakeChannel:
    """Records what would be sent. Inbound calls are plain JSON (no signature), so tests can drive the webhook."""

    name = "fake"

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str, object]] = []  # (how, to, kind or text, variables)
        self.fail_with: str | None = None  # a SendError reason for the next sends
        self.audio: bytes | None = b"fake-ogg"
        self.fetched: list[str] = []  # media references asked for
        self._count = 0

    def _next(self) -> str:
        self._count += 1
        return f"fake-{self._count}"

    def send_template(self, to: str, kind: str, variables: list[str]) -> str:
        if self.fail_with:
            raise SendError(self.fail_with)
        self.sent.append(("template", digits(to), kind, list(variables)))
        return self._next()

    def send_text(self, to: str, text: str) -> str:
        if self.fail_with:
            raise SendError(self.fail_with)
        self.sent.append(("text", digits(to), text, None))
        return self._next()

    def verify_and_parse(self, headers, body: bytes, url: str) -> ParsedRequest:  # type: ignore[no-untyped-def]
        data = json.loads(body)
        parsed = ParsedRequest()
        if "report" in data:
            r = data["report"]
            parsed.reports.append(DeliveryReport("fake", r["id"], r["status"], r.get("reason")))
        else:
            parsed.messages.append(
                InboundMessage("fake", data["id"], digits(data["from"]), data.get("kind", "text"), data.get("text", ""), data.get("media"))
            )
        return parsed

    def fetch_audio(self, media_ref: str) -> tuple[bytes, str]:
        self.fetched.append(media_ref)
        if self.audio is None:
            raise SendError("media_unavailable")
        return self.audio, "audio/ogg"

    # What tests usually want to read
    def texts_to(self, number: str) -> list[str]:
        return [what for how, to, what, _ in self.sent if to == digits(number) and how == "text"]

    def templates_to(self, number: str) -> list[tuple[str, list[str]]]:
        return [(kind, vars_) for how, to, kind, vars_ in self.sent if to == digits(number) and how == "template"]  # type: ignore[misc]

    def words_to(self, number: str) -> list[str]:
        """Everything sent to a number as plain words (templates rendered)."""
        words = []
        for how, to, what, vars_ in self.sent:
            if to == digits(number):
                words.append(what if how == "text" else render_template(what, vars_))  # type: ignore[arg-type]
        return words


def verified(db, email: str, phone: str = "9000000001"):  # type: ignore[no-untyped-def]
    """Gives a seeded person a verified phone number (digits only; the country code is added when linking)."""
    from sqlalchemy import select

    from mrcourt.db.base import utcnow
    from mrcourt.models import User

    user = db.scalar(select(User).where(User.email == email))
    user.phone, user.phone_verified_at = phone, utcnow()
    db.commit()
    return user


def linked(db, email: str, *kinds: str, phone: str = "9000000001"):  # type: ignore[no-untyped-def]
    """A person with a verified, linked number who has switched the given kinds on."""
    from mrcourt.services.whatsapp import consent

    user = verified(db, email, phone)
    consent.link(db, user)
    for kind in kinds:
        consent.set_consent(db, user, kind, True)
    db.commit()
    return user


def send(client, *, sender: str = NUMBER, text: str = "hello", id: str = "m1", kind: str = "text", media: str | None = None) -> None:  # noqa: A002
    """A message arriving at the webhook through the fake channel (plain JSON, handled before the call returns)."""
    body = json.dumps({"id": id, "from": sender, "text": text, "kind": kind, "media": media}).encode()
    response = client.post(WEBHOOK_PATH, content=body)
    assert response.status_code == 200, response.text
