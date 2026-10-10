"""Writes the administrators' audit log.

Entries are added in the caller's own transaction, so an action and its record succeed or fail
together. There is deliberately no function here to change or delete an entry.
"""

import uuid

from sqlalchemy.orm import Session

from mrcourt.models import AuditEntry, User

# Detail keys that must never be stored: the log says what was done, never the private content.
FORBIDDEN_KEYS = frozenset(
    {"text", "message", "body", "password", "password_hash", "code", "content", "reply", "outcome", "notes"}
)

ACTION_LABELS = {
    "user.view": "Opened a person's page",
    "user.update": "Corrected a person's details",
    "user.suspend": "Suspended an account",
    "user.reactivate": "Reactivated an account",
    "user.sign_out": "Forced a sign-out",
    "verification.confirm": "Confirmed a Bar Council number",
    "verification.reject": "Rejected a Bar Council number",
    "case.view": "Opened a case in full",
    "document.download": "Downloaded a case document",
    "knowledge.add": "Added a shared knowledge source",
    "knowledge.remove": "Removed a shared knowledge source",
    "history.view": "Opened a person's question history",
}


def record(
    db: Session,
    admin: User,
    action: str,
    target_type: str,
    target_id: uuid.UUID | None = None,
    **detail: object,
) -> AuditEntry:
    bad = FORBIDDEN_KEYS & set(detail)
    if bad:
        raise ValueError(f"Audit details must not contain: {sorted(bad)}")
    entry = AuditEntry(
        admin_id=admin.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
    )
    db.add(entry)
    db.flush()
    return entry
