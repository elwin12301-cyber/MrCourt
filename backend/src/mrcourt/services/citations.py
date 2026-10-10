"""Checks that a generated answer is fully backed by the passages it was given.

This is the gate behind constitution principle I: an answer that fails any check here is never
shown; the user gets the "could not find a reliable source" response instead.
"""

import re
import uuid
from dataclasses import dataclass, field
from typing import Protocol


class SourceLike(Protocol):
    id: uuid.UUID
    section: str | None
    text: str
    citation_label: str


@dataclass
class GeneratedParagraph:
    text: str
    source_ids: list[uuid.UUID]


@dataclass
class VerifiedParagraph:
    text: str
    citation_numbers: list[int]


@dataclass
class VerifiedAnswer:
    paragraphs: list[VerifiedParagraph]
    citations: list[SourceLike] = field(default_factory=list)  # numbered 1.. in this order


_SECTION_REF = re.compile(r"\b(?:section|sections|s\.|article)\s+(\d+[a-z]{0,2})\b", re.IGNORECASE)


def _supports_section(number: str, source: SourceLike) -> bool:
    number = number.lower()
    if (source.section or "").lower() == number:
        return True
    haystack = f"{source.citation_label} {source.text}".lower()
    return re.search(rf"\b(?:sections|section|articles|article|s\.)\s*{re.escape(number)}\b", haystack) is not None


def verify(
    paragraphs: list[GeneratedParagraph], retrieved: dict[uuid.UUID, SourceLike]
) -> VerifiedAnswer | None:
    """Returns the numbered, verified answer, or None if any rule is broken.

    Rules: there is at least one paragraph; each paragraph cites at least one source; every cited
    source was actually retrieved; and any section number a paragraph mentions appears in one of
    the sources it cites.
    """
    if not paragraphs:
        return None

    numbering: dict[uuid.UUID, int] = {}
    order: list[SourceLike] = []
    out: list[VerifiedParagraph] = []
    for paragraph in paragraphs:
        if not paragraph.text.strip() or not paragraph.source_ids:
            return None
        cited: list[SourceLike] = []
        for source_id in paragraph.source_ids:
            source = retrieved.get(source_id)
            if source is None:
                return None
            if source not in cited:
                cited.append(source)
        for number in _SECTION_REF.findall(paragraph.text):
            if not any(_supports_section(number, source) for source in cited):
                return None
        numbers: list[int] = []
        for source in cited:
            if source.id not in numbering:
                numbering[source.id] = len(order) + 1
                order.append(source)
            numbers.append(numbering[source.id])
        out.append(VerifiedParagraph(paragraph.text.strip(), numbers))
    return VerifiedAnswer(out, order)
