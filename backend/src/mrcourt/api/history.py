import uuid
from typing import Literal

from fastapi import APIRouter, Query

from mrcourt.api.deps import CurrentUser, DbSession
from mrcourt.schemas.history import HistoryDetail, HistoryPage
from mrcourt.services import history

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=HistoryPage)
def my_history(
    user: CurrentUser,
    db: DbSession,
    q: str | None = None,
    outcome: Literal["answered", "none"] | None = None,
    input: Literal["typed", "voice"] | None = None,  # noqa: A002 - the public name is `input`
    mode: Literal["answer", "assistant"] | None = None,
    source: Literal["all", "ask", "text"] | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    before: str | None = None,
) -> HistoryPage:
    return history.list_questions(
        db, user.id, q=q, outcome=outcome, input_method=input, mode=mode, source=source, limit=limit, before=before
    )


@router.get("/{question_id}", response_model=HistoryDetail)
def open_one(question_id: uuid.UUID, user: CurrentUser, db: DbSession) -> HistoryDetail:
    return history.open_question(db, user, question_id)
