"""One-off, repeatable command: gives every passage that lacks meaning-based search data its embedding.

Usage: python -m mrcourt.services.embed_missing [--pace SECONDS] [--limit N]

Safe to run again: passages that already have an embedding from the current model are skipped, and
passages are done in the order they were added. With no embedding key it says so and does nothing.
`--pace` waits that many seconds between requests; use about 60 on a free Voyage account so questions
asked meanwhile still get their share of the per-minute limit.
"""

import argparse
import time

from sqlalchemy import or_, select

from mrcourt.db.base import get_sessionmaker
from mrcourt.models import LegalSource
from mrcourt.services.embeddings import BATCH_CHARS, embed_passages, embedder_name, get_embedder

CHUNK = 48  # passages per request at most (the size limit may make it fewer)


def _todo_query(name: str | None):  # type: ignore[no-untyped-def]
    return (
        select(LegalSource)
        .where(or_(LegalSource.embedding_model.is_(None), LegalSource.embedding_model != name))
        .order_by(LegalSource.created_at, LegalSource.id)
    )


def embed_missing(db, *, pace: float = 0.0, limit: int | None = None, progress=None) -> tuple[int, int]:  # type: ignore[no-untyped-def]
    """Returns (embedded now, still missing)."""
    embedder = get_embedder()
    if embedder is None:
        return 0, 0
    name = embedder_name(embedder)
    todo = list(db.scalars(_todo_query(name)))
    if limit is not None:
        todo = todo[:limit]
    done = 0
    position = 0
    while position < len(todo):
        group, size = [], 0
        while position < len(todo) and len(group) < CHUNK and (not group or size + len(todo[position].text) <= BATCH_CHARS):
            group.append(todo[position])
            size += len(todo[position].text)
            position += 1
        embedded = embed_passages(db, group, patient=True)
        db.commit()
        done += embedded
        if progress:
            progress(done, len(todo))
        if pace and position < len(todo):
            time.sleep(pace)
    return done, len(todo) - done


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pace", type=float, default=0.0, help="seconds to wait between requests")
    parser.add_argument("--limit", type=int, default=None, help="embed at most this many passages")
    args = parser.parse_args()
    if get_embedder() is None:
        raise SystemExit("No embedding service is set up (VOYAGE_API_KEY is empty), so there is nothing to do.")
    with get_sessionmaker()() as db:
        done, missing = embed_missing(
            db, pace=args.pace, limit=args.limit, progress=lambda d, n: print(f"  embedded {d} of {n}", flush=True)
        )
    print(f"Embedded {done} passages; {missing} still missing.")


if __name__ == "__main__":
    main()
