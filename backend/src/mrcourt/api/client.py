"""Endpoints for clients (petitioners). They never return notes, internal documents or other
clients' data; see services/client_view.py."""

import uuid

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from mrcourt.api.deps import Client, DbSession
from mrcourt.db.base import utcnow
from mrcourt.models import ClientUpdate, Document
from mrcourt.schemas.client import AskLawyerIn, ClientCase, ClientDashboard, ClientQuestionOut, UpdatesList
from mrcourt.services import client_questions, client_view
from mrcourt.services import documents as document_service
from mrcourt.services.access import get_client_case

router = APIRouter(prefix="/client", tags=["client"])


@router.get("/dashboard", response_model=ClientDashboard)
def dashboard(user: Client, db: DbSession) -> ClientDashboard:
    return client_view.dashboard(db, user)


@router.get("/cases/{case_id}", response_model=ClientCase)
def case(case_id: uuid.UUID, user: Client, db: DbSession) -> ClientCase:
    return client_view.case_detail(db, user, get_client_case(db, user, case_id))


@router.get("/cases/{case_id}/documents/{document_id}/download")
def download(case_id: uuid.UUID, document_id: uuid.UUID, user: Client, db: DbSession) -> FileResponse:
    case = get_client_case(db, user, case_id)
    document = db.scalars(
        select(Document).where(
            Document.id == document_id,
            Document.case_id == case.id,
            Document.shared_with_client.is_(True),  # internal documents are indistinguishable from missing
        )
    ).first()
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    path = document_service.path_for(document.storage_key)
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File is not available")
    return FileResponse(path, media_type=document.content_type, filename=document.file_name)


@router.get("/cases/{case_id}/questions", response_model=list[ClientQuestionOut])
def my_questions(case_id: uuid.UUID, user: Client, db: DbSession) -> list[ClientQuestionOut]:
    """Only this client's own questions, never another client's."""
    return client_questions.list_own(db, user, get_client_case(db, user, case_id))


@router.post("/cases/{case_id}/questions", response_model=ClientQuestionOut, status_code=status.HTTP_201_CREATED)
def ask_lawyer(case_id: uuid.UUID, data: AskLawyerIn, user: Client, db: DbSession) -> ClientQuestionOut:
    case = get_client_case(db, user, case_id)
    question = client_questions.ask(db, user, case, data.kind, data.text)
    db.commit()
    return question


@router.post("/questions/{question_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def read_reply(question_id: uuid.UUID, user: Client, db: DbSession) -> Response:
    client_questions.mark_reply_read(db, user, question_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/updates", response_model=UpdatesList)
def updates(user: Client, db: DbSession, unread: bool = False) -> UpdatesList:
    """This client's own updates, newest first. Other clients' updates are never included."""
    query = select(ClientUpdate).where(ClientUpdate.client_id == user.id)
    if unread:
        query = query.where(ClientUpdate.read_at.is_(None))
    rows = db.scalars(query.order_by(ClientUpdate.created_at.desc()).limit(100))
    return UpdatesList(
        unread_count=client_view.unread_count(db, user),
        items=[client_view.update_view(u) for u in rows],
    )


@router.post("/updates/read-all", status_code=status.HTTP_204_NO_CONTENT)
def read_all(user: Client, db: DbSession) -> Response:
    for update in db.scalars(
        select(ClientUpdate).where(ClientUpdate.client_id == user.id, ClientUpdate.read_at.is_(None))
    ):
        update.read_at = utcnow()
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/updates/{update_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def read_one(update_id: uuid.UUID, user: Client, db: DbSession) -> Response:
    update = db.get(ClientUpdate, update_id)
    if update is None or update.client_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    if update.read_at is None:
        update.read_at = utcnow()
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
