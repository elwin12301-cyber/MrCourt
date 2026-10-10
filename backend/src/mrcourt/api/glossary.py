from fastapi import APIRouter

from mrcourt.api.deps import CurrentUser
from mrcourt.schemas.client import GlossaryTerm
from mrcourt.services.hearing_descriptions import glossary

router = APIRouter(tags=["glossary"])


@router.get("/glossary", response_model=list[GlossaryTerm])
def get_glossary(_: CurrentUser) -> list[GlossaryTerm]:
    return glossary()
