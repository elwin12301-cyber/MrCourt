"""Advocate-side controls over what clients see. Every endpoint is advocate-only and scoped to
cases the advocate owns (anything else is 403 or 404)."""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from mrcourt.api.deps import Advocate, DbSession
from mrcourt.models import CaseInvitation, Document, Hearing, TimelineEntry, User
from mrcourt.schemas.client import (
    CaseInvitationOut,
    ClientContact,
    ClientQuestionAdvocate,
    ClientStatusIn,
    ClientStatusState,
    ClientUpdateIn,
    OutcomeIn,
    ReplyIn,
    ShareIn,
    TimelineEntryAdvocate,
    TimelineNoteIn,
)
from mrcourt.services import client_questions, client_status
from mrcourt.services.access import get_owned_case
from mrcourt.services.cases import aware

router = APIRouter(tags=["client-view"])


def _entry(entry: TimelineEntry) -> TimelineEntryAdvocate:
    return TimelineEntryAdvocate(
        id=entry.id,
        kind=entry.kind,
        text=entry.text,
        occurred_at=aware(entry.occurred_at),
        shared_with_client=entry.shared_with_client,
    )


@router.put("/cases/{case_id}/client-status", response_model=ClientStatusState)
def set_status(case_id: uuid.UUID, data: ClientStatusIn, user: Advocate, db: DbSession) -> ClientStatusState:
    case = get_owned_case(db, user, case_id)
    state = client_status.set_client_status(db, case, user.id, data.status)
    db.commit()
    return state


@router.post("/cases/{case_id}/client-updates", status_code=status.HTTP_201_CREATED, response_model=TimelineEntryAdvocate)
def post_update(case_id: uuid.UUID, data: ClientUpdateIn, user: Advocate, db: DbSession) -> TimelineEntryAdvocate:
    case = get_owned_case(db, user, case_id)
    entry = client_status.post_update(db, case, user.id, data.message)
    db.commit()
    return _entry(entry)


@router.get("/cases/{case_id}/timeline", response_model=list[TimelineEntryAdvocate])
def timeline(case_id: uuid.UUID, user: Advocate, db: DbSession) -> list[TimelineEntryAdvocate]:
    case = get_owned_case(db, user, case_id)
    rows = db.scalars(
        select(TimelineEntry).where(TimelineEntry.case_id == case.id).order_by(TimelineEntry.occurred_at.desc())
    )
    return [_entry(e) for e in rows]


@router.post("/cases/{case_id}/timeline", status_code=status.HTTP_201_CREATED, response_model=TimelineEntryAdvocate)
def add_note(case_id: uuid.UUID, data: TimelineNoteIn, user: Advocate, db: DbSession) -> TimelineEntryAdvocate:
    case = get_owned_case(db, user, case_id)
    entry = client_status.add_note(db, case, user.id, data.text, data.shared_with_client)
    db.commit()
    return _entry(entry)


@router.put("/cases/{case_id}/timeline/{entry_id}/sharing", response_model=TimelineEntryAdvocate)
def share_entry(case_id: uuid.UUID, entry_id: uuid.UUID, data: ShareIn, user: Advocate, db: DbSession) -> TimelineEntryAdvocate:
    case = get_owned_case(db, user, case_id)
    entry = client_status.set_entry_sharing(db, case, user.id, entry_id, data.shared)
    db.commit()
    return _entry(entry)


@router.put("/cases/{case_id}/documents/{document_id}/sharing")
def share_document(case_id: uuid.UUID, document_id: uuid.UUID, data: ShareIn, user: Advocate, db: DbSession) -> dict[str, bool]:
    case = get_owned_case(db, user, case_id)
    document = db.get(Document, document_id)
    if document is None or document.case_id != case.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    client_status.set_document_sharing(db, case, user.id, document, data.shared)
    db.commit()
    return {"shared": document.shared_with_client}


@router.put("/cases/{case_id}/hearings/{hearing_id}/outcome")
def set_outcome(case_id: uuid.UUID, hearing_id: uuid.UUID, data: OutcomeIn, user: Advocate, db: DbSession) -> dict[str, object]:
    case = get_owned_case(db, user, case_id)
    hearing = db.get(Hearing, hearing_id)
    if hearing is None or hearing.case_id != case.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    client_status.set_outcome(db, case, user.id, hearing, data.outcome, data.shared)
    db.commit()
    return {"outcome": hearing.outcome, "shared": hearing.outcome_shared}


@router.get("/cases/{case_id}/invitations", response_model=list[CaseInvitationOut])
def clients_on_case(case_id: uuid.UUID, user: Advocate, db: DbSession) -> list[CaseInvitationOut]:
    case = get_owned_case(db, user, case_id)
    rows = db.scalars(
        select(CaseInvitation)
        .where(CaseInvitation.case_id == case.id, CaseInvitation.status != "removed")
        .order_by(CaseInvitation.created_at)
    )
    out: list[CaseInvitationOut] = []
    for invitation in rows:
        invitee = db.get(User, invitation.invitee_user_id) if invitation.invitee_user_id else None
        out.append(
            CaseInvitationOut(
                id=invitation.id,
                contact_or_name=invitee.full_name if invitee else (invitation.invitee_contact or ""),
                status=invitation.status,  # type: ignore[arg-type]
                accepted_at=aware(invitation.accepted_at) if invitation.accepted_at else None,
            )
        )
    return out


@router.get("/me/client-contact", response_model=ClientContact)
def get_contact(user: Advocate) -> ClientContact:
    card = (user.settings.client_contact if user.settings else None) or {}
    return ClientContact(**{k: card.get(k) for k in ("phone", "email", "office")})


@router.put("/me/client-contact", response_model=ClientContact)
def set_contact(data: ClientContact, user: Advocate, db: DbSession) -> ClientContact:
    """Only filled-in fields are ever shown to clients."""
    card = {k: v.strip() for k, v in data.model_dump().items() if v and v.strip()}
    user.settings.client_contact = card
    db.commit()
    return ClientContact(**{k: card.get(k) for k in ("phone", "email", "office")})


@router.get("/cases/{case_id}/client-questions", response_model=list[ClientQuestionAdvocate])
def client_questions_for_case(case_id: uuid.UUID, user: Advocate, db: DbSession) -> list[ClientQuestionAdvocate]:
    return client_questions.list_for_advocate(db, get_owned_case(db, user, case_id))


@router.post("/client-questions/{question_id}/reply", response_model=ClientQuestionAdvocate)
def reply_to_client(question_id: uuid.UUID, data: ReplyIn, user: Advocate, db: DbSession) -> ClientQuestionAdvocate:
    question = client_questions.get_question(db, question_id)
    get_owned_case(db, user, question.case_id)  # 404 unless this advocate owns the case
    answered = client_questions.reply(db, user, question, data.text)
    db.commit()
    return answered
