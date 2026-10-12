import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class QuestionIn(BaseModel):
    text: str = Field(max_length=2000)
    case_id: uuid.UUID | None = None
    input_method: Literal["typed", "voice"] = "typed"
    filters: "SourceFilters | None" = None  # limit sources by document details (feature 008)

    @field_validator("text")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Question cannot be empty")
        return value


class ParagraphOut(BaseModel):
    text: str
    citation_numbers: list[int]
    kind: Literal["law", "case"] = "law"


class CitationOut(BaseModel):
    number: int
    label: str
    source_url: str | None = None
    passage_id: uuid.UUID | None = None  # lets the reader open the cited passage
    details: str | None = None  # short document details, e.g. "Judgment · Madras High Court · 07 Apr 2025"


class AnswerOut(BaseModel):
    question_id: uuid.UUID | None = None
    answer_mode: Literal["full", "passages"] = "passages"
    search_mode: Literal["meaning", "keywords"] = "keywords"
    source_language_note: str | None = None
    outcome: Literal["cited", "answered", "no_reliable_source"]
    paragraphs: list[ParagraphOut]
    citations: list[CitationOut]
    message: str | None = None
    disclaimer: str
    # Only for clients (petitioners); always null for advocates.
    case_specific_notice: str | None = None
    lawyer_reminder: str | None = None


class SourceFilters(BaseModel):
    type: Literal["statute", "judgment", "order", "petition", "deed", "deposition", "notice", "other"] | None = None
    court: str | None = Field(default=None, max_length=200)
    year: int | None = Field(default=None, ge=1800, le=2100)
    act: str | None = Field(default=None, max_length=30)
    section: str | None = Field(default=None, max_length=20)
    case: str | None = Field(default=None, max_length=60)


QuestionIn.model_rebuild()
