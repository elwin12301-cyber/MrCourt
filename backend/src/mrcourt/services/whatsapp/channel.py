"""The WhatsApp channel behind a small provider-neutral interface (feature 010).

A channel can send a template message, send a free-text reply (only inside the 24-hour window the provider
allows after the person last wrote), check and read the provider's webhook calls, and fetch a voice note.
Adapters: Meta's WhatsApp Business interface (production), the Twilio sandbox (free testing) and a development
channel that keeps messages on the development outbox. Message text and phone numbers are never logged.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from mrcourt.config import get_settings

WINDOW_HOURS = 24  # free-text replies are allowed this long after the person's last message

KINDS = ("code", "reminder", "update", "activity")

# What each template says. Meta needs the same words approved in its console; the sandbox and development
# channels, and the SMS fallback, send this text directly. {0}, {1} are the variables in order.
TEMPLATE_TEXT = {
    "code": "Your MrCourt code is {0}. Do not share it with anyone.",
    "reminder": "Announcement from MrCourt: your hearing in {0} is {1}.",
    "update": "MrCourt: there is a new update on {0}. Open MrCourt to read it.",
    "activity": "MrCourt: your client sent a message about {0}. Open MrCourt to read it.",
}


def render_template(kind: str, variables: list[str]) -> str:
    """The words of a template message with its variables filled in."""
    return TEMPLATE_TEXT[kind].format(*variables)


def template_name(kind: str) -> str:
    """The template's name in the provider's console, from settings."""
    return getattr(get_settings(), f"whatsapp_template_{kind}")


class SendError(Exception):
    """A message could not be sent. `reason` is a short plain code safe to store and show."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class SignatureError(Exception):
    """A webhook call is not genuinely from the provider."""


@dataclass(frozen=True)
class DeliveryReport:
    provider: str
    provider_message_id: str
    status: str  # sent | delivered | read | failed
    reason: str | None = None  # plain code when failed, for example not_on_whatsapp
    recipient: str | None = None  # the number it went to (digits), for providers whose report may not carry our message id


@dataclass(frozen=True)
class InboundMessage:
    provider: str
    provider_message_id: str
    sender: str  # digits with country code, for example 919000000001
    kind: str  # text | audio | other
    text: str = ""
    media_ref: str | None = None  # Meta media id or Twilio media address
    media_type: str | None = None


@dataclass
class ParsedRequest:
    messages: list[InboundMessage] = field(default_factory=list)
    reports: list[DeliveryReport] = field(default_factory=list)


class WhatsAppChannel(Protocol):
    name: str

    def send_template(self, to: str, kind: str, variables: list[str]) -> str:
        """Sends a template message; returns the provider's message id. Raises SendError."""
        ...

    def send_text(self, to: str, text: str) -> str:
        """Sends a free-text reply (inside the 24-hour window). Returns the provider's message id."""
        ...

    def verify_and_parse(self, headers: Mapping[str, str], body: bytes, url: str) -> ParsedRequest:
        """Checks the provider's signature on the raw body, then reads it. Raises SignatureError."""
        ...

    def fetch_audio(self, media_ref: str) -> tuple[bytes, str]:
        """The bytes and mime type of a voice note. Raises SendError when it cannot be fetched."""
        ...


def digits(number: str) -> str:
    """A phone number as digits only (no plus sign, spaces or the whatsapp: prefix)."""
    return re.sub(r"\D", "", number or "")


_override: WhatsAppChannel | None = None


def set_channel(channel: WhatsAppChannel | None) -> None:
    """Test hook: replace the channel."""
    global _override
    _override = channel


def provider_name() -> str:
    name = (get_settings().whatsapp_provider or "none").strip().lower()
    return name if name in ("meta", "twilio", "fast2sms") else "none"


def is_configured() -> bool:
    """True when a real provider is set up (Settings shows WhatsApp as available)."""
    return _override is not None or provider_name() != "none"


def get_channel() -> WhatsAppChannel:
    if _override is not None:
        return _override
    name = provider_name()
    if name == "meta":
        from mrcourt.services.whatsapp.meta import MetaChannel

        return MetaChannel()
    if name == "twilio":
        from mrcourt.services.whatsapp.twilio_sandbox import TwilioChannel

        return TwilioChannel()
    if name == "fast2sms":
        from mrcourt.services.whatsapp.fast2sms import Fast2SmsChannel

        return Fast2SmsChannel()
    from mrcourt.services.whatsapp.development import DevelopmentChannel

    return DevelopmentChannel()
