import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mrcourt.db.base import Base, IdMixin, TimestampMixin

ROLES = ("advocate", "petitioner", "admin")
VERIFICATION_STATES = ("none", "pending", "verified")


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"

    role: Mapped[str] = mapped_column(String(20), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    username: Mapped[str | None] = mapped_column(String(30), unique=True)  # lower case; signs in like an email
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    phone: Mapped[str | None] = mapped_column(String(32), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    bar_registration_number: Mapped[str | None] = mapped_column(String(64))
    phone_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_status: Mapped[str] = mapped_column(String(20), default="none", nullable=False)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Raising this number ends every current session of this person at once.
    session_epoch: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    settings: Mapped["UserSettings"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), primary_key=True)
    language: Mapped[str] = mapped_column(String(8), default="en", nullable=False)
    whatsapp_reminders: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    hearing_alert_days: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    theme: Mapped[str] = mapped_column(String(10), default="system", nullable=False)
    # Contact details an advocate shows to clients: {"phone": ..., "email": ..., "office": ...}.
    # Empty by default; a field is shown to clients only when filled in.
    client_contact: Mapped[dict[str, str] | None] = mapped_column(JSON, default=dict)

    user: Mapped[User] = relationship(back_populates="settings")


class OtpChallenge(IdMixin, TimestampMixin, Base):
    __tablename__ = "otp_challenges"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[str] = mapped_column(String(20), default="login", nullable=False)  # login | phone | reset
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
