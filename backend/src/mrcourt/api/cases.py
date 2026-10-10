import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse

from mrcourt.api.deps import Advocate, CurrentUser, DbSession
from mrcourt.models import Case, Document
from mrcourt.schemas.cases import (
    CaseDetail,
    CaseInput,
    CaseSummary,
    DocumentOut,
    HearingInput,
    HearingOut,
    HearingPatch,
    InvitationIn,
    InvitationOut,
    PartyIO,
)
from mrcourt.services import cases as case_service
from mrcourt.services import documents as document_service
from mrcourt.services import hearings as hearing_service
from mrcourt.services import invitations as invitation_service
from mrcourt.services.access import get_owned_case, get_visible_case

router = APIRouter(tags=["cases"])


def _detail(case: Case, user_role: str) -> CaseDetail:
    summary = case_service.summarize(case)
    return CaseDetail(
        **summary.model_dump(),
        stage=case.stage,
        court_room=case.room,
        parties=[PartyIO.model_validate(p) for p in case.parties],
        documents=[DocumentOut.model_validate(d) for d in case.documents],
        hearings=[HearingOut.model_validate(h) for h in case.hearings],
        # An advocate's private notes are never shared with petitioners.
        notes=case.notes if user_role == "advocate" else None,
        client_status=case.client_status,
        client_status_changed_at=case.client_status_changed_at,
    )


@router.get("/cases", response_model=list[CaseSummary])
def list_cases(
    user: Advocate,
    db: DbSession,
    q: str | None = None,
    status_filter: Annotated[
        Literal["active", "hearing_soon", "closed"] | None, Query(alias="status")
    ] = None,
) -> list[CaseSummary]:
    return case_service.list_cases(db, user, q, status_filter)


@router.post("/cases", response_model=CaseDetail, status_code=status.HTTP_201_CREATED)
def create_case(data: CaseInput, user: Advocate, db: DbSession) -> CaseDetail:
    case = case_service.create_case(db, user, data)
    db.commit()
    return _detail(case, user.role)


@router.get("/cases/{case_id}", response_model=CaseDetail)
def get_case(case_id: uuid.UUID, user: Advocate, db: DbSession) -> CaseDetail:
    return _detail(get_visible_case(db, user, case_id), user.role)


@router.patch("/cases/{case_id}", response_model=CaseDetail)
def patch_case(case_id: uuid.UUID, data: CaseInput, user: CurrentUser, db: DbSession) -> CaseDetail:
    case = get_owned_case(db, user, case_id)
    case_service.update_case(db, case, data)
    db.commit()
    return _detail(case, user.role)


@router.get("/cases/{case_id}/hearings", response_model=list[HearingOut])
def list_hearings(case_id: uuid.UUID, user: Advocate, db: DbSession) -> list[HearingOut]:
    case = get_visible_case(db, user, case_id)
    return [HearingOut.model_validate(h) for h in case.hearings]


@router.post(
    "/cases/{case_id}/hearings", response_model=HearingOut, status_code=status.HTTP_201_CREATED
)
def add_hearing(case_id: uuid.UUID, data: HearingInput, user: CurrentUser, db: DbSession) -> HearingOut:
    case = get_owned_case(db, user, case_id)
    hearing = hearing_service.add_hearing(db, case, data, user.id)
    db.commit()
    return HearingOut.model_validate(hearing)


@router.patch("/cases/{case_id}/hearings/{hearing_id}", response_model=HearingOut)
def reschedule_hearing(
    case_id: uuid.UUID, hearing_id: uuid.UUID, data: HearingPatch, user: CurrentUser, db: DbSession
) -> HearingOut:
    case = get_owned_case(db, user, case_id)
    hearing = hearing_service.reschedule(db, case, hearing_id, data, user.id)
    db.commit()
    return HearingOut.model_validate(hearing)


@router.get("/cases/{case_id}/documents", response_model=list[DocumentOut])
def list_documents(case_id: uuid.UUID, user: Advocate, db: DbSession) -> list[DocumentOut]:
    case = get_visible_case(db, user, case_id)
    return [DocumentOut.model_validate(d) for d in case.documents]


@router.post(
    "/cases/{case_id}/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED
)
def upload_document(
    case_id: uuid.UUID, user: CurrentUser, db: DbSession, file: Annotated[UploadFile, File()]
) -> DocumentOut:
    case = get_owned_case(db, user, case_id)
    name, key, size, content_type = document_service.save(case.id, file)
    document = Document(
        case_id=case.id,
        file_name=name,
        size_bytes=size,
        content_type=content_type,
        storage_key=key,
        uploaded_by=user.id,
    )
    db.add(document)
    db.commit()
    return DocumentOut.model_validate(document)


@router.get("/cases/{case_id}/documents/{document_id}/download")
def download_document(
    case_id: uuid.UUID, document_id: uuid.UUID, user: Advocate, db: DbSession
) -> FileResponse:
    case = get_visible_case(db, user, case_id)
    document = db.get(Document, document_id)
    if document is None or document.case_id != case.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    path = document_service.path_for(document.storage_key)
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File is not available")
    return FileResponse(path, media_type=document.content_type, filename=document.file_name)


@router.post(
    "/cases/{case_id}/invitations", response_model=InvitationOut, status_code=status.HTTP_201_CREATED
)
def invite(case_id: uuid.UUID, data: InvitationIn, user: CurrentUser, db: DbSession) -> InvitationOut:
    case = get_owned_case(db, user, case_id)
    invitation = invitation_service.invite(db, case, user, data.contact)
    db.commit()
    return InvitationOut(
        id=invitation.id, case_id=case.id, case_title=case.title, status=invitation.status
    )


@router.delete("/cases/{case_id}/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_invitation(
    case_id: uuid.UUID, invitation_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> Response:
    case = get_owned_case(db, user, case_id)
    invitation_service.remove(db, case, invitation_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/invitations", response_model=list[InvitationOut])
def my_invitations(user: CurrentUser, db: DbSession) -> list[InvitationOut]:
    return [
        InvitationOut(id=inv.id, case_id=inv.case_id, case_title=title, status=inv.status)
        for inv, title in invitation_service.pending_for(db, user)
    ]


@router.post("/invitations/{invitation_id}/accept", response_model=InvitationOut)
def accept_invitation(invitation_id: uuid.UUID, user: CurrentUser, db: DbSession) -> InvitationOut:
    invitation = invitation_service.accept(db, user, invitation_id)
    case = db.get(Case, invitation.case_id)
    assert case is not None
    db.commit()
    return InvitationOut(
        id=invitation.id, case_id=case.id, case_title=case.title, status=invitation.status
    )
