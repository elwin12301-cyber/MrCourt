"""Contract tests for the client dashboard and the client's view of a case."""

import pytest
from sqlalchemy import select

from helpers import sign_in
from mrcourt.config import get_settings
from mrcourt.models import Case, Document

API = "/api/v1"
CLIENT = "anita.sharma@example.com"


def case_id_of(db, title="Sharma v. Verma Traders"):
    return str(db.scalars(select(Case).where(Case.title == title)).one().id)


def test_client_endpoints_require_sign_in(client):
    assert client.get(f"{API}/client/dashboard").status_code == 401


def test_advocates_cannot_use_client_endpoints(advocate_client, db):
    assert advocate_client.get(f"{API}/client/dashboard").status_code == 403
    assert advocate_client.get(f"{API}/client/cases/{case_id_of(db)}").status_code == 403


def test_dashboard_shape(petitioner_client):
    body = petitioner_client.get(f"{API}/client/dashboard").json()
    assert set(body) == {"cases", "unread_updates", "latest_updates"}
    assert [c["title"] for c in body["cases"]] == ["Sharma v. Verma Traders"]

    case = body["cases"][0]
    assert case["status"] == "hearing_scheduled"
    assert case["status_changed_at"] is not None
    assert case["court"] == "Saket District Court"
    assert case["next_hearing"]["court"] == "Saket District Court"
    assert case["next_hearing"]["scheduled_at"]
    assert case["lawyer"]["name"] == "Adv. Rohan Sharma"
    assert case["lawyer"]["verification_status"] == "verified"
    assert body["unread_updates"] == 1
    assert len(body["latest_updates"]) == 2


def test_next_hearing_has_a_general_description(petitioner_client):
    hearing = petitioner_client.get(f"{API}/client/dashboard").json()["cases"][0]["next_hearing"]
    description = hearing["description"]
    assert description["label"] == "General information"
    assert description["disclaimer"] == "Informational only, not legal advice."
    assert "witness" in description["text"].lower()


def test_lawyer_card_shows_only_the_details_the_advocate_filled_in(petitioner_client):
    lawyer = petitioner_client.get(f"{API}/client/dashboard").json()["cases"][0]["lawyer"]
    assert lawyer["phone"] == "+91 98100 12345"
    assert lawyer["office"] == "Chamber 14, Saket Courts, New Delhi"
    assert lawyer["email"] is None
    assert lawyer["available"] is True


def test_case_detail_shape(petitioner_client, db):
    detail = petitioner_client.get(f"{API}/client/cases/{case_id_of(db)}").json()
    assert set(detail) >= {
        "id", "title", "court", "status", "status_changed_at", "next_hearing", "lawyer",
        "hearings", "timeline", "documents", "access",
    }
    assert detail["access"]["advocate_name"] == "Adv. Rohan Sharma"
    assert detail["access"]["other_people_with_access"] == 1  # the second client; no name is shown
    assert detail["access"]["since"] is not None


def test_timeline_is_newest_first_and_only_visible_entries(petitioner_client, db):
    timeline = petitioner_client.get(f"{API}/client/cases/{case_id_of(db)}").json()["timeline"]
    times = [e["occurred_at"] for e in timeline]
    assert times == sorted(times, reverse=True)
    assert {e["kind"] for e in timeline} == {"update", "status_change", "hearing_scheduled", "outcome"}
    assert len(timeline) == 4  # the private outcome and the private note are not here


def test_only_shared_documents_and_outcomes_are_returned(petitioner_client, db):
    detail = petitioner_client.get(f"{API}/client/cases/{case_id_of(db)}").json()
    assert [d["file_name"] for d in detail["documents"]] == ["Legal notice.pdf"]
    outcomes = [h["outcome"] for h in detail["hearings"] if h["outcome"]]
    assert outcomes == ["Respondent appeared and was given time to reply."]
    assert len(detail["hearings"]) == 3  # dates are always shown, outcomes only when shared


def test_a_case_the_client_was_not_invited_to_is_404(petitioner_client, db):
    other = case_id_of(db, "State v. Imran Khan")
    assert petitioner_client.get(f"{API}/client/cases/{other}").status_code == 404


def test_a_client_with_no_cases_gets_an_empty_dashboard(client):
    client.post(
        f"{API}/auth/register",
        json={"role": "petitioner", "full_name": "No Cases", "email": "nocases@example.com", "password": "a-strong-password"},
    )
    body = client.get(f"{API}/client/dashboard").json()
    assert body["cases"] == [] and body["unread_updates"] == 0


def test_status_not_set_is_null(petitioner_client, db):
    case = db.scalars(select(Case).where(Case.title == "Sharma v. Verma Traders")).one()
    case.client_status = None
    case.client_status_changed_at = None
    db.commit()
    body = petitioner_client.get(f"{API}/client/cases/{case.id}").json()
    assert body["status"] is None and body["status_changed_at"] is None


def test_shared_document_downloads_and_internal_ones_do_not(petitioner_client, db, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path))
    case = db.scalars(select(Case).where(Case.title == "Sharma v. Verma Traders")).one()
    docs = {d.file_name: d for d in db.scalars(select(Document).where(Document.case_id == case.id))}
    shared, internal = docs["Legal notice.pdf"], docs["Cheque copy.pdf"]
    for doc in (shared, internal):
        target = tmp_path / doc.storage_key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"%PDF-1.4 test")

    ok = petitioner_client.get(f"{API}/client/cases/{case.id}/documents/{shared.id}/download")
    assert ok.status_code == 200 and ok.content.startswith(b"%PDF")
    refused = petitioner_client.get(f"{API}/client/cases/{case.id}/documents/{internal.id}/download")
    assert refused.status_code == 404


def test_glossary_is_available_to_signed_in_users(petitioner_client):
    terms = petitioner_client.get(f"{API}/glossary").json()
    assert {t["term"] for t in terms} >= {"CNR", "Hearing", "Adjournment"}
    assert all(t["meaning"] for t in terms)


@pytest.mark.parametrize("path", ["/cases", "/dashboard", "/drafts"])
def test_clients_cannot_use_advocate_endpoints(client, path):
    sign_in(client, CLIENT)
    assert client.get(f"{API}{path}").status_code in (403, 404)
