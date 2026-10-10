"""Deactivation and export with client data (spec FR-017, FR-012; extends feature 001's rules)."""

from sqlalchemy import func, select

from helpers import sign_in
from mrcourt.models import (
    Case,
    CaseInvitation,
    ClientQuestion,
    ClientUpdate,
    TimelineEntry,
    User,
)

API = "/api/v1"
DEACTIVATE = {"acknowledge_case_retention": True}


def n(db, model, **where):
    q = select(func.count()).select_from(model)
    for k, v in where.items():
        q = q.where(getattr(model, k) == v)
    return db.scalar(q)


def user(db, email):
    return db.scalars(select(User).where(User.email == email)).one()


def test_a_deactivated_client_loses_their_messages_and_updates_only(client, db):
    ravi, anita = user(db, "ravi.mehta@example.com"), user(db, "anita.sharma@example.com")
    case = db.scalars(select(Case).where(Case.title == "Sharma v. Verma Traders")).one()
    anita_questions = n(db, ClientQuestion, client_id=anita.id)
    anita_updates = n(db, ClientUpdate, client_id=anita.id)
    timeline_before = n(db, TimelineEntry, case_id=case.id)
    assert n(db, ClientQuestion, client_id=ravi.id) == 1 and n(db, ClientUpdate, client_id=ravi.id) >= 1

    sign_in(client, "ravi.mehta@example.com")
    assert client.post(f"{API}/me/deactivate", json=DEACTIVATE).status_code == 204
    db.expire_all()

    assert n(db, ClientQuestion, client_id=ravi.id) == 0
    assert n(db, ClientUpdate, client_id=ravi.id) == 0
    accepted = n(db, CaseInvitation, invitee_user_id=ravi.id, status="accepted")
    assert accepted == 0
    # Everyone else's data and the advocate's case records are untouched.
    assert n(db, ClientQuestion, client_id=anita.id) == anita_questions
    assert n(db, ClientUpdate, client_id=anita.id) == anita_updates
    assert n(db, TimelineEntry, case_id=case.id) == timeline_before
    assert db.get(Case, case.id) is not None


def test_a_deactivated_client_is_gone_from_the_advocates_inbox(client, db):
    case = db.scalars(select(Case).where(Case.title == "Sharma v. Verma Traders")).one()
    sign_in(client, "ravi.mehta@example.com")
    client.post(f"{API}/me/deactivate", json=DEACTIVATE)
    client.post(f"{API}/auth/logout")
    sign_in(client, "rohan.sharma@example.com")
    names = {q["client_name"] for q in client.get(f"{API}/cases/{case.id}/client-questions").json()}
    assert names == {"Anita Sharma"}


def test_the_clients_view_after_the_advocate_deactivates(client, db):
    case = db.scalars(select(Case).where(Case.title == "Sharma v. Verma Traders")).one()
    sign_in(client, "rohan.sharma@example.com")
    assert client.post(f"{API}/me/deactivate", json=DEACTIVATE).status_code == 204

    client.post(f"{API}/auth/logout")
    sign_in(client, "anita.sharma@example.com")
    detail = client.get(f"{API}/client/cases/{case.id}").json()
    assert detail["lawyer"]["available"] is False
    assert detail["lawyer"]["name"] == "Your lawyer"
    assert detail["lawyer"]["phone"] is None and detail["lawyer"]["office"] is None  # contact card removed
    assert detail["title"] == "Sharma v. Verma Traders"  # the case record is kept
    sent = client.post(f"{API}/client/cases/{case.id}/questions", json={"kind": "question", "text": "Hello?"})
    assert sent.status_code == 409


def test_a_clients_data_export_includes_their_messages_and_updates(petitioner_client):
    body = petitioner_client.get(f"{API}/me/data-export").json()
    assert [q["text"] for q in body["client_questions"]] == ["When can I expect the court to decide?"]
    assert body["client_questions"][0]["reply"].startswith("After evidence and arguments")
    assert len(body["client_updates"]) == 2
    assert "Ravi" not in str(body) and "Do I need to attend" not in str(body)


def test_an_advocates_export_includes_client_facing_settings(advocate_client):
    body = advocate_client.get(f"{API}/me/data-export").json()
    assert body["client_contact"]["phone"] == "+91 98100 12345"
    sharma = next(c for c in body["cases"] if c["title"] == "Sharma v. Verma Traders")
    assert sharma["client_status"] == "hearing_scheduled"
    assert any(entry["kind"] == "note" for entry in sharma["timeline"])  # their own private notes are theirs
