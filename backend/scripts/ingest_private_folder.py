"""Adds a folder of case documents (PDF, text, images) as PRIVATE knowledge of one advocate.

Only that advocate (and the assistant when answering them) can search these documents; clients and other
advocates cannot. Use this for real case papers, never the shared-sources script. Larger files than the
web upload allows are accepted here. Safe to run again: a title that already exists is skipped.

    DATABASE_URL=sqlite:///./dev.db python scripts/ingest_private_folder.py --folder ../docs --advocate rohan
"""

import argparse
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select

from mrcourt.config import get_settings
from mrcourt.db.base import get_sessionmaker
from mrcourt.models import KnowledgeDocument, User
from mrcourt.services.knowledge import create_document, embed_document, process_document

TYPES = (".pdf", ".txt", ".md", ".png", ".jpg", ".jpeg", ".tif", ".tiff")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", type=Path, required=True)
    parser.add_argument("--advocate", default="rohan", help="username of the advocate who owns these documents")
    parser.add_argument("--no-embed", action="store_true", help="keyword search only; do not send text to Voyage")
    args = parser.parse_args()

    settings = get_settings()
    settings.max_knowledge_bytes = 200 * 1024 * 1024  # this script only: local files may be large
    factory = get_sessionmaker()
    files = sorted(p for p in args.folder.iterdir() if p.suffix.lower() in TYPES)
    with factory() as db:
        advocate = db.scalars(select(User).where(User.username == args.advocate.lower())).first()
        if advocate is None or advocate.role != "advocate":
            raise SystemExit(f"No advocate with the username {args.advocate!r}.")
        advocate_id = advocate.id

    for path in files:
        title = path.stem.replace("_", " ").strip()
        with factory() as db:
            advocate = db.get(User, advocate_id)
            try:
                doc = create_document(
                    db, advocate, title=title, citation=path.name, kind=None, text=None,
                    file_name=path.name, data=path.read_bytes(),
                )
            except HTTPException as exc:
                print(f"skipped  {path.name}: {exc.detail}")
                continue
            db.commit()
            doc_id = doc.id
        process_document(factory, doc_id)
        with factory() as db:
            doc = db.get(KnowledgeDocument, doc_id)
            print(f"{doc.status:8} {path.name}" + (f": {doc.status_reason}" if doc.status_reason else ""))
            ready = doc.status == "ready"
        if ready and not args.no_embed:
            embed_document(factory, doc_id)


if __name__ == "__main__":
    main()
