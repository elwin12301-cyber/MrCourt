"""The administrator's endpoints. Every route here requires the admin role.

What an administrator can do is deliberately narrow: look after accounts, confirm Bar Council
numbers, and read everything (read-only). There is no route to edit, delete, reassign or close a
case, to delete data, or to reset a password. Anything that changes an account or opens private
content writes an audit entry in the same transaction.
"""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import and_, or_, select

from mrcourt.api.deps import Admin, DbSession
from mrcourt.db.base import utcnow
from mrcourt.models import AuditEntry, LegalSource, Question, User
from mrcourt.schemas.admin import (
    AuditPage,
    CaseFull,
    CaseRow,
    Overview,
    RankingExplanation,
    SuspendIn,
    UserDetail,
    UserPatch,
    UserRow,
)
from mrcourt.schemas.auth import PendingVerification, VerificationDecision
from mrcourt.schemas.history import HistoryPage, WorkspacePage
from mrcourt.services import admin_cases, admin_users, audit, history
from mrcourt.services import documents as document_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview", response_model=Overview)
def overview(_: Admin, db: DbSession) -> Overview:
    return admin_users.overview(db)


# ---- people ----------------------------------------------------------------------------------


@router.get("/users", response_model=list[UserRow])
def list_people(
    _: Admin,
    db: DbSession,
    role: Literal["advocate", "petitioner"] | None = None,
    q: str | None = None,
    status_filter: Literal["active", "suspended", "deactivated", "pending"] | None = Query(default=None, alias="status"),
) -> list[UserRow]:
    return admin_users.list_people(db, role, q, status_filter)


@router.get("/users/{user_id}", response_model=UserDetail)
def person(user_id: uuid.UUID, admin: Admin, db: DbSession) -> UserDetail:
    target = admin_users.get_person(db, user_id)
    audit.record(db, admin, "user.view", "user", target.id)
    result = admin_users.detail(db, target)
    db.commit()
    return result


@router.patch("/users/{user_id}", response_model=UserRow)
def edit_person(user_id: uuid.UUID, data: UserPatch, admin: Admin, db: DbSession) -> UserRow:
    target = admin_users.get_person(db, user_id)
    detail = admin_users.edit(db, target, data)
    audit.record(db, admin, "user.update", "user", target.id, **detail)
    db.commit()
    return admin_users.one_row(db, target)


@router.post("/users/{user_id}/suspend", response_model=UserRow)
def suspend_person(user_id: uuid.UUID, data: SuspendIn, admin: Admin, db: DbSession) -> UserRow:
    target = admin_users.get_person(db, user_id)
    admin_users.suspend(db, target, data.reason)
    audit.record(db, admin, "user.suspend", "user", target.id, reason=data.reason.strip())
    db.commit()
    return admin_users.one_row(db, target)


@router.post("/users/{user_id}/reactivate", response_model=UserRow)
def reactivate_person(user_id: uuid.UUID, admin: Admin, db: DbSession) -> UserRow:
    target = admin_users.get_person(db, user_id)
    admin_users.reactivate(db, target)
    audit.record(db, admin, "user.reactivate", "user", target.id)
    db.commit()
    return admin_users.one_row(db, target)


@router.post("/users/{user_id}/sign-out", status_code=status.HTTP_204_NO_CONTENT)
def sign_person_out(user_id: uuid.UUID, admin: Admin, db: DbSession) -> Response:
    target = admin_users.get_person(db, user_id)
    admin_users.sign_out(db, target)
    audit.record(db, admin, "user.sign_out", "user", target.id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- Bar Council verification ----------------------------------------------------------------


@router.get("/questions", response_model=WorkspacePage)
def workspace_questions(
    admin: Admin,
    db: DbSession,
    q: str | None = None,
    outcome: Literal["answered", "none"] | None = None,
    input: Literal["typed", "voice"] | None = None,  # noqa: A002 - the public name is `input`
    source: Literal["all", "ask", "text"] | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    before: str | None = None,
) -> WorkspacePage:
    """Everyone's questions as a list (who asked, no answers). Each listing is recorded, without the text."""
    page = history.list_workspace(db, q=q, outcome=outcome, input_method=input, source=source, limit=limit, before=before)
    audit.record(db, admin, "history.view", "workspace", None, shown=len(page.items))
    db.commit()
    return page


@router.get("/questions/{question_id}/ranking", response_model=RankingExplanation)
def question_ranking(question_id: uuid.UUID, admin: Admin, db: DbSession) -> RankingExplanation:
    """Why each source of an answer ranked where it did (feature 009). Administrators see advocates' private
    passages too (the view is audited); a passage that no longer exists is a hidden row."""
    question = db.get(Question, question_id)
    if question is None or question.answer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")
    stored = question.answer.ranking
    audit.record(db, admin, "answer.ranking.view", "question", question.id)
    db.commit()
    if not stored:
        return RankingExplanation(question_id=question.id, recorded=False)
    passages = []
    for item in stored.get("passages", []):  # type: ignore[union-attr]
        source = db.get(LegalSource, uuid.UUID(str(item["source_id"])))
        # Administrators may see advocates' private documents (this view is audited above); only a passage
        # that no longer exists is hidden.
        hidden = source is None
        passages.append(
            {
                "position": item["position"],
                "hidden": hidden,
                "label": None if hidden else source.citation_label,  # type: ignore[union-attr]
                "pinned": item["pinned"],
                "scores": item["scores"],
                # A hidden row keeps only signals that name nothing (no reference text).
                "signals": [s for s in item["signals"] if not (hidden and s["name"] == "exact_reference")],
            }
        )
    return RankingExplanation(
        question_id=question.id,
        recorded=True,
        mode=stored.get("mode"),  # type: ignore[union-attr]
        question_type=stored.get("question_type"),  # type: ignore[union-attr]
        references=list(stored.get("references", [])),  # type: ignore[union-attr]
        passages=passages,  # type: ignore[arg-type]
    )


@router.get("/users/{user_id}/questions", response_model=HistoryPage)
def person_questions(
    user_id: uuid.UUID,
    admin: Admin,
    db: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
    before: str | None = None,
) -> HistoryPage:
    """A person's questions as a list (no answers). Opening it is recorded, without the text."""
    target = admin_users.get_person(db, user_id)
    page = history.list_questions(db, target.id, limit=limit, before=before)
    audit.record(db, admin, "history.view", "user", target.id, shown=len(page.items))
    db.commit()
    return page


@router.get("/verifications", response_model=list[PendingVerification])
def pending(_: Admin, db: DbSession) -> list[PendingVerification]:
    users = db.scalars(
        select(User)
        .where(User.role == "advocate", User.verification_status == "pending", User.status == "active")
        .order_by(User.created_at)
    )
    return [
        PendingVerification(
            id=u.id,
            full_name=u.full_name,
            email=u.email,
            phone=u.phone,
            bar_registration_number=u.bar_registration_number,
        )
        for u in users
    ]


@router.post("/verifications/{user_id}")
def decide(user_id: uuid.UUID, data: VerificationDecision, admin: Admin, db: DbSession) -> dict[str, str]:
    user = db.get(User, user_id)
    if user is None or user.role != "advocate" or user.verification_status != "pending":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    number = user.bar_registration_number
    if data.decision == "verified":
        user.verification_status = "verified"
        user.verified_by = admin.id
        user.verified_at = utcnow()
    else:  # rejected: back to unverified, and the number can be entered again
        user.verification_status = "none"
        user.bar_registration_number = None
    audit.record(
        db, admin, "verification.confirm" if data.decision == "verified" else "verification.reject",
        "user", user.id, bar_registration_number=number,
    )
    db.commit()
    return {"status": user.verification_status}


# ---- cases (read-only) -----------------------------------------------------------------------


@router.get("/cases", response_model=list[CaseRow])
def list_cases(_: Admin, db: DbSession, q: str | None = None) -> list[CaseRow]:
    """Overview fields only, so listing is not logged. Opening a case in full is."""
    return admin_cases.list_cases(db, q)


@router.get("/cases/{case_id}", response_model=CaseFull)
def case_in_full(case_id: uuid.UUID, admin: Admin, db: DbSession) -> CaseFull:
    case = admin_cases.get_case(db, case_id)
    audit.record(db, admin, "case.view", "case", case.id)
    result = admin_cases.full_view(db, case)
    db.commit()
    return result


@router.get("/cases/{case_id}/documents/{document_id}/download")
def download_document(case_id: uuid.UUID, document_id: uuid.UUID, admin: Admin, db: DbSession) -> FileResponse:
    case = admin_cases.get_case(db, case_id)
    document = admin_cases.get_document(db, case, document_id)
    path = document_service.path_for(document.storage_key)
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File is not available")
    audit.record(db, admin, "document.download", "document", document.id, file_name=document.file_name, case_id=str(case.id))
    db.commit()
    return FileResponse(path, media_type=document.content_type, filename=document.file_name)


# ---- audit log (read-only) -------------------------------------------------------------------


def _parse_cursor(value: str) -> tuple[datetime, uuid.UUID]:
    try:
        stamp, _, entry_id = value.partition("|")
        return datetime.fromisoformat(stamp), uuid.UUID(entry_id)
    except ValueError:
        raise HTTPException(422, "Invalid cursor") from None


@router.get("/audit", response_model=AuditPage)
def audit_log(_: Admin, db: DbSession, limit: int = Query(default=50, ge=1, le=200), before: str | None = None) -> AuditPage:
    query = select(AuditEntry)
    if before:
        stamp, entry_id = _parse_cursor(before)
        query = query.where(
            or_(AuditEntry.created_at < stamp, and_(AuditEntry.created_at == stamp, AuditEntry.id < entry_id))
        )
    entries = list(db.scalars(query.order_by(AuditEntry.created_at.desc(), AuditEntry.id.desc()).limit(limit)))
    items = admin_users.audit_items(db, entries)
    last = entries[-1] if len(entries) == limit else None
    return AuditPage(
        items=items,
        next_before=f"{items[-1].created_at.isoformat()}|{last.id}" if last else None,
    )
