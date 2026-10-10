# Results: Knowledge Assistant design for every role (006)

Run on 2026-10-08.

| Suite | Result |
|-------|--------|
| Backend (pytest) | 478 passed |
| Frontend unit (Vitest) | 15 passed |
| Type check and lint | clean |
| End-to-end (desktop and phone width, includes accessibility) | 394 passed in one full run; 392 passed and 2 flaky (passed on retry) in the next |

## Notes

- Layout, wording and controls follow the reference screen; colours and fonts are MrCourt's tokens (navy buttons, gold accents), as the constitution requires.
- Fixed a long-standing test flaw found along the way: some admin tests clicked the first row of a list right after searching, while the list still showed the old rows, and so sometimes edited the seeded client Anita. That caused bursts of unrelated client and accessibility test failures. They now click the intended row.
- Sign-in in the tests now retries a stalled request up to three times.

## Not verified (needs a person)

- T009: administrators can list everyone's questions (without answers, recorded in the audit log); this should be reviewed against the DPDP Act and policy.
- Everything noted in the earlier results (OCR not run for real, live microphone, Tamil by meaning, privacy review, rotating the keys).
