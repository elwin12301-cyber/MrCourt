"""Client-facing records: the timeline, updates for clients, and questions to the lawyer."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from mrcourt.db.base import Base, IdMixin, TimestampMixin, utcnow

TIMELINE_KINDS = (
    "status_change",
    "hearing_scheduled",
    "hearing_rescheduled",
    "outcome",
    "document_shared",
    "update",
    "note",
)


class TimelineEntry(IdMixin, TimestampMixin, Base):
    """One dated event on a case. Clients see it only while `shared_with_client` is true."""

    __tablename__ = "timeline_entries"

    case_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("cases.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    shared_with_client: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hearing_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("hearings.id"))
    document_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("documents.id"))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))


class ClientUpdate(IdMixin, TimestampMixin, Base):
    """A notice to one client about a change. Each client has their own read state."""

    __tablename__ = "client_updates"

    client_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    case_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("cases.id"), nullable=False)
    timeline_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("timeline_entries.id")
    )
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ClientQuestion(IdMixin, TimestampMixin, Base):
    """A message from one client to their advocate. Private to that client and the advocate."""

    __tablename__ = "client_questions"

    case_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("cases.id"), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # question | update_request
    text: Mapped[str] = mapped_column(Text, nullable=False)
    reply_text: Mapped[str | None] = mapped_column(Text)
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replied_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    reply_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
