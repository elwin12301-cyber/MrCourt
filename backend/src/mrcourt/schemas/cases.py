import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CaseStatus = Literal["active", "hearing_soon", "closed"]


class PartyIO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    side: Literal["petitioner", "respondent"]
    name: str = Field(min_length=1, max_length=300)
    is_client: bool = False


class CaseInput(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    cnr_number: str | None = Field(default=None, min_length=1, max_length=64)
    court: str | None = Field(default=None, min_length=1, max_length=200)
    status: Literal["active", "closed"] | None = None
    stage: str | None = Field(default=None, max_length=100)
    court_room: str | None = Field(default=None, max_length=50)
    notes: str | None = None
    parties: list[PartyIO] | None = None


class HearingInput(BaseModel):
    scheduled_at: datetime
    court_room: str | None = Field(default=None, max_length=50)
    purpose: str | None = Field(default=None, max_length=200)


class HearingPatch(BaseModel):
    scheduled_at: datetime | None = None
    court_room: str | None = Field(default=None, max_length=50)
    purpose: str | None = Field(default=None, max_length=200)
    outcome: str | None = None


class HearingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scheduled_at: datetime
    court_room: str | None
    purpose: str | None
    outcome: str | None
    outcome_shared: bool = False


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    file_name: str
    size_bytes: int
    shared_with_client: bool = False


class CaseSummary(BaseModel):
    id: uuid.UUID
    title: str
    cnr_number: str
    court: str
    status: CaseStatus
    next_hearing_at: datetime | None


class CaseDetail(CaseSummary):
    stage: str | None
    court_room: str | None
    parties: list[PartyIO]
    documents: list[DocumentOut]
    hearings: list[HearingOut]
    notes: str | None
    client_status: str | None = None
    client_status_changed_at: datetime | None = None


class InvitationIn(BaseModel):
    contact: str = Field(min_length=1, max_length=320)


class InvitationOut(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    case_title: str
    status: str


class ActivityOut(BaseModel):
    message: str
    created_at: datetime


class Dashboard(BaseModel):
    active_cases: int
    hearings_this_week: int
    drafts_to_review: int
    upcoming_hearings: list[CaseSummary]
    recent_activity: list[ActivityOut]
