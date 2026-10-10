import pytest
from helpers import sign_in
from sqlalchemy import select

from mrcourt.config import get_settings
from mrcourt.corpus.ingest import load_sample_corpus
from mrcourt.models import AuditEntry, User

QUESTION = "What is the punishment for cheque bounce under Section 138 of the NI Act?"


@pytest.fixture(autouse=True)
def _setup(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "")
    load_sample_corpus(db)
    db.commit()


def _person(db, email):
    return db.scalar(select(User).where(User.email == email))


def test_an_administrator_lists_a_persons_questions_and_it_is_recorded_without_the_text(client, admin_client, db):
    sign_in(client, "rohan.sharma@example.com")
    client.post("/api/v1/questions", json={"text": QUESTION})
    rohan = _person(db, "rohan.sharma@example.com")

    page = admin_client.get(f"/api/v1/admin/users/{rohan.id}/questions").json()
    assert [i["text"] for i in page["items"]] == [QUESTION]
    assert "paragraphs" not in page["items"][0]  # a list only: no answers

    entry = db.scalars(select(AuditEntry).where(AuditEntry.action == "history.view")).one()
    assert entry.target_id == rohan.id and entry.detail == {"shown": 1}
    assert QUESTION not in str(entry.detail)


def test_every_opening_is_recorded(client, admin_client, db):
    sign_in(client, "rohan.sharma@example.com")
    rohan = _person(db, "rohan.sharma@example.com")
    for _ in range(2):
        admin_client.get(f"/api/v1/admin/users/{rohan.id}/questions")
    assert len(db.scalars(select(AuditEntry).where(AuditEntry.action == "history.view")).all()) == 2


def test_advocates_and_clients_cannot_open_anyones_history(client, second_client, db):
    sign_in(client, "rohan.sharma@example.com")
    sign_in(second_client, "anita.sharma@example.com")
    anita = _person(db, "anita.sharma@example.com")
    assert client.get(f"/api/v1/admin/users/{anita.id}/questions").status_code == 403
    assert second_client.get(f"/api/v1/admin/users/{anita.id}/questions").status_code == 403
    assert db.scalars(select(AuditEntry).where(AuditEntry.action == "history.view")).first() is None


def test_an_unknown_person_is_not_found_and_nothing_is_recorded(admin_client, db):
    assert admin_client.get("/api/v1/admin/users/00000000-0000-0000-0000-000000000000/questions").status_code == 404
    assert db.scalars(select(AuditEntry).where(AuditEntry.action == "history.view")).first() is None


def test_the_workspace_list_shows_who_asked_but_never_answers_and_is_recorded(client, admin_client, app, db):
    from fastapi.testclient import TestClient

    sign_in(client, "rohan.sharma@example.com")
    client.post("/api/v1/questions", json={"text": QUESTION})
    with TestClient(app, base_url="http://testserver") as third:  # admin_client already uses the second browser
        sign_in(third, "anita.sharma@example.com")
        third.post("/api/v1/questions", json={"text": "How do I register a trademark in India?"})

    page = admin_client.get("/api/v1/admin/questions").json()
    seen = {(i["asker_name"], i["text"]) for i in page["items"]}
    assert ("Adv. Rohan Sharma", QUESTION) in seen and ("Anita Sharma", "How do I register a trademark in India?") in seen
    assert all("paragraphs" not in i and "lines" not in i for i in page["items"])
    assert {i["asker_role"] for i in page["items"]} >= {"advocate", "petitioner"}

    entries = db.scalars(select(AuditEntry).where(AuditEntry.action == "history.view")).all()
    assert len(entries) == 1 and entries[0].target_type == "workspace" and set(entries[0].detail) == {"shown"}
    assert QUESTION not in str(entries[0].detail)


def test_the_workspace_list_filters_like_a_persons_history(client, admin_client):
    sign_in(client, "rohan.sharma@example.com")
    client.post("/api/v1/questions", json={"text": QUESTION, "input_method": "voice"})
    client.post("/api/v1/questions", json={"text": "How do I register a trademark in India?"})
    texts = lambda **p: [i["text"] for i in admin_client.get("/api/v1/admin/questions", params=p).json()["items"]]  # noqa: E731
    assert texts(q="trademark") == ["How do I register a trademark in India?"]
    assert texts(outcome="answered") == [QUESTION]
    assert texts(input="voice") == [QUESTION]


def test_only_administrators_can_use_the_workspace_list(client, second_client, db):
    sign_in(client, "rohan.sharma@example.com")
    sign_in(second_client, "anita.sharma@example.com")
    assert client.get("/api/v1/admin/questions").status_code == 403
    assert second_client.get("/api/v1/admin/questions").status_code == 403
    assert db.scalars(select(AuditEntry).where(AuditEntry.action == "history.view")).first() is None


def test_other_peoples_answers_cannot_be_opened_by_an_administrator(client, admin_client):
    sign_in(client, "rohan.sharma@example.com")
    asked = client.post("/api/v1/questions", json={"text": QUESTION}).json()
    assert admin_client.get(f"/api/v1/history/{asked['question_id']}").status_code == 404
