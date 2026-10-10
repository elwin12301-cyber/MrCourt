"""Suspending or signing someone out takes effect on their very next request (spec SC-003)."""

from sqlalchemy import select

from helpers import sign_in
from mrcourt.models import User
from mrcourt.services import notify

API = "/api/v1"
ANITA = "anita.sharma@example.com"
ROHAN = "rohan.sharma@example.com"


def target(db, email):
    return str(db.scalars(select(User).where(User.email == email)).one().id)


def test_suspending_ends_an_open_session_at_once(admin_client, client, db):
    sign_in(client, ANITA)
    assert client.get(f"{API}/me").status_code == 200
    admin_client.post(f"{API}/admin/users/{target(db, ANITA)}/suspend", json={"reason": "Policy breach"})
    assert client.get(f"{API}/me").status_code == 401
    assert client.get(f"{API}/client/dashboard").status_code == 401


def test_a_session_from_before_a_suspension_stays_dead_after_reactivation(admin_client, client, db):
    sign_in(client, ANITA)
    admin_client.post(f"{API}/admin/users/{target(db, ANITA)}/suspend", json={"reason": "Check"})
    admin_client.post(f"{API}/admin/users/{target(db, ANITA)}/reactivate")
    assert client.get(f"{API}/me").status_code == 401  # must sign in again
    sign_in(client, ANITA)
    assert client.get(f"{API}/me").status_code == 200


def test_force_sign_out_ends_sessions_but_not_the_account(admin_client, client, db):
    sign_in(client, ANITA)
    assert admin_client.post(f"{API}/admin/users/{target(db, ANITA)}/sign-out").status_code == 204
    assert client.get(f"{API}/me").status_code == 401
    sign_in(client, ANITA)  # signing in again works
    assert client.get(f"{API}/me").status_code == 200


def test_force_sign_out_ends_every_session_of_that_person(admin_client, client, app, db):
    from fastapi.testclient import TestClient

    sign_in(client, ANITA)  # one browser
    with TestClient(app, base_url="http://testserver") as phone:  # and a second device
        sign_in(phone, ANITA)
        assert phone.get(f"{API}/me").status_code == 200
        admin_client.post(f"{API}/admin/users/{target(db, ANITA)}/sign-out")
        assert client.get(f"{API}/me").status_code == 401
        assert phone.get(f"{API}/me").status_code == 401


def test_signing_out_one_person_does_not_affect_others(admin_client, client, db):
    sign_in(client, ROHAN)
    admin_client.post(f"{API}/admin/users/{target(db, ANITA)}/sign-out")
    assert client.get(f"{API}/me").status_code == 200


def test_a_suspended_person_cannot_sign_in_by_any_route(admin_client, client, db):
    admin_client.post(f"{API}/admin/users/{target(db, ANITA)}/suspend", json={"reason": "Check"})
    assert client.post(f"{API}/auth/login", json={"identifier": ANITA, "password": "password123"}).status_code == 403

    client.post(f"{API}/auth/otp/request", json={"identifier": ANITA})
    assert notify.OUTBOX == [], "no passcode is sent to a suspended account"
    assert client.post(f"{API}/auth/otp/verify", json={"identifier": ANITA, "code": "123456"}).status_code == 401


def test_a_suspended_advocate_shows_as_unavailable_to_their_clients(admin_client, client, db):
    admin_client.post(f"{API}/admin/users/{target(db, ROHAN)}/suspend", json={"reason": "Check"})
    sign_in(client, ANITA)
    lawyer = client.get(f"{API}/client/dashboard").json()["cases"][0]["lawyer"]
    assert lawyer["available"] is False
    case_id = client.get(f"{API}/client/dashboard").json()["cases"][0]["id"]
    sent = client.post(f"{API}/client/cases/{case_id}/questions", json={"kind": "question", "text": "Hello?"})
    assert sent.status_code == 409


def test_the_administrators_own_session_survives_actions_on_others(admin_client, db):
    admin_client.post(f"{API}/admin/users/{target(db, ANITA)}/suspend", json={"reason": "Check"})
    admin_client.post(f"{API}/admin/users/{target(db, ROHAN)}/sign-out")
    assert admin_client.get(f"{API}/admin/overview").status_code == 200
