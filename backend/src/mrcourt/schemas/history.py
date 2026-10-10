import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from mrcourt.schemas.assistant import StepOut
from mrcourt.schemas.questions import CitationOut, ParagraphOut
from mrcourt.schemas.text import LineOut

OutcomeLabel = Literal["Answered", "No information found", "Saved"]


class HistoryItem(BaseModel):
    id: uuid.UUID
    text: str
    created_at: datetime
    input_method: Literal["typed", "voice"]
    mode: Literal["answer", "assistant", "text"]
    outcome_label: OutcomeLabel


class WorkspaceItem(HistoryItem):
    asker_id: uuid.UUID
    asker_name: str
    asker_role: Literal["advocate", "petitioner", "admin"]


class WorkspacePage(BaseModel):
    items: list[WorkspaceItem]
    next_before: str | None = None


class HistoryPage(BaseModel):
    items: list[HistoryItem]
    next_before: str | None = None


class HistoryDetail(HistoryItem):
    outcome: str
    answer_mode: Literal["full", "passages"]
    steps: list[StepOut] | None = None
    paragraphs: list[ParagraphOut]
    citations: list[CitationOut]
    message: str | None = None
    disclaimer: str
    lawyer_reminder: str | None = None
    # Text Assistant entries: the conversation as it was, even if it has since been deleted.
    lines: list[LineOut] | None = None
    conversation_id: uuid.UUID | None = None
    conversation_deleted: bool = False
