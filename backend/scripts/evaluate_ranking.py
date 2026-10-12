"""Measures answer ranking (feature 009): hit@1, hit@3, hit@5 and mean reciprocal rank (MRR), overall and per
question type, for the earlier ranker ("rrf", the baseline) and the hybrid ranker, and compares with a saved
baseline. `--grid` tries other weights and boosts on the recorded candidates (no extra service calls).

Query vectors and reranker scores are cached on disk OUTSIDE the repository (in the system temp folder by
default), so repeat runs cost nothing and stay within free-tier limits.

    DATABASE_URL=sqlite:///./dev.db python scripts/evaluate_ranking.py --questions tests/data/ranking_eval_shared.json --mode both
    ... --mode rrf --save-baseline ../specs/009-hybrid-ranking/eval-baseline.json
    ... --mode hybrid --grid --baseline ../specs/009-hybrid-ranking/eval-baseline.json

Exit code 1 when hybrid is below the baseline on hit@1 or MRR.
"""

import argparse
import hashlib
import itertools
import json
import re
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path

from mrcourt.config import get_settings
from mrcourt.db.base import get_sessionmaker
from mrcourt.services import embeddings, ranking, rerank
from mrcourt.services.retrieval import search

LIMIT = 5


# ----- metrics ----------------------------------------------------------------------------------


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").lower()


def is_hit(source, expected: dict) -> bool:  # type: ignore[no-untyped-def]
    if expected.get("instrument", "").lower() not in (source.instrument or "").lower():
        return False
    if expected.get("section"):
        return (source.section or "").strip().upper() == str(expected["section"]).upper()
    phrases = expected.get("contains") or []
    return not phrases or any(norm(p) in norm(source.text) for p in phrases)


def first_rank(sources: list, expected: dict) -> int | None:  # type: ignore[type-arg]
    for position, source in enumerate(sources, start=1):
        if is_hit(source, expected):
            return position
    return None


def metrics(ranks: list[int | None]) -> dict[str, float]:
    n = len(ranks) or 1
    return {
        "n": len(ranks),
        "hit@1": round(sum(1 for r in ranks if r is not None and r <= 1) / n, 3),
        "hit@3": round(sum(1 for r in ranks if r is not None and r <= 3) / n, 3),
        "hit@5": round(sum(1 for r in ranks if r is not None and r <= 5) / n, 3),
        "mrr": round(sum(1 / r for r in ranks if r) / n, 3),
    }


def report(questions: list[dict], ranks: dict[str, int | None]) -> dict[str, object]:
    groups: dict[str, list[int | None]] = {"all": [ranks[q["id"]] for q in questions]}
    for q in questions:
        groups.setdefault(f"type:{q['type']}", []).append(ranks[q["id"]])
        if q.get("exact_reference"):
            groups.setdefault("exact_reference", []).append(ranks[q["id"]])
        if q.get("differently_worded"):
            groups.setdefault("differently_worded", []).append(ranks[q["id"]])
        groups.setdefault(f"language:{q.get('language', 'en')}", []).append(ranks[q["id"]])
    return {"metrics": {k: metrics(v) for k, v in groups.items()}, "ranks": ranks}


# ----- cached services --------------------------------------------------------------------------


class CachedEmbedder:
    def __init__(self, inner, path: Path) -> None:  # type: ignore[no-untyped-def]
        self.inner, self.path, self.name = inner, path, inner.name
        self.cache: dict[str, list[float]] = json.loads(path.read_text()) if path.exists() else {}

    def _key(self, text: str, kind: str) -> str:
        return hashlib.sha256(f"{self.name}|{kind}|{text}".encode()).hexdigest()

    def embed(self, texts, input_type, *, patient=False):  # type: ignore[no-untyped-def]
        missing = [t for t in texts if self._key(t, input_type) not in self.cache]
        if missing:
            for text, vector in zip(missing, self.inner.embed(missing, input_type, patient=True), strict=True):
                self.cache[self._key(text, input_type)] = vector
            self.path.write_text(json.dumps(self.cache))
        return [self.cache[self._key(t, input_type)] for t in texts]


class CachedReranker:
    """One cache entry per (question, passage), so different candidate lists share results."""

    def __init__(self, api_key: str, model: str, path: Path) -> None:
        import voyageai

        self._voyageai = voyageai
        self._client = voyageai.Client(api_key=api_key, max_retries=0, timeout=30)
        self.name, self.path = model, path
        self.cache: dict[str, float] = json.loads(path.read_text()) if path.exists() else {}
        self.calls = 0

    def _key(self, question: str, text: str) -> str:
        return hashlib.sha256(f"{self.name}|{question}|{text}".encode()).hexdigest()

    def score(self, question: str, texts: list[str]) -> list[float]:
        missing = list(dict.fromkeys(t for t in texts if self._key(question, t) not in self.cache))
        if missing:
            for attempt in range(30):
                try:
                    result = self._client.rerank(question[:2000], [t[:6000] for t in missing], model=self.name)
                    break
                except self._voyageai.error.RateLimitError:
                    time.sleep(25)
                except self._voyageai.error.APIConnectionError:  # a dropped connection: wait and try again
                    time.sleep(15)
            else:
                raise rerank.RerankUnavailable("rate limited")
            for item in result.results:
                self.cache[self._key(question, missing[item.index])] = float(item.relevance_score)
            self.calls += 1
            self.path.write_text(json.dumps(self.cache))
        return [self.cache.get(self._key(question, t), 0.0) for t in texts]


# ----- running ----------------------------------------------------------------------------------


def run(db, questions: list[dict], mode: str, recorded: dict | None = None) -> dict[str, int | None]:  # type: ignore[no-untyped-def]
    settings = get_settings()
    settings.ranking_mode = mode
    ranks: dict[str, int | None] = {}
    original = ranking.rank
    for q in questions:
        last: list = []  # type: ignore[type-arg]

        def recording(candidates, ctx, rs):  # type: ignore[no-untyped-def]
            result = original(candidates, ctx, rs)
            last[:] = [result, ctx]
            return result

        ranking.rank = recording
        try:
            found = search(db, q["question"], None, limit=LIMIT, min_score=settings.min_retrieval_score)
        finally:
            ranking.rank = original
        ranks[q["id"]] = first_rank([h.source for h in found.hits], q["expected"])
        if recorded is not None and last:
            recorded[q["id"]] = last
        print(f"  {mode:6} {q['id']}: {ranks[q['id']]}", flush=True)
    return ranks


def offline(recorded: dict, questions: list[dict], rs: ranking.RankSettings) -> dict[str, int | None]:
    """Re-rank the recorded candidates with other settings (safety rule and per-document cap included)."""
    floor = get_settings().min_rerank_score
    ranks: dict[str, int | None] = {}
    for q in questions:
        if q["id"] not in recorded:
            ranks[q["id"]] = None
            continue
        candidates, ctx = recorded[q["id"]]
        ordered = ranking.rank([replace(c) for c in candidates], ctx, rs)
        safe = [c for c in ordered if c.keyword_evidence or c.pinned or (ctx.rerank_available and c.rerank is not None and c.rerank >= floor)]
        chosen = ranking.diversify(safe, rs.per_document, LIMIT)
        ranks[q["id"]] = first_rank([c.source for c in chosen], q["expected"])
    return ranks


def grid(recorded: dict, questions: list[dict], base: ranking.RankSettings) -> list[tuple[float, float, ranking.RankSettings]]:
    results = []
    steps = [round(x * 0.1, 1) for x in range(0, 11)]
    for wk, wm in itertools.product(steps, steps):
        wr = round(1 - wk - wm, 1)
        if wr < 0:
            continue
        for bs, bt in itertools.product((0.0, 0.15, 0.25, 0.4), (0.0, 0.05, 0.10, 0.15)):
            rs = replace(base, w_keyword=wk, w_meaning=wm, w_rerank=wr, boost_section=bs, boost_type=bt)
            m = metrics(list(offline(recorded, questions, rs).values()))
            results.append((m["mrr"], m["hit@1"], rs))
    results.sort(key=lambda r: (r[0], r[1]), reverse=True)
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=Path, action="append", required=True)
    parser.add_argument("--mode", choices=("rrf", "hybrid", "both"), default="both")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--save-baseline", type=Path)
    parser.add_argument("--grid", action="store_true")
    parser.add_argument("--cache", type=Path, default=Path(tempfile.gettempdir()) / "mrcourt-ranking-cache")
    parser.add_argument("--report", type=Path, help="write the full report as JSON")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # questions in Tamil print on a Windows console

    questions = [q for path in args.questions for q in json.loads(path.read_text(encoding="utf-8"))["questions"]]
    settings = get_settings()
    args.cache.mkdir(parents=True, exist_ok=True)
    if settings.voyage_api_key:
        real = embeddings.get_embedder()
        if real is not None:
            embeddings.set_embedder(CachedEmbedder(real, args.cache / "vectors.json"))
        rerank.set_reranker(CachedReranker(settings.voyage_api_key, settings.rerank_model, args.cache / "rerank.json"))
    else:
        print("No VOYAGE_API_KEY: keyword evidence only (meaning search and answer check skipped).")

    modes = ["rrf", "hybrid"] if args.mode == "both" else [args.mode]
    reports: dict[str, dict] = {}
    recorded: dict = {}
    with get_sessionmaker()() as db:
        for mode in modes:
            ranks = run(db, questions, mode, recorded if mode == "hybrid" else None)
            reports[mode] = report(questions, ranks)

    for mode, rep in reports.items():
        print(f"\n== {mode}")
        for group, m in rep["metrics"].items():  # type: ignore[union-attr]
            print(f"  {group:22} n={m['n']:3}  hit@1={m['hit@1']:.3f}  hit@3={m['hit@3']:.3f}  hit@5={m['hit@5']:.3f}  MRR={m['mrr']:.3f}")

    if args.save_baseline:
        mode = modes[0]
        args.save_baseline.write_text(json.dumps({"mode": mode, **reports[mode]}, indent=1), encoding="utf-8")
        print(f"\nSaved baseline ({mode}) to {args.save_baseline}")

    exit_code = 0
    if args.baseline and "hybrid" in reports:
        base = json.loads(args.baseline.read_text(encoding="utf-8"))
        hybrid = reports["hybrid"]
        print("\n== hybrid vs baseline (per question: rank before -> after)")
        for q in questions:
            before, after = base["ranks"].get(q["id"]), hybrid["ranks"][q["id"]]  # type: ignore[index]
            if before != after:
                better = (after or 99) < (before or 99)
                print(f"  {'better' if better else 'WORSE '} {q['id']}: {before} -> {after}  {q['question'][:70]}")
        b, h = base["metrics"]["all"], hybrid["metrics"]["all"]  # type: ignore[index]
        print(f"  overall hit@1 {b['hit@1']:.3f} -> {h['hit@1']:.3f}, MRR {b['mrr']:.3f} -> {h['mrr']:.3f}")
        if h["hit@1"] < b["hit@1"] or h["mrr"] < b["mrr"]:
            exit_code = 1

    if args.grid and recorded:
        print("\n== grid (best 5 by MRR, then hit@1)")
        for mrr, hit1, rs in grid(recorded, questions, ranking.RankSettings.from_settings(settings))[:5]:
            print(f"  MRR={mrr:.3f} hit@1={hit1:.3f}  w_keyword={rs.w_keyword} w_meaning={rs.w_meaning} "
                  f"w_rerank={rs.w_rerank} boost_section={rs.boost_section} boost_type={rs.boost_type}")

    if args.report:
        args.report.write_text(json.dumps(reports, indent=1), encoding="utf-8")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
