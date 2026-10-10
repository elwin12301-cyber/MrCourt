import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


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


class PassageOut(BaseModel):
    id: uuid.UUID
    text: str
    citation: str
    document_title: str | None = None
    page: int | None = None
    read_by_ocr: bool = False
    ocr_confidence: float | None = None
    scope: Literal["shared", "private"]
