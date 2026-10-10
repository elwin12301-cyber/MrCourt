# Quickstart results: AI Assistant Upgrade (004)

Run on 2026-10-08.

| Suite | Result |
|-------|--------|
| Backend (pytest) | 412 passed |
| Frontend unit (Vitest) | 15 passed |
| Type check and lint | clean |
| End-to-end, desktop and mobile (Playwright, includes accessibility) | 354 passed in the last run; the run before had 353 passed and 1 flaky (passed on retry) |

Baseline before this feature: backend 334, unit 9, end-to-end 294.

## Notes

- **Flaky tests.** Under four parallel browsers a sign-in request occasionally stalls for over 15 seconds (seen in
  different tests each run, mostly the first test of a file on the phone-sized project). Two things were changed:
  a one-time warm-up before the tests (the dev server compiles pages on first use), and the password hash uses a
  small setting in test environments only. One retry is now allowed everywhere; a retried test is reported as
  flaky, not hidden. The cause of the remaining stall was not found.
- **Search quality is below target.** Retrieval finds the right page and facts for about 72% of the reference
  questions (target 90%). See [quality-results.md](quality-results.md).
- **The assistant was exercised with a scripted stand-in for the model**, never the live Claude API.
- A new accessibility finding was fixed: the knowledge table's sideways-scroll region was not reachable by keyboard.

## Not verified (needs a person)

- T052: legal and policy review of sending questions and case details to a third-party AI service, retention of
  question history, and administrator access to it.
- The live model path (answers and assistant) with a real `ANTHROPIC_API_KEY`.
- PostgreSQL, still never run.
