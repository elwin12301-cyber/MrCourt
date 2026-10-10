from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from mrcourt.db.base import utcnow
from mrcourt.models import ActivityEvent, Case, Draft, User
from mrcourt.schemas.cases import ActivityOut, Dashboard
from mrcourt.services.access import visible_cases
from mrcourt.services.cases import SOON_DAYS, aware, summarize


def build(db: Session, user: User) -> Dashboard:
    now = utcnow()
    cases = list(db.scalars(visible_cases(user).options(selectinload(Case.hearings))))
    summaries = [summarize(c, now) for c in cases]

    active = sum(1 for s in summaries if s.status != "closed")
    horizon = now + timedelta(days=SOON_DAYS)
    this_week = sum(
        1
        for c in cases
        if c.status != "closed"
        for h in c.hearings
        if now <= aware(h.scheduled_at) <= horizon
    )
    upcoming = sorted(
        (s for s in summaries if s.next_hearing_at and s.status != "closed"),
        key=lambda s: s.next_hearing_at,  # type: ignore[arg-type,return-value]
    )[:3]

    drafts = 0
    if user.role == "advocate":
        drafts = db.scalar(
            select(func.count())
            .select_from(Draft)
            .where(Draft.author_id == user.id, Draft.ai_generated.is_(True), Draft.reviewed.is_(False))
        ) or 0

    events = db.scalars(
        select(ActivityEvent)
        .where(ActivityEvent.user_id == user.id)
        .order_by(ActivityEvent.created_at.desc())
        .limit(5)
    )
    return Dashboard(
        active_cases=active,
        hearings_this_week=this_week,
        drafts_to_review=drafts,
        upcoming_hearings=upcoming,
        recent_activity=[ActivityOut(message=e.message, created_at=aware(e.created_at)) for e in events],
    )
