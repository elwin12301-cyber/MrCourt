"""Draft permissions, versioning and the "nothing leaves without an explicit action" rule."""

from sqlalchemy import select

from helpers import sign_in
from mrcourt.models import Case, Draft, DraftExport

API = "/api/v1"


def test_petitioners_cannot_use_drafts(petitioner_client):
    assert petitioner_client.get(f"{API}/drafts").status_code == 403
    assert petitioner_client.post(f"{API}/drafts", json={"template": "notice"}).status_code == 403


def test_another_advocate_cannot_read_or_change_my_draft(client, db):
    sign_in(client, "rohan.sharma@example.com")
    draft_id = client.post(f"{API}/drafts", json={"template": "notice"}).json()["id"]
    client.post(f"{API}/auth/logout")
    client.post(
        f"{API}/auth/register",
        json={"role": "advocate", "full_name": "Other", "email": "other2@example.com", "password": "another-strong-pw"},
    )
    assert client.get(f"{API}/drafts/{draft_id}").status_code == 404
    assert client.put(f"{API}/drafts/{draft_id}", json={"body": "x"}).status_code == 404
    assert client.post(f"{API}/drafts/{draft_id}/export", json={"format": "pdf"}).status_code == 404


def test_cannot_draft_for_a_case_you_do_not_own(client, db):
    case = db.scalars(select(Case)).first()
    client.post(
        f"{API}/auth/register",
        json={"role": "advocate", "full_name": "Other", "email": "other3@example.com", "password": "another-strong-pw"},
    )
    response = client.post(f"{API}/drafts", json={"template": "notice", "case_id": str(case.id)})
    assert response.status_code == 404


def test_generating_or_saving_never_records_an_export(advocate_client, db):
    draft_id = advocate_client.post(f"{API}/drafts", json={"template": "bail"}).json()["id"]
    advocate_client.put(f"{API}/drafts/{draft_id}", json={"body": "Updated"})
    assert db.scalars(select(DraftExport)).all() == []


def test_export_is_recorded_only_when_requested(advocate_client, db):
    draft_id = advocate_client.post(f"{API}/drafts", json={"template": "bail"}).json()["id"]
    advocate_client.post(f"{API}/drafts/{draft_id}/export", json={"format": "docx"})
    exports = db.scalars(select(DraftExport)).all()
    assert [e.format for e in exports] == ["docx"]


def test_failed_export_leaves_the_draft_unchanged(advocate_client, db, monkeypatch):
    from mrcourt.services import export

    draft_id = advocate_client.post(f"{API}/drafts", json={"template": "reply"}).json()["id"]
    before = advocate_client.get(f"{API}/drafts/{draft_id}").json()

    def boom(*args, **kwargs):
        raise RuntimeError("renderer crashed")

    monkeypatch.setattr(export, "to_pdf", boom)
    response = advocate_client.post(f"{API}/drafts/{draft_id}/export", json={"format": "pdf"})
    assert response.status_code == 500
    assert advocate_client.get(f"{API}/drafts/{draft_id}").json() == before
    assert db.scalars(select(DraftExport)).all() == []


def test_dashboard_counts_unreviewed_drafts(advocate_client, db):
    before = advocate_client.get(f"{API}/dashboard").json()["drafts_to_review"]
    draft_id = advocate_client.post(f"{API}/drafts", json={"template": "notice"}).json()["id"]
    assert advocate_client.get(f"{API}/dashboard").json()["drafts_to_review"] == before + 1
    advocate_client.put(f"{API}/drafts/{draft_id}", json={"body": "Reviewed text"})
    assert advocate_client.get(f"{API}/dashboard").json()["drafts_to_review"] == before
    assert db.scalars(select(Draft)).first() is not None
