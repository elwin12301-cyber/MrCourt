"""Accuracy of document details mapping (feature 008, SC-001 and SC-002).

1. On the FICTIONAL test documents (tests/data/metadata/samples.json): for every expected field, is the mapped
   value right, and what share of fields marked "found" are correct (target 90%+, and nothing invented).
2. On the database: how many statute passages carry a section number, and how many documents are unreadable.

    python scripts/check_metadata.py            (uses DATABASE_URL for part 2)
"""

import json
from pathlib import Path

from sqlalchemy import func, select

from mrcourt.db.base import get_sessionmaker
from mrcourt.models import KnowledgeDocument, LegalSource
from mrcourt.services.metadata import extract

SAMPLES = Path(__file__).resolve().parents[1] / "tests" / "data" / "metadata" / "samples.json"


def main() -> None:
    documents = json.loads(SAMPLES.read_text(encoding="utf-8"))["documents"]
    right = wrong = found_right = found_total = 0
    for doc in documents:
        fields = extract(doc["title"], doc["pages"], doc["kind"])
        for name, (want, want_conf) in doc["expected"].items():
            if name == "page_sections":
                continue
            key = "case_numbers" if name == "case_number" else name
            value = fields[key]["value"]
            if name == "case_number":
                value = value[0] if value else None
            ok = value == want and fields[key]["confidence"] == want_conf
            right, wrong = right + ok, wrong + (not ok)
            if fields[key]["confidence"] == "found" and value not in (None, [], {}):
                found_total += 1
                found_right += value == want
            print(f"  {'ok ' if ok else 'BAD'} {doc['id']:18} {name:12} {value!r}")
    print(f"\nFictional set: {right}/{right + wrong} expected fields right; "
          f"'found' fields correct: {found_right}/{found_total} ({100 * found_right / max(found_total, 1):.0f}%)")

    with get_sessionmaker()() as db:
        statute_docs = select(KnowledgeDocument.id).where(KnowledgeDocument.doc_type == "statute")
        total = db.scalar(select(func.count()).select_from(LegalSource).where(LegalSource.document_id.in_(statute_docs)))
        with_sections = db.scalar(
            select(func.count()).select_from(LegalSource)
            .where(LegalSource.document_id.in_(statute_docs), LegalSource.sections.is_not(None))
        )
        unreadable = db.scalar(select(func.count()).select_from(KnowledgeDocument).where(KnowledgeDocument.text_quality == "unreadable"))
        print(f"Database: {with_sections} of {total} statute passages carry section numbers; {unreadable} documents unreadable (need OCR)")


if __name__ == "__main__":
    main()
