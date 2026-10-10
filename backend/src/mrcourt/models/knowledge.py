import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from mrcourt.db.base import Base, IdMixin, TimestampMixin
from mrcourt.models.legal import JsonType

DOCUMENT_KINDS = ("act_section", "judgment", "note")
DOCUMENT_STATUSES = ("processing", "ready", "failed")


class KnowledgeDocument(IdMixin, TimestampMixin, Base):
    """A source people manage. Its passages (LegalSource rows) are what search reads."""

    __tablename__ = "knowledge_documents"

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    citation: Mapped[str] = mapped_column(String(400), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="processing", nullable=False)
    status_reason: Mapped[str | None] = mapped_column(String(300))
    file_name: Mapped[str | None] = mapped_column(String(300))
    file_path: Mapped[str | None] = mapped_column(String(500))
    page_count: Mapped[int | None] = mapped_column(Integer)
    passage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ocr_pages: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))


class ProposedAction(IdMixin, Base):
    """Something the assistant wants to do, waiting for the person to confirm. Single use."""

    __tablename__ = "proposed_actions"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    question_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("questions.id"))
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    params: Mapped[dict[str, object]] = mapped_column(JsonType, default=dict)
    summary: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    result_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
