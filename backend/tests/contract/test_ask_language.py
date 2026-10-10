import pytest
from helpers import make_document
from sqlalchemy import select

from mrcourt.config import get_settings
from mrcourt.models import LegalSource
from mrcourt.services.embeddings import FakeEmbedder, embed_passages, set_embedder
from mrcourt.services.rerank import FakeReranker, set_reranker

TAMIL = "மேல்முறையீட்டாளர் யார்?"  # "Who is the appellant?"


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "")
    monkeypatch.setattr(get_settings(), "min_vector_score", 0.25)
    set_reranker(FakeReranker({"appellant is Fr.": 0.9}))
    yield
    set_embedder(None)
    set_reranker(None)


def _load(db):
    make_document(
        db,
        title="Judgment",
        citation="S.A. 1106 of 2019",
        passages=["The appellant is Fr. Backiyasamy, the defendant in the original suit."],
    )
    db.flush()
    embed_passages(db, list(db.scalars(select(LegalSource))))
    db.commit()


def test_a_tamil_question_finds_the_english_passage_and_says_the_sources_are_in_english(advocate_client, db):
    set_embedder(FakeEmbedder({TAMIL: "appellant defendant suit"}))
    _load(db)
    body = advocate_client.post("/api/v1/questions", json={"text": TAMIL}).json()
    assert body["outcome"] == "cited" and body["search_mode"] == "meaning"
    assert body["citations"][0]["label"].startswith("S.A. 1106 of 2019")  # citation text untouched
    assert body["source_language_note"] == "The sources are in English."


def test_an_english_question_gets_no_language_note(advocate_client, db):
    set_embedder(FakeEmbedder())
    _load(db)
    body = advocate_client.post("/api/v1/questions", json={"text": "Who is the appellant in the suit?"}).json()
    assert body["outcome"] == "cited" and body["source_language_note"] is None


def test_without_meaning_based_search_a_tamil_question_says_why_nothing_was_found(advocate_client, db):
    set_embedder(None, disabled=True)
    _load(db)
    body = advocate_client.post("/api/v1/questions", json={"text": TAMIL}).json()
    assert body["outcome"] == "no_reliable_source" and body["search_mode"] == "keywords"
    assert "needs meaning-based search" in body["message"] and "could not find a reliable source" in body["message"]
