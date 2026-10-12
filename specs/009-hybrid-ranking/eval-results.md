# Evaluation results: hybrid ranking (feature 009)

Date: 2026-10-12. Database: development PostgreSQL 16 + pgvector (shared law corpus). Question set:
`backend/tests/data/ranking_eval_shared.json` (69 questions: 52 law, 17 other; 20 name an exact section or
article; 32 are worded differently from the source; 5 in Tamil). Query vectors and reranker scores are cached
outside the repository, so every run below sees the same service answers.

## Baseline vs hybrid (T005, T025)

Baseline = the earlier ranker (`RANKING_MODE=rrf`), saved in `eval-baseline.json`.
Hybrid = the new ranker with the chosen defaults (below).

| Group | n | hit@1 | hit@3 | hit@5 | MRR |
|---|---|---|---|---|---|
| **All** baseline | 69 | 0.652 | 0.826 | 0.826 | 0.732 |
| **All** hybrid | 69 | **0.783** | **0.884** | **0.884** | **0.829** |
| Law baseline / hybrid | 52 | 0.577 / 0.731 | 0.769 / 0.846 | 0.769 / 0.846 | 0.663 / 0.782 |
| Exact reference baseline / hybrid | 20 | 0.600 / 0.800 | 0.850 / 0.850 | 0.850 / 0.850 | 0.708 / 0.817 |
| Differently worded baseline / hybrid | 32 | 0.562 / 0.688 | 0.719 / 0.844 | 0.719 / 0.844 | 0.635 / 0.760 |
| Other baseline / hybrid | 17 | 0.882 / 0.941 | 1.000 / 1.000 | 1.000 / 1.000 | 0.941 / 0.971 |
| Tamil baseline / hybrid | 5 | 0.000 / 0.400 | 0.000 / 0.400 | 0.000 / 0.400 | 0.000 / 0.400 |

Per question: 11 better, 1 worse (x06 "What does Article 21 protect?", 2nd → 3rd), the rest unchanged.

## Choosing the weights

1. The first defaults (keyword 0.35, meaning 0.15, answer check 0.50) were measured **below** the baseline
   (hit@1 0.609, MRR 0.708). The grid search on the recorded candidates favoured the answer check (reranker)
   almost alone.
2. Setting keyword 0.1 / meaning 0 / answer check 0.9 then exposed a defect: the shortlist sent to the answer
   check (top 20) was ordered with the final weights, so with meaning at 0 passages found only by meaning were
   never checked (several questions dropped to "not found"). **Fixed**: the shortlist now weighs keyword and
   meaning equally whatever the final weights (`retrieval._hybrid_search`).
3. With the fix, the chosen defaults give the table above.

Chosen defaults (`backend/src/mrcourt/config.py`): `RANK_W_KEYWORD=0.10`, `RANK_W_MEANING=0.0`,
`RANK_W_RERANK=0.90`; boosts unchanged (section 0.25, type 0.10, court 0.08, own case 0.15, recency 0.05);
2 passages per document; 20 candidates checked.

The grid's best setting on these 69 questions (answer check only, section boost 0.15) reaches hit@1 0.812,
MRR 0.850, i.e. about two questions more. It was **not** chosen: it is tuned on the same small set it is scored
on, and a small keyword weight keeps a sensible order when the answer check is unavailable (then only keyword
evidence is used, as before).

## Targets

| Target (spec) | Result | Met? |
|---|---|---|
| Hybrid not below baseline on hit@1 and MRR | 0.652 → 0.783; 0.732 → 0.829 | Yes |
| Differently worded questions found in the top 5: ≥ 90% | 84% (27 of 32) | **No** |
| Exact reference first (hit@1): 100% | 80% (16 of 20) | **No** |

The 4 exact-reference questions not answered first, checked one by one (each has a matching passage):

- **x05 "Section 437 CrPC"**: by design. CrPC s. 437 is repealed; the current-law rule shows its replacement,
  BNSS s. 480, first. The question set should accept BNSS s. 480 (then exact hit@1 is 17 of 20).
- **x06 "Article 21"**: found, at position 3.
- **x18 "Section 11 CPC res judicata"**: the top 5 are all CPC res judicata notes, but not the passage that
  names "section 11", which the question set requires.
- **x16 "Section 58 TPA"**: a real miss. The matching passage is a class-notes page on mortgages with no
  section number mapped (only 6% of law passages carry one, see feature 008 results), so it is neither pinned
  nor found by keywords.

When the named section exists as its own mapped passage, the pin puts it first (covered by
`test_ranking_safety.py`). Loading bare-Act texts, mapped section by section, is the main lever for both missed
targets. Tamil questions (2 of 5 found) need Tamil sources.

## Latency (T034, SC-004)

30 questions × 3 rounds per mode, same machine, cached query vectors and answer-check scores (so only search and
ranking work is timed; network calls are the same for both modes).

| Mode | median | mean | p90 |
|---|---|---|---|
| rrf | 133 ms | 121 ms | 146 ms |
| hybrid | 145 ms | 137 ms | 174 ms |

Hybrid is **+8.9%** on the median, within the 10% limit; on the mean it is +13%, so the margin is thin and
should be re-checked after ranking changes. Two causes of extra time were found and fixed: each candidate's
document (read by the type, court and date signals) was loaded with its own query, and the search for a named
reference read every pooled passage's document. Documents are now loaded in one query per search (20 → 4
queries for a question naming a section).

## Found in the behaviour checks

- A question naming the advocate's own case (a second-appeal number) did not find their judgment: only its
  first page carries the number, and the mapped case number (feature 008) was not used. **Fixed**: the mapped
  case number now counts as an exact match, and those passages are added as candidates (only for people who
  may see them).
- Pinned passages were exempt from the 2-per-document cap, so a named judgment filled all 5 places. **Fixed**:
  pins count toward the cap (FR-004); they still come first.
- Re-run after both fixes: the measurements above are unchanged.
