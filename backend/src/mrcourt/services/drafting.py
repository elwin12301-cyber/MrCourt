"""Creating and saving drafts. Generation fills templates from case data only."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from mrcourt.db.base import utcnow
from mrcourt.models import Case, Draft, User
from mrcourt.services.access import get_owned_case
from mrcourt.services.draft_templates import TEMPLATES, DraftContext


def context_for(case: Case | None) -> DraftContext:
    if case is None:
        return DraftContext()
    client = next((p.name for p in case.parties if p.is_client), None)
    petitioner = next((p.name for p in case.parties if p.side == "petitioner"), None)
    respondent = next((p.name for p in case.parties if p.side == "respondent"), None)
    return DraftContext(
        case_title=case.title,
        cnr_number=case.cnr_number,
        court=case.court,
        client=client or petitioner,
        respondent=respondent,
    )


def create_draft(db: Session, author: User, template: str, case_id: uuid.UUID | None) -> Draft:
    spec = TEMPLATES.get(template)
    if spec is None:
        raise HTTPException(422, "Unknown template")
    case = get_owned_case(db, author, case_id) if case_id else None
    rendered = spec.render(context_for(case))
    draft = Draft(
        case_id=case.id if case else None,
        author_id=author.id,
        template=template,
        title=rendered.title,
        body=rendered.body,
    )
    db.add(draft)
    db.flush()
    return draft


def get_own_draft(db: Session, author: User, draft_id: uuid.UUID) -> Draft:
    draft = db.get(Draft, draft_id)
    if draft is None or draft.author_id != author.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return draft


def list_drafts(db: Session, author: User, case_id: uuid.UUID | None) -> list[Draft]:
    query = select(Draft).where(Draft.author_id == author.id)
    if case_id is not None:
        query = query.where(Draft.case_id == case_id)
    return list(db.scalars(query.order_by(Draft.last_edited_at.desc())))


def save_edits(db: Session, draft: Draft, body: str) -> Draft:
    """Saving counts as the author's review. The AI-generated flag is kept: the text began as such."""
    draft.body = body
    draft.version += 1
    draft.reviewed = True
    draft.last_edited_at = utcnow()
    db.flush()
    return draft
