"""Text embeddings for meaning-based search.

A passage and a question are each turned into a list of numbers; passages whose numbers point the
same way as the question's are about the same thing, even when they use different words. Voyage AI
makes the embeddings (its model is multilingual, so Tamil and English share one space). Everything
here fails soft: with no key, or when the service is down, callers get None and search carries on
with keyword ranking alone.
"""

import hashlib
import logging
import math
import re
import time
from typing import Literal, Protocol

from sqlalchemy.orm import Session

from mrcourt.config import get_settings
from mrcourt.models import LegalSource

logger = logging.getLogger(__name__)

EMBEDDING_DIMENSIONS = 1024
InputType = Literal["query", "document"]
BATCH = 64
BATCH_CHARS = 22_000  # about 7,000 tokens: free-tier accounts allow about 10,000 tokens a minute
RATE_LIMIT_WAIT_SECONDS = 21.0  # free-tier accounts allow only a few requests a minute
MAX_RATE_LIMIT_RETRIES = 8


class EmbeddingUnavailable(Exception):
    """The embedding service cannot be used right now (no key, rate limited, or an error)."""


class Embedder(Protocol):
    name: str

    def embed(self, texts: list[str], input_type: InputType, *, patient: bool = False) -> list[list[float]]: ...


def _batches(texts: list[str]) -> list[list[str]]:
    """Groups texts so no request is longer than the free-tier token limit allows."""
    groups: list[list[str]] = []
    current: list[str] = []
    size = 0
    for text in texts:
        if current and (len(current) >= BATCH or size + len(text) > BATCH_CHARS):
            groups.append(current)
            current, size = [], 0
        current.append(text)
        size += len(text)
    if current:
        groups.append(current)
    return groups


class VoyageEmbedder:
    """Voyage AI. `patient=True` waits out rate limits (background work); otherwise it gives up
    at once so a question is never held up."""

    def __init__(self, api_key: str, model: str) -> None:
        import voyageai

        self._client = voyageai.Client(api_key=api_key, max_retries=0, timeout=20)
        self.name = model

    def embed(self, texts: list[str], input_type: InputType, *, patient: bool = False) -> list[list[float]]:
        import voyageai.error

        out: list[list[float]] = []
        for batch in _batches(texts):
            retries = MAX_RATE_LIMIT_RETRIES if patient else 0
            attempt = 0
            while True:
                try:
                    result = self._client.embed(
                        batch, model=self.name, input_type=input_type, output_dimension=EMBEDDING_DIMENSIONS
                    )
                    out.extend([list(map(float, e)) for e in result.embeddings])
                    break
                except voyageai.error.RateLimitError as exc:
                    if retries <= 0:
                        raise EmbeddingUnavailable("The embedding service is busy") from exc
                    retries -= 1
                    attempt += 1
                    time.sleep(min(RATE_LIMIT_WAIT_SECONDS * attempt, 65.0))  # per-minute limits: wait out the window
                except Exception as exc:  # noqa: BLE001 - any provider error means "not available"
                    raise EmbeddingUnavailable("The embedding service failed") from exc
        return out


_TOKEN = re.compile(r"[^\W_]+")


class FakeEmbedder:
    """Deterministic stand-in for tests: a hashed bag of words, so texts that share words are close.
    Pass `meanings` to make chosen phrases land on the same direction (to imitate synonyms)."""

    name = "fake"

    def __init__(self, meanings: dict[str, str] | None = None) -> None:
        self.meanings = {k.lower(): v.lower() for k, v in (meanings or {}).items()}
        self.calls: list[tuple[str, int]] = []

    def embed(self, texts: list[str], input_type: InputType, *, patient: bool = False) -> list[list[float]]:
        self.calls.append((input_type, len(texts)))
        return [self._one(t) for t in texts]

    def _one(self, text: str) -> list[float]:
        lowered = text.lower()
        for phrase, canonical in self.meanings.items():
            if phrase in lowered:
                lowered += f" {canonical} {canonical} {canonical}"
        vector = [0.0] * EMBEDDING_DIMENSIONS
        for word in _TOKEN.findall(lowered):
            digest = hashlib.sha256(word.encode()).digest()
            vector[int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSIONS] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


_override: Embedder | None = None
_disabled = False


def set_embedder(embedder: Embedder | None, *, disabled: bool = False) -> None:
    """Test hook: replace the embedding service. `disabled=True` imitates having no key."""
    global _override, _disabled
    _override, _disabled = embedder, disabled


def get_embedder() -> Embedder | None:
    if _override is not None:
        return _override
    if _disabled:
        return None
    settings = get_settings()
    if settings.voyage_api_key:
        return VoyageEmbedder(settings.voyage_api_key, settings.embedding_model)
    return None


def available() -> bool:
    return get_embedder() is not None


def embed_query(text: str) -> list[float] | None:
    """The question's embedding, or None when meaning-based search cannot be used right now."""
    embedder = get_embedder()
    if embedder is None or not text.strip():
        return None
    try:
        return embedder.embed([text[:2000]], "query")[0]
    except EmbeddingUnavailable:
        logger.warning("Embedding service unavailable; searching by keywords only")
        return None


def embed_passages(db: Session, passages: list[LegalSource], *, patient: bool = True) -> int:
    """Gives each passage without one its embedding. Returns how many were embedded."""
    embedder = get_embedder()
    todo = [p for p in passages if p.embedding is None or p.embedding_model != embedder_name(embedder)]
    if embedder is None or not todo:
        return 0
    try:
        vectors = embedder.embed([f"{p.citation_label}\n{p.text}"[:6000] for p in todo], "document", patient=patient)
    except EmbeddingUnavailable:
        logger.warning("Could not embed %d passages now; they stay keyword-searchable", len(todo))
        return 0
    for passage, vector in zip(todo, vectors, strict=True):
        passage.embedding = vector
        passage.embedding_model = embedder.name
    db.flush()
    return len(todo)


def embedder_name(embedder: Embedder | None) -> str | None:
    return embedder.name if embedder is not None else None


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def embed_text(text: str) -> list[float] | None:
    """Kept for older callers; passages are now embedded after they are added."""
    return None
