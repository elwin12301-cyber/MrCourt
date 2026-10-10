"""Judging how well each candidate passage answers the question (reranking).

Meaning-based search is good at ordering passages but its raw similarity numbers cannot tell a
relevant passage from an unrelated one (measured on the reference questions: relevant and unrelated
scores overlap). A reranker reads the question and each passage together and gives a score that does
separate them, so it decides which meaning-only candidates are good enough to cite. If it cannot run,
callers fall back to keyword evidence alone, never to an unchecked meaning match.
"""

import logging
from typing import Protocol

from mrcourt.config import get_settings

logger = logging.getLogger(__name__)


class RerankUnavailable(Exception):
    """The reranking service cannot be used right now."""


class Reranker(Protocol):
    name: str

    def score(self, question: str, texts: list[str]) -> list[float]:
        """A relevance score between 0 and 1 for each text, in the same order."""


class VoyageReranker:
    def __init__(self, api_key: str, model: str) -> None:
        import voyageai

        self._client = voyageai.Client(api_key=api_key, max_retries=0, timeout=20)
        self.name = model

    def score(self, question: str, texts: list[str]) -> list[float]:
        try:
            result = self._client.rerank(question[:2000], [t[:6000] for t in texts], model=self.name)
        except Exception as exc:  # noqa: BLE001 - rate limits and errors both mean "not now"
            raise RerankUnavailable("The reranking service is not available right now") from exc
        scores = [0.0] * len(texts)
        for item in result.results:
            scores[item.index] = float(item.relevance_score)
        return scores


class FakeReranker:
    """Deterministic stand-in for tests: the share of the question's words found in the text, or the
    value from `fixed` when a substring of the text is listed there."""

    name = "fake-rerank"

    def __init__(self, fixed: dict[str, float] | None = None) -> None:
        self.fixed = fixed or {}
        self.calls = 0

    def score(self, question: str, texts: list[str]) -> list[float]:
        self.calls += 1
        words = {w for w in question.lower().replace("?", "").split() if len(w) > 3}
        out = []
        for text in texts:
            lowered = text.lower()
            fixed = next((v for k, v in self.fixed.items() if k.lower() in lowered), None)
            out.append(fixed if fixed is not None else (sum(1 for w in words if w in lowered) / len(words) if words else 0.0))
        return out


_override: Reranker | None = None
_disabled = False


def set_reranker(reranker: Reranker | None, *, disabled: bool = False) -> None:
    """Test hook: replace the reranking service. `disabled=True` imitates having none."""
    global _override, _disabled
    _override, _disabled = reranker, disabled


def get_reranker() -> Reranker | None:
    if _override is not None:
        return _override
    if _disabled:
        return None
    settings = get_settings()
    return VoyageReranker(settings.voyage_api_key, settings.rerank_model) if settings.voyage_api_key else None


def rerank_scores(question: str, texts: list[str]) -> list[float] | None:
    """Scores for each text, or None when the service cannot be used."""
    reranker = get_reranker()
    if reranker is None or not texts:
        return None
    try:
        return reranker.score(question, texts)
    except RerankUnavailable:
        logger.warning("Reranking unavailable; using keyword evidence only")
        return None
