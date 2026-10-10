# Retrieval quality on the reference question set (feature 005)

Measured 2026-10-08 with `backend/scripts/import_reference.py`, using the real Voyage AI embedding and rerank services (vectors and scores were cached outside the repository).

**Data**: the two readable English court documents from the earlier RAG project (a 14-page second-appeal judgment and a 7-page writ order, 22 passages). **Questions**: the 39 English lawyer questions for the judgment, with expected page and answer. A question counts as found when one of the top 5 passages is on an expected page and those passages contain at least half of the significant words of the expected answer.

| Search | Right page | Answer facts | Found (both) |
|--------|-----------|--------------|--------------|
| Keywords only (feature 004) | 28 of 39 (72%) | 30 of 39 (77%) | 26 of 39 (**67%**) |
| Keywords + meaning + rerank (this feature) | 36 of 39 (92%) | 35 of 39 (90%) | 34 of 39 (**87%**) |

**Target (SC-001): 90% found. Almost met: 87% on the strict combined measure; right page 92% and facts 90% separately.**

## How the safety of "no reliable source" was kept

Raw meaning similarity could not tell relevant questions from unrelated ones (relevant best similarity min 0.21, unrelated up to 0.48). So a reranker judges the candidates and a meaning-only passage is cited only when it scores at least `MIN_RERANK_SCORE` = 0.5.

| | Best rerank score |
|--|--|
| Relevant questions | min 0.44, 10th percentile 0.50, median 0.70 |
| Unrelated questions (8 samples) | max 0.46, median 0.30 |

The ranges overlap slightly (0.44 to 0.46), so 0.5 was chosen to keep every unrelated sample out; that costs the one or two relevant questions that score just under it. If the reranker is unavailable, only passages with keyword evidence are used.

## What is still missed

- "Who appeared for the parties?" and "To whom was the judgment communicated?": the answer sits in short header or footer lines the reranker scores just under 0.5, so nothing is cited.
- "Under which provision was the second appeal filed?" and the "AB line" question: the right page is found but not enough of the answer's wording is in the top passages.
- "What should the defendant have done at the time of purchase?": the answer is inferred rather than stated.

## Caveats

- Eight unrelated questions and 39 relevant ones are a small sample; the threshold should be rechecked on the owner's own documents.
- Tamil questions were not scored here (the question file is the English one); Tamil search by meaning is covered by tests with a stand-in only.
- Voyage's free tier allows a few requests a minute and each question uses two (embed and rerank), so under that limit questions fall back to keyword search. A payment method on the Voyage account removes the limit.
