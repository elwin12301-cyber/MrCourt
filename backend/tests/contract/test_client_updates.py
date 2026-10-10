"""Contract tests for the client's updates list and unread state."""

import uuid

from sqlalchemy import select

from helpers import sign_in
from mrcourt.models import ClientUpdate, User

API = "/api/v1"


def test_updates_require_sign_in(client):
    assert client.get(f"{API}/client/updates").status_code == 401


def test_advocates_have_no_client_updates(advocate_client):
    assert advocate_client.get(f"{API}/client/updates").status_code == 403


def test_list_shape_and_order(petitioner_client):
    body = petitioner_client.get(f"{API}/client/updates").json()
    assert set(body) == {"unread_count", "items"}
    assert body["unread_count"] == 1 and len(body["items"]) == 2
    first = body["items"][0]
    assert set(first) == {"id", "case_id", "kind", "message", "created_at", "read"}
    times = [i["created_at"] for i in body["items"]]
    assert times == sorted(times, reverse=True)
    assert [i["read"] for i in body["items"]] == [False, True]


def test_unread_filter(petitioner_client):
    body = petitioner_client.get(f"{API}/client/updates", params={"unread": "true"}).json()
    assert len(body["items"]) == 1 and body["items"][0]["read"] is False
    assert body["unread_count"] == 1


def test_marking_one_read(petitioner_client):
    unread = petitioner_client.get(f"{API}/client/updates", params={"unread": "true"}).json()["items"][0]
    assert petitioner_client.post(f"{API}/client/updates/{unread['id']}/read").status_code == 204
    after = petitioner_client.get(f"{API}/client/updates").json()
    assert after["unread_count"] == 0 and all(i["read"] for i in after["items"])
    # Marking it again is harmless.
    assert petitioner_client.post(f"{API}/client/updates/{unread['id']}/read").status_code == 204


def test_marking_everything_read(client):
    # Several updates from the advocate first, then the client marks them all read.
    sign_in(client, "rohan.sharma@example.com")
    case_id = client.get(f"{API}/cases").json()[0]["id"]
    for text in ("One.", "Two.", "Three."):
        client.post(f"{API}/cases/{case_id}/client-updates", json={"message": text})
    client.post(f"{API}/auth/logout")
    sign_in(client, "anita.sharma@example.com")
    assert client.get(f"{API}/client/updates").json()["unread_count"] >= 4
    assert client.post(f"{API}/client/updates/read-all").status_code == 204
    assert client.get(f"{API}/client/updates").json()["unread_count"] == 0


def test_a_client_cannot_mark_someone_elses_update(petitioner_client, db):
    ravi = db.scalars(select(User).where(User.email == "ravi.mehta@example.com")).one()
    theirs = db.scalars(select(ClientUpdate).where(ClientUpdate.client_id == ravi.id)).first()
    assert petitioner_client.post(f"{API}/client/updates/{theirs.id}/read").status_code == 404
    db.expire_all()
    assert db.get(ClientUpdate, theirs.id).read_at is None


def test_unknown_update_is_404(petitioner_client):
    assert petitioner_client.post(f"{API}/client/updates/{uuid.uuid4()}/read").status_code == 404


def test_the_dashboard_unread_count_matches(petitioner_client):
    dash = petitioner_client.get(f"{API}/client/dashboard").json()
    assert dash["unread_updates"] == petitioner_client.get(f"{API}/client/updates").json()["unread_count"]
