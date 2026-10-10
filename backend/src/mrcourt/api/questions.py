from fastapi import APIRouter

from mrcourt.api.deps import CurrentUser, DbSession
from mrcourt.models import Answer, AnswerCitation, Question
from mrcourt.schemas.questions import AnswerOut, CitationOut, ParagraphOut, QuestionIn
from mrcourt.services import ratelimit
from mrcourt.services.access import get_visible_case
from mrcourt.services.advice_guard import CASE_SPECIFIC_NOTICE, LAWYER_REMINDER, looks_case_specific
from mrcourt.services.answering import answer_question

router = APIRouter(prefix="/questions", tags=["questions"])


@router.post("", response_model=AnswerOut)
def ask(data: QuestionIn, user: CurrentUser, db: DbSession) -> AnswerOut:
    ratelimit.hit(f"ask:{user.id}", limit=30, window_seconds=60)  # protects answer-generation cost
    if data.case_id is not None:
        get_visible_case(db, user, data.case_id)  # 404 if the user cannot see that case

    result = answer_question(db, data.text, user)

    question = Question(
        user_id=user.id, case_id=data.case_id, text=data.text, input_method=data.input_method
    )
    answer = Answer(
        outcome=result.outcome,
        paragraphs=[
            {"text": p.text, "citation_numbers": p.citation_numbers} for p in result.paragraphs
        ],
        disclaimer=result.disclaimer,
        answer_mode=result.answer_mode,
    )
    question.answer = answer
    for number, source in enumerate(result.citations, start=1):
        answer.citations.append(
            AnswerCitation(
                source_id=source.id,
                position=number,
                label=source.citation_label,
                source_url=source.source_url,
            )
        )
    db.add(question)
    db.commit()

    is_client = user.role == "petitioner"
    return AnswerOut(
        question_id=question.id,
        answer_mode=result.answer_mode,  # type: ignore[arg-type]
        search_mode=result.search_mode,  # type: ignore[arg-type]
        source_language_note=result.source_note,
        outcome=result.outcome,  # type: ignore[arg-type]
        paragraphs=[ParagraphOut(**p) for p in answer.paragraphs],
        citations=[
            CitationOut(number=i, label=s.citation_label, source_url=s.source_url, passage_id=s.id)
            for i, s in enumerate(result.citations, start=1)
        ],
        message=result.message,
        disclaimer=result.disclaimer,
        # Clients get general information only, and are pointed to their lawyer for their own case.
        case_specific_notice=CASE_SPECIFIC_NOTICE if is_client and looks_case_specific(data.text) else None,
        lawyer_reminder=LAWYER_REMINDER if is_client else None,
    )
