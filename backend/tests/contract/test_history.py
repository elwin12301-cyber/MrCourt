import pytest
from helpers import sign_in
from sqlalchemy import select

from mrcourt.config import get_settings
from mrcourt.corpus.ingest import load_sample_corpus
from mrcourt.models import Question, User

API = "/api/v1/history"
COVERED = "What is the punishment for cheque bounce under Section 138 of the NI Act?"
UNCOVERED = "How do I register a trademark in India?"


@pytest.fixture(autouse=True)
def _setup(db, monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "")
    monkeypatch.setattr(get_settings(), "knowledge_dir", str(tmp_path / "knowledge"))
    load_sample_corpus(db)
    db.commit()


def _ask(client, text, **extra):
    return client.post("/api/v1/questions", json={"text": text, **extra}).json()


def test_history_lists_only_my_questions_newest_first_with_labels(client, second_client):
    sign_in(client, "rohan.sharma@example.com")
    sign_in(second_client, "anita.sharma@example.com")
    _ask(client, COVERED, input_method="voice")
    _ask(client, UNCOVERED)
    _ask(second_client, "What is Section 138 of the NI Act?")

    items = client.get(API).json()["items"]
    assert [i["text"] for i in items] == [UNCOVERED, COVERED]
    assert [i["outcome_label"] for i in items] == ["No information found", "Answered"]
    assert [i["input_method"] for i in items] == ["typed", "voice"]
    assert [i["mode"] for i in items] == ["answer", "answer"]
    assert [i["text"] for i in second_client.get(API).json()["items"]] == ["What is Section 138 of the NI Act?"]


def test_search_and_both_filters(advocate_client):
    _ask(advocate_client, COVERED, input_method="voice")
    _ask(advocate_client, UNCOVERED)
    _ask(advocate_client, COVERED)

    def texts(**params):
        return [i["text"] for i in advocate_client.get(API, params=params).json()["items"]]

    assert texts(q="trademark") == [UNCOVERED]
    assert texts(q="TRADEMARK") == [UNCOVERED]
    assert texts(outcome="none") == [UNCOVERED]
    assert texts(outcome="answered") == [COVERED, COVERED]
    assert texts(input="voice") == [COVERED]
    assert texts(input="voice", outcome="none") == []
    assert texts(q="nothing like this") == []


def test_pages_follow_one_another_without_repeats(advocate_client):
    for n in range(5):
        _ask(advocate_client, f"{COVERED} ({n})")
    first = advocate_client.get(API, params={"limit": 2}).json()
    assert len(first["items"]) == 2 and first["next_before"]
    second = advocate_client.get(API, params={"limit": 2, "before": first["next_before"]}).json()
    third = advocate_client.get(API, params={"limit": 2, "before": second["next_before"]}).json()
    seen = [i["id"] for page in (first, second, third) for i in page["items"]]
    assert len(seen) == 5 == len(set(seen)) and third["next_before"] is None


def test_opening_a_question_shows_the_stored_answer_with_citations(advocate_client):
    asked = _ask(advocate_client, COVERED)
    detail = advocate_client.get(f"{API}/{asked['question_id']}").json()
    assert detail["text"] == COVERED and detail["outcome"] == "cited"
    assert detail["citations"][0]["label"] == asked["citations"][0]["label"]
    assert detail["paragraphs"] and detail["disclaimer"]


def test_a_removed_passage_still_shows_its_label(client, second_client, db):
    admin = second_client
    sign_in(admin, "admin@example.com")
    sign_in(client, "rohan.sharma@example.com")
    doc = admin.post("/api/v1/knowledge/documents", data={"title": "Zanzibar", "citation": "Zanzibar Act", "text": "The zanzibar covenant needs eleven months of notice."}).json()
    asked = _ask(client, "How many months of notice does the zanzibar covenant need?")
    assert asked["outcome"] == "cited"
    admin.delete(f"/api/v1/knowledge/documents/{doc['id']}")
    detail = client.get(f"{API}/{asked['question_id']}").json()
    assert [c["label"] for c in detail["citations"]] == ["Zanzibar Act"]


def test_someone_elses_question_is_not_found(client, second_client):
    sign_in(client, "rohan.sharma@example.com")
    sign_in(second_client, "anita.sharma@example.com")
    asked = _ask(client, COVERED)
    assert second_client.get(f"{API}/{asked['question_id']}").status_code == 404
    assert client.get(f"{API}/00000000-0000-0000-0000-000000000000").status_code == 404


def test_administrators_have_a_history_of_their_own_and_see_only_that_here(admin_client, client):
    from helpers import sign_in

    sign_in(client, "rohan.sharma@example.com")
    _ask(client, COVERED)
    _ask(admin_client, UNCOVERED)
    assert [i["text"] for i in admin_client.get(API).json()["items"]] == [UNCOVERED]
    opened = admin_client.get(f"{API}/{admin_client.get(API).json()['items'][0]['id']}")
    assert opened.status_code == 200 and opened.json()["text"] == UNCOVERED


def test_history_needs_sign_in(client):
    assert client.get(API).status_code == 401


def test_export_includes_questions_and_own_private_notes(advocate_client):
    advocate_client.post("/api/v1/knowledge/documents", data={"title": "Mine", "citation": "Mine", "text": "My private zanzibar note."})
    _ask(advocate_client, COVERED, input_method="voice")
    export = advocate_client.get("/api/v1/me/data-export").json()
    assert export["questions"][0]["input_method"] == "voice" and export["questions"][0]["mode"] == "answer"
    assert [d["title"] for d in export["private_documents"]] == ["Mine"]
    assert "zanzibar" in export["private_documents"][0]["text"]


def test_deactivation_removes_questions_and_private_notes(client, db):
    sign_in(client, "rohan.sharma@example.com")
    client.post("/api/v1/knowledge/documents", data={"title": "Mine", "citation": "Mine", "text": "My private zanzibar note."})
    _ask(client, COVERED)
    rohan = db.scalar(select(User).where(User.email == "rohan.sharma@example.com"))
    rohan_id = rohan.id
    response = client.post("/api/v1/me/deactivate", json={"acknowledge_case_retention": True})
    assert response.status_code in (200, 204), response.text
    db.expire_all()
    assert db.scalars(select(Question).where(Question.user_id == rohan_id)).first() is None
    from mrcourt.models import KnowledgeDocument

    assert db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.owner_id == rohan_id)).first() is None
