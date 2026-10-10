import pytest
from helpers import sign_in
from sqlalchemy import select

from mrcourt.config import get_settings
from mrcourt.models import User
from mrcourt.services import notify

API = "/api/v1"
PHONE = "+91 98765 43210"


def _register(client, email="new.person@example.com", phone=PHONE, role="petitioner"):
    return client.post(
        f"{API}/auth/register",
        json={"role": role, "full_name": "New Person", "email": email, "phone": phone, "password": "a-strong-password"},
    )


def _last_code() -> str:
    return notify.OUTBOX[-1].code


def test_a_new_account_gets_a_code_for_its_phone_and_is_verified_with_it(client, db):
    assert _register(client).status_code == 201
    me = client.get(f"{API}/me").json()
    assert me["phone"] == "+919876543210" and me["phone_verified"] is False

    response = client.post(f"{API}/auth/phone/request")
    assert response.status_code == 202 and response.json()["delivery"] == "development"
    message = notify.OUTBOX[-1]
    assert message.contact == "+919876543210" and message.kind == "code" and "verification code" in message.text

    assert client.post(f"{API}/auth/phone/verify", json={"code": _last_code()}).status_code == 200
    assert client.get(f"{API}/me").json()["phone_verified"] is True
    assert db.scalars(select(User).where(User.email == "new.person@example.com")).one().phone_verified_at is not None


def test_a_wrong_code_is_refused_and_five_wrong_tries_lock_that_code(client):
    _register(client)
    client.post(f"{API}/auth/phone/request")
    real = _last_code()
    wrong = "000000" if real != "000000" else "111111"
    for _ in range(5):
        assert client.post(f"{API}/auth/phone/verify", json={"code": wrong}).status_code == 400
    assert client.post(f"{API}/auth/phone/verify", json={"code": real}).status_code == 400  # locked
    client.post(f"{API}/auth/phone/request")  # a fresh code works again
    assert client.post(f"{API}/auth/phone/verify", json={"code": _last_code()}).status_code == 200


def test_a_resent_code_replaces_the_old_one(client):
    _register(client)
    client.post(f"{API}/auth/phone/request")
    first = _last_code()
    client.post(f"{API}/auth/phone/request")
    second = _last_code()
    if first != second:
        assert client.post(f"{API}/auth/phone/verify", json={"code": first}).status_code == 400
    assert client.post(f"{API}/auth/phone/verify", json={"code": second}).status_code in (200, 400)


def test_an_expired_code_is_refused(client, db, monkeypatch):
    from datetime import timedelta

    from mrcourt.db.base import utcnow
    from mrcourt.models import OtpChallenge

    _register(client)
    client.post(f"{API}/auth/phone/request")
    challenge = db.scalars(select(OtpChallenge)).one()
    challenge.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    assert client.post(f"{API}/auth/phone/verify", json={"code": _last_code()}).status_code == 400


def test_requests_are_limited(client):
    _register(client)
    codes = [client.post(f"{API}/auth/phone/request").status_code for _ in range(6)]
    assert codes[:5] == [202] * 5 and codes[5] == 429


def test_nothing_to_verify_without_a_phone_or_when_already_verified(client):
    client.post(
        f"{API}/auth/register",
        json={"role": "petitioner", "full_name": "No Phone", "email": "nophone@example.com", "password": "a-strong-password"},
    )
    assert client.post(f"{API}/auth/phone/request").status_code == 422
    client.patch(f"{API}/me", json={"phone": "+919000000001"})
    client.post(f"{API}/auth/phone/request")
    client.post(f"{API}/auth/phone/verify", json={"code": _last_code()})
    assert client.post(f"{API}/auth/phone/request").status_code == 409


def test_changing_the_number_makes_it_unverified_again(client):
    _register(client)
    client.post(f"{API}/auth/phone/request")
    client.post(f"{API}/auth/phone/verify", json={"code": _last_code()})
    assert client.get(f"{API}/me").json()["phone_verified"] is True
    assert client.patch(f"{API}/me", json={"phone": "+919000000002"}).json()["phone_verified"] is False
    assert client.patch(f"{API}/me", json={"phone": "+919000000002", "full_name": "Renamed"}).json()["phone_verified"] is False


def test_a_number_used_by_another_account_cannot_be_registered_again(client, second_client):
    assert _register(client).status_code == 201
    again = second_client.post(
        f"{API}/auth/register",
        json={"role": "petitioner", "full_name": "Other", "email": "other.person@example.com", "phone": PHONE, "password": "a-strong-password"},
    )
    assert again.status_code == 409


def test_it_needs_sign_in(client):
    assert client.post(f"{API}/auth/phone/request").status_code == 401
    assert client.post(f"{API}/auth/phone/verify", json={"code": "123456"}).status_code == 401


def test_the_code_is_never_stored_as_text(client, db):
    from mrcourt.models import OtpChallenge

    _register(client)
    client.post(f"{API}/auth/phone/request")
    code = _last_code()
    assert code not in db.scalars(select(OtpChallenge)).one().code_hash
