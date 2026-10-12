import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class DetailsSummary(BaseModel):
    doc_type: str | None = None
    court: str | None = None
    case_number: str | None = None
    decided_on: date | None = None
    language: str | None = None
    text_quality: str | None = None
    short: str | None = None


class DocumentOut(BaseModel):
    id: uuid.UUID
    title: str
    citation: str
    kind: Literal["act_section", "judgment", "note"]
    scope: Literal["shared", "private"]
    status: Literal["processing", "ready", "failed"]
    status_reason: str | None = None
    passage_count: int | None = None
    page_count: int | None = None
    ocr_pages: int | None = None
    created_at: datetime
    can_remove: bool
    details: DetailsSummary | None = None


class PassageOut(BaseModel):
    id: uuid.UUID
    text: str
    citation: str
    document_title: str | None = None
    page: int | None = None
    read_by_ocr: bool = False
    ocr_confidence: float | None = None
    scope: Literal["shared", "private"]
    details: dict[str, object] | None = None  # field -> value, for the passage's document (feature 008)
    details_label: str | None = None


class DetailsOut(BaseModel):
    document_id: uuid.UUID
    can_edit: bool
    text_quality: str | None = None
    fields: dict[str, dict[str, object]]


class DetailsPatch(BaseModel):
    fields: dict[str, object] = Field(min_length=1)


class RemapOut(BaseModel):
    documents: int
    fields_found: dict[str, int]
    unreadable: int


class FilterOptions(BaseModel):
    types: list[str]
    courts: list[str]
    years: list[int]
    acts: list[str]
