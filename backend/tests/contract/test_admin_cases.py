"""The administrator can see every case in full, read-only (spec US3)."""

import uuid

import pytest
from sqlalchemy import select

from mrcourt.config import get_settings
from mrcourt.models import AuditEntry, Case, Document

API = "/api/v1"


def case_id(db, title="Sharma v. Verma Traders") -> str:
    return str(db.scalars(select(Case).where(Case.title == title)).one().id)


def test_every_case_is_listed_with_its_advocate(admin_client):
    rows = admin_client.get(f"{API}/admin/cases").json()
    assert len(rows) == 5
    assert set(rows[0]) == {"id", "title", "court", "status", "advocate_name", "client_count", "next_hearing_at"}
    sharma = next(r for r in rows if r["title"] == "Sharma v. Verma Traders")
    assert sharma["advocate_name"] == "Adv. Rohan Sharma" and sharma["client_count"] == 2


def test_search_cases(admin_client):
    titles = lambda **p: {r["title"] for r in admin_client.get(f"{API}/admin/cases", params=p).json()}  # noqa: E731
    assert titles(q="imran") == {"State v. Imran Khan"}
    assert titles(q="rohan") and len(titles(q="rohan")) == 5  # by advocate name
    assert titles(q="patiala") == {"Gupta v. Gupta Estate"}
    assert titles(q="no such case") == set()


def test_the_full_view_shows_private_content(admin_client, db):
    full = admin_client.get(f"{API}/admin/cases/{case_id(db)}").json()

    assert full["title"] == "Sharma v. Verma Traders" and full["advocate"]["name"] == "Adv. Rohan Sharma"
    assert "prepare cross-examination" in full["notes"]  # the advocate's private notes

    docs = {d["file_name"]: d["shared_with_client"] for d in full["documents"]}
    assert docs == {"Dishonour memo.pdf": False, "Legal notice.pdf": True, "Cheque copy.pdf": False}

    outcomes = {h["outcome"]: h["outcome_shared"] for h in full["hearings"] if h["outcome"]}
    assert outcomes == {
        "Respondent appeared and was given time to reply.": True,
        "Settlement discussed informally; client undecided.": False,  # not shared with the client
    }

    timeline = {e["text"]: e["shared_with_client"] for e in full["timeline"]}
    assert any(not shared for shared in timeline.values())
    assert any("Private note" in text for text in timeline)

    assert {c["name"] for c in full["clients"]} == {"Anita Sharma", "Ravi Mehta"}
    questions = {q["text"]: q["client_name"] for q in full["client_questions"]}
    assert questions == {
        "When can I expect the court to decide?": "Anita Sharma",
        "Do I need to attend the next hearing?": "Ravi Mehta",
    }
    assert any(q["reply_text"] for q in full["client_questions"])


def test_unknown_case_is_404(admin_client):
    assert admin_client.get(f"{API}/admin/cases/{uuid.uuid4()}").status_code == 404


def test_the_case_view_is_read_only(admin_client, db):
    path = f"{API}/admin/cases/{case_id(db)}"
    for method in ("put", "patch", "delete"):
        assert getattr(admin_client, method)(path).status_code == 405, method
    assert admin_client.post(path).status_code == 405
    # No other admin route edits, deletes, reassigns or closes a case.
    for suffix in ("close", "reassign", "delete"):
        assert admin_client.post(f"{path}/{suffix}").status_code in (404, 405)


def test_the_administrator_cannot_change_a_case_through_the_advocate_endpoints(admin_client, db):
    path = f"{API}/cases/{case_id(db)}"
    assert admin_client.patch(path, json={"stage": "x"}).status_code == 403
    assert admin_client.post(f"{path}/hearings", json={"scheduled_at": "2031-01-01T10:00:00Z"}).status_code == 403
    assert admin_client.put(f"{path}/client-status", json={"status": "closed"}).status_code == 403


def test_documents_download_for_the_administrator(admin_client, db, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path))
    internal = db.scalars(select(Document).where(Document.file_name == "Cheque copy.pdf")).one()  # not shared
    target = tmp_path / internal.storage_key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"%PDF-1.4 secret")
    response = admin_client.get(f"{API}/admin/cases/{internal.case_id}/documents/{internal.id}/download")
    assert response.status_code == 200 and response.content.startswith(b"%PDF")


def test_a_missing_file_or_wrong_case_is_404(admin_client, db):
    doc = db.scalars(select(Document)).first()
    assert admin_client.get(f"{API}/admin/cases/{doc.case_id}/documents/{doc.id}/download").status_code == 404  # no file on disk
    other = case_id(db, "State v. Imran Khan")
    assert admin_client.get(f"{API}/admin/cases/{other}/documents/{doc.id}/download").status_code == 404


@pytest.mark.parametrize("email", ["rohan.sharma@example.com", "anita.sharma@example.com"])
def test_nobody_else_can_use_these_endpoints(client, db, email):
    from helpers import sign_in

    sign_in(client, email)
    cid = case_id(db)
    doc = db.scalars(select(Document)).first()
    assert client.get(f"{API}/admin/cases").status_code == 403
    assert client.get(f"{API}/admin/cases/{cid}").status_code == 403
    assert client.get(f"{API}/admin/cases/{cid}/documents/{doc.id}/download").status_code == 403
    assert db.scalars(select(AuditEntry)).first() is None
