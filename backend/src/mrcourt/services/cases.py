"""Case queries, derived status and mutations. Visibility always comes from services.access."""

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from mrcourt.db.base import utcnow
from mrcourt.models import Case, Hearing, Party, User
from mrcourt.schemas.cases import CaseInput, CaseSummary
from mrcourt.services.access import visible_cases

SOON_DAYS = 7


def aware(value: datetime) -> datetime:
    """Some databases return naive datetimes; they are always UTC here."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def next_hearing(case: Case, now: datetime | None = None) -> Hearing | None:
    now = now or utcnow()
    upcoming = [h for h in case.hearings if aware(h.scheduled_at) >= now]
    return min(upcoming, key=lambda h: aware(h.scheduled_at), default=None)


def derived_status(case: Case, now: datetime | None = None) -> str:
    """Closed stays closed; otherwise a hearing within a week makes it "hearing_soon"."""
    if case.status == "closed":
        return "closed"
    now = now or utcnow()
    hearing = next_hearing(case, now)
    if hearing and aware(hearing.scheduled_at) <= now + timedelta(days=SOON_DAYS):
        return "hearing_soon"
    return "active"


def summarize(case: Case, now: datetime | None = None) -> CaseSummary:
    hearing = next_hearing(case, now)
    return CaseSummary(
        id=case.id,
        title=case.title,
        cnr_number=case.cnr_number,
        court=case.court,
        status=derived_status(case, now),  # type: ignore[arg-type]
        next_hearing_at=aware(hearing.scheduled_at) if hearing else None,
    )


def list_cases(db: Session, user: User, q: str | None, status_filter: str | None) -> list[CaseSummary]:
    query = visible_cases(user).options(selectinload(Case.hearings), selectinload(Case.parties))
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        party_match = select(Party.case_id).where(Party.name.ilike(like))
        query = query.where(
            or_(
                Case.title.ilike(like),
                Case.cnr_number.ilike(like),
                Case.court.ilike(like),
                Case.id.in_(party_match),
            )
        )
    now = utcnow()
    summaries = [summarize(c, now) for c in db.scalars(query)]
    if status_filter:
        summaries = [s for s in summaries if s.status == status_filter]
    far = datetime.max.replace(tzinfo=UTC)
    summaries.sort(key=lambda s: (s.next_hearing_at is None, s.next_hearing_at or far, s.title))
    return summaries


def create_case(db: Session, owner: User, data: CaseInput) -> Case:
    missing = [f for f in ("title", "cnr_number", "court") if not getattr(data, f)]
    if missing:
        raise HTTPException(422, f"Missing: {', '.join(missing)}")
    case = Case(
        owner_id=owner.id,
        title=data.title,
        cnr_number=data.cnr_number,
        court=data.court,
        status=data.status or "active",
        stage=data.stage,
        room=data.court_room,
        notes=data.notes,
    )
    case.parties = [Party(**p.model_dump()) for p in data.parties or []]
    db.add(case)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "You already have a case with this CNR number"
        ) from None
    return case


def update_case(db: Session, case: Case, data: CaseInput) -> Case:
    for field in ("title", "cnr_number", "court", "status", "stage", "notes"):
        value = getattr(data, field)
        if value is not None:
            setattr(case, field, value)
    if data.court_room is not None:
        case.room = data.court_room
    if data.parties is not None:
        case.parties = [Party(**p.model_dump()) for p in data.parties]
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "You already have a case with this CNR number"
        ) from None
    return case
