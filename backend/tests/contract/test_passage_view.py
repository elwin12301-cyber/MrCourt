import pytest
from helpers import make_document, sign_in
from sqlalchemy import select

from mrcourt.config import get_settings
from mrcourt.corpus.ingest import load_sample_corpus
from mrcourt.models import LegalSource, User

QUESTION = "What is the punishment for cheque bounce under Section 138 of the NI Act?"


@pytest.fixture(autouse=True)
def _setup(db, monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "")
    monkeypatch.setattr(get_settings(), "knowledge_dir", str(tmp_path / "knowledge"))
    load_sample_corpus(db)
    db.commit()


def test_a_citation_opens_to_the_passage(advocate_client):
    asked = advocate_client.post("/api/v1/questions", json={"text": QUESTION}).json()
    passage_id = asked["citations"][0]["passage_id"]
    body = advocate_client.get(f"/api/v1/knowledge/passages/{passage_id}").json()
    assert "138" in body["citation"] and body["text"] and body["scope"] == "shared"
    assert body["read_by_ocr"] is False and body["document_title"]


def test_clients_can_open_shared_passages(petitioner_client):
    asked = petitioner_client.post("/api/v1/questions", json={"text": QUESTION}).json()
    assert petitioner_client.get(f"/api/v1/knowledge/passages/{asked['citations'][0]['passage_id']}").status_code == 200


def test_a_private_passage_opens_only_for_its_owner(client, second_client, db):
    rohan = db.scalar(select(User).where(User.email == "rohan.sharma@example.com"))
    make_document(db, title="Mine", citation="My note", kind="note", owner=rohan, passages=["Zanzibar clause: eleven months."])
    db.commit()
    passage = db.scalar(select(LegalSource).where(LegalSource.instrument == "Mine"))
    sign_in(client, "rohan.sharma@example.com")
    sign_in(second_client, "anita.sharma@example.com")
    assert client.get(f"/api/v1/knowledge/passages/{passage.id}").json()["scope"] == "private"
    assert second_client.get(f"/api/v1/knowledge/passages/{passage.id}").status_code == 404


def test_a_removed_passage_is_not_found_and_history_keeps_its_label(client, second_client):
    sign_in(second_client, "admin@example.com")
    sign_in(client, "rohan.sharma@example.com")
    doc = second_client.post("/api/v1/knowledge/documents", data={"title": "Zanzibar", "citation": "Zanzibar Act", "text": "The zanzibar covenant needs eleven months of notice."}).json()
    asked = client.post("/api/v1/questions", json={"text": "How many months of notice does the zanzibar covenant need?"}).json()
    passage_id = asked["citations"][0]["passage_id"]
    assert client.get(f"/api/v1/knowledge/passages/{passage_id}").status_code == 200
    second_client.delete(f"/api/v1/knowledge/documents/{doc['id']}")
    assert client.get(f"/api/v1/knowledge/passages/{passage_id}").status_code == 404
    detail = client.get(f"/api/v1/history/{asked['question_id']}").json()
    assert detail["citations"][0]["label"] == "Zanzibar Act" and detail["citations"][0]["passage_id"] is None


def test_it_needs_sign_in(client):
    assert client.get("/api/v1/knowledge/passages/00000000-0000-0000-0000-000000000000").status_code == 401
