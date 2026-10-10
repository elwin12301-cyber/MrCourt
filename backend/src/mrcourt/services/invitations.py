"""Advocate -> petitioner case invitations."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from mrcourt.db.base import utcnow
from mrcourt.models import ActivityEvent, Case, CaseInvitation, ClientUpdate, User
from mrcourt.services.auth import find_user, normalize_identifier


def invite(db: Session, case: Case, advocate: User, contact: str) -> CaseInvitation:
    invitee = find_user(db, contact)
    if invitee is not None and invitee.role != "petitioner":
        raise HTTPException(422, "Only petitioners can be invited")
    email, phone = normalize_identifier(contact)
    invitation = CaseInvitation(
        case_id=case.id,
        invitee_user_id=invitee.id if invitee else None,
        invitee_contact=None if invitee else (email or phone),
        status="pending",
        invited_by=advocate.id,
    )
    db.add(invitation)
    db.flush()
    return invitation


def link_pending_for(db: Session, user: User) -> None:
    """After registration, attach invitations that were sent to this email or phone."""
    contacts = [c for c in (user.email, user.phone) if c]
    if not contacts or user.role != "petitioner":
        return
    pending = db.scalars(
        select(CaseInvitation).where(
            CaseInvitation.invitee_user_id.is_(None), CaseInvitation.invitee_contact.in_(contacts)
        )
    )
    for invitation in pending:
        invitation.invitee_user_id = user.id
        invitation.invitee_contact = None


def pending_for(db: Session, user: User) -> list[tuple[CaseInvitation, str]]:
    rows = db.execute(
        select(CaseInvitation, Case.title)
        .join(Case, Case.id == CaseInvitation.case_id)
        .where(CaseInvitation.invitee_user_id == user.id, CaseInvitation.status == "pending")
    )
    return [(inv, title) for inv, title in rows]


def accept(db: Session, user: User, invitation_id: uuid.UUID) -> CaseInvitation:
    invitation = db.get(CaseInvitation, invitation_id)
    if (
        invitation is None
        or invitation.invitee_user_id != user.id
        or invitation.status != "pending"
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    invitation.status = "accepted"
    invitation.accepted_at = utcnow()
    case = db.get(Case, invitation.case_id)
    assert case is not None
    db.add(
        ActivityEvent(
            user_id=case.owner_id,
            case_id=case.id,
            kind="invite_accepted",
            message=f"{user.full_name} accepted your case invite",
        )
    )
    return invitation


def remove(db: Session, case: Case, invitation_id: uuid.UUID) -> None:
    invitation = db.get(CaseInvitation, invitation_id)
    if invitation is None or invitation.case_id != case.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    invitation.status = "removed"
    if invitation.invitee_user_id:
        # The case and its updates disappear from this client's view, and only theirs.
        db.execute(
            delete(ClientUpdate).where(
                ClientUpdate.case_id == case.id, ClientUpdate.client_id == invitation.invitee_user_id
            )
        )
