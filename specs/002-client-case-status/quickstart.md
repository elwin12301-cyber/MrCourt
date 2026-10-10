# Quickstart: Validating Client Case Status

Run-and-check guide. Data shapes are in [data-model.md](data-model.md) and endpoints in [contracts/openapi.yaml](contracts/openapi.yaml). Setup is the same as feature 001 (see the repository README); rebuild the development database after pulling this feature so revision `0002` and the new seed data are applied.

## Prerequisites

- The 001 application running (`http://localhost:5173` and the API on port 8000)
- Seeded development accounts: advocate `rohan.sharma@example.com`, client `anita.sharma@example.com`, a second client created during the scenarios (password `password123` for seeded accounts)
- The reviewed hearing descriptions file loaded (the development copy is marked UNVERIFIED)

## Validation scenarios

Each maps to a user story in the spec.

1. **See where my case stands (Story 1)**: sign in as the seeded client. Expect the client dashboard (not the advocate one) with the invited case, its plain-language status, the next hearing with date, time and court, and the date the status last changed. Open the case and confirm the timeline reads newest first. Check a case with no status shows "Your lawyer has not shared a status yet", and a case with no hearing shows "No hearing scheduled yet".
2. **Know my lawyer and ask (Story 2)**: on the case, confirm "My lawyer" shows name and verification status and only the contact fields the advocate filled in. Send a question; expect it listed as "Sent" with no promised response time. As the advocate, open the case's client questions, reply, then as the client confirm the reply appears and is marked new.
3. **Be told when something changes (Story 3)**: as the advocate, change the status, reschedule a hearing, record and share an outcome, share a document and post an update. As the client, expect each as an update with an unread count that drops when viewed, within one minute and without reloading.
4. **Advocate controls (Story 4)**: as the advocate, add a private note and an internal document. As the client, confirm neither appears anywhere (case page, timeline, downloads, API responses). Unshare the shared document and confirm its link stops working.
5. **Privacy and general questions (Story 5)**: as the client, open "Who can see my case" (advocate name, since when, number of other people). In Ask MrCourt, ask "What is the punishment under Section 138?" and expect a cited answer, the disclaimer and the standing reminder to ask their lawyer. Ask "Should I accept the settlement offer in my case?" and expect general information at most plus "MrCourt cannot advise on your case. Please ask your lawyer."
6. **Hearing descriptions (FR-021)**: confirm a hearing with purpose "Evidence" shows the general description labelled "General information" with the disclaimer, and a hearing with no recorded purpose shows only date, time and court.
7. **Two clients on one case**: invite a second client, have both ask a question. Each sees only their own question, reply and unread state; both see the same status, hearings and shared items.
8. **Deactivation**: deactivate the second client. Their questions and updates are removed; the first client and the advocate's records are unaffected.

## Automated checks

- Backend: contract tests for every new endpoint; **leak tests** that call every client endpoint for a case holding private notes, an internal document, an unshared outcome and another client's question, and assert none appear; role tests (petitioners get 403 on advocate endpoints; advocates get 404 for other advocates' cases); advice-guard cases for the detector and the standing reminder.
- Frontend: component tests for the status chip, timeline and unread badge.
- End to end: Playwright for the client journey, the advocate's Client view panel, keyboard-only use, axe scans of every new screen in both themes at 360px and 1280px, and a check that the client navigation has no advocate-only entries.

## Expected outcomes

- No private note, internal document, unshared outcome or other client's data is ever visible to a client (SC-002).
- The status and next hearing are findable within 15 seconds (SC-001) and updates appear within a minute (SC-004).
- Every client Ask answer carries the disclaimer and the lawyer reminder (SC-007).
