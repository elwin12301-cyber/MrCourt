import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from mrcourt.api.deps import CurrentUser, DbSession
from mrcourt.config import get_settings
from mrcourt.models import KnowledgeDocument, LegalSource, User
from mrcourt.schemas.knowledge import DocumentOut, PassageOut
from mrcourt.services import knowledge, ratelimit
from mrcourt.services.retrieval import visible_to

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def _out(user: User, doc: KnowledgeDocument) -> DocumentOut:
    state, reason = knowledge.effective_status(doc)
    is_client = user.role == "petitioner"
    return DocumentOut(
        id=doc.id,
        title=doc.title,
        citation=doc.citation,
        kind=doc.kind,  # type: ignore[arg-type]
        scope="shared" if doc.owner_id is None else "private",
        status=state,  # type: ignore[arg-type]
        status_reason=None if is_client else reason,
        passage_count=None if is_client else doc.passage_count,
        page_count=None if is_client else doc.page_count,
        ocr_pages=None if is_client else doc.ocr_pages,
        created_at=doc.created_at,
        can_remove=knowledge.can_remove(user, doc),
    )


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(
    user: CurrentUser,
    db: DbSession,
    q: str | None = None,
    kind: str | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> list[DocumentOut]:
    return [_out(user, d) for d in knowledge.list_documents(db, user, q, kind, status_filter)]


@router.post("/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def add_document(
    user: CurrentUser,
    db: DbSession,
    background: BackgroundTasks,
    title: Annotated[str, Form(max_length=300)],
    citation: Annotated[str, Form(max_length=400)],
    kind: Annotated[str | None, Form()] = None,
    text: Annotated[str | None, Form(max_length=2_000_000)] = None,
    file: Annotated[UploadFile | None, File()] = None,
) -> DocumentOut:
    if user.role == "petitioner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Clients cannot add to the knowledge base")
    ratelimit.hit(f"kb-add:{user.id}", limit=10, window_seconds=3600)
    limit = get_settings().max_knowledge_bytes
    data = None
    if file is not None and file.filename:
        data = await file.read(limit + 1)
    doc = knowledge.create_document(
        db,
        user,
        title=title,
        citation=citation,
        kind=kind,
        text=text,
        file_name=file.filename if data is not None and file else None,
        data=data,
    )
    db.commit()
    factory = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
    if doc.status == "processing":
        background.add_task(knowledge.process_document, factory, doc.id)
    background.add_task(knowledge.embed_document, factory, doc.id)  # does nothing unless the document is ready
    return _out(user, doc)


@router.get("/passages/{passage_id}", response_model=PassageOut)
def read_passage(passage_id: uuid.UUID, user: CurrentUser, db: DbSession) -> PassageOut:
    """The text a citation points to. Only passages the person may use are shown; anything else,
    including a passage that has since been removed, is not found."""
    passage = db.scalar(select(LegalSource).where(LegalSource.id == passage_id, visible_to(user if user.role != "admin" else None)))
    if passage is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")
    doc = db.get(KnowledgeDocument, passage.document_id) if passage.document_id else None
    return PassageOut(
        id=passage.id,
        text=passage.text,
        citation=passage.citation_label,
        document_title=doc.title if doc else passage.instrument,
        page=passage.page,
        read_by_ocr=passage.read_by_ocr,
        ocr_confidence=passage.ocr_confidence,
        scope="shared" if passage.owner_id is None else "private",
    )


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_document(document_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    doc = db.get(KnowledgeDocument, document_id)
    if doc is None or (doc.owner_id is not None and doc.owner_id != user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")
    if not knowledge.can_remove(user, doc):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot remove this source")
    knowledge.remove_document(db, user, doc)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
