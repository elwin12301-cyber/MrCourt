"""Access control: who can see or change which case (FR-003, FR-019, FR-020, SC-009)."""

import uuid

from sqlalchemy import select

from helpers import sign_in
from mrcourt.models import ActivityEvent, Case, CaseInvitation, Hearing, User
from mrcourt.db.base import utcnow
from datetime import timedelta

API = "/api/v1"


def case_id_of(db, title):
    return str(db.scalars(select(Case).where(Case.title == title)).one().id)


def register_advocate(client, email):
    r = client.post(
        f"{API}/auth/register",
        json={"role": "advocate", "full_name": "Other Advocate", "email": email, "password": "another-strong-pw"},
    )
    assert r.status_code == 201


def test_another_advocate_cannot_see_or_change_a_case(client, db):
    case_id = case_id_of(db, "Sharma v. Verma Traders")
    register_advocate(client, "other@example.com")  # registering signs in as the new advocate
    assert client.get(f"{API}/cases").json() == []
    assert client.get(f"{API}/cases/{case_id}").status_code == 404
    assert client.patch(f"{API}/cases/{case_id}", json={"stage": "x"}).status_code == 404
    assert client.get(f"{API}/cases/{case_id}/documents").status_code == 404
    assert client.post(f"{API}/cases/{case_id}/hearings", json={"scheduled_at": "2030-01-01T10:00:00Z"}).status_code == 404


def test_petitioner_sees_only_invited_cases_read_only(petitioner_client, db):
    visible = petitioner_client.get(f"{API}/client/dashboard").json()["cases"]
    assert [c["title"] for c in visible] == ["Sharma v. Verma Traders"]

    not_invited = case_id_of(db, "State v. Imran Khan")
    assert petitioner_client.get(f"{API}/client/cases/{not_invited}").status_code == 404

    invited = visible[0]["id"]
    detail = petitioner_client.get(f"{API}/client/cases/{invited}")
    assert detail.status_code == 200
    assert "notes" not in detail.json(), "advocate's private notes are not part of the client view"

    # The advocate endpoints are closed to clients entirely (they return internal data).
    assert petitioner_client.get(f"{API}/cases").status_code == 403
    assert petitioner_client.get(f"{API}/cases/{invited}").status_code == 403
    assert petitioner_client.patch(f"{API}/cases/{invited}", json={"stage": "x"}).status_code == 403
    assert petitioner_client.post(f"{API}/cases", json={"title": "t", "cnr_number": "c", "court": "x"}).status_code == 403
    assert petitioner_client.post(f"{API}/cases/{invited}/hearings", json={"scheduled_at": "2030-01-01T10:00:00Z"}).status_code == 403


def test_invitation_lifecycle(client, db):
    case_id = case_id_of(db, "Mehta Constructions v. NHAI")
    sign_in(client, "rohan.sharma@example.com")
    invite = client.post(f"{API}/cases/{case_id}/invitations", json={"contact": "anita.sharma@example.com"})
    assert invite.status_code == 201
    invitation_id = invite.json()["id"]

    client.post(f"{API}/auth/logout")
    sign_in(client, "anita.sharma@example.com")
    assert case_id not in {c["id"] for c in client.get(f"{API}/client/dashboard").json()["cases"]}  # not until accepted
    pending = client.get(f"{API}/invitations").json()
    assert [p["case_title"] for p in pending] == ["Mehta Constructions v. NHAI"]
    assert client.post(f"{API}/invitations/{invitation_id}/accept").status_code == 200
    assert case_id in {c["id"] for c in client.get(f"{API}/client/dashboard").json()["cases"]}

    client.post(f"{API}/auth/logout")
    sign_in(client, "rohan.sharma@example.com")
    events = db.scalars(select(ActivityEvent).where(ActivityEvent.kind == "invite_accepted")).all()
    assert any("Anita Sharma accepted" in e.message for e in events)

    # Removing the invitation takes the case away from the petitioner again.
    assert client.delete(f"{API}/cases/{case_id}/invitations/{invitation_id}").status_code == 204
    client.post(f"{API}/auth/logout")
    sign_in(client, "anita.sharma@example.com")
    assert case_id not in {c["id"] for c in client.get(f"{API}/client/dashboard").json()["cases"]}


def test_only_the_invitee_can_accept(client, db):
    case_id = case_id_of(db, "Mehta Constructions v. NHAI")
    sign_in(client, "rohan.sharma@example.com")
    invitation_id = client.post(
        f"{API}/cases/{case_id}/invitations", json={"contact": "anita.sharma@example.com"}
    ).json()["id"]
    client.post(f"{API}/auth/logout")
    client.post(
        f"{API}/auth/register",
        json={"role": "petitioner", "full_name": "Someone Else", "email": "else@example.com", "password": "another-strong-pw"},
    )
    assert client.post(f"{API}/invitations/{invitation_id}/accept").status_code == 404


def test_invitation_to_unregistered_contact_links_on_registration(client, db):
    case_id = case_id_of(db, "Mehta Constructions v. NHAI")
    sign_in(client, "rohan.sharma@example.com")
    client.post(f"{API}/cases/{case_id}/invitations", json={"contact": "newcomer@example.com"})
    client.post(f"{API}/auth/logout")
    client.post(
        f"{API}/auth/register",
        json={"role": "petitioner", "full_name": "New Comer", "email": "newcomer@example.com", "password": "another-strong-pw"},
    )
    assert len(client.get(f"{API}/invitations").json()) == 1


def test_hearing_soon_is_derived_from_the_next_hearing(advocate_client, db):
    case = db.scalars(select(Case).where(Case.title == "Mehta Constructions v. NHAI")).one()
    assert next(c for c in advocate_client.get(f"{API}/cases").json() if c["id"] == str(case.id))["status"] == "active"
    db.add(Hearing(case_id=case.id, scheduled_at=utcnow() + timedelta(days=3)))
    db.commit()
    assert next(c for c in advocate_client.get(f"{API}/cases").json() if c["id"] == str(case.id))["status"] == "hearing_soon"


def test_unknown_case_id_is_404(advocate_client):
    assert advocate_client.get(f"{API}/cases/{uuid.uuid4()}").status_code == 404
    assert advocate_client.get(f"{API}/cases/not-a-uuid").status_code == 422
