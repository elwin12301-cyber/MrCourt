"""WhatsApp channel (feature 010): what Settings shows and what the administrator's Messages view returns."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ConsentKindOut(BaseModel):
    kind: Literal["codes", "reminders", "updates", "activity"]
    enabled: bool
    changed_at: datetime | None = None
    describes: str


class WhatsAppSettingsOut(BaseModel):
    available: bool  # a real provider is set up (otherwise messages appear on the development page)
    linked: bool
    number: str | None = None  # masked
    can_link: bool  # the phone number is verified
    kinds: list[ConsentKindOut]
    last_sent_at: datetime | None = None


class ConsentIn(BaseModel):
    enabled: bool


# ----- the administrator's Messages view: counts and failures, never message text -----


class MessageTotal(BaseModel):
    kind: str
    channel: Literal["whatsapp", "sms"]
    queued: int = 0
    sent: int = 0
    delivered: int = 0
    read: int = 0
    failed: int = 0


class ServiceHealth(BaseModel):
    provider: str
    configured: bool
    healthy: bool | None = None  # None when no provider is connected (development)
    last_ok_at: datetime | None = None


class SummaryOut(BaseModel):
    days: int
    service: ServiceHealth
    totals: list[MessageTotal]


class FailureRow(BaseModel):
    id: uuid.UUID
    time: datetime
    kind: str
    person: str  # the name only: no number, no words
    reason: str  # a plain code, for example not_on_whatsapp
    fell_back_to_sms: bool
    can_resend: bool


class FailuresPage(BaseModel):
    items: list[FailureRow]
    next_before: str | None = None
