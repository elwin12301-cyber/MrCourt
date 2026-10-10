import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

TemplateKey = Literal["notice", "bail", "reply", "affidavit"]


class DraftCreate(BaseModel):
    template: TemplateKey
    case_id: uuid.UUID | None = None


class DraftSave(BaseModel):
    body: str = Field(max_length=100_000)


class ExportRequest(BaseModel):
    format: Literal["docx", "pdf"]


class DraftOut(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID | None
    template: TemplateKey
    title: str
    subtitle: str
    body: str
    version: int
    ai_generated: bool
    reviewed: bool
    last_edited_at: datetime
