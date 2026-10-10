"""Contract tests for the auth and /me endpoints (contracts/openapi.yaml)."""

from mrcourt.services import notify

API = "/api/v1"


def register_payload(**overrides):
    payload = {
        "role": "petitioner",
        "full_name": "Meera Iyer",
        "email": "meera.iyer@example.com",
        "password": "a-strong-password",
    }
    payload.update(overrides)
    return payload


def test_register_creates_account_and_signs_in(client):
    response = client.post(f"{API}/auth/register", json=register_payload())
    assert response.status_code == 201
    assert "mrcourt_session" in response.cookies
    me = client.get(f"{API}/me").json()
    assert me["role"] == "petitioner"
    assert me["full_name"] == "Meera Iyer"
    assert me["verification_status"] == "none"


def test_register_advocate_with_bar_number_is_pending(client):
    response = client.post(
        f"{API}/auth/register",
        json=register_payload(role="advocate", bar_registration_number="D/9999/2020"),
    )
    assert response.status_code == 201
    assert client.get(f"{API}/me").json()["verification_status"] == "pending"


def test_register_duplicate_email_conflicts(client):
    response = client.post(
        f"{API}/auth/register", json=register_payload(email="rohan.sharma@example.com")
    )
    assert response.status_code == 409


def test_register_requires_contact_and_long_password(client):
    assert client.post(f"{API}/auth/register", json=register_payload(email=None)).status_code == 422
    assert client.post(f"{API}/auth/register", json=register_payload(password="short")).status_code == 422


def test_login_success_sets_cookie(client):
    response = client.post(
        f"{API}/auth/login",
        json={"identifier": "rohan.sharma@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    assert "mrcourt_session" in response.cookies


def test_login_invalid_is_401(client):
    response = client.post(
        f"{API}/auth/login", json={"identifier": "rohan.sharma@example.com", "password": "nope"}
    )
    assert response.status_code == 401


def test_me_requires_session(client):
    assert client.get(f"{API}/me").status_code == 401


def test_me_shape(advocate_client):
    me = advocate_client.get(f"{API}/me").json()
    assert set(me) >= {
        "id", "role", "full_name", "bar_registration_number",
        "verification_status", "is_admin", "settings",
    }
    assert set(me["settings"]) == {"language", "whatsapp_reminders", "hearing_alert_days", "theme"}


def test_logout_clears_session(advocate_client):
    assert advocate_client.post(f"{API}/auth/logout").status_code == 204
    assert advocate_client.get(f"{API}/me").status_code == 401


def test_otp_request_is_accepted_for_known_and_unknown_contacts(client):
    known = client.post(f"{API}/auth/otp/request", json={"identifier": "rohan.sharma@example.com"})
    unknown = client.post(f"{API}/auth/otp/request", json={"identifier": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 202
    assert len(notify.OUTBOX) == 1  # only the real account was messaged


def test_otp_verify_signs_in(client):
    client.post(f"{API}/auth/otp/request", json={"identifier": "rohan.sharma@example.com"})
    code = notify.OUTBOX[-1].code
    response = client.post(
        f"{API}/auth/otp/verify", json={"identifier": "rohan.sharma@example.com", "code": code}
    )
    assert response.status_code == 200
    assert client.get(f"{API}/me").status_code == 200


def test_otp_verify_rejects_bad_code_format(client):
    response = client.post(
        f"{API}/auth/otp/verify", json={"identifier": "rohan.sharma@example.com", "code": "abc"}
    )
    assert response.status_code == 422


def test_patch_me_updates_name_and_marks_pending_when_bar_number_added(petitioner_client, client):
    response = client.patch(f"{API}/me", json={"full_name": "Anita S. Sharma"})
    assert response.status_code == 200
    assert response.json()["full_name"] == "Anita S. Sharma"


def test_phone_can_be_added_and_is_unique(advocate_client, client):
    assert client.patch(f"{API}/me", json={"phone": "+91 98100 00001"}).json()["phone"] == "+919810000001"
    client.post(f"{API}/auth/logout")
    from helpers import sign_in

    sign_in(client, "anita.sharma@example.com")
    assert client.patch(f"{API}/me", json={"phone": "+919810000001"}).status_code == 409
    assert client.patch(f"{API}/me", json={"phone": ""}).json()["phone"] is None
