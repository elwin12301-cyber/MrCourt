"""Role and ownership policy. Every case query goes through this module.

Rules (spec FR-003, FR-019):
- An advocate sees and edits only the cases they own.
- A petitioner sees (read-only) only cases with an accepted invitation addressed to them.
- Anything not visible is reported as 404, never 403, so existence is not leaked.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from mrcourt.models import Case, CaseInvitation, User


def visible_cases(user: User) -> Select[tuple[Case]]:
    if user.role == "advocate":
        return select(Case).where(Case.owner_id == user.id)
    accepted = select(CaseInvitation.case_id).where(
        CaseInvitation.invitee_user_id == user.id, CaseInvitation.status == "accepted"
    )
    return select(Case).where(Case.id.in_(accepted))


def get_visible_case(db: Session, user: User, case_id: uuid.UUID) -> Case:
    case = db.scalars(visible_cases(user).where(Case.id == case_id)).first()
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return case


def get_owned_case(db: Session, user: User, case_id: uuid.UUID) -> Case:
    """Case the user may modify: advocates only, and only their own."""
    if user.role != "advocate":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only advocates can change cases")
    case = db.scalars(select(Case).where(Case.id == case_id, Case.owner_id == user.id)).first()
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return case


def get_client_case(db: Session, user: User, case_id: uuid.UUID) -> Case:
    """The case, for a client with an accepted invitation. Anything else is a 404."""
    if user.role != "petitioner":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return get_visible_case(db, user, case_id)
