"""Contract tests for managing advocates and clients (spec US2)."""

import uuid

import pytest
from sqlalchemy import select

from helpers import sign_in
from mrcourt.models import AuditEntry, User

API = "/api/v1"
ROHAN, ANITA, RAVI = "rohan.sharma@example.com", "anita.sharma@example.com", "ravi.mehta@example.com"


def uid(db, email) -> str:
    return str(db.scalars(select(User).where(User.email == email)).one().id)


def users(admin, **params):
    return admin.get(f"{API}/admin/users", params=params).json()


# ---- lists -----------------------------------------------------------------------------------


def test_advocates_list(admin_client):
    rows = users(admin_client, role="advocate")
    assert [r["full_name"] for r in rows] == ["Adv. Rohan Sharma"]
    row = rows[0]
    assert set(row) == {
        "id", "role", "full_name", "email", "phone", "status", "verification_status",
        "bar_registration_number", "created_at", "case_count",
    }
    assert row["case_count"] == 5 and row["status"] == "active" and row["verification_status"] == "verified"


def test_clients_list(admin_client):
    rows = users(admin_client, role="petitioner")
    assert {r["full_name"] for r in rows} == {"Anita Sharma", "Ravi Mehta"}
    assert all(r["case_count"] == 1 for r in rows)


def test_the_administrator_is_never_in_the_lists(admin_client):
    everyone = users(admin_client, role="advocate") + users(admin_client, role="petitioner")
    assert "Site Administrator" not in {r["full_name"] for r in everyone}


def test_search_by_name_email_and_phone(admin_client, db):
    assert [r["full_name"] for r in users(admin_client, role="petitioner", q="ravi")] == ["Ravi Mehta"]
    assert [r["full_name"] for r in users(admin_client, role="petitioner", q="anita.sharma@")] == ["Anita Sharma"]
    anita = db.scalars(select(User).where(User.email == ANITA)).one()
    anita.phone = "+919811111111"
    db.commit()
    assert [r["full_name"] for r in users(admin_client, role="petitioner", q="9811111111")] == ["Anita Sharma"]
    assert users(admin_client, role="petitioner", q="nobody") == []


def test_filter_by_status_and_waiting_verification(admin_client, client, db):
    client.post(f"{API}/auth/register", json={"role": "advocate", "full_name": "Adv. Waiting", "email": "waiting@example.com", "password": "a-strong-password", "bar_registration_number": "D/9/2021"})
    waiting = users(admin_client, role="advocate", status="pending")
    assert [r["full_name"] for r in waiting] == ["Adv. Waiting"]
    admin_client.post(f"{API}/admin/users/{uid(db, ANITA)}/suspend", json={"reason": "Testing the filter"})
    assert [r["full_name"] for r in users(admin_client, role="petitioner", status="suspended")] == ["Anita Sharma"]
    assert [r["full_name"] for r in users(admin_client, role="petitioner", status="active")] == ["Ravi Mehta"]


def test_an_unknown_filter_value_is_rejected(admin_client):
    assert admin_client.get(f"{API}/admin/users", params={"status": "weird"}).status_code == 422
    assert admin_client.get(f"{API}/admin/users", params={"role": "admin"}).status_code == 422


# ---- one person ------------------------------------------------------------------------------


def test_an_advocates_page_lists_their_cases(admin_client, db):
    detail = admin_client.get(f"{API}/admin/users/{uid(db, ROHAN)}").json()
    assert detail["full_name"] == "Adv. Rohan Sharma" and detail["email"] == ROHAN
    assert len(detail["cases"]) == 5
    assert {c["relation"] for c in detail["cases"]} == {"advocate"}
    assert {"id", "title", "status", "relation", "advocate_name"} <= set(detail["cases"][0])


def test_a_clients_page_lists_their_cases_and_lawyers(admin_client, db):
    detail = admin_client.get(f"{API}/admin/users/{uid(db, ANITA)}").json()
    assert [(c["title"], c["relation"], c["advocate_name"]) for c in detail["cases"]] == [
        ("Sharma v. Verma Traders", "client", "Adv. Rohan Sharma")
    ]


def test_unknown_person_is_404(admin_client):
    assert admin_client.get(f"{API}/admin/users/{uuid.uuid4()}").status_code == 404


def test_the_administrator_cannot_be_opened_as_a_person(admin_client, db):
    assert admin_client.get(f"{API}/admin/users/{uid(db, 'admin@example.com')}").status_code == 403


# ---- editing ---------------------------------------------------------------------------------


def test_correct_a_name_and_it_is_saved(admin_client, db):
    target = uid(db, ANITA)
    response = admin_client.patch(f"{API}/admin/users/{target}", json={"full_name": "Anita R. Sharma"})
    assert response.status_code == 200 and response.json()["full_name"] == "Anita R. Sharma"
    assert admin_client.get(f"{API}/admin/users/{target}").json()["full_name"] == "Anita R. Sharma"
    db.expire_all()
    assert db.get(User, uuid.UUID(target)).full_name == "Anita R. Sharma"


def test_email_and_phone_must_stay_unique(admin_client, db):
    target = uid(db, ANITA)
    assert admin_client.patch(f"{API}/admin/users/{target}", json={"email": RAVI}).status_code == 409
    admin_client.patch(f"{API}/admin/users/{uid(db, RAVI)}", json={"phone": "+91 98 7654 3210"})
    assert admin_client.patch(f"{API}/admin/users/{target}", json={"phone": "+919876543210"}).status_code == 409


def test_a_person_cannot_be_left_with_no_way_to_sign_in(admin_client, db):
    target = uid(db, ANITA)
    assert admin_client.patch(f"{API}/admin/users/{target}", json={"email": ""}).status_code == 422


def test_only_advocates_have_a_bar_council_number(admin_client, db):
    assert admin_client.patch(f"{API}/admin/users/{uid(db, ANITA)}", json={"bar_registration_number": "D/1/2020"}).status_code == 422


def test_changing_a_bar_number_asks_for_it_to_be_confirmed_again(admin_client, db):
    target = uid(db, ROHAN)
    response = admin_client.patch(f"{API}/admin/users/{target}", json={"bar_registration_number": "D/4321/2016"})
    assert response.status_code == 200
    assert response.json()["bar_registration_number"] == "D/4321/2016"
    assert response.json()["verification_status"] == "pending"


def test_an_empty_edit_is_rejected(admin_client, db):
    assert admin_client.patch(f"{API}/admin/users/{uid(db, ANITA)}", json={}).status_code == 422


def test_a_deactivated_persons_details_cannot_be_edited(admin_client, client, db):
    sign_in(client, RAVI)
    client.post(f"{API}/me/deactivate", json={"acknowledge_case_retention": True})
    target = db.scalars(select(User).where(User.full_name == "Deactivated user")).one()
    assert admin_client.patch(f"{API}/admin/users/{target.id}", json={"full_name": "Back again"}).status_code == 409


# ---- suspend, reactivate, sign out ------------------------------------------------------------


def test_suspend_needs_a_reason(admin_client, db):
    target = uid(db, ANITA)
    assert admin_client.post(f"{API}/admin/users/{target}/suspend", json={}).status_code == 422
    assert admin_client.post(f"{API}/admin/users/{target}/suspend", json={"reason": "  "}).status_code == 422


def test_suspend_and_reactivate(admin_client, client, db):
    target = uid(db, ANITA)
    suspended = admin_client.post(f"{API}/admin/users/{target}/suspend", json={"reason": "Reported misuse"})
    assert suspended.status_code == 200 and suspended.json()["status"] == "suspended"
    assert admin_client.get(f"{API}/admin/users/{target}").json()["suspension"]["reason"] == "Reported misuse"

    refused = client.post(f"{API}/auth/login", json={"identifier": ANITA, "password": "password123"})
    assert refused.status_code == 403 and "suspended" in refused.json()["detail"].lower()

    back = admin_client.post(f"{API}/admin/users/{target}/reactivate")
    assert back.status_code == 200 and back.json()["status"] == "active"
    assert admin_client.get(f"{API}/admin/users/{target}").json()["suspension"] is None
    sign_in(client, ANITA)


def test_cannot_suspend_twice_or_reactivate_an_active_person(admin_client, db):
    target = uid(db, ANITA)
    assert admin_client.post(f"{API}/admin/users/{target}/reactivate").status_code == 409
    admin_client.post(f"{API}/admin/users/{target}/suspend", json={"reason": "First"})
    assert admin_client.post(f"{API}/admin/users/{target}/suspend", json={"reason": "Again"}).status_code == 409


def test_force_sign_out(admin_client, db):
    assert admin_client.post(f"{API}/admin/users/{uid(db, ANITA)}/sign-out").status_code == 204


def test_administrators_are_not_managed_here(admin_client, db):
    admin_id = uid(db, "admin@example.com")
    assert admin_client.patch(f"{API}/admin/users/{admin_id}", json={"full_name": "X"}).status_code == 403
    assert admin_client.post(f"{API}/admin/users/{admin_id}/suspend", json={"reason": "No"}).status_code == 403
    assert admin_client.post(f"{API}/admin/users/{admin_id}/sign-out").status_code == 403
    assert admin_client.post(f"{API}/admin/users/{admin_id}/reactivate").status_code == 403


@pytest.mark.parametrize("path", ["suspend", "reactivate", "sign-out"])
def test_unknown_person_actions_are_404(admin_client, path):
    body = {"json": {"reason": "x"}} if path == "suspend" else {}
    assert admin_client.post(f"{API}/admin/users/{uuid.uuid4()}/{path}", **body).status_code == 404


def test_advocates_and_clients_cannot_manage_anyone(client, db):
    target = uid(db, RAVI)
    sign_in(client, ANITA)
    assert client.patch(f"{API}/admin/users/{target}", json={"full_name": "X"}).status_code == 403
    assert client.post(f"{API}/admin/users/{target}/suspend", json={"reason": "No"}).status_code == 403
    assert db.scalars(select(AuditEntry)).first() is None


# ---- verification (existing endpoints, now audited) -------------------------------------------


def test_verification_decisions_are_saved_and_logged(admin_client, client, db):
    client.post(f"{API}/auth/register", json={"role": "advocate", "full_name": "Adv. Pending", "email": "pend@example.com", "password": "a-strong-password", "bar_registration_number": "D/8/2019"})
    pending = admin_client.get(f"{API}/admin/verifications").json()
    assert [p["full_name"] for p in pending] == ["Adv. Pending"]
    assert admin_client.post(f"{API}/admin/verifications/{pending[0]['id']}", json={"decision": "verified"}).status_code == 200
    db.expire_all()
    assert db.scalars(select(User).where(User.email == "pend@example.com")).one().verification_status == "verified"
    assert db.scalars(select(AuditEntry.action)).all() == ["verification.confirm"]
