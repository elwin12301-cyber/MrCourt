"""Every case, in full, for administrators. Read-only: nothing here changes a case."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from mrcourt.db.base import utcnow
from mrcourt.models import (
    Case,
    CaseInvitation,
    ClientQuestion,
    Document,
    Party,
    TimelineEntry,
    User,
)
from mrcourt.schemas.admin import (
    AdminAdvocate,
    AdminClient,
    AdminDocument,
    AdminHearing,
    AdminParty,
    AdminQuestion,
    AdminTimelineEntry,
    CaseFull,
    CaseRow,
)
from mrcourt.services.cases import aware, next_hearing


def get_case(db: Session, case_id: uuid.UUID) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return case


def list_cases(db: Session, q: str | None) -> list[CaseRow]:
    query = select(Case).join(User, User.id == Case.owner_id).options(selectinload(Case.hearings))
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        party_match = select(Party.case_id).where(Party.name.ilike(like))
        query = query.where(
            or_(
                Case.title.ilike(like),
                Case.cnr_number.ilike(like),
                Case.court.ilike(like),
                User.full_name.ilike(like),
                Case.id.in_(party_match),
            )
        )
    cases = list(db.scalars(query.order_by(Case.title)))
    owners = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_({c.owner_id for c in cases})))} if cases else {}
    clients = dict(
        db.execute(
            select(CaseInvitation.case_id, func.count())
            .where(CaseInvitation.status == "accepted")
            .group_by(CaseInvitation.case_id)
        ).all()
    )
    now = utcnow()
    rows = []
    for c in cases:
        hearing = next_hearing(c, now)
        rows.append(
            CaseRow(
                id=c.id,
                title=c.title,
                court=c.court,
                status=c.status,
                advocate_name=owners.get(c.owner_id, ""),
                client_count=clients.get(c.id, 0),
                next_hearing_at=aware(hearing.scheduled_at) if hearing else None,
            )
        )
    return rows


def full_view(db: Session, case: Case) -> CaseFull:
    owner = db.get(User, case.owner_id)
    timeline = db.scalars(
        select(TimelineEntry).where(TimelineEntry.case_id == case.id).order_by(TimelineEntry.occurred_at.desc())
    )
    invitations = db.scalars(
        select(CaseInvitation).where(CaseInvitation.case_id == case.id, CaseInvitation.status != "removed")
    ).all()
    names = {
        u.id: u.full_name
        for u in db.scalars(select(User).where(User.id.in_({i.invitee_user_id for i in invitations if i.invitee_user_id})))
    }
    questions = db.execute(
        select(ClientQuestion, User.full_name)
        .join(User, User.id == ClientQuestion.client_id)
        .where(ClientQuestion.case_id == case.id)
        .order_by(ClientQuestion.created_at.desc())
    ).all()
    return CaseFull(
        id=case.id,
        title=case.title,
        cnr_number=case.cnr_number,
        court=case.court,
        status=case.status,
        stage=case.stage,
        court_room=case.room,
        notes=case.notes,
        client_status=case.client_status,
        client_status_changed_at=aware(case.client_status_changed_at) if case.client_status_changed_at else None,
        advocate=AdminAdvocate(id=case.owner_id, name=owner.full_name if owner else ""),
        parties=[AdminParty(side=p.side, name=p.name, is_client=p.is_client) for p in case.parties],
        hearings=[
            AdminHearing(
                id=h.id, scheduled_at=aware(h.scheduled_at), purpose=h.purpose, court_room=h.court_room,
                outcome=h.outcome, outcome_shared=h.outcome_shared,
            )
            for h in case.hearings
        ],
        documents=[
            AdminDocument(id=d.id, file_name=d.file_name, size_bytes=d.size_bytes, shared_with_client=d.shared_with_client)
            for d in case.documents
        ],
        timeline=[
            AdminTimelineEntry(
                id=e.id, kind=e.kind, text=e.text, shared_with_client=e.shared_with_client,
                occurred_at=aware(e.occurred_at),
            )
            for e in timeline
        ],
        clients=[
            AdminClient(
                id=i.invitee_user_id or i.id,
                name=names.get(i.invitee_user_id, i.invitee_contact or "") if i.invitee_user_id else (i.invitee_contact or ""),
                status=i.status,
                accepted_at=aware(i.accepted_at) if i.accepted_at else None,
            )
            for i in invitations
        ],
        client_questions=[
            AdminQuestion(
                id=q.id, client_name=name, kind=q.kind, text=q.text, sent_at=aware(q.created_at),
                reply_text=q.reply_text, replied_at=aware(q.replied_at) if q.replied_at else None,
            )
            for q, name in questions
        ],
    )


def get_document(db: Session, case: Case, document_id: uuid.UUID) -> Document:
    document = db.get(Document, document_id)
    if document is None or document.case_id != case.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return document
