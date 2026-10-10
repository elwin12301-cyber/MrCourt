"""Client-facing status, timeline entries and notices to clients.

Visibility rule (spec Clarification 1): status changes and hearing dates are always shown to
clients; outcomes, shared documents and notes are shown only when the advocate shares them, and
the default is private. A short advocate update is created shared, because writing one is itself an
act of sharing.
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from mrcourt.db.base import utcnow
from mrcourt.models import Case, CaseInvitation, ClientUpdate, Document, Hearing, TimelineEntry
from mrcourt.schemas.client import ClientStatusState
from mrcourt.services.cases import aware

CLIENT_STATUSES = ("notice_stage", "hearing_scheduled", "awaiting_order", "closed")

STATUS_LABELS = {
    "notice_stage": "Notice stage",
    "hearing_scheduled": "Hearing scheduled",
    "awaiting_order": "Awaiting order",
    "closed": "Closed",
}

# Stored as shared and never hidden.
ALWAYS_VISIBLE_KINDS = frozenset(
    {"status_change", "hearing_scheduled", "hearing_rescheduled", "update"}
)
# Kinds whose sharing the advocate controls on the timeline itself.
NOTE_KIND = "note"

IST = timezone(timedelta(hours=5, minutes=30))


def when_text(value: datetime) -> str:
    """"9 Oct 2026, 10:30 AM" in Indian Standard Time, the way the screens write dates."""
    local = aware(value).astimezone(IST)
    hour = local.strftime("%I").lstrip("0") or "12"
    return f"{local.day} {local:%b %Y}, {hour}:{local:%M %p}"


def record_entry(
    db: Session,
    case: Case,
    kind: str,
    text: str,
    *,
    created_by: uuid.UUID | None,
    hearing_id: uuid.UUID | None = None,
    document_id: uuid.UUID | None = None,
    shared: bool | None = None,
    occurred_at: datetime | None = None,
) -> TimelineEntry:
    """Adds a timeline entry. Always-visible kinds ignore `shared`; other kinds default to private."""
    visible = True if kind in ALWAYS_VISIBLE_KINDS else bool(shared)
    entry = TimelineEntry(
        case_id=case.id,
        kind=kind,
        text=text,
        shared_with_client=visible,
        hearing_id=hearing_id,
        document_id=document_id,
        occurred_at=occurred_at or utcnow(),
        created_by=created_by,
    )
    db.add(entry)
    db.flush()
    return entry


def accepted_client_ids(db: Session, case: Case) -> list[uuid.UUID]:
    rows = db.scalars(
        select(CaseInvitation.invitee_user_id).where(
            CaseInvitation.case_id == case.id,
            CaseInvitation.status == "accepted",
            CaseInvitation.invitee_user_id.is_not(None),
        )
    )
    return [r for r in rows if r is not None]


def notify_clients(
    db: Session, case: Case, kind: str, message: str, entry: TimelineEntry | None = None
) -> int:
    """Creates one unread update for every accepted client. Messages never carry private data."""
    count = 0
    for client_id in accepted_client_ids(db, case):
        db.add(
            ClientUpdate(
                client_id=client_id,
                case_id=case.id,
                timeline_entry_id=entry.id if entry else None,
                kind=kind,
                message=f"{case.title}: {message}"[:500],
            )
        )
        count += 1
    db.flush()
    return count


# ---- the client-facing status ----------------------------------------------------------------


def status_state(case: Case) -> ClientStatusState:
    return ClientStatusState(
        status=case.client_status,  # type: ignore[arg-type]
        changed_at=aware(case.client_status_changed_at) if case.client_status_changed_at else None,
    )


def set_client_status(db: Session, case: Case, advocate_id: uuid.UUID, new: str) -> ClientStatusState:
    """Choosing the current value again does nothing. Closed also closes the case; choosing
    anything else on a closed case reopens it."""
    if new not in CLIENT_STATUSES:
        raise HTTPException(422, "Unknown status")
    if case.client_status == new:
        return status_state(case)

    case.client_status = new
    case.client_status_changed_at = utcnow()
    case.client_status_changed_by = advocate_id
    if new == "closed":
        case.status = "closed"
    elif case.status == "closed":
        case.status = "active"

    label = STATUS_LABELS[new]
    entry = record_entry(db, case, "status_change", f"Status changed to {label}.", created_by=advocate_id)
    notify_clients(db, case, "status_change", f"The status changed to {label}.", entry)
    return status_state(case)


# ---- updates and notes -----------------------------------------------------------------------


def _clean(text: str) -> str:
    text = text.strip()
    if not text:
        raise HTTPException(422, "Text cannot be empty")
    return text


def post_update(db: Session, case: Case, advocate_id: uuid.UUID, message: str) -> TimelineEntry:
    message = _clean(message)
    entry = record_entry(db, case, "update", message, created_by=advocate_id)
    notify_clients(db, case, "update", f"Your lawyer posted an update: {message[:160]}", entry)
    return entry


def add_note(db: Session, case: Case, advocate_id: uuid.UUID, text: str, shared: bool) -> TimelineEntry:
    """Notes are private unless the advocate shares them, and never notify on their own."""
    return record_entry(db, case, NOTE_KIND, _clean(text), created_by=advocate_id, shared=shared)


def get_entry(db: Session, case: Case, entry_id: uuid.UUID) -> TimelineEntry:
    entry = db.get(TimelineEntry, entry_id)
    if entry is None or entry.case_id != case.id:
        raise HTTPException(404, "Not found")
    return entry


def set_entry_sharing(
    db: Session, case: Case, advocate_id: uuid.UUID, entry_id: uuid.UUID, shared: bool
) -> TimelineEntry:
    entry = get_entry(db, case, entry_id)
    if entry.kind in ALWAYS_VISIBLE_KINDS:
        raise HTTPException(422, "Status changes, hearing dates and updates are always visible to clients")
    if entry.kind == "outcome" and entry.hearing_id:
        hearing = db.get(Hearing, entry.hearing_id)
        if hearing is not None:
            set_outcome(db, case, advocate_id, hearing, hearing.outcome or "", shared)
            db.refresh(entry)
            return entry
    if entry.kind == "document_shared" and entry.document_id:
        document = db.get(Document, entry.document_id)
        if document is not None:
            set_document_sharing(db, case, advocate_id, document, shared)
            db.refresh(entry)
            return entry
    entry.shared_with_client = shared
    db.flush()
    return entry


# ---- documents and hearing outcomes ----------------------------------------------------------


def set_document_sharing(
    db: Session, case: Case, advocate_id: uuid.UUID, document: Document, shared: bool
) -> None:
    """Sharing notifies clients once; unsharing hides the document at once and says nothing."""
    if document.shared_with_client == shared:
        return
    document.shared_with_client = shared
    if shared:
        entry = record_entry(
            db, case, "document_shared", f"Document shared: {document.file_name}",
            created_by=advocate_id, document_id=document.id, shared=True,
        )
        notify_clients(db, case, "document_shared", "A document was shared with you.", entry)
    else:
        for entry in db.scalars(
            select(TimelineEntry).where(
                TimelineEntry.document_id == document.id, TimelineEntry.kind == "document_shared"
            )
        ):
            entry.shared_with_client = False
    db.flush()


def set_outcome(
    db: Session, case: Case, advocate_id: uuid.UUID, hearing: Hearing, outcome: str, shared: bool
) -> None:
    """Records a hearing outcome. It reaches clients only while `shared` is true."""
    outcome = outcome.strip()
    changed = (hearing.outcome or "") != outcome
    was_shared = hearing.outcome_shared
    hearing.outcome = outcome or None
    hearing.outcome_shared = bool(shared and outcome)

    entry = db.scalars(
        select(TimelineEntry)
        .where(TimelineEntry.hearing_id == hearing.id, TimelineEntry.kind == "outcome")
        .order_by(TimelineEntry.occurred_at.desc())
    ).first()
    if outcome:
        text = f"Hearing on {when_text(hearing.scheduled_at)}: {outcome}"
        if entry is None:
            entry = record_entry(
                db, case, "outcome", text, created_by=advocate_id,
                hearing_id=hearing.id, shared=hearing.outcome_shared,
            )
        else:
            entry.text = text
            entry.shared_with_client = hearing.outcome_shared
        if hearing.outcome_shared and (not was_shared or changed):
            notify_clients(db, case, "outcome", "A hearing outcome was shared with you.", entry)
    elif entry is not None:
        entry.shared_with_client = False
    db.flush()


# ---- hearings --------------------------------------------------------------------------------


def hearing_scheduled(db: Session, case: Case, advocate_id: uuid.UUID, hearing: Hearing) -> None:
    when = when_text(hearing.scheduled_at)
    entry = record_entry(
        db, case, "hearing_scheduled", f"Hearing scheduled for {when}.",
        created_by=advocate_id, hearing_id=hearing.id,
    )
    notify_clients(db, case, "hearing_scheduled", f"A hearing was scheduled for {when}.", entry)


def hearing_rescheduled(
    db: Session, case: Case, advocate_id: uuid.UUID, hearing: Hearing, old: datetime
) -> None:
    new_text, old_text = when_text(hearing.scheduled_at), when_text(old)
    entry = record_entry(
        db, case, "hearing_rescheduled", f"Hearing moved from {old_text} to {new_text}.",
        created_by=advocate_id, hearing_id=hearing.id,
    )
    notify_clients(db, case, "hearing_rescheduled", f"A hearing was moved to {new_text}.", entry)
