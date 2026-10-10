import pytest
from helpers import make_document
from sqlalchemy import select

from mrcourt.config import get_settings
from mrcourt.models import LegalSource, User
from mrcourt.services import embeddings
from mrcourt.services.embed_missing import embed_missing
from mrcourt.services.embeddings import EmbeddingUnavailable, FakeEmbedder, embed_passages, set_embedder
from mrcourt.services.rerank import FakeReranker, set_reranker
from mrcourt.services.retrieval import search

MEANINGS = {
    "who appeared": "counsel",
    "for appellant": "counsel",
    "final result": "outcome",
    "dismissed": "outcome",
}
QUESTION = "Who appeared for the parties?"


@pytest.fixture(autouse=True)
def _embedder(monkeypatch):
    monkeypatch.setattr(get_settings(), "min_vector_score", 0.25)
    set_embedder(FakeEmbedder(MEANINGS))
    set_reranker(FakeReranker({"For Appellant": 0.9, "second appeal is dismissed": 0.8, "partition deed": 0.1}))
    yield
    set_embedder(None)
    set_reranker(None)


def _doc(db, owner=None):
    doc = make_document(
        db,
        title="Judgment",
        citation="S.A. 1 of 2020",
        owner=owner,
        passages=[
            "For Appellant: Mr. Shivakumaran. For Respondent: Ms. Hema.",
            "The second appeal is dismissed with costs and the decree is confirmed.",
            "The partition deed of 1979 allotted the land to the plaintiff.",
        ],
    )
    db.flush()
    passages = list(db.scalars(select(LegalSource).where(LegalSource.document_id == doc.id).order_by(LegalSource.page)))
    embed_passages(db, passages)
    db.commit()
    return passages


def test_a_loosely_worded_question_finds_the_passage_by_meaning(db):
    passages = _doc(db)
    result = search(db, QUESTION, None)
    assert result.mode == "meaning"
    assert result.hits[0].source.id == passages[0].id


def test_keywords_alone_miss_it(db):
    _doc(db)
    set_embedder(None, disabled=True)
    result = search(db, QUESTION, None)
    assert result.mode == "keywords" and result.hits == []


def test_a_failing_embedding_service_falls_back_quietly(db):
    class Down:
        name = "down"

        def embed(self, texts, input_type, *, patient=False):
            raise EmbeddingUnavailable("down")

    _doc(db)
    set_embedder(Down())
    result = search(db, "Is the appeal dismissed with costs?", None)
    assert result.mode == "keywords"
    assert result.hits and "dismissed" in result.hits[0].source.text


def test_passages_found_by_both_lists_come_first(db):
    passages = _doc(db)
    result = search(db, "What was the final result: is the appeal dismissed?", None)
    assert result.hits[0].source.id == passages[1].id


def test_an_unrelated_question_still_finds_nothing(db):
    _doc(db)
    result = search(db, "What colour is a purple elephant on Tuesday?", None)
    assert result.hits == []


def test_private_passages_are_never_found_by_meaning_for_someone_else(db):
    rohan = db.scalar(select(User).where(User.email == "rohan.sharma@example.com"))
    anita = db.scalar(select(User).where(User.email == "anita.sharma@example.com"))
    _doc(db, owner=rohan)
    assert search(db, QUESTION, rohan).hits
    assert search(db, QUESTION, anita).hits == []
    assert search(db, QUESTION, None).hits == []


def test_embedding_is_not_repeated_for_the_same_model_and_redone_for_a_new_one(db):
    passages = _doc(db)
    assert embed_passages(db, passages) == 0
    set_embedder(FakeEmbedder(MEANINGS))
    embeddings.get_embedder().name = "other-model"  # type: ignore[union-attr]
    assert embed_passages(db, passages) == len(passages)


def test_the_one_off_command_fills_older_passages_and_is_repeatable(db):
    make_document(db, title="Old", citation="Old v. State", passages=["An old passage about quokka rules."])
    db.commit()
    assert db.scalar(select(LegalSource).where(LegalSource.instrument == "Old")).embedding is None
    assert embed_missing(db) == (1, 0)
    assert embed_missing(db) == (0, 0)


def test_the_command_does_nothing_without_a_service(db):
    make_document(db, title="Old", citation="Old v. State", passages=["An old passage about quokka rules."])
    db.commit()
    set_embedder(None, disabled=True)
    assert embed_missing(db) == (0, 0)


def test_a_meaning_only_passage_below_the_rerank_floor_is_not_cited(db):
    _doc(db)
    set_reranker(FakeReranker({"For Appellant": 0.3}))  # the reranker says it does not really answer the question
    assert search(db, QUESTION, None).hits == []


def test_results_are_ordered_by_the_reranker(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "min_vector_score", 0.02)
    passages = _doc(db)
    set_reranker(FakeReranker({"For Appellant": 0.6, "second appeal is dismissed": 0.95}))
    result = search(db, "Who appeared for the parties, and what was the final result?", None)
    assert [h.source.id for h in result.hits][:2] == [passages[1].id, passages[0].id]


def test_without_a_reranker_only_keyword_evidence_is_used(db):
    _doc(db)
    set_reranker(None, disabled=True)
    result = search(db, QUESTION, None)  # no keyword evidence for this wording, and no way to check meaning
    assert result.hits == [] and result.mode == "keywords"
    keyword = search(db, "Is the appeal dismissed with costs?", None)
    assert keyword.hits and "dismissed" in keyword.hits[0].source.text and keyword.mode == "keywords"
