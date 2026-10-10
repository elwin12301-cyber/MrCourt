"""Confirming or declining what the assistant proposed.

A proposal is single use, belongs to one person, and expires. Anything else (someone else's id, an
unknown id, one already used) is reported as not found, so nothing about it is revealed.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from mrcourt.db.base import utcnow
from mrcourt.models import ProposedAction, User
from mrcourt.services.cases import aware
from mrcourt.services.drafting import create_draft


def _own_pending(db: Session, user: User, action_id: uuid.UUID) -> ProposedAction:
    action = db.get(ProposedAction, action_id)
    if action is None or action.user_id != user.id or action.status not in ("pending", "expired"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    if action.status == "pending" and aware(action.expires_at) < utcnow():
        action.status = "expired"
        db.commit()  # keep the change even though the request is refused
    if action.status == "expired":
        raise HTTPException(status.HTTP_410_GONE, "expired")
    return action


def confirm(db: Session, user: User, action_id: uuid.UUID) -> uuid.UUID:
    action = _own_pending(db, user, action_id)
    if action.kind != "create_draft" or user.role != "advocate":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot do this")
    params = action.params or {}
    case_id = uuid.UUID(params["case_id"]) if params.get("case_id") else None
    draft = create_draft(db, user, str(params.get("template", "")), case_id)  # re-checks the template and the case
    action.status = "done"
    action.result_id = draft.id
    db.flush()
    return draft.id


def decline(db: Session, user: User, action_id: uuid.UUID) -> None:
    action = _own_pending(db, user, action_id)
    action.status = "declined"
    db.flush()
