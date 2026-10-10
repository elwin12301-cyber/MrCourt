# Quickstart results: Administrator console (003)

Run on 2026-10-08.

| Suite | Result |
|-------|--------|
| Backend (pytest) | 334 passed |
| Frontend unit (Vitest) | 9 passed |
| Type check and lint | clean |
| End-to-end, desktop and mobile (Playwright, includes accessibility and visual checks) | 294 passed, twice in a row |

## Notes

- Fixed a flaky feature 002 test: the advocate's status panel was recreated whenever the status changed,
  which discarded its "Status updated" message. It now keeps the message. The test passed 20 of 20 repeats
  in parallel afterwards.
- One earlier full run had a single failure in "advocate and client screens are closed to the administrator".
  It passed 12 of 12 repeats on its own and in the next two full runs, and could not be reproduced. It looks
  like load-related timing, not a defect. Watch for it.

## Not verified (needs a person)

- T032: legal and policy review of the administrator's broad read access to private case content, against the
  DPDP Act and the organisation's policy. The audit log is the control; it has not been reviewed by anyone.
- PostgreSQL has not been run; all tests use SQLite.
