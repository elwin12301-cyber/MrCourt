"""Contract tests for settings, data export, deactivation and administrator verification."""

from helpers import sign_in

API = "/api/v1"
ADMIN = "admin@example.com"


def test_update_settings(advocate_client):
    response = advocate_client.patch(
        f"{API}/me/settings",
        json={"whatsapp_reminders": False, "hearing_alert_days": 3, "theme": "dark", "language": "en"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "language": "en", "whatsapp_reminders": False, "hearing_alert_days": 3, "theme": "dark",
        "voice_consent": False, "voice_cloud_opt_in": False, "voice_language": None,
    }
    assert advocate_client.get(f"{API}/me").json()["settings"]["theme"] == "dark"


def test_settings_validation(advocate_client):
    assert advocate_client.patch(f"{API}/me/settings", json={"hearing_alert_days": 99}).status_code == 422
    assert advocate_client.patch(f"{API}/me/settings", json={"theme": "neon"}).status_code == 422


def test_settings_require_sign_in(client):
    assert client.patch(f"{API}/me/settings", json={"theme": "dark"}).status_code == 401


def test_data_export_contains_the_users_own_data(advocate_client):
    advocate_client.post(f"{API}/questions", json={"text": "What is Section 138?"})
    body = advocate_client.get(f"{API}/me/data-export").json()
    assert body["profile"]["email"] == "rohan.sharma@example.com"
    assert "password_hash" not in str(body)
    assert len(body["questions"]) == 1
    assert len(body["cases"]) == 5
    assert body["settings"]["language"] == "en"


def test_data_export_never_includes_other_peoples_data(petitioner_client):
    body = petitioner_client.get(f"{API}/me/data-export").json()
    assert body["profile"]["email"] == "anita.sharma@example.com"
    assert body["cases"] == []  # petitioners own no cases


def test_deactivation_requires_acknowledging_case_retention(advocate_client):
    assert advocate_client.post(f"{API}/me/deactivate", json={}).status_code == 422
    assert advocate_client.post(f"{API}/me/deactivate", json={"acknowledge_case_retention": False}).status_code == 422
    assert advocate_client.get(f"{API}/me").status_code == 200  # still active


def test_deactivation_signs_the_user_out(advocate_client):
    response = advocate_client.post(f"{API}/me/deactivate", json={"acknowledge_case_retention": True})
    assert response.status_code == 204
    assert advocate_client.get(f"{API}/me").status_code == 401


def test_verification_endpoints_are_admin_only(advocate_client, petitioner_client):
    assert advocate_client.get(f"{API}/admin/verifications").status_code == 403


def test_admin_confirms_a_pending_advocate(client):
    client.post(
        f"{API}/auth/register",
        json={
            "role": "advocate", "full_name": "Adv. New", "email": "new.adv@example.com",
            "password": "a-strong-password", "bar_registration_number": "D/777/2022",
        },
    )
    assert client.get(f"{API}/me").json()["verification_status"] == "pending"
    new_id = client.get(f"{API}/me").json()["id"]
    client.post(f"{API}/auth/logout")

    sign_in(client, ADMIN)
    pending = client.get(f"{API}/admin/verifications").json()
    assert [p["id"] for p in pending] == [new_id]
    assert pending[0]["bar_registration_number"] == "D/777/2022"
    assert client.post(f"{API}/admin/verifications/{new_id}", json={"decision": "verified"}).status_code == 200
    assert client.get(f"{API}/admin/verifications").json() == []

    client.post(f"{API}/auth/logout")
    sign_in(client, "new.adv@example.com", "a-strong-password")
    assert client.get(f"{API}/me").json()["verification_status"] == "verified"


def test_admin_can_reject(client):
    client.post(
        f"{API}/auth/register",
        json={
            "role": "advocate", "full_name": "Adv. Bad", "email": "bad.adv@example.com",
            "password": "a-strong-password", "bar_registration_number": "X/0/0000",
        },
    )
    bad_id = client.get(f"{API}/me").json()["id"]
    client.post(f"{API}/auth/logout")
    sign_in(client, ADMIN)
    assert client.post(f"{API}/admin/verifications/{bad_id}", json={"decision": "rejected"}).status_code == 200
    client.post(f"{API}/auth/logout")
    sign_in(client, "bad.adv@example.com", "a-strong-password")
    assert client.get(f"{API}/me").json()["verification_status"] == "none"
