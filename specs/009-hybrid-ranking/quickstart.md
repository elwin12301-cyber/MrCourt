# Quickstart: validating hybrid ranking

## Prerequisites

- Backend set up as in the README; `backend/.env` with `VOYAGE_API_KEY` for meaning search and the reranker
  (without it, only keyword evidence is used and the meaning/reranker parts of the evaluation are skipped).
- The law PDFs loaded (`scripts/ingest_law_folder.py`) and, optionally, private case documents
  (`scripts/ingest_private_folder.py`).

## 1. Baseline

```text
cd backend
DATABASE_URL=sqlite:///./dev.db python scripts/evaluate_ranking.py --questions tests/data/ranking_eval_shared.json --mode rrf --save-baseline
```

Expected: a report with hit@1/3/5 and MRR saved to `specs/009-hybrid-ranking/eval-baseline.json`.

## 2. Tune and compare

```text
DATABASE_URL=sqlite:///./dev.db python scripts/evaluate_ranking.py --questions tests/data/ranking_eval_shared.json --mode hybrid --grid
DATABASE_URL=sqlite:///./dev.db python scripts/evaluate_ranking.py --questions tests/data/ranking_eval_shared.json --mode both --baseline ../specs/009-hybrid-ranking/eval-baseline.json
```

Expected: hybrid at or above the baseline on hit@1 and MRR; differently-worded questions ≥ 90% found (SC-001);
every exact-reference question has its source at position 1 (SC-002). Record the chosen settings and results in
`eval-results.md`.

## 3. Behaviour checks in the app

1. Sign in as an advocate; ask "What does Section 379 IPC say?" → first citation is IPC s. 379.
2. Ask "Section 999 IPC" → the answer says that section was not found.
3. Ask a "how have courts decided ..." question → judgments first; no more than 2 citations from one judgment.
4. Sign in as a client; ask about a private case document's number → no private source is cited.
5. Sign in as the administrator; open an answer → "Why these sources?" shows scores and signals; another
   advocate's private passage shows as hidden.

## 4. Tests

```text
cd backend && python -m pytest tests/unit/test_references.py tests/unit/test_question_type.py tests/unit/test_ranking.py tests/integration/test_ranking_safety.py tests/contract/test_admin_ranking.py -q
cd frontend && npx playwright test ranking-explanation.spec.ts a11y.spec.ts
```

## 5. Latency

Time 30 questions with `RANKING_MODE=rrf` and `hybrid`; hybrid must be no more than 10% slower (SC-004).

## Rollback

Set `RANKING_MODE=rrf` and restart: the old ranker is used; stored explanations remain readable.
