import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class QuestionIn(BaseModel):
    text: str = Field(max_length=2000)
    case_id: uuid.UUID | None = None
    input_method: Literal["typed", "voice"] = "typed"

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
