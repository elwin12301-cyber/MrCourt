"""Request and response shapes for the client experience (see contracts/openapi.yaml)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ClientStatus = Literal["notice_stage", "hearing_scheduled", "awaiting_order", "closed"]
QuestionKind = Literal["question", "update_request"]


# ---- what a client may see -------------------------------------------------------------------


class Lawyer(BaseModel):
    name: str
    verification_status: Literal["none", "pending", "verified"]
    phone: str | None = None
    email: str | None = None
    office: str | None = None
    available: bool = True  # false once the advocate has deactivated


class HearingDescription(BaseModel):
    text: str
    label: str = "General information"
    disclaimer: str = "Informational only, not legal advice."


class HearingForClient(BaseModel):
    id: uuid.UUID
    scheduled_at: datetime
    court: str
    description: HearingDescription | None = None
    outcome: str | None = None  # only when the advocate shared it


class TimelineEntryForClient(BaseModel):
    id: uuid.UUID
    kind: str
    text: str
    occurred_at: datetime


class DocumentForClient(BaseModel):
    id: uuid.UUID
    file_name: str
    size_bytes: int


class AccessInfo(BaseModel):
    advocate_name: str
    since: datetime | None
    other_people_with_access: int


class ClientCaseSummary(BaseModel):
    id: uuid.UUID
    title: str
    court: str
    status: ClientStatus | None
    status_changed_at: datetime | None
    next_hearing: HearingForClient | None
    lawyer: Lawyer


class ClientCase(ClientCaseSummary):
    hearings: list[HearingForClient]
    timeline: list[TimelineEntryForClient]
    documents: list[DocumentForClient]
    access: AccessInfo


class ClientUpdateOut(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    kind: str
    message: str
    created_at: datetime
    read: bool


class UpdatesList(BaseModel):
    unread_count: int
    items: list[ClientUpdateOut]


class ClientDashboard(BaseModel):
    cases: list[ClientCaseSummary]
    unread_updates: int
    latest_updates: list[ClientUpdateOut]


class ClientQuestionOut(BaseModel):
    id: uuid.UUID
    kind: QuestionKind
    text: str
    sent_at: datetime
    reply_text: str | None
    replied_at: datetime | None
    reply_read: bool


class ClientQuestionAdvocate(ClientQuestionOut):
    client_name: str


class AskLawyerIn(BaseModel):
    kind: QuestionKind
    text: str | None = Field(default=None, max_length=2000)


class GlossaryTerm(BaseModel):
    term: str
    meaning: str


# ---- what an advocate sends or sees ----------------------------------------------------------


class ClientStatusIn(BaseModel):
    status: ClientStatus


class ClientStatusState(BaseModel):
    status: ClientStatus | None
    changed_at: datetime | None


class ClientUpdateIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class TimelineNoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    shared_with_client: bool = False


class ShareIn(BaseModel):
    shared: bool


class OutcomeIn(BaseModel):
    outcome: str = Field(max_length=2000)
    shared: bool = False


class TimelineEntryAdvocate(TimelineEntryForClient):
    shared_with_client: bool


class ClientContact(BaseModel):
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=320)
    office: str | None = Field(default=None, max_length=300)


class ReplyIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class CaseInvitationOut(BaseModel):
    id: uuid.UUID
    contact_or_name: str
    status: Literal["pending", "accepted", "removed"]
    accepted_at: datetime | None
