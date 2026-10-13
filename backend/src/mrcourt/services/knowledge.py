"""Managing the knowledge base: documents people add, list and remove.

Shared documents (no owner) are managed by administrators and used for everyone's answers. An
advocate's private notes belong to that advocate and are used only for their own answers. Search
reads passages (LegalSource rows); this module keeps documents and their passages together.
"""

import logging
import shutil
import uuid
from datetime import date, timedelta
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from mrcourt.config import get_settings
from mrcourt.db.base import utcnow
from mrcourt.models import AnswerCitation, DocumentReference, KnowledgeDocument, LegalSource, User
from mrcourt.services import audit
from mrcourt.services.cases import aware
from mrcourt.services.embeddings import embed_passages
from mrcourt.services.ingest import (
    IMAGE_TYPES,
    LOW_CONFIDENCE,
    IngestError,
    PageText,
    chunk_pages,
    clean_text,
    read_document,
)

STALE_AFTER = timedelta(minutes=10)
KINDS = ("act_section", "judgment", "note")


def effective_status(doc: KnowledgeDocument) -> tuple[str, str | None]:
    """A document stuck in Processing for too long is shown as failed (the task was lost)."""
    if doc.status == "processing" and aware(doc.updated_at) < utcnow() - STALE_AFTER:
        return "failed", "This did not finish. Remove it and add it again."
    return doc.status, doc.status_reason


def visible_documents(user: User):  # type: ignore[no-untyped-def]
    if user.role == "admin":  # administrators see every document, private ones too (views are audited)
        return select(KnowledgeDocument)
    condition = KnowledgeDocument.owner_id.is_(None)
    if user.role == "advocate":
        condition = or_(condition, KnowledgeDocument.owner_id == user.id)
    if user.role == "petitioner":
        return select(KnowledgeDocument).where(condition, KnowledgeDocument.status == "ready")
    return select(KnowledgeDocument).where(condition)


def apply_filters(query, filters: dict[str, object] | None):  # type: ignore[no-untyped-def]
    """Document details filters (feature 008): type, court, year, act, section, case."""
    if not filters:
        return query
    if value := filters.get("type"):
        query = query.where(KnowledgeDocument.doc_type == value)
    if value := filters.get("court"):
        query = query.where(KnowledgeDocument.court == value)
    if value := filters.get("year"):
        year = int(value)  # type: ignore[call-overload]
        query = query.where(
            KnowledgeDocument.decided_on >= date(year, 1, 1), KnowledgeDocument.decided_on <= date(year, 12, 31)
        )
    if value := filters.get("case"):
        like = f"%{str(value).strip().lower()}%"
        query = query.where(
            or_(func.lower(KnowledgeDocument.case_number).like(like), func.lower(KnowledgeDocument.title).like(like))
        )
    act, section = filters.get("act"), filters.get("section")
    if act or section:
        refs = select(DocumentReference.document_id)
        if act:
            refs = refs.where(DocumentReference.act == str(act).upper())
        if section:
            refs = refs.where(DocumentReference.section == str(section).upper())
        query = query.where(KnowledgeDocument.id.in_(refs))
    return query


def filter_options(db: Session, user: User) -> dict[str, list]:  # type: ignore[type-arg]
    """Filter values from the documents this person may see only (private values never reach others)."""
    docs = list(db.scalars(visible_documents(user)))
    ids = [d.id for d in docs]
    acts = sorted(set(db.scalars(select(DocumentReference.act).where(DocumentReference.document_id.in_(ids))))) if ids else []
    return {
        "types": sorted({d.doc_type for d in docs if d.doc_type}),
        "courts": sorted({d.court for d in docs if d.court}),
        "years": sorted({d.decided_on.year for d in docs if d.decided_on}, reverse=True),
        "acts": acts,
    }


def can_view_details(user: User, doc: KnowledgeDocument) -> bool:
    if doc.owner_id is not None:
        return doc.owner_id == user.id or user.role == "admin"
    return user.role != "petitioner" or doc.status == "ready"


def can_edit_details(user: User, doc: KnowledgeDocument) -> bool:
    if doc.owner_id is not None:
        return user.role == "advocate" and doc.owner_id == user.id
    return user.role == "admin"


LIST_FIELDS = ("case_numbers", "judges", "acts")


def _check(name: str, value: object) -> object:
    from mrcourt.services import metadata

    if value in (None, "", []):
        return None
    if name == "doc_type" and value not in metadata.DOC_TYPES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Choose a type from the list")
    if name == "outcome" and value not in metadata.OUTCOMES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Choose an outcome from the list")
    if name == "decided_on":
        try:
            return date.fromisoformat(str(value)).isoformat()
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Give the date as YYYY-MM-DD") from exc
    if name in LIST_FIELDS:
        if not isinstance(value, list):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{name} must be a list")
        return value[:50]
    if name == "parties":
        if not isinstance(value, dict):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "parties must list petitioner and respondent")
        return {"petitioner": list(value.get("petitioner", []))[:50], "respondent": list(value.get("respondent", []))[:50]}
    if not isinstance(value, str) or len(value) > 300:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{name} must be text of at most 300 characters")
    return value.strip()


def update_details(db: Session, user: User, doc: KnowledgeDocument, fields: dict[str, object]) -> None:
    """A person's corrections: kept as 'confirmed' and never changed by mapping again."""
    from mrcourt.services import metadata

    unknown = [n for n in fields if n not in metadata.FIELDS or n == "text_quality"]
    if unknown:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown field: {', '.join(unknown)}")
    details = dict(doc.details or {})
    stamp = utcnow().isoformat()
    for name, raw in fields.items():
        details[name] = {"value": _check(name, raw), "confidence": "confirmed", "source": "person", "by": str(user.id), "at": stamp}
    doc.details = details
    metadata.apply(db, doc, {})
    if doc.owner_id is None:
        audit.record(db, user, "knowledge.details.edit", "document", doc.id, fields=sorted(fields))


def list_documents(
    db: Session,
    user: User,
    q: str | None,
    kind: str | None,
    status_filter: str | None,
    filters: dict[str, object] | None = None,
) -> list[KnowledgeDocument]:
    query = apply_filters(visible_documents(user), filters)
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        query = query.where(
            or_(func.lower(KnowledgeDocument.title).like(like), func.lower(KnowledgeDocument.citation).like(like))
        )
    if kind:
        query = query.where(KnowledgeDocument.kind == kind)
    docs = list(db.scalars(query.order_by(KnowledgeDocument.created_at.desc())))
    if status_filter:
        docs = [d for d in docs if effective_status(d)[0] == status_filter]
    return docs


def can_remove(user: User, doc: KnowledgeDocument) -> bool:
    if doc.owner_id is None:
        return user.role == "admin"
    return user.role == "advocate" and doc.owner_id == user.id


def _taken(db: Session, owner_id: uuid.UUID | None, title: str) -> bool:
    query = select(KnowledgeDocument.id).where(
        func.lower(KnowledgeDocument.title) == title.lower(),
        KnowledgeDocument.status != "failed",
    )
    query = query.where(
        KnowledgeDocument.owner_id.is_(None) if owner_id is None else KnowledgeDocument.owner_id == owner_id
    )
    return db.scalar(query) is not None


def create_document(
    db: Session,
    user: User,
    *,
    title: str,
    citation: str,
    kind: str | None,
    text: str | None,
    file_name: str | None,
    data: bytes | None,
) -> KnowledgeDocument:
    """Creates the document. Pasted text is ready at once; a file is `processing` until
    `process_document` has run."""
    if user.role == "petitioner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Clients cannot add to the knowledge base")
    if user.role == "admin":
        owner_id = None
        kind = kind if kind in KINDS else "judgment"
    else:
        owner_id = user.id
        kind = "note"
    title, citation = title.strip(), citation.strip()
    if not title or not citation:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Give the source a title and a citation")
    if (text is None or not text.strip()) == (data is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Add either text or a file")
    if _taken(db, owner_id, title):
        raise HTTPException(status.HTTP_409_CONFLICT, "A source with this title already exists")

    settings = get_settings()
    if data is not None and len(data) > settings.max_knowledge_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "That file is too large (10 MB at most)")
    if data is not None and not (file_name or "").lower().endswith((".pdf", ".txt", ".md", *IMAGE_TYPES)):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Only text (.txt, .md), PDF and image (.png, .jpg, .tif) files are supported"
        )

    doc = KnowledgeDocument(
        title=title[:300],
        citation=citation[:400],
        kind=kind,
        owner_id=owner_id,
        status="processing",
        created_by=user.id,
        file_name=Path(file_name).name[:300] if file_name else None,
    )
    db.add(doc)
    db.flush()

    if data is not None:
        folder = Path(settings.knowledge_dir) / str(doc.id)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "original"
        path.write_bytes(data)
        doc.file_path = str(path)
    else:
        publish_pages(db, doc, [(1, text or "")], clean=True)

    if owner_id is None:
        audit.record(db, user, "knowledge.add", "document", doc.id, title=doc.title, citation=doc.citation)
    db.flush()
    return doc


def _label(doc: KnowledgeDocument, page: int, number: int, pages: int, passages: int) -> str:
    if pages > 1:
        return f"{doc.citation}, page {page}"
    return f"{doc.citation}, part {number}" if passages > 1 else doc.citation


LOW_CONFIDENCE_NOTE = (
    "Some scanned pages were hard to read, so the text may contain mistakes. Check it, or add a clearer scan."
)


def _garbled(text: str) -> bool:
    """True for text that is mostly replacement characters (a font the PDF could not decode)."""
    return len(text) > 0 and text.count("\ufffd") / len(text) > 0.1


def publish_pages(
    db: Session, doc: KnowledgeDocument, pages: list[tuple[int, str]] | list[PageText], *, clean: bool = False
) -> None:
    """Splits pages into passages and makes the document ready. Pages may carry OCR details."""
    page_texts = [p if isinstance(p, PageText) else PageText(p[0], clean_text(p[1]) if clean else p[1]) for p in pages]
    if not any(p.text for p in page_texts):
        raise IngestError("No readable text was found in this file.")
    by_number = {p.number: p for p in page_texts}
    passages = [p for p in chunk_pages([(p.number, p.text) for p in page_texts]) if not _garbled(p.text)]
    if not passages:
        raise IngestError("No readable text was found in this file.")
    for number, passage in enumerate(passages, start=1):
        source_page = by_number[passage.page]
        db.add(
            LegalSource(
                kind=doc.kind,
                instrument=doc.title,
                citation_label=_label(doc, passage.page, number, len(page_texts), len(passages)),
                text=passage.text,
                document_id=doc.id,
                owner_id=doc.owner_id,
                page=passage.page,
                read_by_ocr=source_page.ocr,
                ocr_confidence=source_page.confidence,
            )
        )
    scanned = [p for p in page_texts if p.ocr]
    confidences = [p.confidence for p in scanned if p.confidence is not None]
    doc.passage_count = len(passages)
    doc.page_count = len(page_texts)
    doc.ocr_pages = len(scanned)
    doc.status = "ready"
    doc.status_reason = (
        LOW_CONFIDENCE_NOTE if confidences and sum(confidences) / len(confidences) < LOW_CONFIDENCE else None
    )
    _map_details(db, doc)


def _map_details(db: Session, doc: KnowledgeDocument) -> None:
    """Feature 008: map the document's details now that its text is in. Never stops a document being ready."""
    from mrcourt.services import metadata

    try:
        db.flush()
        metadata.map_document(db, doc)
    except Exception:  # noqa: BLE001 - details are an extra; the document stays searchable without them
        logging.getLogger(__name__).warning("Mapping document details failed", exc_info=True)


def process_document(factory: sessionmaker[Session], document_id: uuid.UUID) -> None:
    """Background step for uploaded files: read, split, publish, or fail with a plain reason."""
    with factory() as db:
        doc = db.get(KnowledgeDocument, document_id)
        if doc is None or doc.status != "processing" or not doc.file_path:
            return
        settings = get_settings()
        try:
            data = Path(doc.file_path).read_bytes()
            pages = read_document(data, doc.file_name or "", max_pages=settings.max_knowledge_pages)
            publish_pages(db, doc, pages)
        except IngestError as exc:
            doc.status, doc.status_reason = "failed", str(exc)[:300]
        except Exception:  # noqa: BLE001 - anything unexpected must still end the Processing state
            doc.status, doc.status_reason = "failed", "Something went wrong reading this file."
        db.commit()


def embed_document(factory: sessionmaker[Session], document_id: uuid.UUID) -> None:
    """Background step: give a ready document's passages their meaning-based search data.
    Failure is fine: the passages stay searchable by keywords and `embed_missing` can try again."""
    with factory() as db:
        doc = db.get(KnowledgeDocument, document_id)
        if doc is None or doc.status != "ready":
            return
        passages = list(db.scalars(select(LegalSource).where(LegalSource.document_id == doc.id)))
        embed_passages(db, passages, patient=True)
        db.commit()


def remove_document(db: Session, user: User, doc: KnowledgeDocument) -> None:
    """Erases the document, its passages and its file. Old answers keep their citation label."""
    title, citation, shared = doc.title, doc.citation, doc.owner_id is None
    passage_ids = list(db.scalars(select(LegalSource.id).where(LegalSource.document_id == doc.id)))
    if passage_ids:
        for citation_row in db.scalars(select(AnswerCitation).where(AnswerCitation.source_id.in_(passage_ids))):
            if citation_row.label is None and citation_row.source is not None:
                citation_row.label = citation_row.source.citation_label
            citation_row.source_id = None
        for passage in db.scalars(select(LegalSource).where(LegalSource.replaced_by_id.in_(passage_ids))):
            passage.replaced_by_id = None
        db.flush()
        for passage in db.scalars(select(LegalSource).where(LegalSource.document_id == doc.id)):
            db.delete(passage)
    if doc.file_path:
        shutil.rmtree(Path(doc.file_path).parent, ignore_errors=True)
    db.delete(doc)
    if shared:
        audit.record(db, user, "knowledge.remove", "document", doc.id, title=title, citation=citation)
    db.flush()


def delete_private_documents(db: Session, user: User) -> None:
    """Used when an account is deactivated: the person's own notes go with them."""
    for doc in list(db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.owner_id == user.id))):
        remove_document(db, user, doc)


def ensure_documents(db: Session) -> int:
    """Gives every passage without a document one (used for the bundled sample corpus)."""
    created = 0
    for source in db.scalars(select(LegalSource).where(LegalSource.document_id.is_(None))):
        doc = KnowledgeDocument(
            title=source.citation_label[:300],
            citation=source.citation_label,
            kind=source.kind if source.kind in KINDS else "act_section",
            status="ready",
            passage_count=1,
        )
        db.add(doc)
        db.flush()
        source.document_id = doc.id
        _map_details(db, doc)
        created += 1
    return created
