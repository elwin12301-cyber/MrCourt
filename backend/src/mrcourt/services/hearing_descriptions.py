"""General descriptions of what usually happens at a kind of hearing (spec FR-003, FR-021).

The text comes from a reviewed content file, never from a model, so it cannot state facts about a
particular case, predict an outcome or give advice. A description is chosen from the hearing's
recorded purpose, then from the case stage. If neither matches, there is no description and the
client sees only the date, time and court. While the content is marked UNVERIFIED it is switched
off in production.
"""

import json
import re
from functools import lru_cache
from pathlib import Path

from mrcourt.config import get_settings
from mrcourt.schemas.client import GlossaryTerm, HearingDescription

DATA_DIR = Path(__file__).resolve().parent.parent / "corpus" / "data"
CONTENT_PATH = DATA_DIR / "hearing_descriptions.json"
GLOSSARY_PATH = DATA_DIR / "glossary.json"


@lru_cache
def load_content() -> dict[str, object]:
    return json.loads(CONTENT_PATH.read_text(encoding="utf-8"))


def content_allowed(review_status: str) -> bool:
    """Unreviewed content may be used while developing, but never in production."""
    unverified = "UNVERIFIED" in review_status
    return not (unverified and get_settings().environment == "production")


def _matches(text: str | None, keywords: list[str]) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(re.search(rf"\b{re.escape(k)}", lowered) for k in keywords)


def describe(purpose: str | None, stage: str | None) -> HearingDescription | None:
    content = load_content()
    if not content_allowed(str(content.get("review_status", ""))):
        return None
    kinds: list[dict[str, object]] = content["kinds"]  # type: ignore[assignment]
    for field in (purpose, stage):  # the hearing's own purpose wins over the case stage
        for kind in kinds:
            if _matches(field, kind["keywords"]):  # type: ignore[arg-type]
                return HearingDescription(text=str(kind["text"]))
    return None


def glossary() -> list[GlossaryTerm]:
    data = json.loads(GLOSSARY_PATH.read_text(encoding="utf-8"))
    if not content_allowed(str(data.get("review_status", ""))):
        return []
    return [GlossaryTerm(**t) for t in data["terms"]]
