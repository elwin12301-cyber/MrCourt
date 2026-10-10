"""Contract tests for the advocate-side controls over the client view."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from helpers import sign_in
from mrcourt.db.base import utcnow
from mrcourt.models import Case, ClientUpdate, Document, Hearing

API = "/api/v1"
ADVOCATE = "rohan.sharma@example.com"
CLIENT = "anita.sharma@example.com"


def switch(client, email):
    client.post(f"{API}/auth/logout")
    sign_in(client, email)


def case_id_of(db, title="Sharma v. Verma Traders"):
    return str(db.scalars(select(Case).where(Case.title == title)).one().id)


def client_sees(client, case_id):
    """The client's view of a case, as that client."""
    switch(client, CLIENT)
    return client.get(f"{API}/client/cases/{case_id}").json()


# ---- status ---------------------------------------------------------------------------------


def test_set_client_status(advocate_client, db):
    case_id = case_id_of(db)
    response = advocate_client.put(f"{API}/cases/{case_id}/client-status", json={"status": "awaiting_order"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "awaiting_order" and body["changed_at"]
    assert client_sees(advocate_client, case_id)["status"] == "awaiting_order"


def test_status_must_be_one_of_the_four(advocate_client, db):
    case_id = case_id_of(db)
    for bad in ("evidence_stage", "", "Closed"):
        assert advocate_client.put(f"{API}/cases/{case_id}/client-status", json={"status": bad}).status_code == 422


# ---- updates and timeline -------------------------------------------------------------------


def test_post_a_client_update(advocate_client, db):
    case_id = case_id_of(db)
    response = advocate_client.post(f"{API}/cases/{case_id}/client-updates", json={"message": "Please bring the original cheque."})
    assert response.status_code == 201
    assert "Please bring the original cheque." in client_sees(advocate_client, case_id)["timeline"][0]["text"]


@pytest.mark.parametrize("message", ["", "   ", "x" * 1001])
def test_client_update_must_be_short_and_not_empty(advocate_client, db, message):
    assert advocate_client.post(f"{API}/cases/{case_id_of(db)}/client-updates", json={"message": message}).status_code == 422


def test_internal_timeline_includes_private_entries(advocate_client, db):
    entries = advocate_client.get(f"{API}/cases/{case_id_of(db)}/timeline").json()
    assert {"id", "kind", "text", "occurred_at", "shared_with_client"} <= set(entries[0])
    assert any(not e["shared_with_client"] for e in entries)
    times = [e["occurred_at"] for e in entries]
    assert times == sorted(times, reverse=True)


def test_notes_are_private_unless_shared(advocate_client, db):
    case_id = case_id_of(db)
    private = advocate_client.post(f"{API}/cases/{case_id}/timeline", json={"text": "Call the registry on Monday."})
    assert private.status_code == 201 and private.json()["shared_with_client"] is False
    shared = advocate_client.post(f"{API}/cases/{case_id}/timeline", json={"text": "Court has fixed a new date.", "shared_with_client": True})
    assert shared.json()["shared_with_client"] is True

    texts = [e["text"] for e in client_sees(advocate_client, case_id)["timeline"]]
    assert "Court has fixed a new date." in texts and "Call the registry on Monday." not in texts


def test_share_and_unshare_a_note(advocate_client, db):
    case_id = case_id_of(db)
    note = advocate_client.post(f"{API}/cases/{case_id}/timeline", json={"text": "A note for later."}).json()
    on = advocate_client.put(f"{API}/cases/{case_id}/timeline/{note['id']}/sharing", json={"shared": True})
    assert on.status_code == 200
    assert "A note for later." in [e["text"] for e in client_sees(advocate_client, case_id)["timeline"]]

    switch(advocate_client, ADVOCATE)
    advocate_client.put(f"{API}/cases/{case_id}/timeline/{note['id']}/sharing", json={"shared": False})
    assert "A note for later." not in [e["text"] for e in client_sees(advocate_client, case_id)["timeline"]]


def test_status_changes_and_hearing_dates_cannot_be_hidden(advocate_client, db):
    case_id = case_id_of(db)
    entries = advocate_client.get(f"{API}/cases/{case_id}/timeline").json()
    always = next(e for e in entries if e["kind"] == "status_change")
    response = advocate_client.put(f"{API}/cases/{case_id}/timeline/{always['id']}/sharing", json={"shared": False})
    assert response.status_code == 422


# ---- documents and outcomes -----------------------------------------------------------------


def test_share_a_document(advocate_client, db):
    case_id = case_id_of(db)
    doc = db.scalars(select(Document).where(Document.file_name == "Cheque copy.pdf")).one()
    response = advocate_client.put(f"{API}/cases/{case_id}/documents/{doc.id}/sharing", json={"shared": True})
    assert response.status_code == 200
    names = [d["file_name"] for d in client_sees(advocate_client, case_id)["documents"]]
    assert "Cheque copy.pdf" in names


def test_sharing_an_unknown_document_is_404(advocate_client, db):
    import uuid

    response = advocate_client.put(f"{API}/cases/{case_id_of(db)}/documents/{uuid.uuid4()}/sharing", json={"shared": True})
    assert response.status_code == 404


def test_record_and_share_a_hearing_outcome(advocate_client, db):
    case = db.scalars(select(Case).where(Case.title == "Sharma v. Verma Traders")).one()
    hearing = db.scalars(select(Hearing).where(Hearing.case_id == case.id, Hearing.purpose == "First hearing")).one()
    private = advocate_client.put(f"{API}/cases/{case.id}/hearings/{hearing.id}/outcome", json={"outcome": "Adjourned to a later date."})
    assert private.status_code == 200
    seen = client_sees(advocate_client, str(case.id))
    assert "Adjourned to a later date." not in str(seen)

    switch(advocate_client, ADVOCATE)
    advocate_client.put(f"{API}/cases/{case.id}/hearings/{hearing.id}/outcome", json={"outcome": "Adjourned to a later date.", "shared": True})
    seen = client_sees(advocate_client, str(case.id))
    assert [h["outcome"] for h in seen["hearings"] if h["id"] == str(hearing.id)] == ["Adjourned to a later date."]


def test_hearings_scheduled_and_moved_reach_the_client(advocate_client, db):
    case_id = case_id_of(db)
    when = (utcnow() + timedelta(days=30)).replace(microsecond=0)
    created = advocate_client.post(f"{API}/cases/{case_id}/hearings", json={"scheduled_at": when.isoformat(), "purpose": "Arguments"})
    assert created.status_code == 201
    moved = advocate_client.patch(f"{API}/cases/{case_id}/hearings/{created.json()['id']}", json={"scheduled_at": (when + timedelta(days=7)).isoformat()})
    assert moved.status_code == 200

    kinds = [e["kind"] for e in client_sees(advocate_client, case_id)["timeline"]]
    assert "hearing_scheduled" in kinds and "hearing_rescheduled" in kinds


# ---- clients and contact card ---------------------------------------------------------------


def test_invitations_list_for_the_advocate(advocate_client, db):
    items = advocate_client.get(f"{API}/cases/{case_id_of(db)}/invitations").json()
    assert {i["status"] for i in items} == {"accepted"}
    assert len(items) == 2 and all(i["accepted_at"] for i in items)
    assert {"Anita Sharma", "Ravi Mehta"} == {i["contact_or_name"] for i in items}


def test_contact_card_is_shown_only_for_filled_fields(advocate_client, db):
    response = advocate_client.put(f"{API}/me/client-contact", json={"phone": "+91 99999 00000", "email": "", "office": None})
    assert response.status_code == 200
    assert response.json() == {"phone": "+91 99999 00000", "email": None, "office": None}
    switch(advocate_client, CLIENT)
    lawyer = advocate_client.get(f"{API}/client/dashboard").json()["cases"][0]["lawyer"]
    assert lawyer["phone"] == "+91 99999 00000" and lawyer["email"] is None and lawyer["office"] is None


def test_only_advocates_have_a_contact_card(petitioner_client):
    assert petitioner_client.put(f"{API}/me/client-contact", json={"phone": "1"}).status_code == 403


# ---- who may call these ---------------------------------------------------------------------


def test_clients_are_refused_everywhere_here(petitioner_client, db):
    case_id = case_id_of(db)
    doc = db.scalars(select(Document)).first()
    calls = [
        ("put", f"/cases/{case_id}/client-status", {"status": "closed"}),
        ("post", f"/cases/{case_id}/client-updates", {"message": "hi"}),
        ("get", f"/cases/{case_id}/timeline", None),
        ("post", f"/cases/{case_id}/timeline", {"text": "x"}),
        ("put", f"/cases/{case_id}/documents/{doc.id}/sharing", {"shared": True}),
        ("get", f"/cases/{case_id}/invitations", None),
    ]
    for method, path, body in calls:
        response = getattr(petitioner_client, method)(f"{API}{path}", **({"json": body} if body is not None else {}))
        assert response.status_code in (403, 404), (method, path, response.status_code)


def test_another_advocate_gets_404(client, db):
    case_id = case_id_of(db)
    client.post(
        f"{API}/auth/register",
        json={"role": "advocate", "full_name": "Other", "email": "other-adv@example.com", "password": "a-strong-password"},
    )
    assert client.put(f"{API}/cases/{case_id}/client-status", json={"status": "closed"}).status_code == 404
    assert client.get(f"{API}/cases/{case_id}/timeline").status_code == 404
    assert client.get(f"{API}/cases/{case_id}/invitations").status_code == 404
    assert db.scalars(select(ClientUpdate)).first() is not None


def test_advocate_case_detail_carries_what_the_controls_need(advocate_client, db):
    detail = advocate_client.get(f"{API}/cases/{case_id_of(db)}").json()
    assert detail["client_status"] == "hearing_scheduled" and detail["client_status_changed_at"]
    assert {d["file_name"]: d["shared_with_client"] for d in detail["documents"]} == {
        "Dishonour memo.pdf": False, "Legal notice.pdf": True, "Cheque copy.pdf": False,
    }
    assert any(h["outcome_shared"] for h in detail["hearings"])
    assert any(h["outcome"] and not h["outcome_shared"] for h in detail["hearings"])


def test_advocate_can_read_back_their_contact_card(advocate_client):
    card = advocate_client.get(f"{API}/me/client-contact").json()
    assert card == {"phone": "+91 98100 12345", "email": None, "office": "Chamber 14, Saket Courts, New Delhi"}
