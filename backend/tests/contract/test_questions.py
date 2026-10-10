"""Contract tests for POST /questions."""

import pytest
from sqlalchemy import select

from mrcourt.models import LegalSource
from mrcourt.corpus.ingest import load_sample_corpus

API = "/api/v1"


@pytest.fixture
def corpus(db):
    load_sample_corpus(db)
    db.commit()


def ask(client, text, **extra):
    return client.post(f"{API}/questions", json={"text": text, **extra})


def test_requires_sign_in(client):
    assert ask(client, "What is Section 138?").status_code == 401


def test_cited_answer_has_numbered_citations_and_disclaimer(advocate_client, corpus):
    response = ask(advocate_client, "What is the punishment for cheque bounce under Section 138?")
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "cited"
    assert body["disclaimer"] == "Informational only, not legal advice."
    assert body["paragraphs"]
    numbers = {c["number"] for c in body["citations"]}
    assert numbers
    for paragraph in body["paragraphs"]:
        assert paragraph["citation_numbers"], "every paragraph must be cited"
        assert set(paragraph["citation_numbers"]) <= numbers
    labels = [c["label"] for c in body["citations"]]
    assert any("Negotiable Instruments Act, 1881 · Section 138" == label for label in labels)


def test_unknown_topic_returns_no_reliable_source_with_disclaimer(advocate_client, corpus):
    body = ask(advocate_client, "How do I license a patent for a drug formulation?").json()
    assert body["outcome"] == "no_reliable_source"
    assert body["paragraphs"] == []
    assert body["citations"] == []
    assert "could not find a reliable source" in body["message"].lower()
    assert body["disclaimer"] == "Informational only, not legal advice."


def test_empty_corpus_means_no_reliable_source(advocate_client):
    body = ask(advocate_client, "What is Section 138?").json()
    assert body["outcome"] == "no_reliable_source"


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_blank_question_is_rejected(advocate_client, text):
    assert ask(advocate_client, text).status_code == 422


def test_petitioners_can_ask(petitioner_client, corpus):
    assert ask(petitioner_client, "What is Section 138 of the NI Act?").status_code == 200


def test_question_and_answer_are_stored(advocate_client, corpus, db):
    ask(advocate_client, "What is the punishment under Section 138?")
    from mrcourt.models import Answer, Question

    assert len(db.scalars(select(Question)).all()) == 1
    answer = db.scalars(select(Answer)).one()
    assert answer.outcome == "cited" and len(answer.citations) >= 1
    assert db.scalars(select(LegalSource)).first() is not None


def test_case_id_must_be_visible_to_the_user(petitioner_client, corpus):
    import uuid

    response = ask(petitioner_client, "What is Section 138?", case_id=str(uuid.uuid4()))
    assert response.status_code == 404

