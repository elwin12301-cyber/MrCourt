import base64
import urllib.parse

import pytest

from mrcourt.config import get_settings
from mrcourt.services import notify
from mrcourt.services.notify import ConsoleNotifier, Message, TwilioNotifier, to_msisdn


class Captured:
    def __init__(self):
        self.requests = []
        self.fail_for: set[str] = set()

    def __call__(self, request, timeout=None):
        fields = dict(urllib.parse.parse_qsl(request.data.decode()))
        if any(fields["To"].startswith(prefix) for prefix in self.fail_for):
            raise OSError("provider said no")
        self.requests.append((request, fields))

        class Response:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *args):
                return False

        return Response()


@pytest.fixture
def twilio(monkeypatch):
    captured = Captured()
    monkeypatch.setattr("urllib.request.urlopen", captured)
    return captured


def test_phone_numbers_become_international_digits():
    assert to_msisdn("98765 43210") == "919876543210"
    assert to_msisdn("+91 98765-43210") == "919876543210"
    assert to_msisdn("0091 98765 43210") == "919876543210"
    assert to_msisdn("12345") is None and to_msisdn("") is None


def test_a_text_goes_out_by_sms_and_by_the_whatsapp_sandbox(twilio):
    sender = TwilioNotifier("AC123", "secret", "+15005550006", "whatsapp:+14155238886")
    sender.send(Message(contact="+91 98765 43210", text="Hello"))
    (sms, sms_fields), (wa, wa_fields) = twilio.requests
    assert sms.full_url == "https://api.twilio.com/2010-04-01/Accounts/AC123/Messages.json"
    assert sms_fields == {"To": "+919876543210", "From": "+15005550006", "Body": "Hello"}
    assert wa_fields == {"To": "whatsapp:+919876543210", "From": "whatsapp:+14155238886", "Body": "Hello"}
    assert sms.get_header("Authorization") == "Basic " + base64.b64encode(b"AC123:secret").decode()


def test_only_the_channels_that_are_set_up_are_used(twilio):
    TwilioNotifier("AC123", "secret", "", "whatsapp:+14155238886").send(Message(contact="9876543210", text="Hi"))
    assert [f["To"] for _, f in twilio.requests] == ["whatsapp:+919876543210"]
    twilio.requests.clear()
    TwilioNotifier("AC123", "secret", "+15005550006", "").send(Message(contact="9876543210", text="Hi"))
    assert [f["To"] for _, f in twilio.requests] == ["+919876543210"]


def test_one_channel_failing_does_not_stop_the_other_but_all_failing_is_an_error(twilio):
    sender = TwilioNotifier("AC123", "secret", "+15005550006", "whatsapp:+14155238886")
    twilio.fail_for = {"whatsapp:"}
    sender.send(Message(contact="9876543210", text="Hi"))  # SMS still went
    assert len(twilio.requests) == 1
    twilio.fail_for = {"whatsapp:", "+"}
    with pytest.raises(RuntimeError):
        sender.send(Message(contact="9876543210", text="Hi"))


def test_a_message_without_a_usable_number_is_dropped_quietly(twilio):
    TwilioNotifier("AC123", "secret", "+15005550006", "").send(Message(contact="not a number", text="Hi"))
    assert twilio.requests == []


def test_the_sender_is_chosen_from_the_environment(monkeypatch):
    settings = get_settings()
    notify.set_notifier(None)
    try:
        assert isinstance(notify.configure(), ConsoleNotifier)
        monkeypatch.setattr(settings, "twilio_account_sid", "AC1")
        monkeypatch.setattr(settings, "twilio_auth_token", "t")
        assert isinstance(notify.configure(), ConsoleNotifier)  # no channel yet
        monkeypatch.setattr(settings, "twilio_whatsapp_from", "whatsapp:+14155238886")
        assert isinstance(notify.configure(), TwilioNotifier)
        assert notify.delivers_for_real() is True
    finally:
        notify.set_notifier(ConsoleNotifier())


def test_an_api_key_can_log_in_instead_of_the_auth_token(monkeypatch) -> None:
    import base64

    seen: dict[str, str] = {}

    class _Done:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(request, timeout):
        seen["auth"] = request.get_header("Authorization")
        seen["url"] = request.full_url
        return _Done()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    sender = TwilioNotifier("AC123", "", "+15005550006", "", api_key=("SK999", "keysecret"))
    sender.send(Message(contact="9876543210", text="Hi"))
    assert base64.b64decode(seen["auth"].split()[1]).decode() == "SK999:keysecret"
    assert "/Accounts/AC123/" in seen["url"]
