"""The audit log: who did what, safely, and never changeable (spec US4)."""

import json

from sqlalchemy import select

from mrcourt.models import Case, User

API = "/api/v1"


def uid(db, email):
    return str(db.scalars(select(User).where(User.email == email)).one().id)


def log(admin, **params):
    return admin.get(f"{API}/admin/audit", params=params).json()


def test_entries_show_who_what_whom_and_when(admin_client, db):
    target = uid(db, "anita.sharma@example.com")
    admin_client.post(f"{API}/admin/users/{target}/suspend", json={"reason": "Reported misuse"})
    body = log(admin_client)
    assert set(body) == {"items", "next_before"}
    entry = body["items"][0]
    assert set(entry) == {"id", "admin_name", "action", "action_label", "target_type", "target_id", "target_name", "detail", "created_at"}
    assert entry["admin_name"] == "Site Administrator"
    assert entry["action"] == "user.suspend" and entry["action_label"] == "Suspended an account"
    assert entry["target_name"] == "Anita Sharma" and entry["target_id"] == target
    assert entry["detail"] == {"reason": "Reported misuse"}


def test_newest_first_and_paging(admin_client, db):
    target = uid(db, "anita.sharma@example.com")
    for _ in range(5):
        admin_client.get(f"{API}/admin/users/{target}")
    first = log(admin_client, limit=2)
    assert len(first["items"]) == 2 and first["next_before"]
    times = [i["created_at"] for i in first["items"]]
    assert times == sorted(times, reverse=True)
    second = log(admin_client, limit=2, before=first["next_before"])
    assert len(second["items"]) == 2
    assert {i["id"] for i in first["items"]}.isdisjoint({i["id"] for i in second["items"]})
    rest = log(admin_client, limit=10, before=second["next_before"])
    assert len(rest["items"]) == 1 and rest["next_before"] is None


def test_name_changes_record_before_and_after_but_contact_changes_do_not(admin_client, db):
    target = uid(db, "anita.sharma@example.com")
    admin_client.patch(f"{API}/admin/users/{target}", json={"full_name": "Anita R. Sharma", "email": "anita.new@example.com", "phone": "+919800000001"})
    entry = log(admin_client)["items"][0]
    assert entry["action"] == "user.update"
    assert sorted(entry["detail"]["fields"]) == ["email", "full_name", "phone"]
    assert entry["detail"]["full_name"] == {"from": "Anita Sharma", "to": "Anita R. Sharma"}
    blob = json.dumps(entry)
    assert "anita.new@example.com" not in blob and "+919800000001" not in blob
    assert "anita.sharma@example.com" not in blob


def test_private_content_never_appears_in_the_log(admin_client, db):
    case = db.scalars(select(Case).where(Case.title == "Sharma v. Verma Traders")).one()
    admin_client.get(f"{API}/admin/cases/{case.id}")  # shows notes, messages and outcomes to the admin
    blob = json.dumps(log(admin_client))
    for private in ("cross-examination", "When can I expect the court to decide?", "Do I need to attend", "Settlement discussed", "After evidence and arguments", "Private note"):
        assert private not in blob, private


def test_only_administrators_can_read_it(client):
    from helpers import sign_in

    assert client.get(f"{API}/admin/audit").status_code == 401
    sign_in(client, "rohan.sharma@example.com")
    assert client.get(f"{API}/admin/audit").status_code == 403


def test_entries_cannot_be_changed_or_removed(admin_client, db):
    admin_client.get(f"{API}/admin/users/{uid(db, 'anita.sharma@example.com')}")
    entry = log(admin_client)["items"][0]
    for method in ("put", "patch", "delete"):
        assert getattr(admin_client, method)(f"{API}/admin/audit").status_code == 405
        assert getattr(admin_client, method)(f"{API}/admin/audit/{entry['id']}").status_code in (404, 405)
    assert admin_client.post(f"{API}/admin/audit").status_code == 405
    assert len(log(admin_client)["items"]) == 1


def test_the_helper_refuses_to_store_private_text():
    import pytest

    from mrcourt.services.audit import record

    with pytest.raises(ValueError):
        record(None, None, "case.view", "case", message="private words")  # type: ignore[arg-type]


def test_the_overview_shows_the_latest_entries(admin_client, db):
    target = uid(db, "anita.sharma@example.com")
    for _ in range(7):
        admin_client.get(f"{API}/admin/users/{target}")
    recent = admin_client.get(f"{API}/admin/overview").json()["recent_audit"]
    assert len(recent) == 5 and recent[0]["action"] == "user.view"
