import uuid

from fastapi import APIRouter, HTTPException, status

from mrcourt.api.deps import CurrentUser, DbSession
from mrcourt.config import get_settings
from mrcourt.models import Answer, AnswerCitation, Question
from mrcourt.schemas.assistant import (
    ActionResult,
    AssistantRequestIn,
    AssistantResponse,
    AssistantStatus,
    ProposedActionOut,
    StepOut,
)
from mrcourt.schemas.questions import CitationOut, ParagraphOut
from mrcourt.services import assistant, assistant_actions, embeddings, ocr, ratelimit, speech
from mrcourt.services.advice_guard import CASE_SPECIFIC_NOTICE, LAWYER_REMINDER, looks_case_specific

router = APIRouter(prefix="/assistant", tags=["assistant"])

PASSAGES_ONLY_NOTICE = (
    "Running with cited passages only: no AI service is set up, so answers repeat the matching "
    "passages and the assistant is switched off."
)


@router.get("/status", response_model=AssistantStatus)
def get_status(user: CurrentUser) -> AssistantStatus:
    full = bool(get_settings().anthropic_api_key)
    return AssistantStatus(
        answers="full" if full else "passages",
        assistant=assistant.available() and user.role in ("advocate", "petitioner"),
        notice=None if full else PASSAGES_ONLY_NOTICE,
        search="meaning" if embeddings.available() else "keywords",
        speech=speech.available(),
        ocr=ocr.available(),
    )


@router.post("/requests", response_model=AssistantResponse)
def make_request(data: AssistantRequestIn, user: CurrentUser, db: DbSession) -> AssistantResponse:
    if user.role not in ("advocate", "petitioner"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "The assistant is not available to this account")
    if not assistant.available():
        raise HTTPException(status.HTTP_409_CONFLICT, "assistant_unavailable")
    ratelimit.hit(f"assistant:{user.id}", limit=10, window_seconds=60)

    question = Question(user_id=user.id, text=data.text, input_method=data.input_method, mode="assistant")
    db.add(question)
    db.flush()
    result = assistant.run(db, user, data.text, question.id)

    answer = Answer(
        outcome=result.outcome,
        paragraphs=result.paragraphs,
        disclaimer=result.disclaimer,
        answer_mode="full",
        steps=result.steps,
        ranking=result.ranking,
    )
    question.answer = answer
    for number, source in enumerate(result.citations, start=1):
        answer.citations.append(
            AnswerCitation(
                source_id=source.id, position=number, label=source.citation_label, source_url=source.source_url
            )
        )
    db.commit()

    is_client = user.role == "petitioner"
    return AssistantResponse(
        question_id=question.id,
        outcome=result.outcome,  # type: ignore[arg-type]
        steps=[StepOut(**s) for s in result.steps],
        paragraphs=[ParagraphOut(**p) for p in result.paragraphs],
        citations=[
            CitationOut(number=i, label=s.citation_label, source_url=s.source_url, passage_id=s.id)
            for i, s in enumerate(result.citations, start=1)
        ],
        message=result.message,
        proposed_action=(
            ProposedActionOut(
                id=result.proposal.id,
                kind=result.proposal.kind,
                summary=result.proposal.summary,
                expires_at=result.proposal.expires_at,
            )
            if result.proposal is not None
            else None
        ),
        disclaimer=result.disclaimer,
        case_specific_notice=CASE_SPECIFIC_NOTICE if is_client and looks_case_specific(data.text) else None,
        lawyer_reminder=LAWYER_REMINDER if is_client else None,
    )


@router.post("/actions/{action_id}/confirm", response_model=ActionResult)
def confirm(action_id: uuid.UUID, user: CurrentUser, db: DbSession) -> ActionResult:
    draft_id = assistant_actions.confirm(db, user, action_id)
    db.commit()
    return ActionResult(status="done", draft_id=draft_id)


@router.post("/actions/{action_id}/decline", response_model=ActionResult)
def decline(action_id: uuid.UUID, user: CurrentUser, db: DbSession) -> ActionResult:
    assistant_actions.decline(db, user, action_id)
    db.commit()
    return ActionResult(status="declined")
