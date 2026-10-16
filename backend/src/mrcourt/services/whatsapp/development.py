"""The development WhatsApp channel: nothing leaves the computer.

Sent messages go to the development outbox (read them on the Development messages page). Incoming calls are
signed with a development secret so that the webhook is protected even without a provider; the script
`scripts/whatsapp_dev_send.py` signs and sends them.
"""

import hashlib
import hmac
import json
import logging
import uuid
from collections.abc import Mapping

from mrcourt.config import get_settings
from mrcourt.services import notify
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

SIGNATURE_HEADER = "x-mrcourt-dev-signature"


def dev_secret() -> bytes:
    settings = get_settings()
    secret = settings.session_secret
    if not secret:
        if settings.environment == "production":
            raise SignatureError("no development secret in production")
        secret = "dev-only-insecure-secret"
    return secret.encode()


def sign(body: bytes) -> str:
    return hmac.new(dev_secret(), body, hashlib.sha256).hexdigest()


class DevelopmentChannel:
    name = "development"

    def _keep(self, to: str, text: str, kind: str, code: str | None = None) -> str:
        notify.OUTBOX.append(notify.Message(contact=to, text=text, code=code, kind=kind, channel="whatsapp"))
        del notify.OUTBOX[:-200]
        logger.info("WhatsApp message kept on the development outbox")
        return f"dev-{uuid.uuid4().hex[:16]}"

    def send_template(self, to: str, kind: str, variables: list[str]) -> str:
        return self._keep(to, render_template(kind, variables), kind, variables[0] if kind == "code" and variables else None)

    def send_text(self, to: str, text: str) -> str:
        return self._keep(to, text, "reply")

    def verify_and_parse(self, headers: Mapping[str, str], body: bytes, url: str) -> ParsedRequest:
        given = {k.lower(): v for k, v in headers.items()}.get(SIGNATURE_HEADER, "")
        try:
            expected = sign(body)
        except SignatureError:
            raise
        if not given or not hmac.compare_digest(given, expected):
            raise SignatureError("bad development signature")
        try:
            data = json.loads(body)
        except ValueError as error:
            raise SignatureError("unreadable body") from error
        parsed = ParsedRequest()
        if "report" in data:
            report = data["report"]
            parsed.reports.append(
                DeliveryReport("development", str(report["id"]), str(report["status"]), report.get("reason"))
            )
        else:
            parsed.messages.append(
                InboundMessage(
                    provider="development",
                    provider_message_id=str(data["id"]),
                    sender=digits(str(data["from"])),
                    kind=str(data.get("kind", "text")),
                    text=str(data.get("text", "")),
                    media_ref=data.get("media"),
                    media_type=data.get("media_type"),
                )
            )
        return parsed

    def fetch_audio(self, media_ref: str) -> tuple[bytes, str]:
        raise SendError("not_supported")
