"""Outbound text messages (one-time codes and hearing reminders) behind a provider interface.

Adapters: Twilio (SMS and the free WhatsApp sandbox), Fast2SMS (Indian SMS), WhatsApp Cloud (reminders), and a development adapter that keeps
messages in memory so they can be read on the development messages page. Message text and phone
numbers are never written to the logs.
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
    """Twilio, for SMS and for WhatsApp (including the free WhatsApp sandbox).

    Each message goes out on every channel that is set up. Sandbox rules: a person receives
    WhatsApp only after sending the sandbox's join phrase from their phone, and a free trial
    account can text only numbers verified in the Twilio console. NOT TESTED against the live
    service (no account keys were available when this was written).
    """

    def __init__(
        self, sid: str, token: str, sms_from: str, whatsapp_from: str, country_code: str = "91", api_key: tuple[str, str] | None = None
    ) -> None:
        # The account SID (AC...) is always in the address; the login is the auth token or an API key (SK..., secret).
        self.sid, self.token = sid, token
        self.login = api_key if api_key else (sid, token)
        self.sms_from, self.whatsapp_from = sms_from, whatsapp_from
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
        number = f"+{mobile}"
        channels = []
        if self.sms_from:
            channels.append(("sms", number, self.sms_from))
        if self.whatsapp_from:
            channels.append(("whatsapp", f"whatsapp:{number}", self.whatsapp_from))
        delivered = 0
        for name, to, sender in channels:
            try:
                self._post(to, sender, message.text)
                delivered += 1
            except Exception:  # noqa: BLE001 - one channel failing must not stop the other
                logger.warning("Message not delivered on %s", name)
        if channels and delivered == 0:
            raise RuntimeError("The message could not be delivered on any channel")
        logger.info("Message handed to the text-message provider on %d channel(s)", delivered)


class Fast2SmsNotifier:
    """Fast2SMS (an Indian SMS service). Texts go by its Quick SMS route (works on a funded account); codes can use its OTP route once the
    account has passed Fast2SMS website verification (otp_route=True).

    NOT TESTED against the live service. The account needs wallet balance, and Indian rules about
    registered senders and templates may still apply to the route used.
    """

    URL = "https://www.fast2sms.com/dev/bulkV2"

    WHATSAPP_URL = "https://www.fast2sms.com/dev/whatsapp"

    def __init__(
        self,
        api_key: str,
        country_code: str = "91",
        otp_route: bool = False,
        whatsapp: tuple[str, str, str] | None = None,  # (phone number id, code template id, reminder template id)
    ) -> None:
        self.api_key = api_key
        self.otp_route = otp_route
        self.whatsapp = whatsapp
        self.country_code = country_code

    def send(self, message: Message) -> None:
        mobile = to_msisdn(message.contact, self.country_code)
        if mobile is None:
            logger.warning("Message not sent: no usable phone number")
            return
        number = mobile[-10:] if mobile.startswith("91") else mobile
        delivered, tried = 0, 0
        tried += 1
        try:
            self._sms(message, number)
            delivered += 1
        except Exception:  # noqa: BLE001 - one channel failing must not stop the other
            logger.warning("Message not delivered by SMS")
        values = self._whatsapp_values(message)
        if self.whatsapp and values:
            tried += 1
            try:
                self._whatsapp(number, *values)
                delivered += 1
            except Exception:  # noqa: BLE001
                logger.warning("Message not delivered on WhatsApp")
        if delivered == 0:
            raise RuntimeError("The message could not be delivered on any channel")
        logger.info("Message handed to the text-message provider on %d of %d channel(s)", delivered, tried)

    def _sms(self, message: Message, number: str) -> None:
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

    def _whatsapp_values(self, message: Message) -> tuple[str, str] | None:
        """(template id, values) for this message, or None when no template is set up for it."""
        if not self.whatsapp:
            return None
        _, code_template, reminder_template = self.whatsapp
        clean = lambda text: str(text).replace("|", "/")  # noqa: E731 - the pipe separates the template values
        if message.kind == "code" and message.code and code_template:
            return code_template, clean(message.code)
        if message.kind == "reminder" and reminder_template and {"case", "when"} <= message.variables.keys():
            return reminder_template, f"{clean(message.variables['case'])}|{clean(message.variables['when'])}"
        return None

    def _whatsapp(self, number: str, template_id: str, values: str) -> None:
        import urllib.parse

        assert self.whatsapp is not None
        query = urllib.parse.urlencode(
            {"message_id": template_id, "phone_number_id": self.whatsapp[0], "numbers": number, "variables_values": values}
        )
        request = urllib.request.Request(f"{self.WHATSAPP_URL}?{query}", headers={"authorization": self.api_key})
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 - fixed https URL
            body = json.loads(response.read() or b"{}")
        if body.get("return") is not True and body.get("status") is not True:
            raise RuntimeError("The WhatsApp message could not be delivered")


class WhatsAppCloudNotifier:
    """WhatsApp Business (Cloud API) adapter.

    NOT TESTED against the live service. Outside a user's 24-hour reply window WhatsApp only
    delivers pre-approved message templates, so production use needs a template registered with
    the provider and this payload switched from `text` to `template`.
    """

    def __init__(self, token: str, phone_number_id: str) -> None:
        self.token = token
        self.url = f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"

    def send(self, message: Message) -> None:
        body = json.dumps(
            {
                "messaging_product": "whatsapp",
                "to": message.contact.lstrip("+"),
                "type": "text",
                "text": {"body": message.text},
            }
        ).encode()
        request = urllib.request.Request(
            self.url,
            data=body,
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=10):  # noqa: S310 - fixed https URL
            logger.info("Reminder handed to WhatsApp provider")


_notifier: Notifier | None = None


def configure() -> Notifier:
    """Chooses the sender from the environment: Twilio, else WhatsApp Cloud, else the development outbox."""
    s = get_settings()
    api_key = (s.twilio_api_key_sid, s.twilio_api_key_secret) if s.twilio_api_key_sid and s.twilio_api_key_secret else None
    if s.twilio_account_sid and (s.twilio_auth_token or api_key) and (s.twilio_sms_from or s.twilio_whatsapp_from):
        return TwilioNotifier(
            s.twilio_account_sid, s.twilio_auth_token, s.twilio_sms_from, s.twilio_whatsapp_from, s.sms_country_code, api_key
        )
    if s.fast2sms_api_key:
        whatsapp = (
            (s.fast2sms_whatsapp_phone_number_id, s.fast2sms_whatsapp_code_template, s.fast2sms_whatsapp_reminder_template)
            if s.fast2sms_whatsapp_phone_number_id and (s.fast2sms_whatsapp_code_template or s.fast2sms_whatsapp_reminder_template)
            else None
        )
        return Fast2SmsNotifier(s.fast2sms_api_key, s.sms_country_code, s.fast2sms_otp_route, whatsapp)
    if s.whatsapp_provider_api_key and s.whatsapp_phone_number_id:
        return WhatsAppCloudNotifier(s.whatsapp_provider_api_key, s.whatsapp_phone_number_id)
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
