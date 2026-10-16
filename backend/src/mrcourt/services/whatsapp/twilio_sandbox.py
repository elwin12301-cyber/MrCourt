"""Twilio's WhatsApp sandbox adapter: free testing.

A person receives messages only after sending the sandbox's join phrase from their own WhatsApp, and the join
lapses after a few days. The sandbox needs no approved templates, so template messages are sent as the plain text
of the template. NOT TESTED against the live service; tests use sample payloads and a fake HTTP transport.
"""

import base64
import hashlib
import hmac
import logging
from collections.abc import Mapping
from urllib.parse import parse_qsl

import httpx

from mrcourt.config import get_settings
from mrcourt.services.whatsapp.channel import (
    DeliveryReport,
    InboundMessage,
    ParsedRequest,
    SendError,
    SignatureError,
    digits,
    render_template,
)

logger = logging.getLogger(__name__)

MAX_AUDIO_BYTES = 10 * 1024 * 1024

# Twilio error codes mapped to short plain reasons that are safe to store and show.
REASONS = {
    63015: "not_on_whatsapp",  # the number has not joined the sandbox
    63016: "window_closed",  # a free-text message outside the 24-hour window
    63018: "rate_limited",
    21211: "bad_number",
    21614: "not_on_whatsapp",
}

STATUSES = {"sent": "sent", "delivered": "delivered", "read": "read", "failed": "failed", "undelivered": "failed"}


def reason_for(code: object) -> str:
    try:
        return REASONS.get(int(code), "provider_error")  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return "provider_error"


def signature_for(token: str, url: str, params: Mapping[str, str]) -> str:
    """Twilio's signature: HMAC-SHA1 over the full URL followed by each field name and value, sorted by name."""
    payload = url + "".join(f"{key}{params[key]}" for key in sorted(params))
    return base64.b64encode(hmac.new(token.encode(), payload.encode(), hashlib.sha1).digest()).decode()


class TwilioChannel:
    name = "twilio"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client

    def _http(self) -> httpx.Client:
        return self._client or httpx.Client(timeout=httpx.Timeout(15, connect=8), follow_redirects=True)

    def _login(self) -> tuple[str, str]:
        s = get_settings()
        if s.twilio_api_key_sid and s.twilio_api_key_secret:
            return s.twilio_api_key_sid, s.twilio_api_key_secret
        return s.twilio_account_sid, s.twilio_auth_token

    def _post(self, to: str, body: str) -> str:
        s = get_settings()
        if not (s.twilio_account_sid and s.twilio_whatsapp_from and all(self._login())):
            raise SendError("not_configured")
        try:
            response = self._http().post(
                f"https://api.twilio.com/2010-04-01/Accounts/{s.twilio_account_sid}/Messages.json",
                auth=self._login(),
                data={"To": f"whatsapp:+{digits(to)}", "From": s.twilio_whatsapp_from, "Body": body},
            )
        except httpx.HTTPError as error:
            raise SendError("provider_down") from error
        if response.status_code >= 400:
            try:
                code = response.json().get("code")
            except ValueError:
                code = None
            raise SendError(reason_for(code) if code is not None else ("provider_down" if response.status_code >= 500 else "provider_error"))
        try:
            return str(response.json()["sid"])
        except (ValueError, KeyError) as error:
            raise SendError("provider_error") from error

    def send_template(self, to: str, kind: str, variables: list[str]) -> str:
        return self._post(to, render_template(kind, variables))

    def send_text(self, to: str, text: str) -> str:
        return self._post(to, text)

    def verify_and_parse(self, headers: Mapping[str, str], body: bytes, url: str) -> ParsedRequest:
        token = get_settings().twilio_auth_token
        given = {k.lower(): v for k, v in headers.items()}.get("x-twilio-signature", "")
        if not token or not given:
            raise SignatureError("missing signature")
        try:
            form = dict(parse_qsl(body.decode(), keep_blank_values=True))
        except UnicodeDecodeError as error:
            raise SignatureError("unreadable body") from error
        if not hmac.compare_digest(given, signature_for(token, url, form)):
            raise SignatureError("bad signature")
        parsed = ParsedRequest()
        sid = form.get("MessageSid", "")
        status = form.get("MessageStatus")
        if status and form.get("SmsStatus") != "received":
            if status in STATUSES and sid:
                failed = STATUSES[status] == "failed"
                parsed.reports.append(
                    DeliveryReport("twilio", sid, STATUSES[status], reason_for(form.get("ErrorCode")) if failed else None)
                )
            return parsed
        if sid and form.get("From"):
            media = int(form.get("NumMedia", "0") or 0)
            media_type = form.get("MediaContentType0", "")
            if media and media_type.startswith("audio"):
                parsed.messages.append(
                    InboundMessage("twilio", sid, digits(form["From"]), "audio", media_ref=form.get("MediaUrl0"), media_type=media_type)
                )
            elif media:
                parsed.messages.append(InboundMessage("twilio", sid, digits(form["From"]), "other"))
            else:
                parsed.messages.append(InboundMessage("twilio", sid, digits(form["From"]), "text", form.get("Body", "")))
        return parsed

    def fetch_audio(self, media_ref: str) -> tuple[bytes, str]:
        if not media_ref.startswith("https://api.twilio.com/"):
            raise SendError("media_unavailable")  # only Twilio's own media address is ever fetched, with our login
        try:
            response = self._http().get(media_ref, auth=self._login())
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise SendError("media_unavailable") from error
        if len(response.content) > MAX_AUDIO_BYTES:
            raise SendError("media_too_large")
        return response.content, response.headers.get("content-type", "audio/ogg")
