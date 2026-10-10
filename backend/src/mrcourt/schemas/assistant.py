import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from mrcourt.schemas.questions import CitationOut, ParagraphOut


class AssistantStatus(BaseModel):
    answers: Literal["full", "passages"]
    assistant: bool
    notice: str | None = None
    search: Literal["meaning", "keywords"] = "keywords"  # whether meaning-based search is set up
    speech: bool = False  # server-side speech to text is set up
    ocr: bool = False  # scanned documents can be read


class AssistantRequestIn(BaseModel):
    text: str = Field(max_length=2000)
    input_method: Literal["typed", "voice"] = "typed"

    @field_validator("text")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Request cannot be empty")
        return value


class StepOut(BaseModel):
    tool: str
    label: str
    status: Literal["ok", "refused", "failed"]
    detail: str | None = None


class ProposedActionOut(BaseModel):
    id: uuid.UUID
    kind: str
    summary: str
    expires_at: datetime


class AssistantResponse(BaseModel):
    question_id: uuid.UUID
    outcome: Literal["cited", "answered", "no_reliable_source"]
    steps: list[StepOut]
    paragraphs: list[ParagraphOut]
    citations: list[CitationOut]
    message: str | None = None
    proposed_action: ProposedActionOut | None = None
    disclaimer: str
    case_specific_notice: str | None = None
    lawyer_reminder: str | None = None


class ActionResult(BaseModel):
    status: Literal["done", "declined"]
    draft_id: uuid.UUID | None = None
