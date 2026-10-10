"""Loads Acts and judgments into `legal_sources`.

Usage: mrcourt-ingest [path ...]   (defaults to the bundled development sample)

Files are JSON: {"review_status": "...", "sources": [{key, kind, instrument, section,
citation_label, text, source_url, effective_status?, replaced_by?}]}. Re-running is safe:
entries are matched on citation_label and updated in place.
"""

import json
import sys
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from mrcourt.config import get_settings
from mrcourt.db.base import get_sessionmaker
from mrcourt.models import LegalSource
from mrcourt.services.embeddings import embed_passages, embed_text
from mrcourt.services.knowledge import ensure_documents

SAMPLE_DIR = Path(__file__).parent / "data" / "sample"


def ingest_file(db: Session, path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    review = str(data.get("review_status", ""))
    if "UNVERIFIED" in review and get_settings().environment == "production":
        raise SystemExit(f"Refusing to load unverified corpus file in production: {path.name}")

    by_key: dict[str, LegalSource] = {}
    entries = data["sources"]
    for entry in entries:
        source = db.scalars(
            select(LegalSource).where(LegalSource.citation_label == entry["citation_label"])
        ).first()
        if source is None:
            source = LegalSource(citation_label=entry["citation_label"])
            db.add(source)
        source.kind = entry["kind"]
        source.instrument = entry["instrument"]
        source.section = entry.get("section")
        source.text = entry["text"]
        source.source_url = entry.get("source_url")
        source.effective_status = entry.get("effective_status", "in_force")
        source.embedding = embed_text(f"{entry['citation_label']}. {entry['text']}")
        by_key[entry["key"]] = source
    db.flush()

    for entry in entries:  # second pass: link repealed provisions to their replacements
        target = entry.get("replaced_by")
        if target:
            by_key[entry["key"]].replaced_by_id = by_key[target].id
    db.flush()
    ensure_documents(db)  # people manage documents, so every passage belongs to one
    embed_passages(db, list(by_key.values()), patient=True)  # no-op without an embedding service
    return len(entries)


def load_sample_corpus(db: Session) -> int:
    return sum(ingest_file(db, path) for path in sorted(SAMPLE_DIR.glob("*.json")))


def main() -> None:
    paths = [Path(p) for p in sys.argv[1:]] or sorted(SAMPLE_DIR.glob("*.json"))
    session = get_sessionmaker()()
    try:
        total = sum(ingest_file(session, path) for path in paths)
        if session.get_bind().dialect.name == "postgresql":
            session.execute(text("ANALYZE legal_sources"))
        session.commit()
        print(f"Ingested {total} passages from {len(paths)} file(s).")
    finally:
        session.close()


if __name__ == "__main__":
    main()
