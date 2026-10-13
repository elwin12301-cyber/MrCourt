"""Grounded question answering (constitution principle I).

Flow: retrieve passages -> generate paragraphs that cite those passages -> verify every citation.
Any failure anywhere returns the fixed "could not find a reliable source" outcome. The generator
sees only retrieved passages and is never trusted: `citations.verify` is the gate.
"""

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Protocol

from sqlalchemy.orm import Session

from mrcourt.config import get_settings
from mrcourt.models import LegalSource, User
from mrcourt.services.language import keyword_only_notice, source_language_note
from mrcourt.services.citations import GeneratedParagraph, VerifiedParagraph, verify
from mrcourt.services.retrieval import search

logger = logging.getLogger(__name__)

DISCLAIMER = "Informational only, not legal advice."
NO_SOURCE_MESSAGE = (
    "I could not find a reliable source for that question in the indexed law. "
    "Try rephrasing it, naming the Act or section, or attach a case document so I can search it."
)

SYSTEM_PROMPT = """You answer questions about Indian law for a legal-assistance product.
Use ONLY the numbered passages provided. Never use outside knowledge.
Reply with JSON only, in this shape:
{"paragraphs": [{"text": "...", "sources": ["S1", "S2"]}]}
Rules:
- Every paragraph must list the passage labels that support it.
- Only mention a section number if it appears in a passage you cite.
- If the passages do not answer the question, reply {"paragraphs": []}.
- Be concise and neutral. This is information, not legal advice."""


@dataclass
class AnswerResult:
    outcome: str  # "cited" | "no_reliable_source"
    paragraphs: list[VerifiedParagraph] = field(default_factory=list)
    citations: list[LegalSource] = field(default_factory=list)
    message: str | None = None
    disclaimer: str = DISCLAIMER
    answer_mode: str = "passages"  # "full" when a model wrote the answer, else cited passages only
    search_mode: str = "keywords"  # "meaning" when meaning-based search took part
    source_note: str | None = None  # which language the sources are in, when it differs from the question's
    ranking: dict[str, object] | None = None  # why each source ranked where it did (feature 009)


class AnswerGenerator(Protocol):
    def generate(
        self, question: str, passages: list[LegalSource]
    ) -> list[GeneratedParagraph] | None: ...


class ExtractiveGenerator:
    """No-model fallback: presents each retrieved passage as its own cited paragraph.

    Used when no model API key is configured. It can only repeat the source text, so it is
    grounded by construction.
    """

    def generate(
        self, question: str, passages: list[LegalSource]
    ) -> list[GeneratedParagraph] | None:
        return [GeneratedParagraph(p.text, [p.id]) for p in passages]


class AnthropicGenerator:
    def generate(
        self, question: str, passages: list[LegalSource]
    ) -> list[GeneratedParagraph] | None:
        import anthropic

        settings = get_settings()
        labelled = {f"S{i}": p for i, p in enumerate(passages, start=1)}
        body = "\n\n".join(
            f"[{label}] {p.citation_label}\n{p.text}" for label, p in labelled.items()
        )
        try:
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            message = client.messages.create(
                model=settings.answer_model,
                max_tokens=1500,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": f"Passages:\n\n{body}\n\nQuestion: {question}"}],
            )
            raw = "".join(b.text for b in message.content if getattr(b, "type", "") == "text")
            return _parse_paragraphs(raw, labelled)
        except Exception:  # fail closed: any provider or parsing problem means "no source"
            logger.warning("Answer generation failed; returning no_reliable_source")
            return None


def _parse_paragraphs(raw: str, labelled: dict[str, LegalSource]) -> list[GeneratedParagraph]:
    """The model's JSON reply as paragraphs; labels it invented are dropped (citations are verified later)."""
    start, end = raw.find("{"), raw.rfind("}")
    data = json.loads(raw[start : end + 1])
    paragraphs: list[GeneratedParagraph] = []
    for item in data.get("paragraphs", []):
        ids = [labelled[s].id for s in item.get("sources", []) if s in labelled]
        paragraphs.append(GeneratedParagraph(str(item.get("text", "")), ids))
    return paragraphs


class GeminiGenerator:
    """Google Gemini (has a free tier). Same prompt, same JSON reply, same verification as the other writers."""

    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    RETRY_AFTER = (2.0,)  # seconds to wait before one more try when the free tier says "slow down"

    def __init__(self, client=None, sleep=None) -> None:  # type: ignore[no-untyped-def]
        self._client = client
        self._sleep = sleep

    def generate(
        self, question: str, passages: list[LegalSource]
    ) -> list[GeneratedParagraph] | None:
        import time

        import httpx

        settings = get_settings()
        labelled = {f"S{i}": p for i, p in enumerate(passages, start=1)}
        body = "\n\n".join(f"[{label}] {p.citation_label}\n{p.text}" for label, p in labelled.items())
        payload = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": f"Passages:\n\n{body}\n\nQuestion: {question}"}]}],
            "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 3000, "temperature": 0.2},
        }
        sleep = self._sleep or time.sleep
        try:
            client = self._client or httpx.Client(timeout=httpx.Timeout(30, connect=10))
            headers = {"x-goog-api-key": settings.gemini_api_key}
            models = [m for m in dict.fromkeys((settings.gemini_model, settings.gemini_fallback_model)) if m]
            response = None
            for model in models:
                url = self.URL.format(model=model)
                for wait in (*self.RETRY_AFTER, None):
                    try:
                        response = client.post(url, headers=headers, json=payload)
                    except httpx.TimeoutException:  # a busy model that does not answer in time counts as busy
                        response = httpx.Response(503)
                    if response.status_code in (429, 500, 503) and wait is not None:
                        sleep(wait)
                        continue
                    break
                if response.status_code not in (429, 500, 503):
                    break  # answered, or refused for a reason another model will not change
                logger.warning("Gemini model %s is busy or out of quota; trying the next one", model)
            assert response is not None
            response.raise_for_status()
            parts = response.json()["candidates"][0]["content"]["parts"]
            raw = "".join(str(part.get("text", "")) for part in parts if not part.get("thought"))
            return _parse_paragraphs(raw, labelled)
        except Exception as error:  # fail closed, as for every provider
            # The kind of failure helps (a busy model, an expired key, a bad reply); never the question or passages.
            logger.warning("Gemini answer generation failed (%s)", type(error).__name__)
            return None


_generator_override: AnswerGenerator | None = None


def set_generator(generator: AnswerGenerator | None) -> None:
    """Test hook: replace the answer generator."""
    global _generator_override
    _generator_override = generator


def get_generator() -> AnswerGenerator:
    if _generator_override is not None:
        return _generator_override
    settings = get_settings()
    if settings.anthropic_api_key:
        return AnthropicGenerator()
    if settings.gemini_api_key:
        return GeminiGenerator()
    return ExtractiveGenerator()


def no_source(answer_mode: str = "passages", search_mode: str = "keywords") -> AnswerResult:
    return AnswerResult(
        outcome="no_reliable_source", message=NO_SOURCE_MESSAGE, answer_mode=answer_mode, search_mode=search_mode
    )


NO_FILTER_MATCH = "No source matches the filters you chose. Try fewer filters."
WRITER_BUSY_NOTE = "A written answer was not available just now, so the cited passages are shown as they are."


def answer_question(
    db: Session, question: str, user: User | None = None, filters: dict[str, object] | None = None
) -> AnswerResult:
    """`user` limits retrieval to shared passages plus that person's own private notes; `filters` (document
    details: type, court, year, act, section, case) narrow the sources further."""
    settings = get_settings()
    found = search(db, question, user, limit=5, min_score=settings.min_retrieval_score, filters=filters)
    hits, search_mode = found.hits, found.mode
    # A section or case the question names but no source contains: say so, never pass another off as it.
    missing = missing_note(found.missing_references)
    generator = get_generator()
    mode = "passages" if isinstance(generator, ExtractiveGenerator) else "full"

    def unanswered() -> AnswerResult:
        result = no_source(mode, search_mode)
        result.ranking = found.ranking
        if missing:
            result.message = f"{missing} {NO_SOURCE_MESSAGE}"
        return result

    if not hits:
        result = unanswered()
        if filters and any(filters.values()):
            result.message = f"{NO_FILTER_MATCH} {result.message}"
            return result
        notice = keyword_only_notice(question) if search_mode == "keywords" else None
        if notice:
            result.message = f"{result.message} {notice}"
        return result

    passages = [h.source for h in hits]
    generated = generator.generate(question, passages)
    if generated is None and isinstance(generator, GeminiGenerator):
        # The free Gemini service was busy or refused (None; an empty list means "these passages do not answer").
        # Show the cited passages as they are, as when no model is set up: grounded by construction.
        logger.warning("Gemini unavailable; showing the cited passages as they are")
        mode = "passages"
        missing = " ".join(filter(None, [missing, WRITER_BUSY_NOTE]))
        generated = ExtractiveGenerator().generate(question, passages)
    if not generated:
        return unanswered()

    by_id: dict[uuid.UUID, LegalSource] = {p.id: p for p in passages}
    verified = verify(generated, by_id)  # type: ignore[arg-type]
    if verified is None:
        logger.warning("Generated answer failed citation verification")
        return unanswered()
    return AnswerResult(
        outcome="cited",
        paragraphs=verified.paragraphs,
        citations=list(verified.citations),  # type: ignore[arg-type]
        message=missing,
        answer_mode=mode,
        search_mode=search_mode,
        source_note=source_language_note(question, [p.text for p in verified.citations]),  # type: ignore[attr-defined]
        ranking=found.ranking,
    )


def missing_note(labels: list[str]) -> str | None:
    if not labels:
        return None
    return f"Not found in the sources: {', '.join(labels)}. The sources below are related, not that provision."


def clean_question(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
