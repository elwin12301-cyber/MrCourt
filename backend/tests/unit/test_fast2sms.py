import json

import pytest

from mrcourt.services.notify import Fast2SmsNotifier, Message


class _Reply:
    def __init__(self, body: dict) -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self) -> bytes:
        return json.dumps(self.body).encode()


@pytest.fixture
def sent(monkeypatch):
    class Seen(list):
        state: dict = {"reply": {"return": True}}

    seen = Seen()
    state = seen.state = {"reply": {"return": True}}

    def fake(request, timeout):
        seen.append((request, json.loads(request.data) if request.data else {}))
        return _Reply(state["reply"])

    monkeypatch.setattr("urllib.request.urlopen", fake)
    return seen


def test_a_code_goes_by_the_otp_route_to_a_ten_digit_number(sent) -> None:
    Fast2SmsNotifier("KEY", otp_route=True).send(Message(contact="+91 98765 43210", text="Your MrCourt code is 123456.", code="123456"))
    request, fields = sent[0]
    assert request.get_header("Authorization") == "KEY"
    assert fields == {"route": "otp", "variables_values": "123456", "numbers": "9876543210"}


def test_a_reminder_goes_by_the_quick_route_with_its_text(sent) -> None:
    Fast2SmsNotifier("KEY").send(Message(contact="9876543210", text="Hearing tomorrow", kind="reminder"))
    assert sent[0][1]["route"] == "q" and sent[0][1]["message"] == "Hearing tomorrow"


def test_a_refusal_from_the_service_is_an_error_without_the_text(sent) -> None:
    sent.state["reply"] = {"return": False, "message": ["Insufficient balance"]}
    with pytest.raises(RuntimeError) as error:
        Fast2SmsNotifier("KEY").send(Message(contact="9876543210", text="secret text", code="111111"))
    assert "secret" not in str(error.value) and "111111" not in str(error.value)


def test_no_usable_number_sends_nothing(sent) -> None:
    Fast2SmsNotifier("KEY").send(Message(contact="12", text="x"))
    assert sent == []


def test_codes_use_quick_sms_unless_the_otp_route_is_switched_on(sent) -> None:
    Fast2SmsNotifier("KEY").send(Message(contact="9876543210", text="Your MrCourt code is 123456.", code="123456"))
    assert sent[0][1]["route"] == "q" and "123456" in sent[0][1]["message"]


def test_a_refusal_or_an_error_is_raised_for_the_caller_to_record(monkeypatch, sent) -> None:
    def fails(request, timeout):
        raise OSError("down")

    monkeypatch.setattr("urllib.request.urlopen", fails)
    with pytest.raises(OSError):
        Fast2SmsNotifier("KEY").send(Message(contact="9876543210", text="x", code="123456"))
