import uuid
from datetime import date
from types import SimpleNamespace

import pytest

from mrcourt.services.ranking import (
    Candidate, Context, RankSettings, base_score, diversify, explain, keyword_score, rank,
)
from mrcourt.services.references import parse_references

RS = RankSettings()


def src(**kw):
    defaults = dict(id=uuid.uuid4(), instrument="Some Act", section=None, citation_label="", text="", kind="act_section",
                    owner_id=None, document_id=None)
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def test_keyword_score_mixes_relative_bm25_and_coverage() -> None:
    assert keyword_score(10, 10, 1.0) == 1.0
    assert keyword_score(5, 10, 0.5) == pytest.approx(0.5)
    assert keyword_score(3, 0, 0.4) == pytest.approx(0.2)


def test_weights_are_normalised_and_shared_out_without_an_answer_check() -> None:
    c = Candidate(src(), keyword=1.0, meaning=1.0, rerank=1.0)
    assert base_score(c, RS, rerank_available=True) == pytest.approx(1.0)
    c = Candidate(src(), keyword=1.0, meaning=0.0)
    assert base_score(c, RS, rerank_available=False) == pytest.approx(1.0)
    uneven = RankSettings(w_keyword=2, w_meaning=1, w_rerank=1)
    assert base_score(Candidate(src(), keyword=1.0), uneven, True) == pytest.approx(0.5)


def test_the_answer_check_decides_between_similar_keyword_matches() -> None:
    a = Candidate(src(), keyword=0.8, rerank=0.2)
    b = Candidate(src(), keyword=0.7, rerank=0.9)
    assert rank([a, b], Context(), RS)[0] is b


def test_an_exact_reference_is_pinned_first() -> None:
    exact = Candidate(src(instrument="Negotiable Instruments Act, 1881", section="138"), keyword=0.1)
    strong = Candidate(src(instrument="Negotiable Instruments Act (notes)"), keyword=1.0, rerank=1.0)
    ctx = Context(question="Section 138 NI Act", references=parse_references("Section 138 NI Act"))
    ordered = rank([strong, exact], ctx, RS)
    assert ordered[0] is exact and exact.pinned
    assert explain(exact, 1)["signals"][0]["name"] == "exact_reference"


def test_a_mention_is_boosted_not_pinned() -> None:
    mention = Candidate(src(text="Under Section 138 the drawer is liable", instrument="NI notes"), keyword=0.5)
    other = Candidate(src(), keyword=0.6)
    ctx = Context(references=parse_references("section 138"))
    ordered = rank([other, mention], ctx, RS)
    assert ordered[0] is mention and not mention.pinned


def test_question_type_prefers_the_right_kind_of_document() -> None:
    statute = Candidate(src(kind="act_section"), keyword=0.5)
    judgment = Candidate(src(kind="judgment"), keyword=0.5)
    assert rank([judgment, statute], Context(question_type="law"), RS)[0] is statute
    assert rank([statute, judgment], Context(question_type="courts"), RS)[0] is judgment


def test_own_case_documents_first_for_my_case_questions_only() -> None:
    me = uuid.uuid4()
    mine = Candidate(src(kind="note", owner_id=me), keyword=0.5)
    shared = Candidate(src(), keyword=0.55)
    assert rank([shared, mine], Context(question_type="my_case", user_id=me), RS)[0] is mine
    assert rank([shared, mine], Context(question_type="other", user_id=me), RS)[0] is shared


def test_recency_and_court_signals_when_details_exist() -> None:
    new = Candidate(src(kind="judgment", decided_on=date(2024, 1, 1)), keyword=0.5)
    old = Candidate(src(kind="judgment", decided_on=date(1990, 1, 1)), keyword=0.5)
    ordered = rank([old, new], Context(question_type="courts", today=date(2026, 1, 1)), RS)
    assert ordered[0] is new
    madras = Candidate(src(kind="judgment", court="Madras High Court"), keyword=0.5)
    other = Candidate(src(kind="judgment", court="Delhi High Court"), keyword=0.5)
    assert rank([other, madras], Context(question="what did the Madras High Court hold?"), RS)[0] is madras


def test_missing_details_give_no_boost_and_no_penalty() -> None:
    plain = Candidate(src(kind="judgment"), keyword=0.5)
    rank([plain], Context(question_type="courts", question="Madras High Court"), RS)
    assert [s.name for s in plain.signals] == ["type_judgment"]


def test_ties_prefer_shared_sources() -> None:
    mine = Candidate(src(owner_id=uuid.uuid4()), keyword=0.5)
    shared = Candidate(src(), keyword=0.5)
    assert rank([mine, shared], Context(), RS)[0] is shared


def test_at_most_two_per_document_unless_nothing_else() -> None:
    doc = uuid.uuid4()
    long_judgment = [Candidate(src(document_id=doc), combined=1 - i / 100) for i in range(6)]
    others = [Candidate(src(document_id=uuid.uuid4())) for _ in range(3)]
    chosen = diversify(long_judgment + others, per_document=2, limit=5)
    assert sum(1 for c in chosen if c.source.document_id == doc) == 2 and len(chosen) == 5
    only = diversify(long_judgment, per_document=2, limit=5)
    assert len(only) == 5  # nothing else qualifies: the cap is lifted


def test_pinned_passages_count_toward_the_cap() -> None:
    doc = uuid.uuid4()
    named_case = [Candidate(src(document_id=doc), combined=0.5, pinned=True) for _ in range(6)]
    others = [Candidate(src(document_id=uuid.uuid4()), combined=0.9) for _ in range(3)]
    chosen = diversify(named_case + others, per_document=2, limit=5)
    assert [c.pinned for c in chosen[:2]] == [True, True]
    assert sum(1 for c in chosen if c.source.document_id == doc) == 2
