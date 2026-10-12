# Tasks: Hybrid ranking for answers and knowledge search

**Input**: Design documents from `/specs/009-hybrid-ranking/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ranking-api.md, quickstart.md

**Tests**: Included. The project constitution and every earlier feature require tests for retrieval and
privacy behaviour, and the plan lists them.

**Organization**: Tasks are grouped by user story so each story can be built and tested on its own.

Paths are relative to the repository root. Backend commands run from `backend/`, frontend from `frontend/`.

## Phase 1: Setup

**Purpose**: Settings, migration, and a measured baseline before any ranking changes.

- [X] T001 Add ranking settings to `backend/src/mrcourt/config.py`: `ranking_mode` ("hybrid" | "rrf", default "hybrid"), `rank_w_keyword=0.35`, `rank_w_meaning=0.15`, `rank_w_rerank=0.50`, `rank_boost_type=0.10`, `rank_boost_court=0.08`, `rank_boost_own_case=0.15`, `rank_recency_max=0.05`, `rank_per_document=2`, `rerank_candidates=20` (see data-model.md)
- [X] T002 [P] Create migration `backend/alembic/versions/0008_answer_ranking.py` adding nullable JSON column `answers.ranking`, idempotent like 0007; add `ranking: Mapped[dict | None]` to `Answer` in `backend/src/mrcourt/models/legal.py`
- [X] T003 [P] Create the shared evaluation set `backend/tests/data/ranking_eval_shared.json` with at least 60 questions on the shared law corpus only (no private case documents), each with `id`, `question`, `type` (law | courts | my_case | other), `expected` (instrument + section, or document title + page), `exact_reference`, `language`; include at least 20 exact-reference questions, 20 differently-worded questions and 5 Tamil questions
- [X] T004 Create `backend/scripts/evaluate_ranking.py` per contracts/ranking-api.md (Evaluation CLI): load questions, run `search()` per question with `RANKING_MODE` forced per mode, find the rank of the first expected source, print hit@1/3/5, MRR, per-type counts; `--save-baseline` writes JSON; cache query vectors and reranker scores on disk outside the repository (reuse the cache approach in `backend/scripts/import_reference.py`)
- [ ] T005 Run `evaluate_ranking.py --mode rrf --save-baseline` against `dev.db` and commit the result as `specs/009-hybrid-ranking/eval-baseline.json`

**Checkpoint**: Baseline numbers exist before any ranking change.

---

## Phase 2: Foundational (blocking all stories)

**Purpose**: The scored ranker wired into search, with all existing safety gates in their new order.

- [X] T006 [P] Unit tests for score normalisation and the weighted sum in `backend/tests/unit/test_ranking.py`: keyword = mean(BM25/max BM25, coverage); meaning clipped 0..1; rerank absent ⇒ weight redistributed; weights normalised to sum 1; ties broken by recency then shared-before-private
- [X] T007 Create `backend/src/mrcourt/services/ranking.py` with `Candidate` (source, keyword, meaning, rerank, signals, pinned, combined) and `rank(candidates, settings) -> list[Candidate]` implementing research.md §1; no database access in this module
- [X] T008 Refactor `search()` in `backend/src/mrcourt/services/retrieval.py`: keep candidate gathering and `_fuse` (used when `ranking_mode == "rrf"`); for "hybrid" build `Candidate`s from keyword and meaning hits, call `rerank_scores` once for the top `rerank_candidates`, call `ranking.rank`, then apply in order: safety gate (meaning-only passages need rerank ≥ `min_rerank_score`; reranker unavailable ⇒ keyword-evidence only), repealed-law swap, limit (research.md §5); return the candidates so callers can record an explanation
- [X] T009 Integration test `backend/tests/integration/test_ranking_safety.py`: with `ranking_mode` both values, a client never receives a private passage; a meaning-only passage below the floor is never returned; reranker down ⇒ only keyword-evidence passages; nothing above threshold ⇒ answer outcome `no_reliable_source`; repealed provisions swapped as before
- [X] T010 Run the full backend suite (`python -m pytest -q`) with `RANKING_MODE=hybrid` and with `rrf`; both must pass unchanged

**Checkpoint**: Hybrid ranking is live behind the setting, all existing tests pass, safety unchanged.

---

## Phase 3: User Story 1 - A named section or case comes first (P1) 🎯 MVP

**Goal**: An exact section or case reference in the question is cited first when the person may see it.

**Independent Test**: The 20+ exact-reference questions in the evaluation set all have their source at position 1; a missing section is reported as not found.

- [X] T011 [P] [US1] Unit tests `backend/tests/unit/test_references.py`: "Section 379 IPC", "Sec. 379", "s.379", "u/s 379", "379 IPC", "section 303 BNS", "W.P. No. 11944 of 2013", "W.P. 11944/2013", "O.S. 581", a 16-character CNR; no false match on years or page numbers; Act aliases from `ALIASES` in retrieval.py
- [X] T012 [P] [US1] Create `backend/src/mrcourt/services/references.py` with `parse_references(question) -> list[Reference]` (data-model.md "Reference")
- [X] T013 [US1] In `ranking.py`, pin candidates whose `instrument`/`section` match a section reference, or whose document title/case number (from 008 metadata when present, else the document title and citation) matches a case reference; several Acts with the same section number ⇒ all pinned in instrument order; IPC and BNS never treated as equal
- [X] T014 [US1] In `retrieval.py`, when a section reference is parsed and no visible passage matches it, fetch the exact `section` match from visible sources even if it was not among keyword/meaning candidates; if none exists, expose `missing_references` on the search result
- [X] T015 [US1] In `backend/src/mrcourt/services/answering.py`, when `missing_references` is set, say "Section X of the Act was not found in the sources" before any other citation, and never present another section as the named one
- [X] T016 [US1] Integration tests in `backend/tests/integration/test_ranking_safety.py`: named section first; missing section reported; private case number pinned only for its owner, others told no matching source exists

**Checkpoint**: Exact references work end to end (MVP).

---

## Phase 4: User Story 2 - Ranking uses document details and the kind of question (P1)

**Goal**: Statutes for law questions, judgments (newer first) for "how have courts decided", own case documents for "my case", court match raised.

**Independent Test**: For each question type in the evaluation set, the preferred document type is in the top 3 when it exists.

- [X] T017 [P] [US2] Unit tests `backend/tests/unit/test_question_type.py`: English and Tamil wordings for law, courts, my_case, other; "my case" from a client or administrator is never my_case
- [X] T018 [P] [US2] Create `backend/src/mrcourt/services/question_type.py` with `classify(question, user) -> str` (research.md §3)
- [X] T019 [US2] In `ranking.py`, add signals: document type suited to the question type (`rank_boost_type`), court named in the question (`rank_boost_court`), recency for judgments (`rank_recency_max`, linear to 0 at 20 years), own private documents for my_case questions (`rank_boost_own_case`); read type/court/date from 008 metadata when present, otherwise use `LegalSource.kind` and skip the rest without penalty
- [X] T020 [US2] Unit tests in `backend/tests/unit/test_ranking.py` for each signal and for "metadata missing ⇒ no boost, no penalty"

**Checkpoint**: Question-type and metadata signals applied and tested.

---

## Phase 5: User Story 3 - Varied sources, same safety (P1)

**Goal**: At most 2 citations per document unless nothing else qualifies; all safety rules hold.

**Independent Test**: No answer in the evaluation set has more than 2 passages from one document while others qualify.

- [X] T021 [US3] In `ranking.py`, add `diversify(candidates, per_document)` applied after the safety gate: keep at most `rank_per_document` per document (passages without a document count by instrument), fill from the next best; lift the cap only if no other candidate passes the gate
- [X] T022 [US3] Tests in `backend/tests/unit/test_ranking.py` and `backend/tests/integration/test_ranking_safety.py`: one long judgment with 30 relevant passages plus other sources ⇒ ≤ 2 from it; only that judgment relevant ⇒ cap lifted

**Checkpoint**: US1–US3 together satisfy the P1 scope.

---

## Phase 6: User Story 4 - Every change is measured (P2)

**Goal**: A report compares hybrid with the baseline per question and per type; weights are tuned by measurement.

**Independent Test**: `evaluate_ranking.py --mode both --baseline ...` prints both reports and per-question changes.

- [X] T023 [US4] Extend `backend/scripts/evaluate_ranking.py`: `--mode both`, `--baseline` comparison (better / worse / same per question), exit code 1 if hybrid is below baseline on hit@1 or MRR
- [X] T024 [US4] Add `--grid` to `evaluate_ranking.py`: search weights (0.1 steps, summing to 1) and boosts (0, 0.05, 0.10, 0.15) using cached scores only; print the best 5 settings
- [ ] T025 [US4] Run the grid on the shared set (and on a private question set kept outside the repository, if available); set the chosen defaults in `backend/src/mrcourt/config.py`; write `specs/009-hybrid-ranking/eval-results.md` with baseline vs hybrid hit@1/3/5, MRR, per type, differently-worded hit rate (target ≥ 90%) and exact-reference hit@1 (target 100%)
- [X] T026 [P] [US4] Unit test `backend/tests/unit/test_evaluate_ranking.py` for the metric functions (hit@k, MRR, per-type grouping) on a tiny fixed example

**Checkpoint**: Defaults are measured; SC-001 to SC-003 recorded.

---

## Phase 7: User Story 5 - Administrators can see why a passage ranked where it did (P3)

**Goal**: "Why these sources?" for any answer, with other users' private sources hidden.

**Independent Test**: An administrator opens an answer and sees scores and signals; another advocate's private passage shows as hidden.

- [ ] T027 [US5] In `backend/src/mrcourt/services/answering.py`, store the explanation in `Answer.ranking` (data-model.md shape; ids and numbers only, no text or names); same for assistant answers that cite sources in `backend/src/mrcourt/services/assistant_tools.py` *(Ask answers done; assistant answers not yet recorded: the assistant may search several times per answer)*
- [X] T028 [P] [US5] Contract tests `backend/tests/contract/test_admin_ranking.py` for `GET /api/v1/admin/answers/{id}/ranking`: 403 non-admin, 404 unknown, `recorded:false` for old answers, hidden passages for another user's private document, audit entry `answer.ranking.view`
- [X] T029 [US5] Implement the endpoint in `backend/src/mrcourt/api/admin.py` with response schema in `backend/src/mrcourt/schemas/admin.py` (contracts/ranking-api.md); plain-language signal labels ("Named in the question", "Statute suits this question", "Same court", "Recent judgment", "Your own case document")
- [X] T030 [P] [US5] Add `getAnswerRanking(answerId)` to `frontend/src/services/assistant.ts` (or the admin service file used by the Ask pages)
- [X] T031 [US5] Create `frontend/src/components/RankingExplanation.tsx`: a disclosure "Why these sources?" with a table (position, source or "Private document of another user", combined score, the three scores, signals in words); existing tokens and `.ka-*` styles; keyboard reachable
- [X] T032 [US5] Show `RankingExplanation` under answers for administrators only in `frontend/src/pages/ask/AskTab.tsx` and the admin "Everyone's questions" history view in `frontend/src/pages/ask/HistoryTab.tsx`
- [X] T033 [US5] Playwright test `frontend/tests/e2e/ranking-explanation.spec.ts` (admin sees panel, advocate does not, hidden private row) and an axe scan of the panel in `frontend/tests/e2e/a11y.spec.ts` (both themes, desktop and mobile)

**Checkpoint**: All stories done.

---

## Phase 8: Polish & cross-cutting

- [ ] T034 Latency check per quickstart.md §5: 30 questions, `rrf` vs `hybrid`; hybrid ≤ 10% slower (SC-004); record in `specs/009-hybrid-ranking/eval-results.md`
- [X] T035 [P] README section "How answers are ranked" in `README.md`: signals, settings, `RANKING_MODE=rrf` rollback, how to run the evaluation
- [ ] T036 Full regression: backend pytest, Vitest, `tsc`, ESLint, full Playwright run; record counts in `specs/009-hybrid-ranking/results.md`
- [ ] T037 Run quickstart.md §3 behaviour checks in the running app and record outcomes in `specs/009-hybrid-ranking/results.md`

---

## Dependencies & execution order

- **Setup (T001–T005)** first; T005 needs T003 and T004. The baseline must be saved before T008 changes ranking.
- **Foundational (T006–T010)** blocks every story.
- **US1, US2, US3** can proceed in parallel after Phase 2 (they touch different parts of `ranking.py`; merge carefully). US2's metadata signals use 008 when present but do not require it.
- **US4** needs US1–US3 to tune meaningful defaults (T023/T024 can be written earlier).
- **US5** needs T002 (column) and T008 (candidates returned); independent of US1–US4 otherwise.
- **Polish** last.

## Parallel examples

- Setup: T002 and T003 together.
- US1: T011 and T012 together, then T013–T016.
- US2: T017 and T018 together, then T019, T020.
- US5: T028 and T030 together, then T029, T031, T032, T033.

## Implementation strategy

1. **MVP**: Phases 1–3 (settings, baseline, scored ranker, exact references). Measure with the evaluation script; ship behind `RANKING_MODE=hybrid` with `rrf` as rollback.
2. Add US3 (diversity), then US2 (signals; richer once 008 is built).
3. Tune with US4 and fix the defaults by measurement.
4. Add US5 for administrators.
