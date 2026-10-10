import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from mrcourt.db.base import Base, IdMixin, TimestampMixin, utcnow

TEMPLATES = ("notice", "bail", "reply", "affidavit")


class Draft(IdMixin, TimestampMixin, Base):
    __tablename__ = "drafts"

    case_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("cases.id"))
    author_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    template: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_edited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # True once the author has saved at least one edit after generation.
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class DraftExport(IdMixin, Base):
    __tablename__ = "draft_exports"

    draft_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("drafts.id"), nullable=False)
    format: Mapped[str] = mapped_column(String(10), nullable=False)
    requested_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
