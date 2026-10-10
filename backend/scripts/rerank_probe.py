"""Probe: do Voyage reranker scores separate relevant questions from unrelated ones?

Not part of the app. Loads the reference documents from a folder outside the repository, takes the
top meaning-based passages for each question (from the on-disk vector cache made by
import_reference.py), reranks them, and prints the best relevance score per question.
"""

import hashlib
import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import import_reference as ir  # noqa: E402
import voyageai  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import mrcourt.models  # noqa: E402,F401
from mrcourt.config import get_settings  # noqa: E402
from mrcourt.db.base import Base  # noqa: E402
from mrcourt.models import KnowledgeDocument, LegalSource  # noqa: E402
from mrcourt.services import embeddings  # noqa: E402
from mrcourt.services.ingest import read_pages  # noqa: E402
from mrcourt.services.knowledge import publish_pages  # noqa: E402

MODEL = sys.argv[1] if len(sys.argv) > 1 else "rerank-2.5"
LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else 12
cache = json.loads((Path(tempfile.gettempdir()) / "mrcourt-embed-cache.json").read_text())


def key(text: str, input_type: str) -> str:
    return hashlib.sha256(f"voyage-3.5|{input_type}|{text}".encode()).hexdigest()


engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Base.metadata.create_all(engine)
db = sessionmaker(bind=engine, expire_on_commit=False)()
source = Path(r"D:\ClaudeTraning\Domains\RAG\docs")
for name in ir.DEFAULT_DOCUMENTS:
    doc = KnowledgeDocument(title=name, citation=Path(name).stem, kind="judgment", status="processing")
    db.add(doc)
    db.flush()
    publish_pages(db, doc, read_pages((source / name).read_bytes(), name, max_pages=300))
db.commit()
passages = list(db.scalars(select(LegalSource)))
vectors = {p.id: cache[key(f"{p.citation_label}\n{p.text}"[:6000], "document")] for p in passages}
client = voyageai.Client(api_key=get_settings().voyage_api_key, max_retries=0, timeout=30)


def best_score(question: str) -> tuple[float, int | None]:
    qv = cache[key(question, "query")]
    top = sorted(passages, key=lambda p: -embeddings.cosine(qv, vectors[p.id]))[:5]
    while True:
        try:
            result = client.rerank(question, [p.text for p in top], model=MODEL, top_k=1)
            hit = result.results[0]
            return hit.relevance_score, top[hit.index].page
        except voyageai.error.RateLimitError:
            time.sleep(21)


questions = ir.parse_questions(Path(r"D:\ClaudeTraning\Domains\RAG\SA_1106_2019_Lawyer_Questions.txt").read_text(encoding="utf-8"))
relevant = []
for number, question, _answer, pages in questions[:LIMIT]:
    score, page = best_score(question)
    relevant.append(score)
    print(f"relevant  {score:.2f}  page {page} (expected {sorted(pages)})  {question[:60]}", flush=True)
unrelated = []
for question in ir.UNRELATED:
    if key(question, "query") in cache:
        score, page = best_score(question)
        unrelated.append(score)
        print(f"unrelated {score:.2f}  {question[:60]}", flush=True)
print(f"relevant: min {min(relevant):.2f} median {statistics.median(relevant):.2f}; unrelated: max {max(unrelated):.2f}", flush=True)
