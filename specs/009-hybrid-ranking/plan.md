# Implementation Plan: Hybrid ranking for answers and knowledge search

**Branch**: `009-hybrid-ranking` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/009-hybrid-ranking/spec.md`

## Summary

Replace the position-only merge (reciprocal rank fusion) in `services/retrieval.py` with a scored hybrid
ranker: normalised keyword, meaning and reranker scores combined with configurable weights, plus rule-based
signals (exact section / case reference, question type to document type, court, recency, own case). An exact
reference is pinned first; at most two passages per document are kept; every existing safety gate (visibility,
reranker floor for meaning-only passages, keyword-only fallback, repealed-law swap, citation verification,
"no reliable source") stays and runs after scoring. An offline evaluation script reports hit@1/3/5 and MRR
against the current ranker, which stays selectable (`RANKING_MODE=rrf`) as the baseline. Each answer stores a
short ranking explanation that administrators can open, with other users' private sources redacted.

Metadata signals read the fields from 008-metadata-mapping when present and are simply skipped when absent,
so stories 1, 3 and 4 can ship before 008.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5 / React 18 (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2, Alembic; Voyage embeddings and reranker (existing); no new services

**Storage**: SQLite (dev/tests), PostgreSQL 16 + pgvector (production); one new JSON column `answers.ranking`

**Testing**: pytest (unit, contract, integration), Vitest, Playwright (admin explanation panel, a11y)

**Target Platform**: Linux container (Render) and local Windows development

**Project Type**: Web application (backend + frontend)

**Performance Goals**: answers no more than 10% slower than today (SC-004); ranking itself under 20 ms for 250 candidates

**Constraints**: Voyage free tier (3 requests/min): one reranker call per question, as today; evaluation caches vectors and reranker scores on disk outside the repository

**Scale/Scope**: about 5,200 passages today (35 law PDFs + private case documents); evaluation set of at least 100 questions

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | How this plan complies | Status |
|---|---|---|
| I. Grounded, cited answers only | Ranking only reorders candidates; citation verification and the "no reliable source" reply are unchanged and run after ranking. Exact-reference pin never invents a source: if the section is absent, the answer says so (FR-002, US1 scenario 2). | Pass |
| II. Informational only, not legal advice | No change to answer wording, disclaimers or the advice guard. | Pass |
| III. Privacy by design (DPDP) | Visibility filter (`visible_to`) is applied before any scoring; own-case boost only for the owner; ranking explanations redact other users' private sources (FR-007, SC-005). No new data leaves the system. | Pass |
| IV. Accessibility and responsive design | The administrator "Why these sources?" panel uses existing table/disclosure patterns, keyboard reachable, tested with axe in both themes and both widths. | Pass |
| V. Design system consistency | Panel uses existing tokens and `.ka-*` styles; no new visual language. | Pass |
| VI. Simplicity | Rule-based signals and a weighted sum; no learned model, no new service, no new dependency. Old ranker kept only as a switchable baseline for measurement. | Pass |

Post-design re-check (after Phase 1): still passes. The only schema change is one nullable JSON column.

## Project Structure

### Documentation (this feature)

```text
specs/009-hybrid-ranking/
├── plan.md              # This file
├── research.md          # Phase 0 decisions
├── data-model.md        # Phase 1: ranking settings, explanation, evaluation question
├── quickstart.md        # Phase 1: how to run and validate
├── contracts/
│   └── ranking-api.md   # Phase 1: admin explanation endpoint and evaluation CLI
└── tasks.md             # Phase 2 (/speckit-tasks, not created here)
```

### Source Code (repository root)

```text
backend/
├── src/mrcourt/
│   ├── config.py                     # + ranking_mode, ranking weights, per-document cap
│   ├── services/
│   │   ├── retrieval.py              # search() calls the ranker; RRF kept as baseline
│   │   ├── ranking.py                # NEW: feature normalisation, weights, signals, pin, diversity, explanation
│   │   ├── references.py             # NEW: parse "Section 379 IPC", "s.420", "W.P. 11944/2013", CNR
│   │   ├── question_type.py          # NEW: law / how-courts-decided / my-case / other
│   │   └── answering.py              # stores the explanation on the answer
│   ├── api/admin.py                  # + GET /admin/answers/{id}/ranking
│   └── models/legal.py               # + Answer.ranking (JSON, nullable)
├── alembic/versions/0008_answer_ranking.py
├── scripts/evaluate_ranking.py       # NEW: hit@1/3/5, MRR, per type, vs baseline; weight grid search
└── tests/
    ├── unit/test_references.py, test_question_type.py, test_ranking.py
    ├── integration/test_ranking_safety.py      # visibility, floor, fallback, cap, no-source
    ├── contract/test_admin_ranking.py
    └── data/ranking_eval_shared.json           # evaluation questions on the shared law corpus only

frontend/
├── src/components/RankingExplanation.tsx       # NEW: admin "Why these sources?" panel
├── src/pages/ask/... (admin answer view uses it)
└── tests/e2e/ranking-explanation.spec.ts
```

**Structure Decision**: Existing web-application layout. Ranking logic moves into its own module so
`retrieval.py` keeps candidate gathering and safety gates, and the ranker can be unit tested without a database.

## Complexity Tracking

No constitution violations. Keeping the old ranker selectable is deliberate: it is the measured baseline that
SC-001 and SC-003 are judged against, and it gives a one-setting rollback.
