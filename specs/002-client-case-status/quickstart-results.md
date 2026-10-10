# Quickstart validation results: Client Case Status

Run on 2026-10-08 against SQLite (no PostgreSQL available), with the built-in answer writer (no model API
key), the development content files (marked UNVERIFIED) and the seeded fictional data. Evidence is cited by
test file. Items under "Not verified" were not checked.

| # | Scenario | Result | Evidence |
|---|----------|--------|----------|
| 1 | See where my case stands (Story 1) | Pass | `frontend/tests/e2e/client.spec.ts` (client dashboard, My cases, case page, timeline order, empty states, "not shared yet", keyboard use, no horizontal scroll); `backend/tests/contract/test_client_view.py` |
| 2 | Know my lawyer and ask (Story 2) | Pass | `client-questions.spec.ts` (lawyer card shows only filled details; send, reply, reply labelled new; "Ask for an update"; lawyer deactivated); `test_client_questions.py` |
| 3 | Be told when something changes (Story 3) | Pass, with a note on timing | `client-updates.spec.ts` (the badge appears without reloading; every kind of change produces a notice; unsharing produces none; mark all read; per-client read state; removed client loses the case and updates); `test_update_fanout.py`. The browser tests use a 3-second refresh; the production default of 30 seconds was not run in a browser |
| 4 | Advocate controls (Story 4) | Pass | `client-privacy.spec.ts` (private note and internal document never reach the client; sharing and unsharing a document including its direct download link; outcome private until shared; status and hearing dates cannot be hidden); `test_sharing_rules.py`; `test_client_leaks.py` |
| 5 | Privacy and general questions (Story 5) | Pass, with a limit | `client-ask.spec.ts`, `test_questions_client.py`, `test_advice_guard.py`. The "own case" detector is keyword-based; the standing reminder on every client answer is the backstop |
| 6 | Hearing descriptions (FR-021) | Pass for behaviour. Content not reviewed | `test_hearing_descriptions.py` (general wording only, no numbers or advice phrases, none when there is no basis, off in production while UNVERIFIED); `client.spec.ts` |
| 7 | Two clients on one case | Pass | `client-questions.spec.ts` (each sees only their own questions and replies); `test_client_question_privacy.py`; `test_client_leaks.py` |
| 8 | Deactivation | Pass in the API tests. No browser run of a client deactivating | `test_client_privacy_deletion.py` (client data removed, case records kept, advocate's view of the inbox, export contents); the advocate-side deactivation flow in the browser is covered by feature 001's `settings.spec.ts` |

## Success criteria

| Criterion | Status |
|-----------|--------|
| SC-002: no private item visible to a client | Held in every automated check (leak tests across every client endpoint, browser checks of page text). A review of real screens by a person has not been done |
| SC-004: updates within a minute | Design supports it (30-second refresh plus refresh on focus). Not timed with the production interval |
| SC-006: WCAG 2.1 AA in both themes at 360px and 1280px | Pass: 44 accessibility scans across advocate, client and empty-state screens |
| SC-007: disclaimer and lawyer reminder on every client answer | Pass in tests. The "own case" notice depends on the keyword check |
| SC-001, SC-003, SC-005, SC-008 | Need real people and a stopwatch; not measured |

## Regression (T071)

| Check | Result |
|-------|--------|
| Backend (pytest) | 264 passed |
| Frontend unit (Vitest) | 9 passed |
| Types (tsc) and lint (ESLint) | Clean |
| Browser tests (Playwright, desktop and phone) | 196 passed, two consecutive full runs |

Before this feature: 119 backend, 9 unit and 106 browser tests (`baseline.md`).

## Not verified

- Migration `0002` on PostgreSQL. It was run on SQLite for a fresh database and for an old-shape database
  (downgrade then upgrade), but never on PostgreSQL.
- The hearing descriptions and the glossary have not been reviewed by a lawyer (task T070).
- Behaviour on real phones and with real WhatsApp delivery.
- Time-based success criteria (SC-001, SC-003, SC-005, SC-008) with real users.

## Behaviour change to know about

Clients can no longer call the advocate endpoints (`/cases`, `/dashboard` and similar). In feature 001
they could, and those responses included internal documents and every hearing outcome. Two feature-001 backend tests and one browser test that relied on the old behaviour were updated to the new rule; two more backend tests were adjusted only because the richer seed data changed a count.
