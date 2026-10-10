"""A person's own question history. It is personal data: only the asker can open it, and it is
exported and deleted with the account. Administrators see only a list, through the audit log."""

import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from mrcourt.models import Answer, Question, TextConversation, User
from mrcourt.schemas.assistant import StepOut
from mrcourt.schemas.history import HistoryDetail, HistoryItem, HistoryPage, WorkspaceItem, WorkspacePage
from mrcourt.schemas.questions import CitationOut, ParagraphOut
from mrcourt.schemas.text import LineOut
from mrcourt.services.advice_guard import LAWYER_REMINDER
from mrcourt.services.answering import DISCLAIMER, NO_SOURCE_MESSAGE
from mrcourt.services.cases import aware

ANSWERED = ("cited", "answered")


def outcome_label(answer: Answer | None, mode: str = "answer") -> str:
    if mode == "text":
        return "Saved"
    return "Answered" if answer is not None and answer.outcome in ANSWERED else "No information found"


def _item(q: Question) -> HistoryItem:
    return HistoryItem(
        id=q.id,
        text=q.text,
        created_at=aware(q.created_at),
        input_method=q.input_method,  # type: ignore[arg-type]
        mode=q.mode,  # type: ignore[arg-type]
        outcome_label=outcome_label(q.answer, q.mode),  # type: ignore[arg-type]
    )


def parse_cursor(value: str) -> tuple[datetime, uuid.UUID]:
    try:
        stamp, ident = value.split("|", 1)
        return datetime.fromisoformat(stamp), uuid.UUID(ident)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Bad cursor") from exc


def _filtered(
    query,  # type: ignore[no-untyped-def]
    *,
    q: str | None,
    outcome: str | None,
    input_method: str | None,
    mode: str | None,
    source: str | None,
    before: str | None,
):
    if q and q.strip():
        query = query.where(func.lower(Question.text).like(f"%{q.strip().lower()}%"))
    if input_method in ("typed", "voice"):
        query = query.where(Question.input_method == input_method)
    if mode in ("answer", "assistant"):
        query = query.where(Question.mode == mode)
    if source == "ask":
        query = query.where(Question.mode.in_(("answer", "assistant")))
    elif source == "text":
        query = query.where(Question.mode == "text")
    if outcome in ("answered", "none"):
        query = query.where(Question.mode != "text")  # saved conversations have no outcome
        answered = select(Answer.question_id).where(Answer.outcome.in_(ANSWERED))
        query = query.where(Question.id.in_(answered) if outcome == "answered" else Question.id.not_in(answered))
    if before:
        stamp, ident = parse_cursor(before)
        query = query.where(or_(Question.created_at < stamp, and_(Question.created_at == stamp, Question.id < ident)))
    return query.order_by(Question.created_at.desc(), Question.id.desc())


def _cursor(page: list[Question]) -> str:
    return f"{aware(page[-1].created_at).isoformat()}|{page[-1].id}"


def list_questions(
    db: Session,
    user_id: uuid.UUID,
    *,
    q: str | None = None,
    outcome: str | None = None,
    input_method: str | None = None,
    mode: str | None = None,
    source: str | None = None,
    limit: int = 20,
    before: str | None = None,
) -> HistoryPage:
    query = _filtered(
        select(Question).options(selectinload(Question.answer)).where(Question.user_id == user_id),
        q=q, outcome=outcome, input_method=input_method, mode=mode, source=source, before=before,
    )
    rows = list(db.scalars(query.limit(limit + 1)))
    page, more = rows[:limit], len(rows) > limit
    return HistoryPage(items=[_item(r) for r in page], next_before=_cursor(page) if more and page else None)


def list_workspace(
    db: Session,
    *,
    q: str | None = None,
    outcome: str | None = None,
    input_method: str | None = None,
    mode: str | None = None,
    source: str | None = None,
    limit: int = 20,
    before: str | None = None,
) -> WorkspacePage:
    """Everyone's questions, for an administrator: who asked and what, never the answers."""
    query = _filtered(
        select(Question).options(selectinload(Question.answer)),
        q=q, outcome=outcome, input_method=input_method, mode=mode, source=source, before=before,
    )
    rows = list(db.scalars(query.limit(limit + 1)))
    page, more = rows[:limit], len(rows) > limit
    askers = {u.id: u for u in db.scalars(select(User).where(User.id.in_({r.user_id for r in page})))}
    items = []
    for r in page:
        asker = askers.get(r.user_id)
        items.append(
            WorkspaceItem(
                **_item(r).model_dump(),
                asker_id=r.user_id,
                asker_name=asker.full_name if asker else "Unknown",
                asker_role=asker.role if asker else "advocate",  # type: ignore[arg-type]
            )
        )
    return WorkspacePage(items=items, next_before=_cursor(page) if more and page else None)


def open_question(db: Session, user: User, question_id: uuid.UUID) -> HistoryDetail:
    question = db.get(Question, question_id)
    if question is None or question.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    answer = question.answer
    item = _item(question)
    if question.mode == "text":
        conversation = db.get(TextConversation, question.conversation_id) if question.conversation_id else None
        return HistoryDetail(
            **item.model_dump(),
            outcome="saved",
            answer_mode="passages",
            paragraphs=[],
            citations=[],
            disclaimer=DISCLAIMER,
            lines=[LineOut(id=line.id, text=line.text, source=line.source, created_at=line.created_at) for line in conversation.lines]  # type: ignore[arg-type]
            if conversation
            else [],
            conversation_id=question.conversation_id,
            conversation_deleted=conversation is None or conversation.deleted_at is not None,
        )
    citations = []
    if answer is not None:
        for c in answer.citations:
            label = c.label or (c.source.citation_label if c.source else "A source that has since been removed")
            citations.append(CitationOut(number=c.position, label=label, source_url=c.source_url, passage_id=c.source_id))
    outcome = answer.outcome if answer else "no_reliable_source"
    return HistoryDetail(
        **item.model_dump(),
        outcome=outcome,
        answer_mode=(answer.answer_mode if answer else "passages"),  # type: ignore[arg-type]
        steps=[StepOut(**s) for s in answer.steps] if answer and answer.steps else None,
        paragraphs=[ParagraphOut(**p) for p in (answer.paragraphs if answer else [])],
        citations=citations,
        message=NO_SOURCE_MESSAGE if outcome == "no_reliable_source" else None,
        disclaimer=answer.disclaimer if answer else DISCLAIMER,
        lawyer_reminder=LAWYER_REMINDER if user.role == "petitioner" else None,
    )
