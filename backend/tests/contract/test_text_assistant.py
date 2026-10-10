import pytest
from helpers import sign_in
from sqlalchemy import select

from mrcourt.config import get_settings
from mrcourt.models import KnowledgeDocument, Question, TextConversation

API = "/api/v1/text/conversations"


@pytest.fixture(autouse=True)
def _dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "knowledge_dir", str(tmp_path / "knowledge"))


def _new(client, language="en-IN"):
    return client.post(API, json={"language": language}).json()


def _line(client, cid, text, source="typed"):
    return client.post(f"{API}/{cid}/lines", json={"text": text, "source": source})


def test_a_conversation_collects_lines_and_takes_its_title_from_the_first(advocate_client):
    c = _new(advocate_client, "ta-IN")
    assert c["title"] == "New conversation" and c["language"] == "ta-IN" and c["lines"] == []
    assert _line(advocate_client, c["id"], "Meeting about the Sharma case today", "voice").status_code == 201
    assert _line(advocate_client, c["id"], "Next hearing on the fifth").status_code == 201
    got = advocate_client.get(f"{API}/{c['id']}").json()
    assert got["title"] == "Meeting about the Sharma case today"
    assert [(l["text"], l["source"]) for l in got["lines"]] == [
        ("Meeting about the Sharma case today", "voice"),
        ("Next hearing on the fifth", "typed"),
    ]
    assert [r["line_count"] for r in advocate_client.get(API).json()] == [2]


def test_lines_can_be_edited_and_removed_and_blank_lines_are_refused(advocate_client):
    c = _new(advocate_client)
    first = _line(advocate_client, c["id"], "First").json()
    _line(advocate_client, c["id"], "Second")
    assert advocate_client.patch(f"{API}/{c['id']}/lines/{first['id']}", json={"text": "First, corrected"}).json()["text"] == "First, corrected"
    assert _line(advocate_client, c["id"], "   ").status_code == 422
    assert advocate_client.delete(f"{API}/{c['id']}/lines/{first['id']}").status_code == 204
    assert [l["text"] for l in advocate_client.get(f"{API}/{c['id']}").json()["lines"]] == ["Second"]


def test_conversations_are_private_to_their_owner(client, second_client):
    sign_in(client, "rohan.sharma@example.com")
    sign_in(second_client, "anita.sharma@example.com")
    c = _new(client)
    _line(client, c["id"], "Private matter")
    assert second_client.get(f"{API}/{c['id']}").status_code == 404
    assert second_client.post(f"{API}/{c['id']}/lines", json={"text": "x"}).status_code == 404
    assert second_client.delete(f"{API}/{c['id']}").status_code == 404
    assert second_client.get(f"{API}/{c['id']}/pdf").status_code == 404
    assert second_client.get(API).json() == []


def test_an_administrator_can_keep_conversations_and_add_one_as_a_shared_source(admin_client, advocate_client, db):
    c = _new(admin_client)
    _line(admin_client, c["id"], "The zorvexshared covenant needs eleven months of notice.")
    body = admin_client.post(f"{API}/{c['id']}/knowledge", json={"citation": "Shared meeting note"}).json()
    assert (body["scope"], body["kind"], body["status"]) == ("shared", "note", "ready")
    answer = advocate_client.post("/api/v1/questions", json={"text": "How many months of notice does the zorvexshared covenant need?"}).json()
    assert answer["outcome"] == "cited"


def test_deleting_hides_the_conversation_but_not_its_history_entry(advocate_client, db):
    c = _new(advocate_client)
    _line(advocate_client, c["id"], "Keep me in history", "voice")
    assert advocate_client.delete(f"{API}/{c['id']}").status_code == 204
    assert advocate_client.get(API).json() == []
    assert advocate_client.get(f"{API}/{c['id']}").status_code == 404
    items = advocate_client.get("/api/v1/history", params={"source": "text"}).json()["items"]
    assert [(i["text"], i["mode"], i["input_method"], i["outcome_label"]) for i in items] == [
        ("Keep me in history", "text", "voice", "Saved")
    ]
    detail = advocate_client.get(f"/api/v1/history/{items[0]['id']}").json()
    assert detail["conversation_deleted"] is True and [l["text"] for l in detail["lines"]] == ["Keep me in history"]
    assert db.scalars(select(TextConversation)).one().deleted_at is not None


def test_the_pdf_downloads(advocate_client):
    c = _new(advocate_client)
    _line(advocate_client, c["id"], "A line for the PDF")
    response = advocate_client.get(f"{API}/{c['id']}/pdf")
    assert response.status_code == 200 and response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_the_pdf_builds_with_tamil_text_even_without_a_font(advocate_client):
    c = _new(advocate_client, "ta-IN")
    _line(advocate_client, c["id"], "வணக்கம் world", "voice")
    assert advocate_client.get(f"{API}/{c['id']}/pdf").content.startswith(b"%PDF")


def test_an_advocate_adds_it_to_the_knowledge_base_as_a_private_note(advocate_client, client, db):
    c = _new(advocate_client)
    _line(advocate_client, c["id"], "The zorvex covenant needs eleven months of notice.")
    response = advocate_client.post(f"{API}/{c['id']}/knowledge", json={"citation": "Meeting note"})
    assert response.status_code == 201
    body = response.json()
    assert (body["scope"], body["kind"], body["status"]) == ("private", "note", "ready")
    answer = advocate_client.post("/api/v1/questions", json={"text": "How many months of notice does the zorvex covenant need?"}).json()
    assert answer["outcome"] == "cited" and answer["citations"][0]["label"].startswith("Meeting note")
    assert db.scalars(select(KnowledgeDocument)).first() is not None


def test_clients_keep_conversations_but_cannot_add_them_to_the_knowledge_base(petitioner_client):
    c = _new(petitioner_client)
    _line(petitioner_client, c["id"], "My own notes")
    assert petitioner_client.post(f"{API}/{c['id']}/knowledge", json={}).status_code == 403
    assert petitioner_client.get(f"{API}/{c['id']}/pdf").status_code == 200


def test_an_empty_conversation_cannot_be_added(advocate_client):
    c = _new(advocate_client)
    assert advocate_client.post(f"{API}/{c['id']}/knowledge", json={}).status_code == 422


def test_the_history_entry_follows_renames_and_removed_lines(advocate_client, db):
    c = _new(advocate_client)
    _line(advocate_client, c["id"], "typed line")
    advocate_client.patch(f"{API}/{c['id']}", json={"title": "Renamed talk"})
    row = db.scalars(select(Question).where(Question.mode == "text")).one()
    db.refresh(row)
    assert row.text == "Renamed talk" and row.input_method == "typed"


def test_export_and_deletion_include_conversations(client, db):
    sign_in(client, "rohan.sharma@example.com")
    c = _new(client)
    _line(client, c["id"], "Export me")
    export = client.get("/api/v1/me/data-export").json()
    assert export["text_conversations"][0]["lines"][0]["text"] == "Export me"
    assert client.post("/api/v1/me/deactivate", json={"acknowledge_case_retention": True}).status_code == 204
    db.expire_all()
    assert db.scalars(select(TextConversation)).first() is None
    assert db.scalars(select(Question).where(Question.mode == "text")).first() is None
