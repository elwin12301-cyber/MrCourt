import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from mrcourt.db.base import Base, IdMixin


class ReminderLog(IdMixin, Base):
    """One row per reminder already sent (or covered by a later one) for a person and a hearing."""

    __tablename__ = "reminder_log"
    __table_args__ = (UniqueConstraint("hearing_id", "user_id", "offset_days", name="uq_reminder"),)

    hearing_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("hearings.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, index=True)
    offset_days: Mapped[int] = mapped_column(Integer, nullable=False)  # 5, 1 or 0 days before
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
