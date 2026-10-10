import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from mrcourt.models import Case, Hearing
from mrcourt.schemas.cases import HearingInput, HearingPatch
from mrcourt.services import client_status, reminders
from mrcourt.services.cases import aware


def add_hearing(db: Session, case: Case, data: HearingInput, advocate_id: uuid.UUID) -> Hearing:
    hearing = Hearing(case_id=case.id, **data.model_dump())
    db.add(hearing)
    db.flush()
    # Clients are always told about hearing dates (no sharing choice involved).
    client_status.hearing_scheduled(db, case, advocate_id, hearing)
    return hearing


def reschedule(
    db: Session, case: Case, hearing_id: uuid.UUID, data: HearingPatch, advocate_id: uuid.UUID
) -> Hearing:
    hearing = db.get(Hearing, hearing_id)
    if hearing is None or hearing.case_id != case.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    old = aware(hearing.scheduled_at)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(hearing, field, value)
    db.flush()
    if aware(hearing.scheduled_at) != old:
        reminders.forget_reminders(db, hearing)
        client_status.hearing_rescheduled(db, case, advocate_id, hearing, old)
    return hearing
