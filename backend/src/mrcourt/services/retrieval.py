"""Finds the passages of Indian law that could support an answer.

Candidates come from the database (PostgreSQL full-text search; other databases scan the table),
and only ever from passages the asker may use: shared ones plus their own private notes, from
documents that are ready. Every candidate gets the same minimum-evidence check (how many of the
question's significant terms it contains), so that rule behaves identically everywhere; the
survivors are ranked with BM25. When embeddings are available they can be fused in here (see
services/embeddings.py).
"""

import math
import re
import uuid
from collections import Counter
from contextvars import ContextVar
from dataclasses import dataclass, field, replace

from pgvector.sqlalchemy import Vector
from sqlalchemy import ColumnElement, and_, or_, select, text, type_coerce
from sqlalchemy.orm import Session

from mrcourt.config import get_settings
from mrcourt.models import KnowledgeDocument, LegalSource, User
from mrcourt.models.legal import EMBEDDING_DIMENSIONS
from mrcourt.services import ranking as ranker
from mrcourt.services.metadata import case_label
from mrcourt.services.question_type import classify
from mrcourt.services.references import match as reference_match
from mrcourt.services.references import parse_references
from mrcourt.services.rerank import rerank_scores
from mrcourt.services.embeddings import available, cosine, embed_query, embedder_name, get_embedder

STOPWORDS = frozenset(
    """a about after all also an and any are as at be been but by can could did do does for from
    had has have how i if in into is it its may me my of on or our should so some such than that
    the their them then there these they this to under was we what when where which who whom why
    will with would you your act acts section sections law laws india indian ni please tell
    explain""".split()
)

# Acronyms people type for the instruments in the corpus.
ALIASES = {
    "bnss": "bharatiya nagarik suraksha sanhita",
    "bns": "bharatiya nyaya sanhita",
    "bsa": "bharatiya sakshya adhiniyam",
    "crpc": "code criminal procedure",
    "ipc": "indian penal code",
    "nia": "negotiable instruments",
}
MAX_CANDIDATES = 200
BM25_K1 = 1.4
BM25_B = 0.75
COVERAGE_CUTOFF = 0.6
RRF_K = 60
MEANING_CANDIDATES = 8
RERANK_CANDIDATES = 10


def stem(word: str) -> str:
    """Crude suffix stripping, applied to both questions and passages so forms line up."""
    if len(word) <= 4:
        return word
    for suffix in ("ing", "ed", "es", "s", "e"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def significant_terms(question: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", question.lower())
    expanded: list[str] = []
    for token in tokens:
        expanded.extend(ALIASES.get(token, token).split())
    seen: dict[str, None] = {}
    for token in expanded:
        if token in STOPWORDS or len(token) < 2:
            continue
        seen.setdefault(stem(token))
    return list(seen)


@dataclass
class Retrieved:
    source: LegalSource
    score: float  # 0..1, share of the question's significant terms found in the passage
    rank: float = 0.0  # BM25, used only to order passages
    similarity: float = 0.0  # cosine similarity of meaning, when meaning-based search ran


def _tokens(source: LegalSource) -> list[str]:
    words = re.findall(r"[a-z0-9]+", f"{source.citation_label} {source.text}".lower())
    return [stem(w) for w in words]


def visible_to(user: User | None) -> ColumnElement[bool]:
    """SQL condition: the passage is shared or the asker's own, and its document is ready."""
    owner_ok = LegalSource.owner_id.is_(None)
    if user is not None:
        owner_ok = or_(owner_ok, LegalSource.owner_id == user.id)
    ready = or_(
        LegalSource.document_id.is_(None),
        LegalSource.document_id.in_(
            select(KnowledgeDocument.id).where(KnowledgeDocument.status == "ready")
        ),
    )
    return and_(owner_ok, ready)


# Document-details filters for the current search (feature 008), applied wherever passages are looked up.
_FILTERS: ContextVar[dict[str, object] | None] = ContextVar("search_filters", default=None)


def _scope(user: User | None) -> ColumnElement[bool]:
    condition = visible_to(user)
    filters = _FILTERS.get()
    if filters:
        from mrcourt.services.knowledge import apply_filters

        documents = apply_filters(select(KnowledgeDocument.id), filters)
        condition = and_(condition, LegalSource.document_id.in_(documents))
    return condition


def _section_ok(source: LegalSource, section: str) -> bool:
    """A section filter keeps a statute passage only when it carries that section; other documents refer to it."""
    if getattr(source, "doc_type", None) != "statute":
        return True
    return source.section == section or section in (source.sections or [])


def _candidates(db: Session, terms: list[str], user: User | None) -> list[LegalSource]:
    condition = _scope(user)
    if db.get_bind().dialect.name == "postgresql":
        safe = [re.sub(r"[^a-z0-9]", "", t) for t in terms]
        query = " | ".join(t for t in safe if t)
        if not query:
            return []
        ids = list(
            db.execute(
                text(
                    "SELECT id FROM legal_sources WHERE to_tsvector('english', "
                    "coalesce(citation_label,'') || ' ' || text) @@ to_tsquery('english', :q) "
                    "LIMIT :n"
                ),
                {"q": query, "n": MAX_CANDIDATES},
            ).scalars()
        )
        return list(db.scalars(select(LegalSource).where(LegalSource.id.in_(ids), condition)))
    return list(db.scalars(select(LegalSource).where(condition)))


def _bm25(
    scored: list[tuple[LegalSource, list[str]]],
    corpus: list[tuple[LegalSource, list[str]]],
    terms: list[str],
) -> dict[uuid.UUID, float]:
    """BM25: rare terms count more, long passages count less. Rarity is measured over every
    passage the asker may use (the corpus), so a word found everywhere (like "court") counts little."""
    if not scored:
        return {}
    size = max(len(corpus), 1)
    average = sum(len(tokens) for _, tokens in corpus) / size or 1.0
    document_frequency = {t: sum(1 for _, tokens in corpus if t in tokens) for t in terms}
    scores: dict[uuid.UUID, float] = {}
    for source, tokens in scored:
        counts = Counter(tokens)
        score = 0.0
        for term in terms:
            frequency = counts.get(term, 0)
            if not frequency:
                continue
            df = document_frequency[term]
            idf = math.log(1 + (size - df + 0.5) / (df + 0.5))
            norm = frequency * (BM25_K1 + 1) / (
                frequency + BM25_K1 * (1 - BM25_B + BM25_B * len(tokens) / average)
            )
            score += idf * norm
        scores[source.id] = score
    return scores


@dataclass
class SearchResult:
    hits: list[Retrieved]
    mode: str  # "meaning" (keywords and meaning combined) or "keywords"
    ranking: dict[str, object] | None = None  # hybrid only: why each hit is where it is (ids and numbers)
    missing_references: list[str] = field(default_factory=list)  # named sections or cases not found


def _lexical(
    pool: list[tuple[LegalSource, list[str]]], terms: list[str], min_score: float, relative_cutoff: float
) -> list[Retrieved]:
    """Keyword hits, best first, after the minimum-evidence rule and relative cutoffs."""
    if not terms:
        return []
    evidence: list[tuple[LegalSource, list[str], float]] = []
    for source, tokens in pool:
        have = set(tokens)
        matched = [t for t in terms if t in have]
        score = len(matched) / len(terms)
        has_number = any(t.isdigit() and t in have for t in terms)
        # A one-word question needs that word; longer ones need at least two of their words.
        if score >= min_score and (len(matched) >= min(2, len(terms)) or has_number):
            evidence.append((source, tokens, score))
    if not evidence:
        return []

    ranks = _bm25([(source, tokens) for source, tokens, _ in evidence], pool, terms)
    scored = [Retrieved(source, score, ranks.get(source.id, 0.0)) for source, _, score in evidence]
    scored.sort(key=lambda r: (r.rank, r.score), reverse=True)
    # Keep a passage if it ranks well, or covers nearly as many of the question's terms as the
    # best-covering one (a short provision can rank low yet still be needed, like a companion section).
    best = scored[0].rank
    best_cover = max(r.score for r in scored)
    return [
        r
        for r in scored
        if best <= 0 or r.rank >= relative_cutoff * best or r.score >= COVERAGE_CUTOFF * best_cover
    ]


def meaning_query(user: User | None, query_vector: list[float], limit: int):  # type: ignore[no-untyped-def]
    """PostgreSQL: the nearest passages by meaning. The column type is "JSON, or a vector on PostgreSQL", so it
    is coerced to the vector type for the distance operator."""
    distance = type_coerce(LegalSource.embedding, Vector(EMBEDDING_DIMENSIONS)).cosine_distance(query_vector)
    return (
        select(LegalSource, distance.label("d"))
        .where(_scope(user), LegalSource.embedding.is_not(None))
        .order_by("d")
        .limit(limit)
    )


def _meaning_hits(
    db: Session, query_vector: list[float], user: User | None, pool: list[tuple[LegalSource, list[str]]], model: str | None,
    limit: int = MEANING_CANDIDATES,
) -> tuple[list[Retrieved], bool]:
    """Passages whose meaning is close to the question's, best first. Also says whether any
    passage the person may use has an embedding at all."""
    threshold = get_settings().min_vector_score
    if db.get_bind().dialect.name == "postgresql":
        rows = db.execute(meaning_query(user, query_vector, limit)).all()
        scored = [(source, 1.0 - float(d)) for source, d in rows]
        any_embedded = bool(rows)
    else:
        embedded = [
            s for s, _ in pool if s.embedding is not None and (model is None or s.embedding_model == model)
        ]
        any_embedded = bool(embedded)
        scored = sorted(((s, cosine(query_vector, s.embedding)) for s in embedded), key=lambda x: x[1], reverse=True)  # type: ignore[arg-type]
    scored = [(s, c) for s, c in scored if c >= threshold][:limit]
    return [Retrieved(s, c, 0.0, c) for s, c in scored], any_embedded


def _fuse(lists: list[list[Retrieved]]) -> list[Retrieved]:
    """Reciprocal rank fusion: a passage ranked well in either list, best in both, comes first."""
    total: dict[uuid.UUID, float] = {}
    first: dict[uuid.UUID, Retrieved] = {}
    for ranked in lists:
        for position, hit in enumerate(ranked, start=1):
            total[hit.source.id] = total.get(hit.source.id, 0.0) + 1.0 / (RRF_K + position)
            if hit.source.id in first:
                first[hit.source.id].similarity = max(first[hit.source.id].similarity, hit.similarity)
                first[hit.source.id].rank = max(first[hit.source.id].rank, hit.rank)
                first[hit.source.id].score = max(first[hit.source.id].score, hit.score)
            else:
                first[hit.source.id] = hit
    return [first[i] for i in sorted(total, key=lambda i: (-total[i], str(i)))]


def search(
    db: Session,
    question: str,
    user: User | None = None,
    *,
    limit: int = 8,
    min_score: float = 0.3,
    relative_cutoff: float = 0.5,
    filters: dict[str, object] | None = None,
) -> SearchResult:
    if filters:
        token = _FILTERS.set({k: v for k, v in filters.items() if v not in (None, "")})
        try:
            found = search(db, question, user, limit=limit * 3, min_score=min_score, relative_cutoff=relative_cutoff)
        finally:
            _FILTERS.reset(token)
        section = str(filters.get("section") or "").upper()
        if section:
            found.hits = [h for h in found.hits if _section_ok(h.source, section)]
        found.hits = found.hits[:limit]
        if found.ranking:
            kept = {str(h.source.id) for h in found.hits}
            found.ranking["passages"] = [p for p in found.ranking["passages"] if p["source_id"] in kept]  # type: ignore[index]
        return found
    if get_settings().ranking_mode != "rrf":
        return _hybrid_search(db, question, user, limit=limit, min_score=min_score, relative_cutoff=relative_cutoff)
    terms = significant_terms(question)
    pool = [(source, _tokens(source)) for source in _candidates(db, terms, user)] if terms else []
    keyword_hits = _lexical(pool, terms, min_score, relative_cutoff)

    meaning_hits: list[Retrieved] = []
    any_embedded = False
    mode = "keywords"
    query_vector = embed_query(question) if available() else None
    if query_vector is not None:
        if not pool and db.get_bind().dialect.name != "postgresql":
            # Off PostgreSQL the keyword pool is every passage the person may use; with no keywords
            # it was not loaded, so load it for the meaning list.
            pool = [(s, []) for s in db.scalars(select(LegalSource).where(_scope(user)))]
        embedder = get_embedder()
        meaning_hits, any_embedded = _meaning_hits(db, query_vector, user, pool, embedder_name(embedder))
        if any_embedded:
            mode = "meaning"

    ordered = _fuse([keyword_hits, meaning_hits]) if meaning_hits else keyword_hits
    if meaning_hits:
        # Raw similarity cannot say whether a meaning-only passage really answers the question, so a
        # reranker judges the best candidates. If it is unavailable, only passages with keyword
        # evidence are used: never an unchecked meaning match.
        candidates = ordered[:RERANK_CANDIDATES]
        scores = rerank_scores(question, [h.source.text for h in candidates])
        if scores is None:
            ordered, mode = keyword_hits, "keywords"
        else:
            floor = get_settings().min_rerank_score
            keyword_ids = {h.source.id for h in keyword_hits}
            for hit, score in zip(candidates, scores, strict=True):
                hit.similarity = score
            kept = [h for h in candidates if h.source.id in keyword_ids or h.similarity >= floor]
            kept.sort(key=lambda h: -h.similarity)
            seen = {h.source.id for h in candidates}
            ordered = kept + [h for h in keyword_hits if h.source.id not in seen]
            if not any_embedded:
                mode = "keywords"

    return SearchResult(_current_law(db, ordered)[:limit], mode)


def _current_law(db: Session, ordered: list[Retrieved]) -> list[Retrieved]:
    """Cite current law: swap repealed provisions for their replacements, drop dead ends."""
    current: list[Retrieved] = []
    seen: set[object] = set()
    for hit in ordered:
        source = hit.source
        if source.effective_status == "repealed":
            if source.replaced_by_id is None:
                continue
            successor = db.get(LegalSource, source.replaced_by_id)
            if successor is None:
                continue
            hit = Retrieved(successor, hit.score, hit.rank, hit.similarity)
        if hit.source.id not in seen:
            seen.add(hit.source.id)
            current.append(hit)
    return current


def _matches(ref, source: LegalSource, *, mapped: bool = True) -> str | None:  # type: ignore[no-untyped-def]
    """`mapped=False` leaves out the document's mapped case number (reading it loads the document)."""
    return reference_match(
        ref, instrument=source.instrument or "", section=source.section,
        label=source.citation_label or "", text=source.text or "", sections=source.sections,
        case_number=source.case_number if mapped and ref.kind == "case" else None,
    )


def _case_documents(db: Session, references: list, user: User | None) -> list[LegalSource]:  # type: ignore[type-arg]
    """Passages the person may see whose document's mapped case number is one the question names."""
    wanted = []
    for ref in references:
        if ref.kind != "case" or ref.cnr:
            continue
        label = case_label(ref.case_type or "", ref.number, ref.year)
        wanted.append(KnowledgeDocument.case_number == label)
        if ref.year is None:
            wanted.append(KnowledgeDocument.case_number.like(f"{label}/%"))
    if not wanted:
        return []
    return list(
        db.scalars(
            select(LegalSource)
            .join(KnowledgeDocument, LegalSource.document_id == KnowledgeDocument.id)
            .where(_scope(user), or_(*wanted))
        )
    )


def _hybrid_search(
    db: Session, question: str, user: User | None, *, limit: int, min_score: float, relative_cutoff: float
) -> SearchResult:
    """Feature 009: score every candidate, apply the question's signals, then the same safety rules as before."""
    settings = get_settings()
    rs = ranker.RankSettings.from_settings(settings)
    terms = significant_terms(question)
    pool = [(source, _tokens(source)) for source in _candidates(db, terms, user)] if terms else []
    keyword_hits = _lexical(pool, terms, min_score, relative_cutoff)

    meaning_hits: list[Retrieved] = []
    any_embedded = False
    query_vector = embed_query(question) if available() else None
    if query_vector is not None:
        if not pool and db.get_bind().dialect.name != "postgresql":
            pool = [(s, []) for s in db.scalars(select(LegalSource).where(_scope(user)))]
        meaning_hits, any_embedded = _meaning_hits(
            db, query_vector, user, pool, embedder_name(get_embedder()), limit=settings.rerank_candidates
        )

    candidates: dict[object, ranker.Candidate] = {}
    best_bm25 = max((h.rank for h in keyword_hits), default=0.0)
    for hit in keyword_hits:
        candidates[hit.source.id] = ranker.Candidate(
            hit.source,
            keyword=ranker.keyword_score(hit.rank, best_bm25, hit.score),
            keyword_evidence=True,
            coverage=hit.score,
            bm25=hit.rank,
        )
    for hit in meaning_hits:
        c = candidates.setdefault(hit.source.id, ranker.Candidate(hit.source))
        c.meaning = max(c.meaning, hit.similarity)

    # A named section, article or case is a candidate even if neither search found it.
    references = parse_references(question)
    if references:
        extra = [s for s, _ in pool] if pool else list(db.scalars(select(LegalSource).where(_scope(user))))
        for source in extra:
            if source.id not in candidates and any(_matches(ref, source, mapped=False) == "exact" for ref in references):
                candidates[source.id] = ranker.Candidate(source)
        # A named case is also found through the case number mapped for its document (feature 008): later
        # pages of a judgment do not repeat it.
        for source in _case_documents(db, references, user):
            candidates.setdefault(source.id, ranker.Candidate(source))

    # The signals read each passage's document (type, court, date): load them in one query, not one per passage.
    # The list is kept until the search ends: the session holds loaded objects only while something refers to them.
    document_ids = {c.source.document_id for c in candidates.values() if c.source.document_id is not None}
    documents = (
        db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.id.in_(document_ids))).all() if document_ids else []
    )

    missing = [
        ref.label() for ref in references if not any(_matches(ref, c.source) for c in candidates.values())
    ]

    ctx = ranker.Context(
        question=question,
        references=references,
        question_type=classify(question, user),
        user_id=user.id if user is not None else None,
        rerank_available=False,
    )
    # The shortlist for the answer check weighs both searches equally, whatever the final weights: with a low
    # meaning weight, passages only the meaning search found would otherwise never be checked at all.
    shortlist = replace(rs, w_keyword=1.0, w_meaning=1.0)
    preliminary = ranker.rank(list(candidates.values()), ctx, shortlist)
    judged = preliminary[: settings.rerank_candidates]
    scores = rerank_scores(question, [c.source.text for c in judged]) if judged and meaning_hits else None
    if scores is not None:
        for c, score in zip(judged, scores, strict=True):
            c.rerank = score
        ctx.rerank_available = True
    ordered = ranker.rank(list(candidates.values()), ctx, rs)

    # Safety: the answer check must vouch for a passage (a lower bar when it shares words with the question),
    # unless the question named it exactly. Without an answer check, keyword evidence is required, as before.
    safe = [c for c in ordered if ranker.is_safe(c, ctx, settings.min_rerank_score, settings.min_rerank_score_keyword)]
    chosen = ranker.diversify(safe, rs.per_document, max(limit, 1) * 3)
    hits = _current_law(
        db, [Retrieved(c.source, c.coverage, c.bm25, c.rerank if c.rerank is not None else c.meaning) for c in chosen]
    )[:limit]
    by_id = {c.source.id: c for c in chosen}
    explanation: dict[str, object] = {
        "mode": "hybrid",
        "question_type": ctx.question_type,
        "references": [ref.label() for ref in references],
        "missing_references": missing,
        "passages": [ranker.explain(by_id[h.source.id], i) for i, h in enumerate(hits, start=1) if h.source.id in by_id],
    }
    mode = "meaning" if any_embedded and ctx.rerank_available else "keywords"
    del documents
    return SearchResult(hits, mode, explanation, missing)


def retrieve(
    db: Session,
    question: str,
    user: User | None = None,
    *,
    limit: int = 8,
    min_score: float = 0.3,
    relative_cutoff: float = 0.5,
) -> list[Retrieved]:
    return search(db, question, user, limit=limit, min_score=min_score, relative_cutoff=relative_cutoff).hits
