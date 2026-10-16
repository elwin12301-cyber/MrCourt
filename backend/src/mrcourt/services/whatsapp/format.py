"""An answer as a short WhatsApp message (feature 010): the answer, its sources by name, the disclaimer, a link.

The words come from the same answer as on the website. Only the length changes: the answer is cut at a sentence
to fit a phone, but the sources, the disclaimer and (for clients) the reminder to ask their lawyer are never dropped.
"""

from mrcourt.config import get_settings
from mrcourt.services.answering import NO_SOURCE_MESSAGE, AnswerResult

ANSWER_BUDGET = 700  # characters for the answer paragraphs
MAX_SOURCES = 4
SOURCE_WIDTH = 90


def _cut(text: str, limit: int) -> str:
    """The text cut at the last sentence that fits (or the last word), with a mark that it goes on."""
    if len(text) <= limit:
        return text
    head = text[:limit]
    end = max(head.rfind(". "), head.rfind("? "), head.rfind("! "), head.rfind("। "))
    if end >= limit * 0.4:
        return head[: end + 1] + " …"
    return head.rsplit(" ", 1)[0].rstrip(",;:") + " …"


def _answer_body(result: AnswerResult) -> str:
    """The paragraphs within the budget. Each keeps its citation mark even when its words are cut."""
    pieces: list[str] = []
    left = ANSWER_BUDGET
    for paragraph in result.paragraphs:
        marks = f" [{', '.join(str(n) for n in paragraph.citation_numbers)}]" if paragraph.citation_numbers else ""
        if pieces and left < 120:
            pieces.append("…")
            break
        piece = _cut(paragraph.text.strip(), max(left - len(marks), 60)) + marks
        pieces.append(piece)
        left -= len(piece) + 2
    return "\n\n".join(pieces)


def _label(text: str) -> str:
    return text if len(text) <= SOURCE_WIDTH else text[: SOURCE_WIDTH - 1].rstrip() + "…"


def answer_text(result: AnswerResult, *, case_specific_notice: str | None = None, lawyer_reminder: str | None = None) -> str:
    """The whole reply for a question: notice, answer, sources, disclaimer, reminder and the link."""
    parts: list[str] = []
    if case_specific_notice:
        parts.append(case_specific_notice)
    if result.outcome == "cited" and result.paragraphs:
        if result.message:  # for example: Not found in the sources: Section 999 IPC. The sources below are related...
            parts.append(result.message)
        parts.append(_answer_body(result))
        shown = result.citations[:MAX_SOURCES]
        lines = [f"[{i}] {_label(c.citation_label)}" for i, c in enumerate(shown, start=1)]
        if len(result.citations) > len(shown):
            lines.append(f"+{len(result.citations) - len(shown)} more in MrCourt")
        parts.append("Sources:\n" + "\n".join(lines))
    else:
        parts.append(result.message or NO_SOURCE_MESSAGE)
    parts.append(result.disclaimer)
    if lawyer_reminder:
        parts.append(lawyer_reminder)
    parts.append("Read more: " + get_settings().public_app_url.rstrip("/") + "/ask/history")
    return "\n\n".join(parts)
