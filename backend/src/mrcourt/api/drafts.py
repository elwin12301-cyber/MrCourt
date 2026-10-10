import logging
import uuid

from fastapi import APIRouter, HTTPException, Response, status

from mrcourt.api.deps import Advocate, DbSession
from mrcourt.models import Draft, DraftExport
from mrcourt.schemas.drafts import DraftCreate, DraftOut, DraftSave, ExportRequest
from mrcourt.services import drafting, export
from mrcourt.services.cases import aware
from mrcourt.services.draft_templates import TEMPLATES

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/drafts", tags=["drafts"])

DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _out(draft: Draft) -> DraftOut:
    return DraftOut(
        id=draft.id,
        case_id=draft.case_id,
        template=draft.template,  # type: ignore[arg-type]
        title=draft.title,
        subtitle=TEMPLATES[draft.template].subtitle,
        body=draft.body,
        version=draft.version,
        ai_generated=draft.ai_generated,
        reviewed=draft.reviewed,
        last_edited_at=aware(draft.last_edited_at),
    )


@router.get("", response_model=list[DraftOut])
def list_drafts(user: Advocate, db: DbSession, case_id: uuid.UUID | None = None) -> list[DraftOut]:
    return [_out(d) for d in drafting.list_drafts(db, user, case_id)]


@router.post("", response_model=DraftOut, status_code=status.HTTP_201_CREATED)
def create_draft(data: DraftCreate, user: Advocate, db: DbSession) -> DraftOut:
    draft = drafting.create_draft(db, user, data.template, data.case_id)
    db.commit()
    return _out(draft)


@router.get("/{draft_id}", response_model=DraftOut)
def get_draft(draft_id: uuid.UUID, user: Advocate, db: DbSession) -> DraftOut:
    return _out(drafting.get_own_draft(db, user, draft_id))


@router.put("/{draft_id}", response_model=DraftOut)
def save_draft(draft_id: uuid.UUID, data: DraftSave, user: Advocate, db: DbSession) -> DraftOut:
    draft = drafting.get_own_draft(db, user, draft_id)
    drafting.save_edits(db, draft, data.body)
    db.commit()
    return _out(draft)


@router.post("/{draft_id}/export")
def export_draft(draft_id: uuid.UUID, data: ExportRequest, user: Advocate, db: DbSession) -> Response:
    draft = drafting.get_own_draft(db, user, draft_id)
    try:
        if data.format == "docx":
            content, media = export.to_docx(draft), DOCX_TYPE
        else:
            content, media = export.to_pdf(draft), "application/pdf"
    except Exception:
        logger.exception("Draft export failed")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Export failed") from None
    db.add(DraftExport(draft_id=draft.id, format=data.format, requested_by=user.id))
    db.commit()
    filename = export.safe_filename(draft.title, data.format)
    return Response(
        content,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
