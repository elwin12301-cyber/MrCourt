from fastapi import APIRouter

from mrcourt.api.deps import CurrentUser, DbSession
from mrcourt.schemas.questions import AnswerOut, CitationOut, ParagraphOut, QuestionIn
from mrcourt.services import ask as asking
from mrcourt.services import metadata, ratelimit
from mrcourt.services.access import get_visible_case

router = APIRouter(prefix="/questions", tags=["questions"])


@router.post("", response_model=AnswerOut)
def ask(data: QuestionIn, user: CurrentUser, db: DbSession) -> AnswerOut:
    ratelimit.hit(f"ask:{user.id}", limit=30, window_seconds=60)  # protects answer-generation cost
    if data.case_id is not None:
        get_visible_case(db, user, data.case_id)  # 404 if the user cannot see that case

    asked = asking.ask(
        db,
        user,
        data.text,
        filters=data.filters.model_dump() if data.filters else None,
        case_id=data.case_id,
        input_method=data.input_method,
    )
    db.commit()
    result = asked.result
    return AnswerOut(
        question_id=asked.question.id,
        answer_mode=result.answer_mode,  # type: ignore[arg-type]
        search_mode=result.search_mode,  # type: ignore[arg-type]
        source_language_note=result.source_note,
        outcome=result.outcome,  # type: ignore[arg-type]
        paragraphs=[ParagraphOut(**p) for p in asked.answer.paragraphs],
        citations=[
            CitationOut(
                number=i,
                label=s.citation_label,
                source_url=s.source_url,
                passage_id=s.id,
                details=metadata.short_label(s.document, s),
            )
            for i, s in enumerate(result.citations, start=1)
        ],
        message=result.message,
        disclaimer=result.disclaimer,
        case_specific_notice=asked.case_specific_notice,
        lawyer_reminder=asked.lawyer_reminder,
    )
