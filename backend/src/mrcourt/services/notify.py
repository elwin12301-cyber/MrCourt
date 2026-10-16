"""Outbound text messages (SMS) behind a provider interface: one-time codes and hearing reminders.

Adapters: Twilio (SMS), Fast2SMS (Indian SMS), and a development adapter that keeps messages in memory so they can
be read on the development messages page. WhatsApp is a separate channel (services/whatsapp) with delivery status
and consent; this module is only the text-message sender, also used as the fallback when WhatsApp fails. Message
text and phone numbers are never written to the logs.
"""

import json
import logging
import re
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from mrcourt.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class Message:
    contact: str
    text: str
    code: str | None = None  # populated for one-time passcodes so tests can read them
    kind: str = "code"  # "code" for one-time codes, "reminder" for hearing reminders
    variables: dict[str, str] = field(default_factory=dict)  # template fields for SMS providers
    channel: str = "sms"  # "whatsapp" for messages the development WhatsApp channel keeps here
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class Notifier(Protocol):
    def send(self, message: Message) -> None: ...


def to_msisdn(contact: str, country_code: str = "91") -> str | None:
    """A phone number as digits with its country code (what SMS providers want), or None."""
    digits = re.sub(r"\D", "", contact or "")
    if len(digits) == 10:
        return f"{country_code}{digits}"
    if 11 <= len(digits) <= 15:
        return digits.removeprefix("00") if digits.startswith("00") else digits
    return None


# Development/test outbox. Never populated by a real provider.
OUTBOX: list[Message] = []


class ConsoleNotifier:
    """Keeps messages in memory (read them on the development messages page); delivers nothing."""

    def send(self, message: Message) -> None:
        OUTBOX.append(message)
        del OUTBOX[:-200]
        logger.info("Message queued for delivery (development adapter)")


class TwilioNotifier:
    """Twilio SMS. A free trial account can text only numbers verified in the Twilio console. NOT TESTED against the
    live service (no account keys were available when this was written)."""

    def __init__(
        self, sid: str, token: str, sms_from: str, country_code: str = "91", api_key: tuple[str, str] | None = None
    ) -> None:
        # The account SID (AC...) is always in the address; the login is the auth token or an API key (SK..., secret).
        self.sid, self.token = sid, token
        self.login = api_key if api_key else (sid, token)
        self.sms_from = sms_from
        self.country_code = country_code
        self.url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"

    def _post(self, to: str, sender: str, body: str) -> None:
        import base64
        import urllib.parse

        data = urllib.parse.urlencode({"To": to, "From": sender, "Body": body}).encode()
        auth = base64.b64encode(f"{self.login[0]}:{self.login[1]}".encode()).decode()
        request = urllib.request.Request(
            self.url, data=data, headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"}
        )
        with urllib.request.urlopen(request, timeout=10):  # noqa: S310 - fixed https URL
            pass

    def send(self, message: Message) -> None:
        mobile = to_msisdn(message.contact, self.country_code)
        if mobile is None:
            logger.warning("Message not sent: no usable phone number")
            return
        self._post(f"+{mobile}", self.sms_from, message.text)
        logger.info("Message handed to the text-message provider")


class Fast2SmsNotifier:
    """Fast2SMS (an Indian SMS service). Texts go by its Quick SMS route (works on a funded account); codes can use its OTP route once the
    account has passed Fast2SMS website verification (otp_route=True).

    NOT TESTED against the live service. The account needs wallet balance, and Indian rules about
    registered senders and templates may still apply to the route used.
    """

    URL = "https://www.fast2sms.com/dev/bulkV2"

    def __init__(self, api_key: str, country_code: str = "91", otp_route: bool = False) -> None:
        self.api_key = api_key
        self.otp_route = otp_route
        self.country_code = country_code

    def send(self, message: Message) -> None:
        mobile = to_msisdn(message.contact, self.country_code)
        if mobile is None:
            logger.warning("Message not sent: no usable phone number")
            return
        number = mobile[-10:] if mobile.startswith("91") else mobile
        if self.otp_route and message.kind == "code" and message.code and message.code.isdigit():
            fields = {"route": "otp", "variables_values": message.code, "numbers": number}
        else:
            fields = {"route": "q", "message": message.text, "numbers": number, "flash": "0"}
        request = urllib.request.Request(
            self.URL,
            data=json.dumps(fields).encode(),
            headers={"authorization": self.api_key, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 - fixed https URL
            body = json.loads(response.read() or b"{}")
        if body.get("return") is not True:
            raise RuntimeError("The message could not be delivered")
        logger.info("Message handed to the text-message provider")


_notifier: Notifier | None = None


def configure() -> Notifier:
    """Chooses the text-message sender from the environment: Twilio, else Fast2SMS, else the development outbox."""
    s = get_settings()
    api_key = (s.twilio_api_key_sid, s.twilio_api_key_secret) if s.twilio_api_key_sid and s.twilio_api_key_secret else None
    if s.twilio_account_sid and (s.twilio_auth_token or api_key) and s.twilio_sms_from:
        return TwilioNotifier(s.twilio_account_sid, s.twilio_auth_token, s.twilio_sms_from, s.sms_country_code, api_key)
    if s.fast2sms_api_key:
        return Fast2SmsNotifier(s.fast2sms_api_key, s.sms_country_code, s.fast2sms_otp_route)
    return ConsoleNotifier()


def get_notifier() -> Notifier:
    global _notifier
    if _notifier is None:
        _notifier = configure()
    return _notifier


def set_notifier(notifier: Notifier | None) -> None:
    """Replaces the sender (tests); None goes back to choosing from the environment."""
    global _notifier
    _notifier = notifier


def delivers_for_real() -> bool:
    """False when messages only go to the development outbox."""
    return not isinstance(get_notifier(), ConsoleNotifier)
