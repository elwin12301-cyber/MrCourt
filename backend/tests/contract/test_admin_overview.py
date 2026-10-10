"""The admin role is separate from advocates and clients, in both directions (spec US1)."""

import pytest

from helpers import sign_in

API = "/api/v1"
ADMIN_PATHS = ["/admin/overview", "/admin/users", "/admin/cases", "/admin/audit", "/admin/verifications"]


def test_admin_endpoints_need_a_sign_in(client):
    for path in ADMIN_PATHS:
        assert client.get(f"{API}{path}").status_code == 401, path


@pytest.mark.parametrize("email", ["rohan.sharma@example.com", "anita.sharma@example.com"])
def test_advocates_and_clients_are_refused_every_admin_endpoint(client, email):
    sign_in(client, email)
    for path in ADMIN_PATHS:
        assert client.get(f"{API}{path}").status_code == 403, path


def test_the_administrator_has_their_own_role(admin_client):
    me = admin_client.get(f"{API}/me").json()
    assert me["role"] == "admin" and me["is_admin"] is True


def test_the_administrator_cannot_use_advocate_or_client_screens(admin_client):
    for path in ("/cases", "/dashboard", "/drafts", "/client/dashboard", "/client/updates"):
        assert admin_client.get(f"{API}{path}").status_code == 403, path


def test_the_administrator_cannot_deactivate_themselves(admin_client):
    response = admin_client.post(f"{API}/me/deactivate", json={"acknowledge_case_retention": True})
    assert response.status_code == 403
    assert admin_client.get(f"{API}/me").status_code == 200


def test_overview_counts(admin_client):
    body = admin_client.get(f"{API}/admin/overview").json()
    assert set(body) == {
        "advocates", "clients", "open_cases", "pending_verifications", "suspended_accounts", "recent_audit",
    }
    assert body["advocates"] == 1 and body["clients"] == 2
    assert body["open_cases"] == 4  # one of the five seeded cases is closed
    assert body["pending_verifications"] == 0 and body["suspended_accounts"] == 0
    assert body["recent_audit"] == []


def test_overview_counts_follow_changes(admin_client, client):
    client.post(
        f"{API}/auth/register",
        json={"role": "advocate", "full_name": "Adv. New", "email": "newadv@example.com",
              "password": "a-strong-password", "bar_registration_number": "D/5/2020"},
    )
    body = admin_client.get(f"{API}/admin/overview").json()
    assert body["advocates"] == 2 and body["pending_verifications"] == 1


def test_an_admin_account_cannot_be_created_through_sign_up(client):
    response = client.post(
        f"{API}/auth/register",
        json={"role": "admin", "full_name": "Sneaky", "email": "sneaky@example.com", "password": "a-strong-password"},
    )
    assert response.status_code == 422
