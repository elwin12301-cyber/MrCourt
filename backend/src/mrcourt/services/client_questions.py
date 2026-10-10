"""Private messages from a client to their advocate, and the advocate's single reply.

Every read here is filtered by client id in one place, so one client can never see another
client's question, reply or read state.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from mrcourt.db.base import utcnow
from mrcourt.models import Case, ClientQuestion, ClientUpdate, User
from mrcourt.schemas.client import ClientQuestionAdvocate, ClientQuestionOut
from mrcourt.services import ratelimit
from mrcourt.services.cases import aware

UPDATE_REQUEST_TEXT = "Please send me an update on my case."
LAWYER_GONE = "Your lawyer is no longer available on MrCourt. Please contact them directly."


def _out(q: ClientQuestion) -> ClientQuestionOut:
    return ClientQuestionOut(
        id=q.id,
        kind=q.kind,  # type: ignore[arg-type]
        text=q.text,
        sent_at=aware(q.created_at),
        reply_text=q.reply_text,
        replied_at=aware(q.replied_at) if q.replied_at else None,
        reply_read=q.reply_read_at is not None,
    )


def list_own(db: Session, client: User, case: Case) -> list[ClientQuestionOut]:
    rows = db.scalars(
        select(ClientQuestion)
        .where(ClientQuestion.case_id == case.id, ClientQuestion.client_id == client.id)
        .order_by(ClientQuestion.created_at.desc())
    )
    return [_out(q) for q in rows]


def ask(db: Session, client: User, case: Case, kind: str, text: str | None) -> ClientQuestionOut:
    owner = db.get(User, case.owner_id)
    if owner is None or owner.status != "active":
        raise HTTPException(status.HTTP_409_CONFLICT, LAWYER_GONE)
    ratelimit.hit(f"ask-lawyer:{client.id}", limit=20, window_seconds=3600)

    body = (text or "").strip()
    if kind == "question" and not body:
        raise HTTPException(422, "Please write your question")
    question = ClientQuestion(
        case_id=case.id,
        client_id=client.id,
        kind=kind,
        text=body or UPDATE_REQUEST_TEXT,
    )
    db.add(question)
    db.flush()
    return _out(question)


def mark_reply_read(db: Session, client: User, question_id: uuid.UUID) -> None:
    question = db.get(ClientQuestion, question_id)
    if question is None or question.client_id != client.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    if question.reply_text and question.reply_read_at is None:
        question.reply_read_at = utcnow()
        db.flush()


# ---- the advocate's side ---------------------------------------------------------------------


def list_for_advocate(db: Session, case: Case) -> list[ClientQuestionAdvocate]:
    rows = db.execute(
        select(ClientQuestion, User.full_name)
        .join(User, User.id == ClientQuestion.client_id)
        .where(ClientQuestion.case_id == case.id)
        .order_by(ClientQuestion.reply_text.is_(None).desc(), ClientQuestion.created_at.desc())
    )
    return [ClientQuestionAdvocate(**_out(q).model_dump(), client_name=name) for q, name in rows]


def get_question(db: Session, question_id: uuid.UUID) -> ClientQuestion:
    question = db.get(ClientQuestion, question_id)
    if question is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return question


def reply(db: Session, advocate: User, question: ClientQuestion, text: str) -> ClientQuestionAdvocate:
    body = text.strip()
    if not body:
        raise HTTPException(422, "Please write a reply")
    if question.reply_text:
        raise HTTPException(status.HTTP_409_CONFLICT, "This question has already been answered")
    question.reply_text = body
    question.replied_at = utcnow()
    question.replied_by = advocate.id
    case = db.get(Case, question.case_id)
    if case is not None:
        # Only the client who asked is told. The notice does not repeat the reply itself.
        db.add(
            ClientUpdate(
                client_id=question.client_id,
                case_id=case.id,
                kind="question_reply",
                message=f"{case.title}: Your lawyer replied to your question."[:500],
            )
        )
    db.flush()
    name = db.get(User, question.client_id).full_name  # type: ignore[union-attr]
    return ClientQuestionAdvocate(**_out(question).model_dump(), client_name=name)
