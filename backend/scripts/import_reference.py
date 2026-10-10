"""Measures how well retrieval finds the right passage for a set of reference questions.

It reads court documents and a question file from a folder on this machine (nothing is copied
into the repository), loads the readable documents into a throw-away in-memory database as shared
sources, asks every question, and reports whether the expected page and the facts of the expected
answer were found: first with keyword search alone, then with meaning-based search added (when an
embedding key is set). It also prints the similarity range for relevant and unrelated questions,
which is what `MIN_VECTOR_SCORE` is chosen from. Vectors are cached on disk, outside the
repository, so repeat runs cost nothing and stay within free-tier limits.

Usage (from the backend folder):
    python scripts/import_reference.py ^
        --source D:\\ClaudeTraning\\Domains\\RAG\\docs ^
        --questions D:\\ClaudeTraning\\Domains\\RAG\\SA_1106_2019_Lawyer_Questions.txt

A question counts as found when one of the top passages is on an expected page AND those passages
contain at least half of the significant words of the expected answer.
"""

import argparse
import hashlib
import json
import re
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import mrcourt.models  # noqa: E402,F401
from mrcourt.config import get_settings  # noqa: E402
from mrcourt.db.base import Base  # noqa: E402
from mrcourt.models import KnowledgeDocument, LegalSource  # noqa: E402
from mrcourt.services import embeddings, rerank  # noqa: E402
from mrcourt.services.ingest import IngestError, read_pages  # noqa: E402
from mrcourt.services.knowledge import publish_pages  # noqa: E402
from mrcourt.services.retrieval import search, significant_terms, stem  # noqa: E402

DEFAULT_SOURCE = Path(r"D:\ClaudeTraning\Domains\RAG\docs")
DEFAULT_DOCUMENTS = ["judgement.pdf", "WP 11944-2013 _ Order.pdf"]
TOP = 5
COVERAGE = 0.5

UNRELATED = [
    "What is the capital of France?",
    "How do I bake a chocolate cake?",
    "Can you recommend a good restaurant near Saket court?",
    "How do I register a trademark in India?",
    "What is the weather in Chennai today?",
    "Explain Newton's third law in simple words.",
    "Who won the cricket world cup in 2011?",
    "What is the best laptop for students?",
]

_BLOCK = re.compile(r"^Q(\d+)\.\s+(.*?)(?=^Q\d+\.|^={5,}|\Z)", re.DOTALL | re.MULTILINE)
_PAGES = re.compile(r"\[([\d,\s\-]+)\]\s*$")


def parse_questions(text: str) -> list[tuple[int, str, str, set[int]]]:
    """[(number, question, expected answer, expected pages)] from a `Qn. ...  A: ... [page]` file."""
    found = []
    for number, body in _BLOCK.findall(text):
        question, _, answer = body.partition("\nA:")
        if not answer.strip():
            continue
        answer = " ".join(answer.split())
        pages: set[int] = set()
        match = _PAGES.search(answer)
        if match:
            for part in match.group(1).split(","):
                part = part.strip()
                if "-" in part:
                    low, high = part.split("-", 1)
                    pages.update(range(int(low), int(high) + 1))
                elif part.isdigit():
                    pages.add(int(part))
            answer = answer[: match.start()].strip()
        found.append((int(number), " ".join(question.split()), answer, pages))
    return found


class CachedEmbedder:
    """Wraps the real embedder and remembers every vector on disk."""

    def __init__(self, inner: embeddings.Embedder, path: Path) -> None:
        self.inner, self.path, self.name = inner, path, inner.name
        self.cache: dict[str, list[float]] = json.loads(path.read_text()) if path.exists() else {}
        self.fetched = 0

    def _key(self, text: str, input_type: str) -> str:
        return hashlib.sha256(f"{self.name}|{input_type}|{text}".encode()).hexdigest()

    def embed(self, texts: list[str], input_type: embeddings.InputType, *, patient: bool = False) -> list[list[float]]:
        missing = [t for t in texts if self._key(t, input_type) not in self.cache]
        if missing:
            vectors = self.inner.embed(missing, input_type, patient=True)
            for text, vector in zip(missing, vectors, strict=True):
                self.cache[self._key(text, input_type)] = vector
            self.fetched += len(missing)
            self.path.write_text(json.dumps(self.cache))
        return [self.cache[self._key(t, input_type)] for t in texts]


class CachedReranker:
    """The real reranker, patient about rate limits, with every result remembered on disk."""

    def __init__(self, api_key: str, model: str, path: Path) -> None:
        import voyageai

        self._voyageai = voyageai
        self._client = voyageai.Client(api_key=api_key, max_retries=0, timeout=30)
        self.name, self.path = model, path
        self.cache: dict[str, list[float]] = json.loads(path.read_text()) if path.exists() else {}
        self.fetched = 0
        self.best: dict[str, float] = {}  # the best score each question got, for calibration

    def score(self, question: str, texts: list[str]) -> list[float]:
        key = hashlib.sha256(f"{self.name}|{question}|{'|'.join(texts)}".encode()).hexdigest()
        if key not in self.cache:
            while True:
                try:
                    result = self._client.rerank(question, texts, model=self.name)
                    break
                except self._voyageai.error.RateLimitError:
                    time.sleep(21)
            scores = [0.0] * len(texts)
            for item in result.results:
                scores[item.index] = float(item.relevance_score)
            self.cache[key] = scores
            self.fetched += 1
            self.path.write_text(json.dumps(self.cache))
        scores = self.cache[key]
        self.best[question] = max(scores, default=0.0)
        return scores


def score_run(db, questions, label: str) -> tuple[int, list]:  # type: ignore[no-untyped-def]
    page_hits = answer_hits = both = 0
    misses = []
    for number, question, answer, pages in questions:
        found = search(db, question, None, limit=TOP, min_score=0.2)
        hits = found.hits
        have = {stem(w) for h in hits for w in re.findall(r"[a-z0-9]+", h.source.text.lower())}
        wanted = significant_terms(answer)
        coverage = (sum(1 for t in wanted if t in have) / len(wanted)) if wanted else 1.0
        on_page = bool(pages) and any(h.source.page in pages for h in hits)
        page_hits += on_page
        answer_hits += coverage >= COVERAGE
        if on_page and coverage >= COVERAGE:
            both += 1
        else:
            misses.append((number, question, sorted(pages), round(coverage, 2), [h.source.page for h in hits]))
    total = len(questions)
    print(f"\n{label}: {total} questions, top {TOP} passages each")
    print(f"  right page found      : {page_hits}/{total} ({100 * page_hits / total:.0f}%)")
    print(f"  answer facts found    : {answer_hits}/{total} ({100 * answer_hits / total:.0f}%)")
    print(f"  found (page and facts): {both}/{total} ({100 * both / total:.0f}%)")
    return both, misses


def best_similarity(db, embedder, text: str) -> float:  # type: ignore[no-untyped-def]
    vector = embedder.embed([text], "query")[0]
    return max(
        (embeddings.cosine(vector, s.embedding) for s in db.scalars(select(LegalSource)) if s.embedding is not None),
        default=0.0,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="folder with the court documents")
    parser.add_argument("--questions", type=Path, required=True, help="question file (Qn. ... A: ... [page])")
    parser.add_argument("--documents", nargs="+", default=DEFAULT_DOCUMENTS, help="files to load; the first is the one the questions are about")
    parser.add_argument("--cache", type=Path, default=Path(tempfile.gettempdir()) / "mrcourt-embed-cache.json")
    args = parser.parse_args()

    if ROOT in args.source.resolve().parents or args.source.resolve() == ROOT:
        raise SystemExit("Keep reference documents outside the repository.")

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()

    print(f"Reading documents from {args.source}")
    for name in args.documents:
        path = args.source / name
        try:
            pages = read_pages(path.read_bytes(), path.name, max_pages=300)
        except (IngestError, OSError) as exc:
            print(f"  skipped  {name}: {exc}")
            continue
        doc = KnowledgeDocument(title=path.name, citation=path.stem, kind="judgment", status="processing")
        db.add(doc)
        db.flush()
        publish_pages(db, doc, pages)
        print(f"  loaded   {name}: {doc.page_count} pages, {doc.passage_count} passages")
    db.commit()

    questions = parse_questions(args.questions.read_text(encoding="utf-8"))
    if not questions:
        print("No English questions found in that file (retrieval here is English-only for keywords).")
        return 1

    embeddings.set_embedder(None, disabled=True)
    keyword_found, _ = score_run(db, questions, "Keywords only")

    real = embeddings.VoyageEmbedder(get_settings().voyage_api_key, get_settings().embedding_model) if get_settings().voyage_api_key else None
    if real is None:
        print("\nNo VOYAGE_API_KEY set, so meaning-based search was not measured.")
        return 0
    cached = CachedEmbedder(real, args.cache)
    embeddings.set_embedder(cached)
    passages = list(db.scalars(select(LegalSource)))
    embeddings.embed_passages(db, passages, patient=True)
    db.commit()
    print(f"\nEmbedded {len(passages)} passages ({cached.fetched} new vectors fetched)")

    reranker = CachedReranker(get_settings().voyage_api_key, get_settings().rerank_model, args.cache.with_name("mrcourt-rerank-cache.json"))
    rerank.set_reranker(reranker)
    combined_found, misses = score_run(db, questions, "Keywords + meaning + rerank")
    print(f"Reranker scores fetched this run: {reranker.fetched}")

    # How well can the reranker's best score tell a relevant question from an unrelated one?
    relevant = sorted(reranker.best.get(q, 0.0) for _, q, _, _ in questions)
    for question in UNRELATED:
        embeddings.embed_query(question)  # warm the cache for the question vector
        search(db, question, None, limit=TOP, min_score=0.2)
    unrelated = sorted(reranker.best.get(q, 0.0) for q in UNRELATED)
    print(f"\nBest rerank score, relevant questions : min {relevant[0]:.2f}, 10th percentile {relevant[len(relevant) // 10]:.2f}, median {statistics.median(relevant):.2f}")
    print(f"Best rerank score, unrelated questions: max {unrelated[-1]:.2f}, median {statistics.median(unrelated):.2f}")
    print(f"Current MIN_RERANK_SCORE: {get_settings().min_rerank_score}")
    total = len(questions)
    print(f"\nImprovement: {100 * keyword_found / total:.0f}% -> {100 * combined_found / total:.0f}%")
    if misses:
        print("\nMisses with meaning-based search and reranking (number, question, expected pages, fact coverage, pages retrieved):")
        for row in misses:
            print("  ", row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
