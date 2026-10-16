"""Asking a legal question: the one path the website and WhatsApp both use (feature 010).

Retrieval, the written answer, citation checking, the client advice rule and storing the question with its answer
all happen here, so an answer cannot differ between the two channels. The caller commits.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from mrcourt.models import Answer, AnswerCitation, Question, User
from mrcourt.services.advice_guard import CASE_SPECIFIC_NOTICE, LAWYER_REMINDER, looks_case_specific
from mrcourt.services.answering import AnswerResult, answer_question


@dataclass
class Asked:
    question: Question
    answer: Answer
    result: AnswerResult
    case_specific_notice: str | None  # clients only: shown when the question sounds like it is about their own case
    lawyer_reminder: str | None  # clients only: the standing reminder to ask their lawyer


def ask(
    db: Session,
    user: User,
    text: str,
    *,
    filters: dict[str, object] | None = None,
    case_id=None,  # noqa: ANN001 - a UUID or None
    input_method: str = "typed",
    channel: str = "app",
    shared_sources_only: bool = False,
) -> Asked:
    """Answers `text` for `user` and stores the question. With `shared_sources_only` the person's own private
    documents are not searched or quoted (used for WhatsApp, where a message is kept by the provider)."""
    result = answer_question(db, text, None if shared_sources_only else user, filters)
    question = Question(user_id=user.id, case_id=case_id, text=text, input_method=input_method, channel=channel)
    answer = Answer(
        outcome=result.outcome,
        paragraphs=[{"text": p.text, "citation_numbers": p.citation_numbers} for p in result.paragraphs],
        disclaimer=result.disclaimer,
        answer_mode=result.answer_mode,
        ranking=result.ranking,
    )
    question.answer = answer
    for number, source in enumerate(result.citations, start=1):
        answer.citations.append(
            AnswerCitation(source_id=source.id, position=number, label=source.citation_label, source_url=source.source_url)
        )
    db.add(question)
    db.flush()
    is_client = user.role == "petitioner"
    return Asked(
        question=question,
        answer=answer,
        result=result,
        # Clients get general information only, and are pointed to their lawyer for their own case.
        case_specific_notice=CASE_SPECIFIC_NOTICE if is_client and looks_case_specific(text) else None,
        lawyer_reminder=LAWYER_REMINDER if is_client else None,
    )
