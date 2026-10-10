"""Every administrator action that changes an account or opens private content is audited exactly once;
overview lists are not (spec FR-013, SC-002)."""

from sqlalchemy import func, select

from helpers import sign_in
from mrcourt.config import get_settings
from mrcourt.models import AuditEntry, Case, Document, User

API = "/api/v1"


def entries(db):
    db.expire_all()
    return list(db.scalars(select(AuditEntry).order_by(AuditEntry.created_at)))


def actions(db):
    return [e.action for e in entries(db)]


def uid(db, email):
    return str(db.scalars(select(User).where(User.email == email)).one().id)


def test_lists_and_overviews_write_nothing(admin_client, db):
    for path in ("/admin/overview", "/admin/users?role=advocate", "/admin/users?role=petitioner&q=a", "/admin/cases", "/admin/cases?q=x", "/admin/verifications", "/admin/audit"):
        assert admin_client.get(f"{API}{path}").status_code == 200, path
    assert actions(db) == []


def test_opening_a_person_is_audited_once(admin_client, db):
    target = uid(db, "anita.sharma@example.com")
    admin_client.get(f"{API}/admin/users/{target}")
    [entry] = entries(db)
    assert (entry.action, entry.target_type, str(entry.target_id)) == ("user.view", "user", target)
    assert str(entry.admin_id) == uid(db, "admin@example.com")


def test_opening_a_case_in_full_is_audited_each_time(admin_client, db):
    case = db.scalars(select(Case).where(Case.title == "Sharma v. Verma Traders")).one()
    admin_client.get(f"{API}/admin/cases/{case.id}")
    admin_client.get(f"{API}/admin/cases/{case.id}")
    assert actions(db) == ["case.view", "case.view"]
    assert all(e.target_type == "case" and e.target_id == case.id for e in entries(db))


def test_a_document_download_is_audited(admin_client, db, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path))
    doc = db.scalars(select(Document).where(Document.file_name == "Cheque copy.pdf")).one()
    path = tmp_path / doc.storage_key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4 x")
    admin_client.get(f"{API}/admin/cases/{doc.case_id}/documents/{doc.id}/download")
    [entry] = entries(db)
    assert entry.action == "document.download" and entry.target_id == doc.id
    assert entry.detail["file_name"] == "Cheque copy.pdf"


def test_every_account_action_is_audited_once(admin_client, db):
    target = uid(db, "anita.sharma@example.com")
    admin_client.patch(f"{API}/admin/users/{target}", json={"full_name": "Anita S."})
    admin_client.post(f"{API}/admin/users/{target}/suspend", json={"reason": "Check"})
    admin_client.post(f"{API}/admin/users/{target}/reactivate")
    admin_client.post(f"{API}/admin/users/{target}/sign-out")
    assert actions(db) == ["user.update", "user.suspend", "user.reactivate", "user.sign_out"]


def test_refused_actions_are_not_logged_as_done(admin_client, db):
    admin_id = uid(db, "admin@example.com")
    admin_client.post(f"{API}/admin/users/{admin_id}/suspend", json={"reason": "No"})
    admin_client.patch(f"{API}/admin/users/{uid(db, 'anita.sharma@example.com')}", json={"email": "ravi.mehta@example.com"})
    assert actions(db) == []


def test_a_failed_action_leaves_neither_a_change_nor_an_entry(admin_client, db):
    target = uid(db, "anita.sharma@example.com")
    admin_client.patch(f"{API}/admin/users/{target}", json={"phone": ""}).status_code  # allowed (email remains)
    before = db.scalar(select(func.count()).select_from(AuditEntry))
    admin_client.patch(f"{API}/admin/users/{target}", json={"email": ""})  # would leave no sign-in method
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(AuditEntry)) == before
    assert db.scalars(select(User).where(User.email == "anita.sharma@example.com")).one() is not None


def test_other_people_never_create_entries(client, db):
    sign_in(client, "rohan.sharma@example.com")
    client.get(f"{API}/cases")
    client.post(f"{API}/questions", json={"text": "What is Section 138?"})
    assert actions(db) == []
