# Results: hybrid ranking (feature 009)

Date: 2026-10-13. Development database: PostgreSQL 16 + pgvector (Docker). Measurements of ranking quality and
speed are in `eval-results.md`.

## Regression (T036)

- Backend: **641 passed** (adds the assistant ranking record, case-number matching and pinned-passage cap
  tests).
- Frontend: TypeScript and ESLint clean; Vitest 15 passed.
- Browser (Playwright, desktop and phone): **440 passed**, none flaky (4.2 minutes). An earlier run the same day had
  2 flaky tests (sign-up phone code, voice), both passing on retry and outside this feature.

## Behaviour checks in the running app (T037, quickstart §3)

Run against the development API with the real search services (`scratchpad` script, accounts from the seed).

| # | Check | Outcome |
|---|---|---|
| 1 | Advocate asks "What does Section 379 IPC say?" → first citation is IPC s. 379 | **Partly.** First citation is the IPC class notes on theft (illustrations of s. 378/379), labelled "Statute". The corpus has no passage that is IPC s. 379 itself (only a CrPC page that mentions it), so nothing can be pinned. Needs the bare IPC text. |
| 2 | "Section 999 IPC" → answer says the section was not found | **Pass.** "Not found in the sources: Section 999 IPC. The sources below are related, not that provision." |
| 3 | "How have courts decided …" → judgments first; at most 2 citations from one document | **Pass for the cap** (5 citations, at most 2 per document). Judgments first cannot be seen: the shared corpus has no judgments, only notes and statutes. |
| 4 | Client asks about a private case document's number → no private source cited | **Pass.** Two questions naming the case numbers of the advocate's private judgment and order: 0 private sources cited. |
| 4b | The owning advocate asks the same | **Pass after a fix.** Before: none of their own documents were cited (see below). After: 2 passages of their judgment, then other sources. |
| 5 | Administrator opens an answer → scores and signals; another advocate's private passage hidden | **Pass.** Mode, question type, scores and signals shown; the advocate's private passages appear as hidden rows without label or the named-reference signal. |

## Fixed during these checks

- **Named case not found for its owner**: only the first page of a judgment carries the case number, and the
  mapped case number (feature 008) was not used. Now a case number in the question matches the document's
  mapped case number (exact), and those passages become candidates for people who may see them.
- **Pins ignored the 2-per-document cap**, so a named judgment could fill all 5 places. Pins now count toward
  the cap (FR-004) and still come first.
- **Assistant answers did not record the explanation** (T027): now kept, for each cited passage, from the first
  search that ranked it.
- **Shortlist for the answer check** used the final weights (see `eval-results.md`).
- **Extra database queries** per search (see `eval-results.md`, latency).

## Open

- Targets not met on this corpus: differently-worded questions in the top 5 (84%, target 90%) and exact
  reference first (85%, target 100%). Both need statute texts mapped section by section; Tamil questions need
  Tamil sources.
- Latency is within the limit on the median (+8.9%) but not on the mean (+13%).
- Questions such as "What was decided in S.A. <number>/<year>?" are classed as "courts", not "my case"; the named
  case is still pinned, so the outcome is right.
