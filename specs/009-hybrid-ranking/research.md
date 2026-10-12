# Research: Hybrid ranking

## 1. How to combine keyword, meaning and reranker scores

- **Decision**: Weighted sum of normalised scores. Keyword: BM25 divided by the best BM25 for the question
  (0..1), averaged with term coverage. Meaning: cosine similarity clipped to 0..1. Reranker: its 0..1 score,
  used for the top 20 candidates (one call, as today); passages outside the top 20 get the mean of the
  others' missing-reranker contribution, i.e. their rerank term is 0 and their weight is redistributed.
  Defaults `w_keyword=0.35, w_meaning=0.15, w_rerank=0.50`, then tuned by grid search on the evaluation set.
- **Rationale**: Rank fusion throws away how far ahead a passage is; a weighted sum keeps it and is easy to
  explain to administrators. The reranker is the most reliable judge of "does this answer the question"
  (measured in 005), so it gets the largest default weight.
- **Alternatives**: keep RRF and add boosts (cannot express "much better"); a learned ranker (needs
  labelled data we do not have; violates simplicity); reranker-only ordering (loses exact keyword matches
  for section numbers, which the reranker under-weights).

## 2. Exact legal references

- **Decision**: A small parser (`references.py`) recognises section references ("Section 379", "Sec. 379",
  "s.379", "u/s 379", "379 IPC", with Act aliases already in `ALIASES`) and case references (W.P./O.S./
  Crl.A./S.A. numbers with year, and CNR). A passage whose `section` and `instrument` match a referenced
  section, or whose document's case number (008) or title matches a referenced case, is pinned first.
  If the Act is not named and several Acts match, all matches are pinned in instrument order and the answer
  names each Act (spec US1-3). Old and new codes are never treated as equal unless the source says so.
- **Rationale**: Lawyers expect the named provision first; the current pipeline can rank it below a judgment
  that repeats the words more often.
- **Alternatives**: a large boost instead of a pin (can still lose to long documents); asking the language
  model to choose (slower, not deterministic, not explainable).

## 3. Question type

- **Decision**: Rule-based classifier on wording: "punishment, penalty, what is/does section, define,
  ingredients" → law (prefer statute); "held, decided, precedent, case law, courts, judgment on" →
  how-courts-decided (prefer judgment, recency); "my case, my client, this case, our matter" (advocate only)
  → my-case (prefer own private documents); otherwise none. Signals are small additive boosts (0.05–0.15),
  tuned on the evaluation set.
- **Rationale**: Clear, testable, multilingual-friendly (Tamil keyword list added), no extra service call.
- **Alternatives**: language-model classification (latency and cost for a small gain); none (fails US2).

## 4. Diversity

- **Decision**: After ordering, keep at most 2 passages per document (configurable), filling remaining
  slots with the next best passages from other documents; if nothing else passes the reliability floor,
  the cap is lifted (FR-004).
- **Alternatives**: MMR on embeddings (needs vectors for all candidates; overkill for 5 slots).

## 5. Safety order of operations

- **Decision**: visibility filter → candidates → scores → signals → pin → safety gate (meaning-only passages
  need rerank ≥ `min_rerank_score`; reranker down ⇒ keyword-evidence only) → diversity → repealed swap →
  limit → citation verification (unchanged, in answering).
- **Rationale**: No ranking signal can bring in a passage the safety gate would refuse.

## 6. Evaluation

- **Decision**: `scripts/evaluate_ranking.py` runs each question through both rankers (`rrf` baseline and
  `hybrid`) against a chosen database, records the rank of the first expected source, and prints hit@1/3/5,
  MRR, per question type and per-question changes. Vectors and reranker scores are cached on disk outside
  the repository (as in `import_reference.py`), so grid search over weights costs no extra API calls.
  Shared-law questions live in `backend/tests/data/ranking_eval_shared.json`; questions about real case
  documents are kept outside the repository.
- **Baseline**: the 005 measurement (87% for differently-worded questions) plus a fresh baseline run of
  `rrf` on the new set, saved as `specs/009-hybrid-ranking/eval-baseline.json`.

## 7. Explanation

- **Decision**: Store per answer a compact list: for each cited passage its position, the three scores,
  the signals applied with their amounts, and whether it was pinned. Shown only to administrators; passages
  owned by someone else are returned as `{"hidden": true}` with scores but no label or text.
- **Alternatives**: recompute on demand (results would change as documents change); log only (not visible
  to administrators).
