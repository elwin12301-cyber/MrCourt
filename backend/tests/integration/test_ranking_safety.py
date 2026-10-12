"""Hybrid ranking keeps every safety rule, puts named sections and cases first, and limits passages per document."""
import pytest
from helpers import make_document
from sqlalchemy import select

from mrcourt.config import get_settings
from mrcourt.models import LegalSource, User
from mrcourt.services.answering import answer_question
from mrcourt.services.embeddings import FakeEmbedder, embed_passages, set_embedder
from mrcourt.services.rerank import FakeReranker, set_reranker
from mrcourt.services.retrieval import search


def _user(db, email):
    return db.scalar(select(User).where(User.email == email))


@pytest.fixture(params=["hybrid", "rrf"])
def mode(request, monkeypatch):
    monkeypatch.setattr(get_settings(), "ranking_mode", request.param)
    return request.param


@pytest.fixture
def hybrid(monkeypatch):
    monkeypatch.setattr(get_settings(), "ranking_mode", "hybrid")


@pytest.fixture(autouse=True)
def _services():
    yield
    set_embedder(None)
    set_reranker(None)


def _passages(db, doc):
    return list(db.scalars(select(LegalSource).where(LegalSource.document_id == doc.id).order_by(LegalSource.page)))


def test_a_client_never_gets_a_private_passage(db, mode):
    rohan = _user(db, "rohan.sharma@example.com")
    anita = _user(db, "anita.sharma@example.com")
    make_document(db, title="Rohan note", citation="Rohan note", kind="note", owner=rohan,
                  passages=["Zanzibar clause: the zanzibar limitation is eleven months."])
    db.commit()
    assert search(db, "zanzibar limitation clause", anita).hits == []
    assert search(db, "zanzibar limitation clause", rohan).hits


def test_a_meaning_only_passage_needs_the_answer_check(db, hybrid, monkeypatch):
    monkeypatch.setattr(get_settings(), "min_vector_score", 0.25)
    set_embedder(FakeEmbedder({"who appeared": "counsel", "for appellant": "counsel"}))
    set_reranker(FakeReranker({"For Appellant": 0.2}))  # below the 0.5 floor
    doc = make_document(db, title="Judgment", citation="S.A. 1 of 2020",
                        passages=["For Appellant: Mr. Kumar. For Respondent: Ms. Hema."])
    db.flush()
    embed_passages(db, _passages(db, doc))
    db.commit()
    assert search(db, "Who appeared for the parties?", None).hits == []
    set_reranker(FakeReranker({"For Appellant": 0.9}))
    assert search(db, "Who appeared for the parties?", None).hits


def test_without_the_answer_check_only_keyword_evidence_is_used(db, hybrid, monkeypatch):
    monkeypatch.setattr(get_settings(), "min_vector_score", 0.25)
    set_embedder(FakeEmbedder({"who appeared": "counsel", "for appellant": "counsel"}))
    set_reranker(None, disabled=True)
    doc = make_document(db, title="Judgment", citation="S.A. 1 of 2020",
                        passages=["For Appellant: Mr. Kumar. For Respondent: Ms. Hema."])
    db.flush()
    embed_passages(db, _passages(db, doc))
    db.commit()
    result = search(db, "Who appeared for the parties?", None)
    assert result.hits == [] and result.mode == "keywords"


def test_nothing_reliable_means_no_answer(db, mode):
    assert answer_question(db, "What colour is a purple elephant on Tuesday?", None).outcome == "no_reliable_source"


def _ni_act(db):
    exact = make_document(db, title="Negotiable Instruments Act, 1881", citation="NI Act s.138", kind="act_section",
                          passages=["Dishonour of cheque for insufficiency of funds in the account."])
    notes = make_document(db, title="Negotiable Instruments notes", citation="NI notes", kind="act_section",
                          passages=["Cheque dishonour: when a cheque is dishonoured the payee may sue; cheque dishonour "
                                    "notice; cheque dishonour complaint; what the law says about cheque dishonour."])
    db.flush()
    _passages(db, exact)[0].section = "138"
    db.commit()
    return _passages(db, exact)[0], _passages(db, notes)[0]


def test_a_named_section_comes_first(db, hybrid):
    exact, notes = _ni_act(db)
    hits = search(db, "What does Section 138 NI Act say about cheque dishonour?", None).hits
    assert hits[0].source.id == exact.id
    assert notes.id in [h.source.id for h in hits]


def test_a_missing_section_is_reported_not_replaced(db, hybrid):
    _ni_act(db)
    found = search(db, "What does Section 999 of the NI Act say about cheque dishonour?", None)
    assert found.missing_references == ["Section 999 NI"]
    result = answer_question(db, "What does Section 999 of the NI Act say about cheque dishonour?", None)
    assert result.message and result.message.startswith("Not found in the sources: Section 999 NI")


def test_a_private_case_number_is_first_only_for_its_owner(db, hybrid):
    rohan = _user(db, "rohan.sharma@example.com")
    anita = _user(db, "anita.sharma@example.com")
    doc = make_document(db, title="WP 11944-2013 Order", citation="WP 11944-2013 Order", kind="note", owner=rohan,
                        passages=["W.P.No.11944 of 2013. The writ petition is allowed and the order is set aside."])
    db.commit()
    mine = search(db, "Summarise W.P. 11944/2013", rohan)
    assert mine.hits and mine.hits[0].source.document_id == doc.id
    others = search(db, "Summarise W.P. 11944/2013", anita)
    assert all(h.source.document_id != doc.id for h in others.hits)
    assert others.missing_references == ["WP 11944/2013"]


def test_no_more_than_two_passages_from_one_document(db, hybrid):
    long_one = make_document(db, title="Long judgment", citation="Long", passages=[
        f"Quokka habitat ruling part {i}: the quokka habitat must be protected." for i in range(6)])
    for n in range(3):
        make_document(db, title=f"Other {n}", citation=f"Other {n}",
                      passages=[f"Quokka habitat note {n}: the quokka habitat is protected by law."])
    db.commit()
    hits = search(db, "Is the quokka habitat protected?", None, limit=5).hits
    assert len(hits) == 5
    assert sum(1 for h in hits if h.source.document_id == long_one.id) == 2


def test_the_explanation_has_numbers_and_ids_only(db, hybrid):
    exact, _ = _ni_act(db)
    found = search(db, "Section 138 NI Act cheque dishonour", None)
    first = found.ranking["passages"][0]
    assert first["source_id"] == str(exact.id) and first["pinned"] is True
    assert "Dishonour of cheque" not in str(found.ranking)
