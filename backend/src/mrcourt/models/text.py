import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mrcourt.db.base import Base, IdMixin, TimestampMixin


class TextConversation(IdMixin, TimestampMixin, Base):
    """A person's private, editable list of spoken or typed lines (the Text Assistant)."""

    __tablename__ = "text_conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), default="New conversation", nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="en-IN", nullable=False)
    # Deleting hides it from the Text Assistant tab; its History entry (and the text) stay.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    lines: Mapped[list["TextLine"]] = relationship(
        cascade="all, delete-orphan", order_by="TextLine.position"
    )


class TextLine(IdMixin, Base):
    __tablename__ = "text_lines"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("text_conversations.id"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(10), default="typed", nullable=False)  # voice | typed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
