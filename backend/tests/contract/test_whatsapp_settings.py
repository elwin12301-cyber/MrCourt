"""Settings → WhatsApp: link, choose what is sent, unlink; everything audited without message content."""
from helpers import sign_in
from helpers_whatsapp import linked, verified
from sqlalchemy import select

from mrcourt.db.base import utcnow
from mrcourt.models import AuditEntry, Message, User

API = "/api/v1/me/whatsapp"
ROHAN = "rohan.sharma@example.com"
ANITA = "anita.sharma@example.com"


def _kinds(body):
    return {k["kind"]: k["enabled"] for k in body["kinds"]}


def test_before_linking_everything_is_off_and_the_kinds_follow_the_role(advocate_client) -> None:
    advocate = advocate_client.get(API).json()
    assert advocate["linked"] is False and advocate["available"] is False and advocate["can_link"] is False
    assert _kinds(advocate) == {"codes": False, "reminders": False, "activity": False}
    assert all(k["describes"] for k in advocate["kinds"])


def test_each_role_sees_only_its_own_kinds(client, second_client) -> None:
    sign_in(client, ANITA)
    assert list(_kinds(client.get(API).json())) == ["codes", "reminders", "updates"]
    sign_in(second_client, "admin@example.com")
    assert list(_kinds(second_client.get(API).json())) == ["codes"]


def test_linking_needs_a_verified_phone_then_everything_stays_off(advocate_client, db) -> None:
    refused = advocate_client.post(f"{API}/link")
    assert refused.status_code == 409 and refused.json()["detail"] == "phone_not_verified"
    verified(db, ROHAN)
    assert advocate_client.get(API).json()["can_link"] is True
    body = advocate_client.post(f"{API}/link").json()
    assert body["linked"] is True and body["number"] == "+91 ••••• ••001"
    assert not any(_kinds(body).values())


def test_a_number_already_linked_to_someone_else_is_refused_without_naming_them(advocate_client, db) -> None:
    linked(db, ANITA, phone="9000000001")
    verified(db, ROHAN, "+919000000001")
    response = advocate_client.post(f"{API}/link")
    assert response.status_code == 409 and response.json()["detail"] == "number_in_use"
    assert "Anita" not in response.text and "anita" not in response.text


def test_a_kind_is_switched_on_with_the_time_it_changed(advocate_client, db) -> None:
    verified(db, ROHAN)
    advocate_client.post(f"{API}/link")
    body = advocate_client.put(f"{API}/consents/reminders", json={"enabled": True}).json()
    assert _kinds(body) == {"codes": False, "reminders": True, "activity": False}
    assert next(k for k in body["kinds"] if k["kind"] == "reminders")["changed_at"] is not None
    assert _kinds(advocate_client.put(f"{API}/consents/reminders", json={"enabled": False}).json())["reminders"] is False


def test_a_kind_of_another_role_or_an_unlinked_number_is_refused(advocate_client, db) -> None:
    verified(db, ROHAN)
    assert advocate_client.put(f"{API}/consents/reminders", json={"enabled": True}).json()["detail"] == "not_linked"
    advocate_client.post(f"{API}/link")
    assert advocate_client.put(f"{API}/consents/updates", json={"enabled": True}).status_code == 404
    assert advocate_client.put(f"{API}/consents/nonsense", json={"enabled": True}).status_code == 404


def test_unlinking_switches_everything_off(advocate_client, db) -> None:
    linked(db, ROHAN, "codes", "reminders")
    assert advocate_client.delete(API).status_code == 204
    body = advocate_client.get(API).json()
    assert body["linked"] is False and body["number"] is None and not any(_kinds(body).values())


def test_changing_the_phone_number_unlinks_and_switches_everything_off(advocate_client, db) -> None:
    linked(db, ROHAN, "reminders")
    assert advocate_client.patch("/api/v1/me", json={"phone": "9000000055"}).status_code == 200
    body = advocate_client.get(API).json()
    assert body["linked"] is False and not any(_kinds(body).values())


def test_linking_and_choices_are_audited_without_message_content(advocate_client, db) -> None:
    verified(db, ROHAN)
    advocate_client.post(f"{API}/link")
    advocate_client.put(f"{API}/consents/codes", json={"enabled": True})
    advocate_client.delete(API)
    db.expire_all()
    entries = list(db.scalars(select(AuditEntry).where(AuditEntry.action.like("whatsapp.%")).order_by(AuditEntry.created_at)))
    assert [e.action for e in entries] == ["whatsapp.link", "whatsapp.consent", "whatsapp.unlink"]
    assert entries[1].detail == {"kind": "codes", "enabled": True}
    assert all("text" not in (e.detail or {}) and "body" not in (e.detail or {}) for e in entries)


def test_the_person_can_delete_their_delivery_records(advocate_client, db) -> None:
    user = linked(db, ROHAN, "reminders")
    db.add(Message(user_id=user.id, kind="reminder", channel="whatsapp", status="delivered", created_at=utcnow()))
    other = linked(db, ANITA, "reminders", phone="9000000002")
    db.add(Message(user_id=other.id, kind="reminder", channel="whatsapp", status="delivered", created_at=utcnow()))
    db.commit()
    assert advocate_client.delete(f"{API}/history").status_code == 204
    db.expire_all()
    assert [m.user_id for m in db.scalars(select(Message))] == [other.id]


def test_you_must_be_signed_in(client) -> None:
    assert client.get(API).status_code == 401
    assert client.post(f"{API}/link").status_code == 401
    assert client.put(f"{API}/consents/codes", json={"enabled": True}).status_code == 401
