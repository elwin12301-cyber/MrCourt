from mrcourt.config import get_settings
from mrcourt.services import notify
from mrcourt.services.notify import ConsoleNotifier, Message, TwilioNotifier

URL = "/api/v1/dev/messages"


def test_messages_can_be_read_in_development(client):
    notify.OUTBOX.clear()
    client.post("/api/v1/auth/password/forgot", json={"identifier": "nobody@example.com"})
    notify.get_notifier().send(Message(contact="+919810054321", text="Hello there", code="123456", kind="code"))
    body = client.get(URL).json()
    assert body[0]["to"] == "+919810054321" and body[0]["text"] == "Hello there" and body[0]["kind"] == "code"


def test_newest_first_and_capped(client):
    notify.OUTBOX.clear()
    for number in range(60):
        notify.get_notifier().send(Message(contact="+911", text=f"m{number}"))
    body = client.get(URL).json()
    assert len(body) == 50 and body[0]["text"] == "m59"


def test_the_page_does_not_exist_in_production(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "environment", "production")
    assert client.get(URL).status_code == 404


def test_the_page_does_not_exist_once_a_real_service_is_set_up(client):
    notify.set_notifier(TwilioNotifier("AC123", "token", "+15005550006", ""))
    try:
        assert client.get(URL).status_code == 404
    finally:
        notify.set_notifier(ConsoleNotifier())


def test_a_failing_text_service_does_not_change_the_reply_or_break_sign_in_codes(client) -> None:
    class Failing:
        def send(self, message) -> None:
            raise RuntimeError("The message could not be delivered on any channel")

    notify.set_notifier(Failing())
    body = {"role": "petitioner", "full_name": "Fail Test", "username": "failtest", "email": "fail@example.com", "phone": "+919800000077", "password": "a-strong-password"}
    assert client.post("/api/v1/auth/register", json=body).status_code == 201
    client.post("/api/v1/auth/logout")
    known = client.post("/api/v1/auth/otp/request", json={"identifier": "failtest"})
    unknown = client.post("/api/v1/auth/otp/request", json={"identifier": "nobody-here"})
    assert known.status_code == unknown.status_code
    assert known.json() == unknown.json()
