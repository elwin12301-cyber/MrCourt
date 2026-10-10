"""The rules that keep the client view safe and honest (spec FR-006, FR-010, FR-014, SC-002)."""

import uuid

from sqlalchemy import func, select

from helpers import sign_in
from mrcourt.models import Case, ClientUpdate, Document, TimelineEntry

API = "/api/v1"


def case_of(db, title="Sharma v. Verma Traders"):
    return db.scalars(select(Case).where(Case.title == title)).one()


def updates(db):
    return db.scalar(select(func.count()).select_from(ClientUpdate))


def test_sharing_a_document_notifies_every_client_once(advocate_client, db):
    case = case_of(db)
    doc = db.scalars(select(Document).where(Document.case_id == case.id, Document.file_name == "Cheque copy.pdf")).one()
    before = updates(db)
    advocate_client.put(f"{API}/cases/{case.id}/documents/{doc.id}/sharing", json={"shared": True})
    assert updates(db) == before + 2  # two accepted clients on this case

    # Sharing again changes nothing and does not notify twice.
    advocate_client.put(f"{API}/cases/{case.id}/documents/{doc.id}/sharing", json={"shared": True})
    assert updates(db) == before + 2


def test_the_notice_does_not_name_the_file(advocate_client, db):
    case = case_of(db)
    doc = db.scalars(select(Document).where(Document.case_id == case.id, Document.file_name == "Cheque copy.pdf")).one()
    advocate_client.put(f"{API}/cases/{case.id}/documents/{doc.id}/sharing", json={"shared": True})
    newest = db.scalars(select(ClientUpdate).order_by(ClientUpdate.created_at.desc())).first()
    assert "Cheque copy" not in newest.message and "document" in newest.message.lower()


def test_unsharing_hides_the_item_at_once_without_a_notice(advocate_client, db):
    case = case_of(db)
    doc = db.scalars(select(Document).where(Document.case_id == case.id, Document.file_name == "Legal notice.pdf")).one()
    assert doc.shared_with_client is True
    before = updates(db)
    advocate_client.put(f"{API}/cases/{case.id}/documents/{doc.id}/sharing", json={"shared": False})
    db.expire_all()
    assert db.get(Document, doc.id).shared_with_client is False
    assert updates(db) == before


def test_new_items_default_to_private(advocate_client, db):
    case = case_of(db)
    note = advocate_client.post(f"{API}/cases/{case.id}/timeline", json={"text": "Internal reminder."}).json()
    entry = db.get(TimelineEntry, uuid.UUID(note["id"]))
    assert entry.shared_with_client is False
    before = updates(db)
    advocate_client.post(f"{API}/cases/{case.id}/timeline", json={"text": "Another private one."})
    assert updates(db) == before


def test_choosing_closed_closes_the_case_and_reopening_reopens_it(advocate_client, db):
    case = case_of(db)
    advocate_client.put(f"{API}/cases/{case.id}/client-status", json={"status": "closed"})
    db.expire_all()
    assert db.get(Case, case.id).status == "closed"

    advocate_client.put(f"{API}/cases/{case.id}/client-status", json={"status": "awaiting_order"})
    db.expire_all()
    assert db.get(Case, case.id).status == "active"
    assert db.get(Case, case.id).client_status == "awaiting_order"


def test_choosing_the_same_status_again_does_nothing(advocate_client, db):
    case = case_of(db)
    current = case.client_status
    before_updates, before_entries = updates(db), db.scalar(select(func.count()).select_from(TimelineEntry))
    advocate_client.put(f"{API}/cases/{case.id}/client-status", json={"status": current})
    assert updates(db) == before_updates
    assert db.scalar(select(func.count()).select_from(TimelineEntry)) == before_entries


def test_a_status_change_is_recorded_and_notified(advocate_client, db):
    case = case_of(db)
    before = updates(db)
    advocate_client.put(f"{API}/cases/{case.id}/client-status", json={"status": "awaiting_order"})
    assert updates(db) == before + 2
    entry = db.scalars(select(TimelineEntry).where(TimelineEntry.kind == "status_change").order_by(TimelineEntry.occurred_at.desc())).first()
    assert "Awaiting order" in entry.text and entry.shared_with_client is True


def test_only_the_owning_advocate_can_act(client, db):
    case = case_of(db)
    client.post(
        f"{API}/auth/register",
        json={"role": "advocate", "full_name": "Not Owner", "email": "notowner@example.com", "password": "a-strong-password"},
    )
    before = updates(db)
    assert client.put(f"{API}/cases/{case.id}/client-status", json={"status": "closed"}).status_code == 404
    assert client.post(f"{API}/cases/{case.id}/client-updates", json={"message": "hello"}).status_code == 404
    assert updates(db) == before
    assert case_of(db).client_status == "hearing_scheduled"


def test_clients_see_updates_they_receive_but_each_has_their_own_read_state(client, db):
    sign_in(client, "rohan.sharma@example.com")
    case = case_of(db)
    client.post(f"{API}/cases/{case.id}/client-updates", json={"message": "Bring photo ID."})

    client.post(f"{API}/auth/logout")
    sign_in(client, "anita.sharma@example.com")
    assert client.get(f"{API}/client/dashboard").json()["unread_updates"] == 2  # seeded one plus this
    client.post(f"{API}/auth/logout")
    sign_in(client, "ravi.mehta@example.com")
    assert client.get(f"{API}/client/dashboard").json()["unread_updates"] == 2
