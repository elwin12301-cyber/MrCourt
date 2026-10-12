"""Hybrid ranking (feature 009): word-match, meaning-match and answer-check scores combined with weights, plus
signals from the question (exact references, kind of question, court, recency, the advocate's own case).

No database access here: `retrieval.search` gathers the candidates and applies the safety rules; this module
only orders them and explains the order. An exact reference ("Section 138 NI Act") is pinned first.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from mrcourt.services.references import Reference, match


@dataclass
class Signal:
    name: str
    label: str
    value: float | str


@dataclass
class Candidate:
    source: Any  # LegalSource
    keyword: float = 0.0  # 0..1: half best-relative BM25, half share of the question's words found
    meaning: float = 0.0  # 0..1 cosine similarity
    rerank: float | None = None  # 0..1 answer-check score; None when not judged
    keyword_evidence: bool = False  # passed the keyword evidence rule
    coverage: float = 0.0
    bm25: float = 0.0
    pinned: bool = False
    signals: list[Signal] = field(default_factory=list)
    combined: float = 0.0


@dataclass
class RankSettings:
    w_keyword: float = 0.35
    w_meaning: float = 0.15
    w_rerank: float = 0.50
    boost_section: float = 0.25
    boost_type: float = 0.10
    boost_court: float = 0.08
    boost_own_case: float = 0.15
    recency_max: float = 0.05
    per_document: int = 2

    @classmethod
    def from_settings(cls, s: Any) -> "RankSettings":
        return cls(
            s.rank_w_keyword, s.rank_w_meaning, s.rank_w_rerank, s.rank_boost_section, s.rank_boost_type,
            s.rank_boost_court, s.rank_boost_own_case, s.rank_recency_max, s.rank_per_document,
        )


@dataclass
class Context:
    question: str = ""
    references: list[Reference] = field(default_factory=list)
    question_type: str = "other"
    user_id: Any = None
    rerank_available: bool = True
    today: date = field(default_factory=date.today)


def keyword_score(bm25: float, best_bm25: float, coverage: float) -> float:
    relative = bm25 / best_bm25 if best_bm25 > 0 else 0.0
    return max(0.0, min(1.0, 0.5 * relative + 0.5 * coverage))


def base_score(c: Candidate, rs: RankSettings, rerank_available: bool) -> float:
    """Weighted sum of the three scores; without an answer check at all, its weight is shared out."""
    parts = [(rs.w_keyword, c.keyword), (rs.w_meaning, max(0.0, min(1.0, c.meaning)))]
    if rerank_available:
        parts.append((rs.w_rerank, c.rerank or 0.0))
    total = sum(w for w, _ in parts) or 1.0
    return sum(w * v for w, v in parts) / total


def _year(source: Any) -> int | None:
    value = getattr(source, "decided_on", None) or getattr(source, "decided_year", None)
    if isinstance(value, date):
        return value.year
    return int(value) if isinstance(value, int) else None


def apply_signals(c: Candidate, ctx: Context, rs: RankSettings) -> None:
    c.signals, c.pinned = [], False
    s = c.source
    for ref in ctx.references:
        found = match(
            ref, instrument=s.instrument or "", section=s.section, label=s.citation_label or "", text=s.text or "",
            sections=getattr(s, "sections", None),
        )
        if found == "exact":
            c.pinned = True
            c.signals.append(Signal("exact_reference", "Named in the question", ref.label()))
        elif found == "mentions":
            c.signals.append(Signal("mentions_reference", "Mentions what the question names", rs.boost_section))
    # The mapped document type (feature 008) when known, else the passage kind.
    kind = {"statute": "act_section"}.get(getattr(s, "doc_type", None) or "", getattr(s, "doc_type", None) or getattr(s, "kind", None))
    shared = getattr(s, "owner_id", None) is None
    if ctx.question_type == "law" and kind == "act_section" and shared:
        c.signals.append(Signal("type_statute", "Law text suits this question", rs.boost_type))
    if ctx.question_type == "courts" and kind == "judgment":
        c.signals.append(Signal("type_judgment", "A judgment suits this question", rs.boost_type))
    if ctx.question_type == "my_case" and ctx.user_id is not None and getattr(s, "owner_id", None) == ctx.user_id:
        c.signals.append(Signal("own_case", "Your own case document", rs.boost_own_case))
    court = getattr(s, "court", None)
    if court and court.lower() in ctx.question.lower():
        c.signals.append(Signal("court", "Same court as in the question", rs.boost_court))
    year = _year(s)
    if year is not None and kind == "judgment" and ctx.question_type == "courts":
        age = max(0, ctx.today.year - year)
        boost = round(rs.recency_max * max(0.0, 1 - age / 20), 4)
        if boost > 0:
            c.signals.append(Signal("recent", "Recent judgment", boost))


def _sort_key(c: Candidate) -> tuple:
    year = _year(c.source) or 0
    return (not c.pinned, -c.combined, -year, getattr(c.source, "owner_id", None) is not None, str(c.source.id))


def rank(candidates: list[Candidate], ctx: Context, rs: RankSettings) -> list[Candidate]:
    for c in candidates:
        apply_signals(c, ctx, rs)
        boost = sum(sig.value for sig in c.signals if isinstance(sig.value, float))
        c.combined = round(base_score(c, rs, ctx.rerank_available) + boost, 6)
    return sorted(candidates, key=_sort_key)


def _document(c: Candidate) -> object:
    return getattr(c.source, "document_id", None) or getattr(c.source, "instrument", None) or c.source.id


def diversify(ordered: list[Candidate], per_document: int, limit: int) -> list[Candidate]:
    """At most `per_document` passages from one document; the rest only when nothing else is left."""
    chosen: list[Candidate] = []
    held: list[Candidate] = []
    counts: dict[object, int] = {}
    for c in ordered:
        key = _document(c)
        if c.pinned or counts.get(key, 0) < per_document:
            chosen.append(c)
            counts[key] = counts.get(key, 0) + 1
        else:
            held.append(c)
        if len(chosen) >= limit:
            return chosen
    return (chosen + held)[:limit]


def explain(c: Candidate, position: int) -> dict[str, object]:
    """The explanation kept with an answer: ids and numbers only, never passage text or names."""
    return {
        "source_id": str(c.source.id),
        "position": position,
        "pinned": c.pinned,
        "scores": {
            "keyword": round(c.keyword, 3),
            "meaning": round(c.meaning, 3),
            "rerank": None if c.rerank is None else round(c.rerank, 3),
            "combined": round(c.combined, 3),
        },
        "signals": [{"name": s.name, "label": s.label, "value": s.value} for s in c.signals],
    }


Ranker = Callable[[list[Candidate], Context, RankSettings], list[Candidate]]
