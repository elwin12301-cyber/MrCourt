"""Integration tests for security-relevant sign-in behaviour."""

from datetime import timedelta

from sqlalchemy import select

from mrcourt.db.base import utcnow
from mrcourt.models import OtpChallenge, User
from mrcourt.services import notify

API = "/api/v1"
EMAIL = "rohan.sharma@example.com"


def test_bad_credentials_give_the_same_generic_error_for_unknown_and_wrong_password(client):
    wrong_pw = client.post(f"{API}/auth/login", json={"identifier": EMAIL, "password": "wrong"})
    unknown = client.post(f"{API}/auth/login", json={"identifier": "ghost@example.com", "password": "wrong"})
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.json() == unknown.json()


def test_deactivated_user_gets_403_not_a_session(client, db):
    user = db.scalars(select(User).where(User.email == EMAIL)).one()
    user.status = "deactivated"
    db.commit()
    response = client.post(f"{API}/auth/login", json={"identifier": EMAIL, "password": "password123"})
    assert response.status_code == 403
    assert "mrcourt_session" not in response.cookies


def test_deactivated_user_with_existing_cookie_is_signed_out(advocate_client, db):
    user = db.scalars(select(User).where(User.email == EMAIL)).one()
    user.status = "deactivated"
    db.commit()
    assert advocate_client.get(f"{API}/me").status_code == 401


def test_otp_expires(client, db):
    client.post(f"{API}/auth/otp/request", json={"identifier": EMAIL})
    code = notify.OUTBOX[-1].code
    challenge = db.scalars(select(OtpChallenge)).one()
    challenge.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    response = client.post(f"{API}/auth/otp/verify", json={"identifier": EMAIL, "code": code})
    assert response.status_code == 401


def test_otp_is_single_use(client):
    client.post(f"{API}/auth/otp/request", json={"identifier": EMAIL})
    code = notify.OUTBOX[-1].code
    assert client.post(f"{API}/auth/otp/verify", json={"identifier": EMAIL, "code": code}).status_code == 200
    client.post(f"{API}/auth/logout")
    assert client.post(f"{API}/auth/otp/verify", json={"identifier": EMAIL, "code": code}).status_code == 401


def test_otp_locks_after_too_many_wrong_attempts(client):
    client.post(f"{API}/auth/otp/request", json={"identifier": EMAIL})
    good = notify.OUTBOX[-1].code
    wrong = "000000" if good != "000000" else "111111"
    for _ in range(5):
        assert client.post(f"{API}/auth/otp/verify", json={"identifier": EMAIL, "code": wrong}).status_code == 401
    # Even the correct code no longer works once the attempt limit is reached.
    assert client.post(f"{API}/auth/otp/verify", json={"identifier": EMAIL, "code": good}).status_code == 401


def test_otp_requests_are_rate_limited(client):
    statuses = [
        client.post(f"{API}/auth/otp/request", json={"identifier": EMAIL}).status_code for _ in range(7)
    ]
    assert statuses[:5] == [202] * 5
    assert 429 in statuses[5:]


def test_login_attempts_are_rate_limited(client):
    statuses = [
        client.post(f"{API}/auth/login", json={"identifier": EMAIL, "password": "bad"}).status_code
        for _ in range(12)
    ]
    assert 429 in statuses


def test_logs_do_not_contain_the_otp_code(client, caplog):
    with caplog.at_level("DEBUG"):
        client.post(f"{API}/auth/otp/request", json={"identifier": EMAIL})
    code = notify.OUTBOX[-1].code
    assert code not in caplog.text
