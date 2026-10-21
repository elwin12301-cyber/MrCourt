"""Fast2SMS WhatsApp adapter (an Indian provider; feature 010).

Built from Fast2SMS's published guides, NOT TESTED against the live service. Things only a live test can settle are
marked "verify live" below. It needs, from the Fast2SMS panel: the connected number's id, the ids of four approved
templates, and a WhatsApp webhook (see the README for the payload to paste in).

Sending a template: `GET /dev/whatsapp` (template id, number id, recipient, values joined by "|").
Replying inside a conversation the person started: `POST /dev/whatsapp-session`.
Receiving: Fast2SMS posts `incoming_message` and `status_update` events to our webhook. Those requests are NOT signed;
they carry a fixed secret in the `webhook_secret_key` header, which is compared in constant time. That is weaker than
Meta's or Twilio's signature (anyone who learns the secret can forge a call), so keep the secret out of logs and rotate it
if it leaks.
"""

import hmac
import json
import logging
import uuid
from collections.abc import Mapping
from urllib.parse import parse_qsl, urlparse

import httpx

from mrcourt.config import get_settings
from mrcourt.services.whatsapp.channel import (
    DeliveryReport,
    InboundMessage,
    ParsedRequest,
    SendError,
    SignatureError,
    digits,
)

logger = logging.getLogger(__name__)

TEMPLATE_URL = "https://www.fast2sms.com/dev/whatsapp"
SESSION_URL = "https://www.fast2sms.com/dev/whatsapp-session"
SECRET_HEADERS = ("webhook_secret_key", "webhook-secret-key")  # a proxy may turn underscores into dashes
MAX_AUDIO_BYTES = 10 * 1024 * 1024

# Delivery words as Fast2SMS may write them (verify live); anything else is ignored.
STATUS_WORDS = {
    "sent": "sent", "submitted": "sent", "accepted": "sent",
    "delivered": "delivered",
    "read": "read", "seen": "read",
    "failed": "failed", "undelivered": "failed", "rejected": "failed", "error": "failed",
}
AUDIO_TYPES = ("audio", "voice", "ptt")


def reason_for(text: object) -> str:
    """A short plain reason from whatever Fast2SMS says went wrong."""
    words = str(text or "").lower()
    if "131049" in words or "healthy ecosystem" in words:
        return "not_delivered"  # Meta held the message back (seen live for a marketing template to a new contact)
    if "template" in words:
        return "template_missing"
    if "whatsapp" in words and ("not" in words or "no " in words or "invalid" in words):
        return "not_on_whatsapp"
    return "provider_error"  # including an empty wallet: the person sees only that it was refused


def _national(number: str) -> str:
    """Ten digits for an Indian number (Fast2SMS's template call takes the number without the country code)."""
    cleaned = digits(number)
    return cleaned[-10:] if cleaned.startswith("91") and len(cleaned) == 12 else cleaned


class Fast2SmsChannel:
    name = "fast2sms"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client

    def _http(self) -> httpx.Client:
        return self._client or httpx.Client(timeout=httpx.Timeout(15, connect=8))

    @staticmethod
    def _template_id(kind: str) -> str:
        return str(getattr(get_settings(), f"fast2sms_whatsapp_template_{kind}", "") or "")

    def _headers(self) -> dict[str, str]:
        return {"authorization": get_settings().fast2sms_api_key}  # the raw key, no "Bearer"

    def send_template(self, to: str, kind: str, variables: list[str]) -> str:
        s = get_settings()
        template = self._template_id(kind)
        if not (s.fast2sms_api_key and template):
            raise SendError("not_configured")
        values = "|".join(str(v).replace("|", "/") for v in variables)  # a pipe in a case title cannot split the values
        params = {"message_id": template, "numbers": _national(to), "variables_values": values}
        if s.fast2sms_whatsapp_phone_number_id:
            # Optional for templates: Fast2SMS looked the template up first when it was left out (verify live).
            params["phone_number_id"] = s.fast2sms_whatsapp_phone_number_id
        try:
            response = self._http().get(TEMPLATE_URL, params=params, headers=self._headers())
        except httpx.HTTPError as error:
            raise SendError("provider_down") from error
        body = _json(response)
        if response.status_code >= 500:
            raise SendError("provider_down")
        if response.status_code >= 400 or not (body.get("return") is True or body.get("status") in (True, "success")):
            raise SendError(reason_for(body.get("message")))
        # The request id is what Fast2SMS says traces a message in its reports (verify live that reports carry it).
        return str(body.get("request_id") or body.get("message_id") or f"f2s-{uuid.uuid4().hex[:16]}")

    def send_text(self, to: str, text: str) -> str:
        s = get_settings()
        if not (s.fast2sms_api_key and s.fast2sms_whatsapp_phone_number_id):
            raise SendError("not_configured")
        try:
            response = self._http().post(
                SESSION_URL,
                params={"phone_number_id": s.fast2sms_whatsapp_phone_number_id, "to": digits(to)},
                headers={**self._headers(), "Content-Type": "application/json"},
                json={"type": "text", "text": text},
            )
        except httpx.HTTPError as error:
            raise SendError("provider_down") from error
        body = _json(response)
        if response.status_code >= 500:
            raise SendError("provider_down")
        if response.status_code >= 400 or body.get("status") not in ("success", True):
            raise SendError(reason_for(body.get("message")))
        return f"session-{uuid.uuid4().hex[:16]}"  # the reply is accepted without an id we could follow

    def verify_and_parse(self, headers: Mapping[str, str], body: bytes, url: str) -> ParsedRequest:
        secret = get_settings().fast2sms_webhook_secret
        lowered = {k.lower(): v for k, v in headers.items()}
        given = next((lowered[h] for h in SECRET_HEADERS if lowered.get(h)), "")
        if not secret or not given or not hmac.compare_digest(given.encode(), secret.encode()):
            raise SignatureError("bad secret")
        events = _events(body)
        parsed = ParsedRequest()
        for event in events:
            kind = str(event.get("webhook_type", "")).lower()
            if kind == "incoming_message":
                sender, message_id = digits(str(event.get("from", ""))), str(event.get("message_id") or "")
                if not sender or not message_id:
                    continue
                message_type = str(event.get("message_type") or "text").lower()
                if message_type == "text":
                    parsed.messages.append(InboundMessage("fast2sms", message_id, sender, "text", str(event.get("body") or "")))
                elif message_type in AUDIO_TYPES:
                    parsed.messages.append(
                        InboundMessage("fast2sms", message_id, sender, "audio", media_ref=str(event.get("media_url") or "") or None, media_type=str(event.get("mime_type") or "") or None)
                    )
                else:
                    parsed.messages.append(InboundMessage("fast2sms", message_id, sender, "other"))
            elif kind == "status_update":
                state = STATUS_WORDS.get(str(event.get("status", "")).lower())
                # `fast2sms_request_id` is the id our send call returned; `request_id` is WhatsApp's own (wamid) one.
                message_id = str(event.get("fast2sms_request_id") or event.get("message_id") or event.get("request_id") or "")
                if state is None or not message_id:
                    continue
                reason = reason_for(event.get("error_message") or event.get("status_description")) if state == "failed" else None
                parsed.reports.append(DeliveryReport("fast2sms", message_id, state, reason, recipient=digits(str(event.get("recipient_id") or "")) or None))
        return parsed

    def fetch_report(self, request_id: str) -> DeliveryReport | None:
        """Asks Fast2SMS what became of one template message (`GET /dev/whatsapp/<id>`), for hosts where its delivery
        webhook cannot reach us. None when it knows nothing yet or says something we do not map."""
        if not request_id or not all(c.isalnum() or c in "-_." for c in request_id):
            return None  # the id goes into the address, so only plain characters are used
        try:
            response = self._http().get(f"{TEMPLATE_URL}/{request_id}", headers=self._headers())
        except httpx.HTTPError:
            return None
        events = _json(response).get("data")
        if response.status_code >= 400 or not isinstance(events, list) or not events or not isinstance(events[-1], dict):
            return None
        event = events[-1]
        state = STATUS_WORDS.get(str(event.get("status", "")).lower())
        if state is None:
            return None
        reason = reason_for(event.get("status_description")) if state == "failed" else None
        return DeliveryReport("fast2sms", request_id, state, reason, recipient=digits(str(event.get("recipient_id") or event.get("mobile") or "")) or None)

    def fetch_audio(self, media_ref: str) -> tuple[bytes, str]:
        host = (urlparse(media_ref).hostname or "").lower()
        if not media_ref.startswith("https://") or not (host == "fast2sms.com" or host.endswith(".fast2sms.com")):
            # Our login is never sent to another address, and a forged webhook cannot make us fetch an arbitrary one.
            raise SendError("media_unavailable")
        try:
            response = self._http().get(media_ref, headers=self._headers())
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise SendError("media_unavailable") from error
        if len(response.content) > MAX_AUDIO_BYTES:
            raise SendError("media_too_large")
        return response.content, response.headers.get("content-type", "audio/ogg")


def _json(response: httpx.Response) -> dict:  # type: ignore[type-arg]
    try:
        data = response.json()
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}


def _events(body: bytes) -> list[dict]:  # type: ignore[type-arg]
    """The events in a webhook body: JSON (one object or a list) or form fields. Unreadable means nothing to do."""
    try:
        data = json.loads(body)
    except ValueError:
        try:
            return [dict(parse_qsl(body.decode(), keep_blank_values=True))]
        except UnicodeDecodeError:
            return []
    if isinstance(data, dict):
        return [data]
    return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []
