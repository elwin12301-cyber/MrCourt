"""Shapes for the admin console (spec 003)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AuditItem(BaseModel):
    id: uuid.UUID
    admin_name: str
    action: str
    action_label: str
    target_type: str
    target_id: uuid.UUID | None
    target_name: str | None
    detail: dict[str, object]
    created_at: datetime


class AuditPage(BaseModel):
    items: list[AuditItem]
    next_before: str | None


class Overview(BaseModel):
    advocates: int
    clients: int
    open_cases: int
    pending_verifications: int
    suspended_accounts: int
    recent_audit: list[AuditItem]


class UserRow(BaseModel):
    id: uuid.UUID
    role: Literal["advocate", "petitioner"]
    full_name: str
    email: str | None
    phone: str | None
    status: Literal["active", "suspended", "deactivated"]
    verification_status: Literal["none", "pending", "verified"]
    bar_registration_number: str | None
    created_at: datetime
    case_count: int


class UserCase(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    relation: Literal["advocate", "client"]
    advocate_name: str


class Suspension(BaseModel):
    reason: str
    at: datetime
    by: str


class UserDetail(UserRow):
    cases: list[UserCase]
    suspension: Suspension | None


class UserPatch(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=32)
    bar_registration_number: str | None = Field(default=None, max_length=64)


class SuspendIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class CaseRow(BaseModel):
    id: uuid.UUID
    title: str
    court: str
    status: str
    advocate_name: str
    client_count: int
    next_hearing_at: datetime | None


class AdminParty(BaseModel):
    side: str
    name: str
    is_client: bool


class AdminHearing(BaseModel):
    id: uuid.UUID
    scheduled_at: datetime
    purpose: str | None
    court_room: str | None
    outcome: str | None
    outcome_shared: bool


class AdminDocument(BaseModel):
    id: uuid.UUID
    file_name: str
    size_bytes: int
    shared_with_client: bool


class AdminTimelineEntry(BaseModel):
    id: uuid.UUID
    kind: str
    text: str
    shared_with_client: bool
    occurred_at: datetime


class AdminClient(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    accepted_at: datetime | None


class AdminQuestion(BaseModel):
    id: uuid.UUID
    client_name: str
    kind: str
    text: str
    sent_at: datetime
    reply_text: str | None
    replied_at: datetime | None


class AdminAdvocate(BaseModel):
    id: uuid.UUID
    name: str


class CaseFull(BaseModel):
    id: uuid.UUID
    title: str
    cnr_number: str
    court: str
    status: str
    stage: str | None
    court_room: str | None
    notes: str | None
    client_status: str | None
    client_status_changed_at: datetime | None
    advocate: AdminAdvocate
    parties: list[AdminParty]
    hearings: list[AdminHearing]
    documents: list[AdminDocument]
    timeline: list[AdminTimelineEntry]
    clients: list[AdminClient]
    client_questions: list[AdminQuestion]


class RankingScores(BaseModel):
    keyword: float
    meaning: float
    rerank: float | None
    combined: float


class RankingSignal(BaseModel):
    name: str
    label: str
    value: float | str


class RankedPassage(BaseModel):
    position: int
    hidden: bool  # another user's private document: no label, no case or person named
    label: str | None
    pinned: bool
    scores: RankingScores
    signals: list[RankingSignal]


class RankingExplanation(BaseModel):
    question_id: uuid.UUID
    recorded: bool
    mode: str | None = None
    question_type: str | None = None
    references: list[str] = Field(default_factory=list)
    passages: list[RankedPassage] = Field(default_factory=list)
