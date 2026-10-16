"""WhatsApp channel (feature 010): who linked a number, what they agreed to receive, delivery records, incoming
messages (to ignore repeats) and the short memory of a "choose a case" list. No message text is stored here."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from mrcourt.db.base import Base, IdMixin, utcnow

CONSENT_KINDS = ("codes", "reminders", "updates", "activity")
# What an incoming message can be (PostgreSQL enforces the column width; SQLite does not, so a test checks it).
INBOUND_KINDS = ("text", "audio", "other", "stop", "question", "voice", "status", "unknown_sender")
INBOUND_KIND_WIDTH = 16
STATUS_ORDER = {"queued": 0, "sent": 1, "delivered": 2, "read": 3}  # failed is final and handled separately


class WhatsAppLink(Base):
    """A verified number allowed to use the channel. One per account; a number belongs to one account."""

    __tablename__ = "whatsapp_links"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    msisdn: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # opens the 24-hour window
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unlinked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # set: the link is inactive

    @property
    def active(self) -> bool:
        return self.unlinked_at is None


class MessageConsent(Base):
    __tablename__ = "message_consents"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), primary_key=True)  # codes | reminders | updates | activity
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    changed_by: Mapped[str] = mapped_column(String(12), default="person", nullable=False)  # person | stop | system


class Message(IdMixin, Base):
    """One outbound message and what became of it. Holds kind, status and time, never the text."""

    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_status_send_after", "status", "send_after"),)

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # code | reminder | update | activity
    channel: Mapped[str] = mapped_column(String(10), nullable=False)  # whatsapp | sms
    status: Mapped[str] = mapped_column(String(10), default="queued", nullable=False)  # queued|sent|delivered|read|failed
    provider: Mapped[str] = mapped_column(String(12), default="", nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), index=True)
    case_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("cases.id", ondelete="SET NULL"))
    hearing_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("hearings.id", ondelete="SET NULL"))
    fallback_of: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("messages.id", ondelete="SET NULL"))
    failure_reason: Mapped[str | None] = mapped_column(String(60))
    send_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class InboundMessage(IdMixin, Base):
    """A message received from a number, kept only to ignore repeats and to retry unfinished work."""

    __tablename__ = "inbound_messages"
    __table_args__ = (UniqueConstraint("provider", "provider_message_id", name="uq_inbound_provider_message"),)

    provider: Mapped[str] = mapped_column(String(12), nullable=False)
    provider_message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    sender_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)  # never a stranger's raw number
    kind: Mapped[str] = mapped_column(String(INBOUND_KIND_WIDTH), default="text", nullable=False)
    status: Mapped[str] = mapped_column(String(10), default="received", nullable=False)  # received | processed | failed
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    question_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("questions.id", ondelete="SET NULL"))
    # What the background step needs to answer: the text or the voice note's reference. Cleared when processed.
    payload: Mapped[dict[str, str] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)


class ConversationState(Base):
    """A person is choosing from a short list of cases (ids only), for a few minutes."""

    __tablename__ = "conversation_state"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    awaiting: Mapped[str] = mapped_column(String(20), nullable=False)  # case_choice
    options: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    intent: Mapped[str] = mapped_column(String(12), default="", nullable=False)  # next_hearing | status
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
