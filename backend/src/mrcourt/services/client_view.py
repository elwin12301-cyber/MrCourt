"""The client's view of a case. This is the ONLY read path used for clients.

Everything a client can see is listed here by hand (an allow-list). Notes, internal documents,
unshared outcomes, other clients and internal identifiers are not fetched at all, so a new private
field added to a case later cannot reach a client by default.
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from mrcourt.db.base import utcnow
from mrcourt.models import (
    Case,
    CaseInvitation,
    ClientUpdate,
    Document,
    Hearing,
    TimelineEntry,
    User,
)
from mrcourt.schemas.client import (
    AccessInfo,
    ClientCase,
    ClientCaseSummary,
    ClientDashboard,
    ClientUpdateOut,
    DocumentForClient,
    HearingForClient,
    Lawyer,
    TimelineEntryForClient,
)
from mrcourt.services.access import visible_cases
from mrcourt.services.cases import aware, next_hearing
from mrcourt.services.hearing_descriptions import describe

LATEST_UPDATES = 5


def lawyer_card(db: Session, case: Case) -> Lawyer:
    owner = db.get(User, case.owner_id)
    if owner is None or owner.status != "active":
        return Lawyer(name="Your lawyer", verification_status="none", available=False)
    contact = (owner.settings.client_contact if owner.settings else None) or {}
    return Lawyer(
        name=owner.full_name,
        verification_status=owner.verification_status,  # type: ignore[arg-type]
        phone=contact.get("phone") or None,
        email=contact.get("email") or None,
        office=contact.get("office") or None,
        available=True,
    )


def hearing_view(case: Case, hearing: Hearing) -> HearingForClient:
    return HearingForClient(
        id=hearing.id,
        scheduled_at=aware(hearing.scheduled_at),
        court=case.court,
        description=describe(hearing.purpose, case.stage),
        # A recorded outcome is shown only when the advocate has shared it.
        outcome=hearing.outcome if hearing.outcome_shared and hearing.outcome else None,
    )


def case_summary(db: Session, case: Case, now: datetime) -> ClientCaseSummary:
    upcoming = next_hearing(case, now)
    return ClientCaseSummary(
        id=case.id,
        title=case.title,
        court=case.court,
        status=case.client_status,  # type: ignore[arg-type]
        status_changed_at=aware(case.client_status_changed_at) if case.client_status_changed_at else None,
        next_hearing=hearing_view(case, upcoming) if upcoming else None,
        lawyer=lawyer_card(db, case),
    )


def update_view(update: ClientUpdate) -> ClientUpdateOut:
    return ClientUpdateOut(
        id=update.id,
        case_id=update.case_id,
        kind=update.kind,
        message=update.message,
        created_at=aware(update.created_at),
        read=update.read_at is not None,
    )


def unread_count(db: Session, user: User) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(ClientUpdate)
            .where(ClientUpdate.client_id == user.id, ClientUpdate.read_at.is_(None))
        )
        or 0
    )


def dashboard(db: Session, user: User) -> ClientDashboard:
    now = utcnow()
    cases = list(db.scalars(visible_cases(user).options(selectinload(Case.hearings))))
    summaries = [case_summary(db, c, now) for c in cases]
    far = datetime.max.replace(tzinfo=now.tzinfo)
    # Open cases first, soonest hearing first.
    summaries.sort(key=lambda s: (s.status == "closed", s.next_hearing.scheduled_at if s.next_hearing else far, s.title))
    latest = db.scalars(
        select(ClientUpdate)
        .where(ClientUpdate.client_id == user.id)
        .order_by(ClientUpdate.created_at.desc())
        .limit(LATEST_UPDATES)
    )
    return ClientDashboard(
        cases=summaries,
        unread_updates=unread_count(db, user),
        latest_updates=[update_view(u) for u in latest],
    )


def case_detail(db: Session, user: User, case: Case) -> ClientCase:
    now = utcnow()
    summary = case_summary(db, case, now)

    hearings = sorted(case.hearings, key=lambda h: aware(h.scheduled_at))
    timeline = db.scalars(
        select(TimelineEntry)
        .where(TimelineEntry.case_id == case.id, TimelineEntry.shared_with_client.is_(True))
        .order_by(TimelineEntry.occurred_at.desc())
    )
    documents = db.scalars(
        select(Document).where(Document.case_id == case.id, Document.shared_with_client.is_(True))
    )

    mine = db.scalars(
        select(CaseInvitation).where(
            CaseInvitation.case_id == case.id,
            CaseInvitation.invitee_user_id == user.id,
            CaseInvitation.status == "accepted",
        )
    ).first()
    accepted = (
        db.scalar(
            select(func.count())
            .select_from(CaseInvitation)
            .where(CaseInvitation.case_id == case.id, CaseInvitation.status == "accepted")
        )
        or 0
    )
    return ClientCase(
        **summary.model_dump(),
        hearings=[hearing_view(case, h) for h in hearings],
        timeline=[
            TimelineEntryForClient(id=e.id, kind=e.kind, text=e.text, occurred_at=aware(e.occurred_at))
            for e in timeline
        ],
        documents=[
            DocumentForClient(id=d.id, file_name=d.file_name, size_bytes=d.size_bytes) for d in documents
        ],
        access=AccessInfo(
            advocate_name=summary.lawyer.name,
            since=aware(mine.accepted_at) if mine and mine.accepted_at else None,
            other_people_with_access=max(accepted - 1, 0),  # a count only; names are never shown
        ),
    )
