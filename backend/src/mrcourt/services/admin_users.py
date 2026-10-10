"""Looking after advocates' and clients' accounts. Administrators are never managed here.

Every change takes effect at once, and the caller records it in the audit log in the same
transaction (see api/admin.py).
"""

import re
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from mrcourt.models import AuditEntry, Case, CaseInvitation, User
from mrcourt.schemas.admin import (
    AuditItem,
    Overview,
    Suspension,
    UserCase,
    UserDetail,
    UserPatch,
    UserRow,
)
from mrcourt.services.audit import ACTION_LABELS
from mrcourt.services.cases import aware


def get_person(db: Session, user_id: uuid.UUID) -> User:
    """An advocate or a client. Unknown ids are 404; administrators are refused (403)."""
    person = db.get(User, user_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    if person.role == "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator accounts are not managed here")
    return person


def _case_counts(db: Session) -> tuple[dict[uuid.UUID, int], dict[uuid.UUID, int]]:
    owned = dict(db.execute(select(Case.owner_id, func.count()).group_by(Case.owner_id)).all())
    linked = dict(
        db.execute(
            select(CaseInvitation.invitee_user_id, func.count(func.distinct(CaseInvitation.case_id)))
            .where(CaseInvitation.status == "accepted", CaseInvitation.invitee_user_id.is_not(None))
            .group_by(CaseInvitation.invitee_user_id)
        ).all()
    )
    return owned, linked  # type: ignore[return-value]


def row(user: User, owned: dict[uuid.UUID, int], linked: dict[uuid.UUID, int]) -> UserRow:
    count = owned.get(user.id, 0) if user.role == "advocate" else linked.get(user.id, 0)
    return UserRow(
        id=user.id,
        role=user.role,  # type: ignore[arg-type]
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        status=user.status,  # type: ignore[arg-type]
        verification_status=user.verification_status,  # type: ignore[arg-type]
        bar_registration_number=user.bar_registration_number,
        created_at=aware(user.created_at),
        case_count=count,
    )


def one_row(db: Session, user: User) -> UserRow:
    owned, linked = _case_counts(db)
    return row(user, owned, linked)


def list_people(
    db: Session, role: str | None, q: str | None, status_filter: str | None
) -> list[UserRow]:
    query = select(User).where(User.role.in_([role] if role else ["advocate", "petitioner"]))
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        query = query.where(
            or_(User.full_name.ilike(like), User.email.ilike(like), User.phone.ilike(like))
        )
    if status_filter == "pending":
        query = query.where(User.verification_status == "pending", User.status == "active")
    elif status_filter:
        query = query.where(User.status == status_filter)
    owned, linked = _case_counts(db)
    return [row(u, owned, linked) for u in db.scalars(query.order_by(User.full_name))]


def detail(db: Session, person: User) -> UserDetail:
    owned, linked = _case_counts(db)
    if person.role == "advocate":
        cases = db.scalars(select(Case).where(Case.owner_id == person.id).order_by(Case.title)).all()
        relation = "advocate"
    else:
        cases = db.scalars(
            select(Case)
            .join(CaseInvitation, CaseInvitation.case_id == Case.id)
            .where(CaseInvitation.invitee_user_id == person.id, CaseInvitation.status == "accepted")
            .order_by(Case.title)
        ).all()
        relation = "client"
    names = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_({c.owner_id for c in cases})))}
    suspension = None
    if person.status == "suspended":
        entry = db.scalars(
            select(AuditEntry)
            .where(AuditEntry.action == "user.suspend", AuditEntry.target_id == person.id)
            .order_by(AuditEntry.created_at.desc())
        ).first()
        if entry is not None:
            by = db.get(User, entry.admin_id)
            suspension = Suspension(
                reason=str((entry.detail or {}).get("reason", "")),
                at=aware(entry.created_at),
                by=by.full_name if by else "an administrator",
            )
    return UserDetail(
        **row(person, owned, linked).model_dump(),
        cases=[
            UserCase(
                id=c.id, title=c.title, status=c.status,
                relation=relation,  # type: ignore[arg-type]
                advocate_name=names.get(c.owner_id, ""),
            )
            for c in cases
        ],
        suspension=suspension,
    )


# ---- changes ---------------------------------------------------------------------------------


def _clean_phone(value: str) -> str | None:
    return re.sub(r"[\s-]", "", value) or None


def edit(db: Session, person: User, data: UserPatch) -> dict[str, object]:
    """Applies the corrections and returns safe audit detail (field names; before/after only for
    name and Bar Council number, never for email or phone)."""
    if person.status == "deactivated":
        raise HTTPException(status.HTTP_409_CONFLICT, "This person deactivated their account and their details were removed")
    sent = data.model_dump(exclude_unset=True)
    if not sent:
        raise HTTPException(422, "Nothing to change")

    email = person.email
    phone = person.phone
    changed: list[str] = []
    detail: dict[str, object] = {}

    if "full_name" in sent and data.full_name is not None and data.full_name.strip() != person.full_name:
        detail["full_name"] = {"from": person.full_name, "to": data.full_name.strip()}
        person.full_name = data.full_name.strip()
        changed.append("full_name")

    if "email" in sent:
        new_email = (data.email or "").strip().lower() or None
        if new_email != email:
            email = new_email
            changed.append("email")
    if "phone" in sent:
        new_phone = _clean_phone(data.phone or "")
        if new_phone != phone:
            phone = new_phone
            changed.append("phone")
    if not email and not phone:
        raise HTTPException(422, "A person needs an email or a phone number to sign in")
    for field, value in (("email", email), ("phone", phone)):
        if field in changed and value:
            clash = db.scalars(select(User).where(getattr(User, field) == value, User.id != person.id)).first()
            if clash is not None:
                raise HTTPException(status.HTTP_409_CONFLICT, f"That {field} is already used by another account")
    person.email, person.phone = email, phone

    if "bar_registration_number" in sent:
        if person.role != "advocate":
            raise HTTPException(422, "Only advocates have a Bar Council number")
        new_bar = (data.bar_registration_number or "").strip() or None
        if new_bar != person.bar_registration_number:
            detail["bar_registration_number"] = {"from": person.bar_registration_number, "to": new_bar}
            person.bar_registration_number = new_bar
            # A changed number has to be confirmed again.
            person.verification_status = "pending" if new_bar else "none"
            person.verified_by = None
            person.verified_at = None
            changed.append("bar_registration_number")

    if not changed:
        raise HTTPException(422, "Nothing to change")
    db.flush()
    return {"fields": changed, **detail}


def suspend(db: Session, person: User, reason: str) -> None:
    if not reason.strip():
        raise HTTPException(422, "Please give a reason")
    if person.status == "suspended":
        raise HTTPException(status.HTTP_409_CONFLICT, "This account is already suspended")
    if person.status != "active":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only active accounts can be suspended")
    person.status = "suspended"
    person.session_epoch += 1  # signs them out everywhere at once
    db.flush()


def reactivate(db: Session, person: User) -> None:
    if person.status != "suspended":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only suspended accounts can be reactivated")
    person.status = "active"
    db.flush()


def sign_out(db: Session, person: User) -> None:
    person.session_epoch += 1
    db.flush()


# ---- overview --------------------------------------------------------------------------------


def audit_items(db: Session, entries: list[AuditEntry]) -> list[AuditItem]:
    admins = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_({e.admin_id for e in entries})))}
    user_ids = {e.target_id for e in entries if e.target_type == "user" and e.target_id}
    case_ids = {e.target_id for e in entries if e.target_type == "case" and e.target_id}
    people = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_(user_ids)))} if user_ids else {}
    cases = {c.id: c.title for c in db.scalars(select(Case).where(Case.id.in_(case_ids)))} if case_ids else {}
    items = []
    for e in entries:
        if e.target_type == "user":
            name = people.get(e.target_id) if e.target_id else None
        elif e.target_type == "case":
            name = cases.get(e.target_id) if e.target_id else None
        else:
            name = str((e.detail or {}).get("file_name")) if (e.detail or {}).get("file_name") else None
        items.append(
            AuditItem(
                id=e.id,
                admin_name=admins.get(e.admin_id, "an administrator"),
                action=e.action,
                action_label=ACTION_LABELS.get(e.action, e.action),
                target_type=e.target_type,
                target_id=e.target_id,
                target_name=name,
                detail=dict(e.detail or {}),
                created_at=aware(e.created_at),
            )
        )
    return items


def overview(db: Session) -> Overview:
    def count(*conditions: object) -> int:
        return db.scalar(select(func.count()).select_from(User).where(*conditions)) or 0  # type: ignore[arg-type]

    latest = list(db.scalars(select(AuditEntry).order_by(AuditEntry.created_at.desc(), AuditEntry.id.desc()).limit(5)))
    return Overview(
        advocates=count(User.role == "advocate", User.status != "deactivated"),
        clients=count(User.role == "petitioner", User.status != "deactivated"),
        open_cases=db.scalar(select(func.count()).select_from(Case).where(Case.status != "closed")) or 0,
        pending_verifications=count(User.role == "advocate", User.verification_status == "pending", User.status == "active"),
        suspended_accounts=count(User.status == "suspended"),
        recent_audit=audit_items(db, latest),
    )


def utc_now() -> datetime:
    return datetime.now(UTC)
