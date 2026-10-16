"""Meta's WhatsApp Business (Cloud API) adapter: the production target.

NOT TESTED against the live service (it needs a verified business account and approved templates; see
specs/010-whatsapp-channel/research.md). Tests use sample payloads and a fake HTTP transport. Check the API
version and error codes against Meta's current documentation before launch.
"""

import hashlib
import hmac
import json
import logging
from collections.abc import Mapping

import httpx

from mrcourt.config import get_settings
from mrcourt.services.whatsapp.channel import (
    DeliveryReport,
    InboundMessage,
    ParsedRequest,
    SendError,
    SignatureError,
    digits,
    template_name,
)

logger = logging.getLogger(__name__)

GRAPH = "https://graph.facebook.com/v21.0"
MAX_AUDIO_BYTES = 10 * 1024 * 1024

# Meta error codes mapped to short plain reasons that are safe to store and show.
REASONS = {
    131026: "not_on_whatsapp",  # message undeliverable (the number has no WhatsApp account)
    131047: "window_closed",  # a free-text reply outside the 24-hour window
    131049: "not_delivered",  # blocked by WhatsApp's healthy-ecosystem engagement rules
    132000: "template_missing",
    132001: "template_missing",
    132005: "template_missing",
    132012: "template_missing",
    131008: "bad_request",
    131009: "bad_request",
}


def reason_for(code: object) -> str:
    try:
        return REASONS.get(int(code), "provider_error")  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return "provider_error"


def verify_challenge(mode: str | None, token: str | None) -> bool:
    """Meta's one-time webhook setup call: answer only when the token matches the one we hold."""
    expected = get_settings().whatsapp_verify_token
    return bool(expected) and mode == "subscribe" and token is not None and hmac.compare_digest(token, expected)


class MetaChannel:
    name = "meta"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client

    def _http(self) -> httpx.Client:
        return self._client or httpx.Client(timeout=httpx.Timeout(15, connect=8))

    def _post(self, payload: dict) -> str:  # type: ignore[type-arg]
        s = get_settings()
        if not (s.whatsapp_phone_number_id and s.whatsapp_access_token):
            raise SendError("not_configured")
        try:
            response = self._http().post(
                f"{GRAPH}/{s.whatsapp_phone_number_id}/messages",
                headers={"Authorization": f"Bearer {s.whatsapp_access_token}"},
                json=payload,
            )
        except httpx.HTTPError as error:
            raise SendError("provider_down") from error
        if response.status_code >= 400:
            try:
                code = response.json().get("error", {}).get("code")
            except ValueError:
                code = None
            raise SendError(reason_for(code) if code is not None else ("provider_down" if response.status_code >= 500 else "provider_error"))
        try:
            return str(response.json()["messages"][0]["id"])
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise SendError("provider_error") from error

    def send_template(self, to: str, kind: str, variables: list[str]) -> str:
        components: list[dict] = [  # type: ignore[type-arg]
            {"type": "body", "parameters": [{"type": "text", "text": v} for v in variables]}
        ]
        if kind == "code" and variables:  # an authentication template also carries the code on its copy button
            components.append(
                {"type": "button", "sub_type": "url", "index": "0", "parameters": [{"type": "text", "text": variables[0]}]}
            )
        return self._post(
            {
                "messaging_product": "whatsapp",
                "to": digits(to),
                "type": "template",
                "template": {"name": template_name(kind), "language": {"code": "en"}, "components": components},
            }
        )

    def send_text(self, to: str, text: str) -> str:
        return self._post({"messaging_product": "whatsapp", "to": digits(to), "type": "text", "text": {"body": text}})

    def verify_and_parse(self, headers: Mapping[str, str], body: bytes, url: str) -> ParsedRequest:
        secret = get_settings().whatsapp_app_secret
        given = {k.lower(): v for k, v in headers.items()}.get("x-hub-signature-256", "")
        if not secret or not given.startswith("sha256="):
            raise SignatureError("missing signature")
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(given.removeprefix("sha256="), expected):
            raise SignatureError("bad signature")
        try:
            data = json.loads(body)
        except ValueError as error:
            raise SignatureError("unreadable body") from error
        parsed = ParsedRequest()
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for item in value.get("messages", []):
                    kind = item.get("type")
                    if kind == "text":
                        parsed.messages.append(
                            InboundMessage("meta", item["id"], digits(item["from"]), "text", str(item.get("text", {}).get("body", "")))
                        )
                    elif kind == "audio":
                        audio = item.get("audio", {})
                        parsed.messages.append(
                            InboundMessage("meta", item["id"], digits(item["from"]), "audio", media_ref=audio.get("id"), media_type=audio.get("mime_type"))
                        )
                    else:
                        parsed.messages.append(InboundMessage("meta", item["id"], digits(item["from"]), "other"))
                for status in value.get("statuses", []):
                    if status.get("status") not in ("sent", "delivered", "read", "failed"):
                        continue
                    reason = None
                    if status["status"] == "failed":
                        errors = status.get("errors") or [{}]
                        reason = reason_for(errors[0].get("code"))
                    parsed.reports.append(DeliveryReport("meta", status["id"], status["status"], reason))
        return parsed

    def fetch_audio(self, media_ref: str) -> tuple[bytes, str]:
        token = get_settings().whatsapp_access_token
        headers = {"Authorization": f"Bearer {token}"}
        try:
            http = self._http()
            meta = http.get(f"{GRAPH}/{media_ref}", headers=headers)
            meta.raise_for_status()
            info = meta.json()
            audio = http.get(info["url"], headers=headers)
            audio.raise_for_status()
        except (httpx.HTTPError, ValueError, KeyError) as error:
            raise SendError("media_unavailable") from error
        if len(audio.content) > MAX_AUDIO_BYTES:
            raise SendError("media_too_large")
        return audio.content, str(info.get("mime_type", "audio/ogg"))
