import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class LineOut(BaseModel):
    id: uuid.UUID
    text: str
    source: Literal["voice", "typed"]
    created_at: datetime


class ConversationRow(BaseModel):
    id: uuid.UUID
    title: str
    language: str
    updated_at: datetime
    line_count: int


class ConversationOut(ConversationRow):
    lines: list[LineOut]


class ConversationIn(BaseModel):
    language: str = "en-IN"


class ConversationPatch(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    language: str | None = None


class LineIn(BaseModel):
    text: str = Field(max_length=2000)
    source: Literal["voice", "typed"] = "typed"


class LinePatch(BaseModel):
    text: str = Field(max_length=2000)


class KnowledgeIn(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    citation: str | None = Field(default=None, max_length=400)
