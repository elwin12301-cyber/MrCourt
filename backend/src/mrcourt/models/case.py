import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mrcourt.db.base import Base, IdMixin, TimestampMixin

CASE_STATUSES = ("active", "hearing_soon", "closed")


class Case(IdMixin, TimestampMixin, Base):
    __tablename__ = "cases"
    __table_args__ = (UniqueConstraint("owner_id", "cnr_number", name="uq_case_owner_cnr"),)

    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    cnr_number: Mapped[str] = mapped_column(String(64), nullable=False)
    court: Mapped[str] = mapped_column(String(200), nullable=False)
    # Stored as "active" or "closed"; "hearing_soon" is derived from the next hearing.
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    stage: Mapped[str | None] = mapped_column(String(100))
    room: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)
    # What the client sees: one of notice_stage, hearing_scheduled, awaiting_order, closed (or unset).
    client_status: Mapped[str | None] = mapped_column(String(20))
    client_status_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    client_status_changed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))

    parties: Mapped[list["Party"]] = relationship(cascade="all, delete-orphan")
    hearings: Mapped[list["Hearing"]] = relationship(
        cascade="all, delete-orphan", order_by="Hearing.scheduled_at"
    )
    documents: Mapped[list["Document"]] = relationship(cascade="all, delete-orphan")


class Party(IdMixin, Base):
    __tablename__ = "parties"

    case_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("cases.id"), nullable=False)
    side: Mapped[str] = mapped_column(String(20), nullable=False)  # petitioner | respondent
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    is_client: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Hearing(IdMixin, TimestampMixin, Base):
    __tablename__ = "hearings"

    case_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("cases.id"), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    court_room: Mapped[str | None] = mapped_column(String(50))
    purpose: Mapped[str | None] = mapped_column(String(200))
    outcome: Mapped[str | None] = mapped_column(Text)
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome_shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Document(IdMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    case_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("cases.id"), nullable=False)
    file_name: Mapped[str] = mapped_column(String(300), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    shared_with_client: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class CaseInvitation(IdMixin, TimestampMixin, Base):
    __tablename__ = "case_invitations"

    case_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("cases.id"), nullable=False)
    invitee_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    invitee_contact: Mapped[str | None] = mapped_column(String(320))
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    invited_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
