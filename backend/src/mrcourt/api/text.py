import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response, status
from sqlalchemy.orm import sessionmaker

from mrcourt.api.deps import CurrentUser, DbSession
from mrcourt.api.knowledge import _out as document_out
from mrcourt.models import TextConversation, TextLine
from mrcourt.schemas.knowledge import DocumentOut
from mrcourt.schemas.text import (
    ConversationIn,
    ConversationOut,
    ConversationPatch,
    ConversationRow,
    KnowledgeIn,
    LineIn,
    LineOut,
    LinePatch,
)
from mrcourt.services import knowledge, text_assistant

router = APIRouter(prefix="/text", tags=["text assistant"])


def _row(c: TextConversation) -> ConversationRow:
    return ConversationRow(id=c.id, title=c.title, language=c.language, updated_at=c.updated_at, line_count=len(c.lines))


def _line(line: TextLine) -> LineOut:
    return LineOut(id=line.id, text=line.text, source=line.source, created_at=line.created_at)  # type: ignore[arg-type]


def _full(c: TextConversation) -> ConversationOut:
    return ConversationOut(**_row(c).model_dump(), lines=[_line(line) for line in c.lines])


@router.get("/conversations", response_model=list[ConversationRow])
def list_conversations(user: CurrentUser, db: DbSession) -> list[ConversationRow]:
    return [_row(c) for c in text_assistant.list_own(db, user)]


@router.post("/conversations", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def create_conversation(data: ConversationIn, user: CurrentUser, db: DbSession) -> ConversationOut:
    conversation = text_assistant.create(db, user, data.language)
    db.commit()
    return _full(conversation)


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
def get_conversation(conversation_id: uuid.UUID, user: CurrentUser, db: DbSession) -> ConversationOut:
    return _full(text_assistant.get_own(db, user, conversation_id))


@router.patch("/conversations/{conversation_id}", response_model=ConversationOut)
def patch_conversation(conversation_id: uuid.UUID, data: ConversationPatch, user: CurrentUser, db: DbSession) -> ConversationOut:
    conversation = text_assistant.get_own(db, user, conversation_id)
    text_assistant.rename(db, conversation, data.title, data.language)
    db.commit()
    return _full(conversation)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    text_assistant.delete(db, text_assistant.get_own(db, user, conversation_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/conversations/{conversation_id}/lines", response_model=LineOut, status_code=status.HTTP_201_CREATED)
def add_line(conversation_id: uuid.UUID, data: LineIn, user: CurrentUser, db: DbSession) -> LineOut:
    conversation = text_assistant.get_own(db, user, conversation_id)
    line = text_assistant.add_line(db, conversation, data.text, data.source)
    db.commit()
    return _line(line)


@router.patch("/conversations/{conversation_id}/lines/{line_id}", response_model=LineOut)
def edit_line(conversation_id: uuid.UUID, line_id: uuid.UUID, data: LinePatch, user: CurrentUser, db: DbSession) -> LineOut:
    conversation = text_assistant.get_own(db, user, conversation_id)
    line = text_assistant.edit_line(db, conversation, line_id, data.text)
    db.commit()
    return _line(line)


@router.delete("/conversations/{conversation_id}/lines/{line_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_line(conversation_id: uuid.UUID, line_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    conversation = text_assistant.get_own(db, user, conversation_id)
    text_assistant.remove_line(db, conversation, line_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/conversations/{conversation_id}/pdf")
def download_pdf(conversation_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    conversation = text_assistant.get_own(db, user, conversation_id)
    return Response(
        content=text_assistant.to_pdf(conversation),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="conversation.pdf"'},
    )


@router.post("/conversations/{conversation_id}/knowledge", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def add_to_knowledge(
    conversation_id: uuid.UUID, data: KnowledgeIn, user: CurrentUser, db: DbSession, background: BackgroundTasks
) -> DocumentOut:
    """Advocates keep it as a private note; clients cannot add to the knowledge base."""
    conversation = text_assistant.get_own(db, user, conversation_id)
    if not conversation.lines:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Add at least one line first")
    title = (data.title or conversation.title).strip()
    doc = knowledge.create_document(
        db,
        user,
        title=title,
        citation=(data.citation or title).strip(),
        kind="note",
        text=text_assistant.as_text(conversation),
        file_name=None,
        data=None,
    )
    db.commit()
    background.add_task(knowledge.embed_document, sessionmaker(bind=db.get_bind(), expire_on_commit=False), doc.id)
    return document_out(user, doc)
