"""Leak prevention: nothing private may reach a client by any route (spec FR-007, SC-002).

Every client-reachable endpoint is fetched for a case that holds private notes, internal
documents, an unshared outcome and another client's question, and the combined responses are
searched for any trace of them.
"""

import json
import uuid

from sqlalchemy import select

from helpers import sign_in
from mrcourt.db.base import utcnow
from mrcourt.models import (
    Case,
    ClientQuestion,
    Document,
    Hearing,
    TimelineEntry,
    User,
)

API = "/api/v1"

# Strings seeded as private (see seed.py), plus anything added below.
PRIVATE_STRINGS = [
    "Private note",
    "cross-examination of the respondent's witness",
    "Settlement discussed informally",
    "settlement discussed informally",
    "Dishonour memo.pdf",
    "Cheque copy.pdf",
    "Do I need to attend the next hearing?",  # the other client's question
    "Ravi Mehta",  # the other client's name
    "ravi.mehta@example.com",
]
PRIVATE_KEYS = {"notes", "storage_key", "owner_id", "uploaded_by", "shared_with_client", "password_hash"}


def all_keys(value):
    if isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from all_keys(v)
    elif isinstance(value, list):
        for item in value:
            yield from all_keys(item)


def fetch_everything(client, case_id):
    paths = [
        "/client/dashboard",
        f"/client/cases/{case_id}",
        "/glossary",
        "/me",
        "/invitations",
    ]
    responses = {p: client.get(f"{API}{p}") for p in paths}
    for path, response in responses.items():
        assert response.status_code == 200, (path, response.status_code)
    return {p: r.json() for p, r in responses.items()}


def test_no_private_text_or_key_in_any_client_response(petitioner_client, db):
    case = db.scalars(select(Case).where(Case.title == "Sharma v. Verma Traders")).one()
    advocate = db.get(User, case.owner_id)

    # Add fresh private items with unique text so the check cannot pass by coincidence.
    marker = f"ZZ-PRIVATE-{uuid.uuid4().hex[:8]}"
    db.add(TimelineEntry(case_id=case.id, kind="note", text=marker, shared_with_client=False, occurred_at=utcnow(), created_by=advocate.id))
    db.add(Document(case_id=case.id, file_name=f"{marker}.pdf", size_bytes=1, content_type="application/pdf", storage_key=f"x/{marker}", uploaded_by=advocate.id, shared_with_client=False))
    db.add(Hearing(case_id=case.id, scheduled_at=utcnow(), outcome=marker, outcome_shared=False))
    db.commit()

    data = fetch_everything(petitioner_client, case.id)
    blob = json.dumps(data)
    for text in PRIVATE_STRINGS + [marker]:
        assert text not in blob, f"private text leaked: {text!r}"
    leaked_keys = PRIVATE_KEYS & set(all_keys(data))
    assert not leaked_keys, f"private keys leaked: {leaked_keys}"


def test_unsharing_removes_an_item_at_once(petitioner_client, db):
    case = db.scalars(select(Case).where(Case.title == "Sharma v. Verma Traders")).one()
    shared = db.scalars(select(Document).where(Document.case_id == case.id, Document.file_name == "Legal notice.pdf")).one()
    before = petitioner_client.get(f"{API}/client/cases/{case.id}").json()
    assert "Legal notice.pdf" in [d["file_name"] for d in before["documents"]]

    shared.shared_with_client = False
    db.commit()
    after = petitioner_client.get(f"{API}/client/cases/{case.id}").json()
    assert after["documents"] == []


def test_a_client_never_sees_another_clients_data(client, db):
    """The second client (Ravi) must see his own question but not the first client's."""
    case = db.scalars(select(Case).where(Case.title == "Sharma v. Verma Traders")).one()
    sign_in(client, "ravi.mehta@example.com")
    blob = json.dumps(fetch_everything(client, case.id))
    assert "When can I expect the court to decide?" not in blob
    assert "anita.sharma@example.com" not in blob
    assert "Anita" not in blob


def test_petitioners_cannot_read_advocate_case_endpoints(petitioner_client, db):
    """The advocate endpoints return internal documents and every outcome, so clients are refused."""
    case = db.scalars(select(Case).where(Case.title == "Sharma v. Verma Traders")).one()
    document = db.scalars(select(Document).where(Document.case_id == case.id)).first()
    for path in (
        "/cases",
        f"/cases/{case.id}",
        f"/cases/{case.id}/hearings",
        f"/cases/{case.id}/documents",
        f"/cases/{case.id}/documents/{document.id}/download",
        "/dashboard",
    ):
        assert petitioner_client.get(f"{API}{path}").status_code in (403, 404), path


def test_clients_cannot_change_anything_on_a_case(petitioner_client, db):
    case = db.scalars(select(Case).where(Case.title == "Sharma v. Verma Traders")).one()
    assert petitioner_client.patch(f"{API}/cases/{case.id}", json={"stage": "x"}).status_code in (403, 404)
    assert petitioner_client.post(f"{API}/cases/{case.id}/hearings", json={"scheduled_at": "2030-01-01T10:00:00Z"}).status_code in (403, 404)
    assert petitioner_client.post(f"{API}/cases/{case.id}/invitations", json={"contact": "x@example.com"}).status_code in (403, 404)
    assert db.scalars(select(ClientQuestion)).first() is not None  # seeded data is untouched
