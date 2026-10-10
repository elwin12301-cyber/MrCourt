"""The administrators' audit log. Entries are only ever added, never changed or removed."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from mrcourt.db.base import Base, IdMixin, utcnow


class AuditEntry(IdMixin, Base):
    __tablename__ = "audit_log"

    admin_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    target_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    # Safe details only: field names, statuses, reasons. Never message text, passwords or file contents.
    detail: Mapped[dict[str, object] | None] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )
