from datetime import timedelta

from helpers import sign_in
from sqlalchemy import select

from mrcourt.db.base import utcnow
from mrcourt.models import OtpChallenge, User
from mrcourt.services import notify

API = "/api/v1"
EMAIL = "anita.sharma@example.com"
PHONE = "+919810054321"


def _give_verified_phone(db, email=EMAIL, phone=PHONE):
    user = db.scalars(select(User).where(User.email == email)).one()
    user.phone = phone
    user.phone_verified_at = utcnow()
    db.commit()
    return user


def _forgot(client, identifier=EMAIL):
    return client.post(f"{API}/auth/password/forgot", json={"identifier": identifier})


def _reset(client, code, password="a-brand-new-password", identifier=EMAIL):
    return client.post(f"{API}/auth/password/reset", json={"identifier": identifier, "code": code, "new_password": password})


def test_a_code_goes_to_the_verified_phone_and_resets_the_password(client, db):
    _give_verified_phone(db)
    notify.OUTBOX.clear()
    response = _forgot(client)
    assert response.status_code == 202 and response.json()["delivery"] == "development"
    message = notify.OUTBOX[-1]
    assert message.contact == PHONE and "password reset code" in message.text

    assert _reset(client, message.code).status_code == 200
    assert client.post(f"{API}/auth/login", json={"identifier": EMAIL, "password": "password123"}).status_code == 401
    assert client.post(f"{API}/auth/login", json={"identifier": EMAIL, "password": "a-brand-new-password"}).status_code == 200


def test_the_phone_number_works_as_the_identifier_too(client, db):
    _give_verified_phone(db)
    notify.OUTBOX.clear()
    _forgot(client, PHONE)
    assert _reset(client, notify.OUTBOX[-1].code, identifier=PHONE).status_code == 200


def test_the_reply_is_the_same_for_unknown_unverified_and_suspended_accounts(client, db):
    _give_verified_phone(db)
    reply = _forgot(client).json()["detail"]
    notify.OUTBOX.clear()

    assert _forgot(client, "nobody@example.com").json()["detail"] == reply
    unverified = db.scalars(select(User).where(User.email == "rohan.sharma@example.com")).one()
    unverified.phone = "+919810012345"
    db.commit()
    assert _forgot(client, "rohan.sharma@example.com").json()["detail"] == reply

    anita = db.scalars(select(User).where(User.email == EMAIL)).one()
    anita.status = "suspended"
    db.commit()
    assert _forgot(client).json()["detail"] == reply
    assert notify.OUTBOX == [], "nothing is sent to an unknown, unverified or suspended account"


def test_resetting_signs_the_person_out_everywhere(client, second_client, db):
    _give_verified_phone(db)
    sign_in(second_client, EMAIL)
    assert second_client.get(f"{API}/me").status_code == 200
    _forgot(client)
    _reset(client, notify.OUTBOX[-1].code)
    assert second_client.get(f"{API}/me").status_code == 401


def test_wrong_expired_and_reused_codes_are_refused(client, db):
    _give_verified_phone(db)
    _forgot(client)
    code = notify.OUTBOX[-1].code
    wrong = "000000" if code != "000000" else "111111"
    assert _reset(client, wrong).status_code == 400
    assert _reset(client, code).status_code == 200
    assert _reset(client, code, password="another-new-password").status_code == 400  # used up

    _forgot(client)
    challenge = db.scalars(select(OtpChallenge).where(OtpChallenge.purpose == "reset", OtpChallenge.consumed_at.is_(None))).one()
    challenge.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    assert _reset(client, notify.OUTBOX[-1].code).status_code == 400


def test_five_wrong_tries_lock_the_code(client, db):
    _give_verified_phone(db)
    _forgot(client)
    code = notify.OUTBOX[-1].code
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        _reset(client, wrong)
    assert _reset(client, code).status_code == 400


def test_a_short_password_is_refused_and_a_phone_code_cannot_reset_a_password(client, db):
    _give_verified_phone(db)
    _forgot(client)
    assert _reset(client, notify.OUTBOX[-1].code, password="short").status_code == 422

    user = db.scalars(select(User).where(User.email == EMAIL)).one()
    user.phone_verified_at = None
    db.commit()
    sign_in(client, EMAIL)
    client.post(f"{API}/auth/phone/request")
    phone_code = notify.OUTBOX[-1].code
    assert _reset(client, phone_code).status_code == 400  # a code for another purpose does not work here


def test_requests_are_limited(client, db):
    _give_verified_phone(db)
    codes = [_forgot(client).status_code for _ in range(6)]
    assert codes[:5] == [202] * 5 and codes[5] == 429


def test_the_sign_in_one_time_code_still_works_and_goes_to_the_phone(client, db):
    _give_verified_phone(db)
    notify.OUTBOX.clear()
    client.post(f"{API}/auth/otp/request", json={"identifier": EMAIL})
    assert notify.OUTBOX[-1].contact == PHONE
    assert client.post(f"{API}/auth/otp/verify", json={"identifier": EMAIL, "code": notify.OUTBOX[-1].code}).status_code == 200
