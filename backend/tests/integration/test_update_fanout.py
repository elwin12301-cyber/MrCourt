"""Who gets which notice, and who never does (spec FR-010, SC-004, edge cases)."""

import json

from sqlalchemy import func, select

from helpers import sign_in
from mrcourt.models import Case, CaseInvitation, ClientQuestion, ClientUpdate, User

API = "/api/v1"


def case_of(db):
    return db.scalars(select(Case).where(Case.title == "Sharma v. Verma Traders")).one()


def switch(client, email):
    client.post(f"{API}/auth/logout")
    sign_in(client, email)


def unread(client):
    return client.get(f"{API}/client/updates").json()["unread_count"]


def count(db, **where):
    q = select(func.count()).select_from(ClientUpdate)
    for k, v in where.items():
        q = q.where(getattr(ClientUpdate, k) == v)
    return db.scalar(q)


def test_every_visible_change_notifies_every_accepted_client(advocate_client, db):
    case = case_of(db)
    before = count(db)
    advocate_client.put(f"{API}/cases/{case.id}/client-status", json={"status": "awaiting_order"})
    advocate_client.post(f"{API}/cases/{case.id}/client-updates", json={"message": "Order reserved."})
    advocate_client.post(f"{API}/cases/{case.id}/hearings", json={"scheduled_at": "2031-01-05T10:00:00Z"})
    assert count(db) == before + 3 * 2  # three events, two clients


def test_a_private_change_notifies_nobody(advocate_client, db):
    case = case_of(db)
    before = count(db)
    advocate_client.post(f"{API}/cases/{case.id}/timeline", json={"text": "Private reminder."})
    hearing = case.hearings[0]
    advocate_client.put(f"{API}/cases/{case.id}/hearings/{hearing.id}/outcome", json={"outcome": "Heard briefly.", "shared": False})
    assert count(db) == before


def test_a_pending_invitee_is_not_notified(advocate_client, db):
    case = case_of(db)
    advocate_client.post(f"{API}/cases/{case.id}/invitations", json={"contact": "not-yet@example.com"})
    before = count(db)
    advocate_client.post(f"{API}/cases/{case.id}/client-updates", json={"message": "Hello."})
    assert count(db) == before + 2  # the two accepted clients only


def test_read_state_is_per_client(client, db):
    case = case_of(db)
    sign_in(client, "rohan.sharma@example.com")
    client.post(f"{API}/cases/{case.id}/client-updates", json={"message": "Bring photo ID."})

    switch(client, "anita.sharma@example.com")
    assert unread(client) == 2
    client.post(f"{API}/client/updates/read-all")
    assert unread(client) == 0

    switch(client, "ravi.mehta@example.com")
    assert unread(client) == 2  # his own are untouched


def test_a_reply_notifies_only_the_client_who_asked(client, db):
    case = case_of(db)
    ravi = db.scalars(select(User).where(User.email == "ravi.mehta@example.com")).one()
    anita = db.scalars(select(User).where(User.email == "anita.sharma@example.com")).one()
    ravi_before, anita_before = count(db, client_id=ravi.id), count(db, client_id=anita.id)

    sign_in(client, "rohan.sharma@example.com")
    waiting = db.scalars(select(ClientQuestion).where(ClientQuestion.client_id == ravi.id)).one()
    client.post(f"{API}/client-questions/{waiting.id}/reply", json={"text": "Yes, please attend."})

    assert count(db, client_id=ravi.id) == ravi_before + 1
    assert count(db, client_id=anita.id) == anita_before
    notice = db.scalars(select(ClientUpdate).where(ClientUpdate.kind == "question_reply")).one()
    assert notice.client_id == ravi.id
    assert "Yes, please attend." not in notice.message, "the notice does not carry the reply itself"
    assert case.title in notice.message


def test_removing_a_client_deletes_their_updates_but_not_the_others(client, db):
    case = case_of(db)
    ravi = db.scalars(select(User).where(User.email == "ravi.mehta@example.com")).one()
    anita = db.scalars(select(User).where(User.email == "anita.sharma@example.com")).one()
    anita_updates = count(db, client_id=anita.id)

    sign_in(client, "rohan.sharma@example.com")
    invitation = db.scalars(select(CaseInvitation).where(CaseInvitation.case_id == case.id, CaseInvitation.invitee_user_id == ravi.id)).one()
    assert client.delete(f"{API}/cases/{case.id}/invitations/{invitation.id}").status_code == 204

    db.expire_all()
    assert count(db, client_id=ravi.id) == 0
    assert count(db, client_id=anita.id) == anita_updates


def test_notices_never_contain_private_text(advocate_client, db):
    case = case_of(db)
    advocate_client.post(f"{API}/cases/{case.id}/timeline", json={"text": "SECRET-NOTE-TEXT"})
    advocate_client.put(f"{API}/cases/{case.id}/client-status", json={"status": "closed"})
    messages = " ".join(m for (m,) in db.execute(select(ClientUpdate.message)))
    assert "SECRET-NOTE-TEXT" not in messages


def test_the_updates_list_never_leaks_other_clients_notices(client, db):
    sign_in(client, "anita.sharma@example.com")
    blob = json.dumps(client.get(f"{API}/client/updates").json())
    assert "Ravi" not in blob
