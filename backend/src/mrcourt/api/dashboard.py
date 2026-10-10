from fastapi import APIRouter

from mrcourt.api.deps import Advocate, DbSession
from mrcourt.schemas.cases import Dashboard
from mrcourt.services import dashboard as dashboard_service

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=Dashboard)
def get_dashboard(user: Advocate, db: DbSession) -> Dashboard:
    return dashboard_service.build(db, user)
