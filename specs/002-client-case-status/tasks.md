---

description: "Task list for Client Case Status (My Lawyer, My Case)"
---

# Tasks: Client Case Status ("My Lawyer, My Case")

**Input**: Design documents from `/specs/002-client-case-status/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml, quickstart.md. This feature extends feature 001 (all of its tasks are complete), so every path below is an existing or new file in the same repository.

**Tests**: Included. The riskiest failure is exposing something private to a client, so leak-prevention and role-separation tests are written first. Write each story's tests first and confirm they fail before implementing.

**Organization**: Tasks are grouped by user story. Stories US1, US4 and US2 are all P1. They are ordered US1 (what the client sees), US4 (how the advocate feeds it), US2 (messaging), then US3 and US5 (both P2).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1 to US5)
- Paths are relative to the repository root. Backend source is `backend/src/mrcourt/`, frontend source is `frontend/src/`.

## Working notes

- Edit files with the Edit tool or a UTF-8 aware script; do not round-trip files through PowerShell `Get-Content`/`Set-Content` (it corrupts non-ASCII characters).
- Client screens must only call `/client/*` endpoints and never receive private fields (plan R1).
- Content files are marked UNVERIFIED until a lawyer reviews them (T070).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the starting point

- [X] T001 Run the baseline before changing anything: `backend` pytest, `frontend` Vitest, and the Playwright suite must all pass; record the counts in `specs/002-client-case-status/baseline.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Data model, migration, shared services and shared UI that every story needs

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T002 Add the new columns to the existing models: `client_status`, `client_status_changed_at`, `client_status_changed_by` on `Case` and `shared_with_client` on `Document` and `outcome_shared` on `Hearing` in `backend/src/mrcourt/models/case.py`; `accepted_at` on `CaseInvitation` in the same file; `client_contact` (JSON, default empty) on `UserSettings` in `backend/src/mrcourt/models/user.py`
- [X] T003 [P] Create `TimelineEntry`, `ClientUpdate` and `ClientQuestion` models per data-model.md in `backend/src/mrcourt/models/client.py` and export them from `backend/src/mrcourt/models/__init__.py`
- [X] T004 Write Alembic revision `0002` that adds the columns and tables for both SQLite (batch mode) and PostgreSQL, and backfills `accepted_at` for already accepted invitations, in `backend/alembic/versions/0002_client_case_status.py` (depends on T002, T003)
- [X] T005 [P] Create all client schemas (status enum, client case and dashboard read models, updates, questions, contact card, advocate request bodies) per contracts/openapi.yaml in `backend/src/mrcourt/schemas/client.py`
- [X] T006 Implement the shared status and timeline core in `backend/src/mrcourt/services/client_status.py`: status labels, `record_entry` (always-visible kinds are stored shared, advocate-controlled kinds default to private) and `notify_clients` (one update per accepted client) (depends on T003)
- [X] T007 [P] Add the `require_client` dependency (petitioners only) in `backend/src/mrcourt/api/deps.py` and `get_client_case` (accepted invitation or 404) in `backend/src/mrcourt/services/access.py`
- [X] T008 Set `accepted_at` when an invitation is accepted in `backend/src/mrcourt/services/invitations.py` (depends on T002)
- [X] T009 Extend the seed in `backend/src/mrcourt/seed.py`: client statuses and change dates, timeline entries, one shared and one internal document, a private note, a shared and an unshared hearing outcome, an advocate contact card, a second client (Ravi Mehta) on the first case, and a client question with reply (depends on T002, T003)
- [X] T010 [P] Create the client data layer in `frontend/src/services/client.ts`: types for the client case, dashboard, updates and questions, and TanStack Query hooks (`useClientDashboard`, `useClientCase`)
- [X] T011 [P] Give petitioners their own navigation (Dashboard, My cases, Updates, Ask MrCourt, Settings) and keep advocate navigation unchanged in `frontend/src/components/AppShell.tsx`
- [X] T012 [P] Add end-to-end helpers in `frontend/tests/e2e/support/helpers.ts`: create a throwaway advocate with a case, invite and accept a throwaway client, and return separate browser contexts for each, so tests never share data
- [X] T013 [P] Create shared client UI components `ClientStatusChip.tsx` (four statuses, text plus colour) and `Explain.tsx` ("What does this mean?" disclosure using the glossary) in `frontend/src/components/`

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - See where my case stands (Priority: P1) 🎯 MVP

**Goal**: A client signs in to a dashboard made for them and sees each case's plain-language status, next hearing with a general description, and a timeline.

**Independent Test**: Sign in as the seeded client; confirm the client dashboard (not the advocate one), the case's status and date changed, the next hearing with date, time, court and description, and a newest-first timeline, with correct empty states.

### Tests for User Story 1

- [X] T014 [P] [US1] Contract tests for `GET /client/dashboard`, `GET /client/cases/{id}` and the shared-document download, including 403 for advocates and 404 for non-clients, in `backend/tests/contract/test_client_view.py`
- [X] T015 [P] [US1] Leak-prevention tests: for a case holding a private note, an internal document, an unshared outcome and another client's question, no client endpoint response contains any of them, in `backend/tests/integration/test_client_leaks.py`
- [X] T016 [P] [US1] Unit tests for hearing descriptions (matches by purpose, then case stage, otherwise nothing; never mentions case facts or outcomes) in `backend/tests/unit/test_hearing_descriptions.py`

### Implementation for User Story 1

- [X] T017 [P] [US1] Write the reviewed-content files `hearing_descriptions.json` and `glossary.json`, both marked `UNVERIFIED` with the production refusal rule, in `backend/src/mrcourt/corpus/data/`
- [X] T018 [US1] Implement description selection (purpose keyword, then case stage, else none; label and disclaimer included; refuses UNVERIFIED content in production) in `backend/src/mrcourt/services/hearing_descriptions.py` (depends on T017)
- [X] T019 [US1] Implement the client read model builder as an explicit allow-list (status, next hearing, hearing history, visible timeline, shared documents, access info, lawyer card) in `backend/src/mrcourt/services/client_view.py` (depends on T006, T007, T018)
- [X] T020 [US1] Implement `GET /client/dashboard`, `GET /client/cases/{id}` and `GET /client/cases/{id}/documents/{docId}/download` (shared only) in `backend/src/mrcourt/api/client.py` and register the router in `backend/src/mrcourt/main.py` (depends on T019)
- [X] T021 [P] [US1] Implement `GET /glossary` in `backend/src/mrcourt/api/glossary.py` and register it in `backend/src/mrcourt/main.py`
- [X] T022 [US1] Build the client dashboard (greeting, my cases with status, next hearing, empty state explaining how invitations work) in `frontend/src/pages/ClientDashboard.tsx` (depends on T010, T013)
- [X] T023 [P] [US1] Build "My cases" (card list with status chip, next hearing, last status change) in `frontend/src/pages/ClientCases.tsx`
- [X] T024 [US1] Build the client case page (status and date, next hearing with description, hearing history, shared documents, "not set yet" and "no hearing scheduled yet" states) in `frontend/src/pages/ClientCaseDetail.tsx` (depends on T025)
- [X] T025 [P] [US1] Build the newest-first timeline component in `frontend/src/components/Timeline.tsx`
- [X] T026 [US1] Make `/dashboard`, `/cases` and `/cases/:id` render the client screens for petitioners and the existing screens for advocates in `frontend/src/App.tsx` (depends on T022, T023, T024)
- [X] T027 [US1] End-to-end test for the client journey, empty states, keyboard-only use and no horizontal scrolling at 360px in `frontend/tests/e2e/client.spec.ts`

**Checkpoint**: A client can see where their case stands

---

## Phase 4: User Story 4 - Advocate controls what the client sees (Priority: P1)

**Goal**: An advocate sets the client-facing status, posts short updates and decides what is shared; private items never reach clients.

**Independent Test**: As an advocate, set a status, post an update, share one document and keep another internal; as the client, confirm only the status, update and shared document appear.

### Tests for User Story 4

- [X] T028 [P] [US4] Contract tests for `PUT /cases/{id}/client-status`, `POST /cases/{id}/client-updates`, the timeline, sharing and outcome endpoints, invitations list and `PUT /me/client-contact` in `backend/tests/contract/test_client_admin.py`
- [X] T029 [P] [US4] Rules tests: new items default to private, unsharing hides immediately without a notice, choosing Closed closes the case, same status twice does nothing, only the owning advocate can act, petitioners get 403, in `backend/tests/integration/test_sharing_rules.py`

### Implementation for User Story 4

- [X] T030 [US4] Implement `set_client_status` (writes a timeline entry, closes or reopens the case, no-op on the same value) in `backend/src/mrcourt/services/client_status.py` (depends on T006)
- [X] T031 [US4] Implement share and unshare for documents, hearing outcomes and notes, and posting a client update, in `backend/src/mrcourt/services/client_status.py` (same file as T030, run after it)
- [X] T032 [US4] Create timeline entries and notify clients when a hearing is scheduled or rescheduled in `backend/src/mrcourt/services/hearings.py` (depends on T006)
- [X] T033 [US4] Implement the advocate endpoints from contracts/openapi.yaml (status, updates, timeline get and post, sharing, outcome, invitations list, contact card) in `backend/src/mrcourt/api/client_admin.py` and register the router in `backend/src/mrcourt/main.py` (depends on T030, T031, T032)
- [X] T034 [P] [US4] Create the advocate-side data hooks in `frontend/src/services/clientAdmin.ts`
- [X] T035 [US4] Build the "Client view" panel on the advocate case page (status picker, post update, internal timeline with share toggles) in `frontend/src/components/ClientViewPanel.tsx` and add it to `frontend/src/pages/CaseDetail.tsx` (depends on T034)
- [X] T036 [P] [US4] Add "Share with client" controls to documents and a hearing outcome form with a share option in `frontend/src/components/OutcomeForm.tsx` and the documents card of `frontend/src/pages/CaseDetail.tsx`
- [X] T037 [P] [US4] Build the contact card form (phone, email, office; empty means hidden) in `frontend/src/components/ContactCardForm.tsx` and add it to `frontend/src/pages/Settings.tsx`
- [X] T038 [US4] Show the invited clients with their state and a remove button in the case's invite section of `frontend/src/pages/CaseDetail.tsx` (depends on T033)
- [X] T039 [US4] End-to-end privacy test: advocate adds a private note and internal document, client never sees them; unsharing removes a document and its link, in `frontend/tests/e2e/client-privacy.spec.ts` (depends on T026, T035, T036)

**Checkpoint**: Advocates can feed the client view, and privacy rules are proven end to end

---

## Phase 5: User Story 2 - Know who my lawyer is and ask them something (Priority: P1)

**Goal**: A client sees their lawyer's details and can send a question or ask for an update, then see the reply.

**Independent Test**: As a client, view the lawyer card, send a question, see it as Sent; as the advocate, reply; as the client, see the reply marked new. A second client on the same case sees none of it.

### Tests for User Story 2

- [X] T040 [P] [US2] Contract tests for client questions on both sides (send, list own, advocate list, reply once, empty and over-long rejected, rate limit, lawyer unavailable) in `backend/tests/contract/test_client_questions.py`
- [X] T041 [P] [US2] Multi-client privacy tests: a client never sees another client's questions, replies or read states, and removing one client leaves the other's access, in `backend/tests/integration/test_client_question_privacy.py`

### Implementation for User Story 2

- [X] T042 [US2] Implement send, list own, advocate list, reply and mark-reply-read, filtering by client id in one query function, in `backend/src/mrcourt/services/client_questions.py`
- [X] T043 [US2] Add `GET` and `POST /client/cases/{id}/questions` to `backend/src/mrcourt/api/client.py` and `GET /cases/{id}/client-questions` plus `POST /client-questions/{id}/reply` to `backend/src/mrcourt/api/client_admin.py` (depends on T042)
- [X] T044 [P] [US2] Build the lawyer card (name, verified or pending, only filled contact fields, "no longer available") in `frontend/src/components/LawyerCard.tsx`
- [X] T045 [P] [US2] Build the ask-your-lawyer box (question, "Ask for an update", sent list showing only "Sent" or the reply) in `frontend/src/components/AskLawyer.tsx`
- [X] T046 [US2] Place the lawyer card and ask box on the client case page and a "My lawyer" panel on the client dashboard in `frontend/src/pages/ClientCaseDetail.tsx` and `frontend/src/pages/ClientDashboard.tsx` (depends on T044, T045)
- [X] T047 [US2] Add the advocate's client questions inbox with a reply form to `frontend/src/components/ClientViewPanel.tsx` (depends on T043)
- [X] T048 [US2] End-to-end test of ask, reply and two-client privacy in `frontend/tests/e2e/client-questions.spec.ts`

**Checkpoint**: Clients can reach their lawyer inside MrCourt

---

## Phase 6: User Story 3 - Be told when something changes (Priority: P2)

**Goal**: Clients see updates with an unread indicator when the advocate changes anything they can see.

**Independent Test**: As the advocate, change the status and reschedule a hearing; as the client, see both as unread updates within a minute without reloading, and see the count drop when viewed.

### Tests for User Story 3

- [X] T049 [P] [US3] Contract tests for `GET /client/updates`, mark read and read all in `backend/tests/contract/test_client_updates.py`
- [X] T050 [P] [US3] Fan-out tests: one update per accepted client, unsharing creates none, a removed client loses their updates, read states are independent, in `backend/tests/integration/test_update_fanout.py`

### Implementation for User Story 3

- [X] T051 [US3] Implement `GET /client/updates`, `POST /client/updates/{id}/read` and `POST /client/updates/read-all`, and include the unread count in the dashboard, in `backend/src/mrcourt/api/client.py`
- [X] T052 [US3] Create a `question_reply` update when an advocate replies, and remove a client's updates when their invitation is removed, in `backend/src/mrcourt/services/client_questions.py` and `backend/src/mrcourt/services/invitations.py`
- [X] T053 [P] [US3] Build the Updates page and an unread badge with a text count in `frontend/src/pages/Updates.tsx` and `frontend/src/components/AppShell.tsx`, and add the `/updates` route in `frontend/src/App.tsx`
- [X] T054 [US3] Refresh the unread count every 30 seconds and on window focus (interval configurable through `VITE_UPDATES_POLL_MS` so tests can shorten it) in `frontend/src/services/client.ts`
- [X] T055 [US3] Show the latest updates on the client dashboard in `frontend/src/pages/ClientDashboard.tsx`
- [X] T056 [US3] End-to-end test: advocate acts, client's badge appears without reloading and clears when viewed, in `frontend/tests/e2e/client-updates.spec.ts`

**Checkpoint**: Clients no longer need to keep checking

---

## Phase 7: User Story 5 - Know my privacy and ask general legal questions safely (Priority: P2)

**Goal**: Clients can see who can view their case, and Ask MrCourt gives general information only, pointing to the lawyer for case-specific advice.

**Independent Test**: As a client, view the access information; ask a general question and a "should I accept this offer in my case" question; confirm citations and the disclaimer on both, the lawyer reminder on every answer, and the specific notice on the second.

### Tests for User Story 5

- [X] T057 [P] [US5] Unit tests for the advice guard (flags "my case", "should I accept", "will I win"; does not flag general questions) in `backend/tests/unit/test_advice_guard.py`
- [X] T058 [P] [US5] Contract tests: petitioner answers contain `lawyer_reminder` always and `case_specific_notice` when flagged; advocates do not get them, in `backend/tests/contract/test_questions_client.py`
- [X] T059 [P] [US5] Deletion tests: a deactivated client's questions, updates and invitations are removed while the advocate's timeline stays; an advocate's deactivation leaves clients a clear message; the data export includes client data, in `backend/tests/integration/test_client_privacy_deletion.py`

### Implementation for User Story 5

- [X] T060 [US5] Implement the heuristic detector in `backend/src/mrcourt/services/advice_guard.py`
- [X] T061 [US5] Add `case_specific_notice` and `lawyer_reminder` for petitioners in `backend/src/mrcourt/api/questions.py` and `backend/src/mrcourt/schemas/questions.py` (depends on T060)
- [X] T062 [P] [US5] Show the notice and the standing reminder, with a one-step link to ask the lawyer, in `frontend/src/components/ChatMessage.tsx`, `frontend/src/pages/Ask.tsx` and `frontend/src/services/questions.ts`
- [X] T063 [P] [US5] Build the "Who can see my case" panel (advocate name, since when, number of other people) in `frontend/src/components/AccessPanel.tsx` and place it on `frontend/src/pages/ClientCaseDetail.tsx`
- [X] T064 [US5] Extend deactivation and data export for the new personal data in `backend/src/mrcourt/services/privacy.py` (depends on T059)
- [X] T065 [US5] End-to-end test of the access panel and both kinds of Ask question in `frontend/tests/e2e/client-ask.spec.ts`

**Checkpoint**: All user stories are independently functional

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates that span stories

- [X] T066 [P] Extend the accessibility scans to every client screen and the Client view panel in both themes at 360px and 1280px in `frontend/tests/e2e/a11y.spec.ts`
- [X] T067 [P] Audit client-facing wording for jargon and add `Explain` disclosures where legal terms remain (FR-019) across `frontend/src/pages/ClientCaseDetail.tsx` and `frontend/src/pages/ClientCases.tsx`
- [X] T068 [P] Document the client experience, the new migration and the content-review caveat in `README.md`
- [X] T069 Run the quickstart scenarios and record results in `specs/002-client-case-status/quickstart-results.md`
- [ ] T070 Obtain legal review of `hearing_descriptions.json` and `glossary.json`, then remove their UNVERIFIED marking (a person with legal expertise must do this)
- [X] T071 Run the full regression: backend pytest, Vitest, lint, type checks and the whole Playwright suite must pass twice in a row, with the counts added to `specs/002-client-case-status/quickstart-results.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Setup; blocks all user stories
- **US1 (Phase 3)**: depends on Foundational. It is the MVP: a client can see their case (statuses come from the seed)
- **US4 (Phase 4)**: depends on Foundational; its end-to-end test (T039) also needs US1's screens
- **US2 (Phase 5)**: depends on US1 (client case page) and on US4 (the inbox lives in the Client view panel)
- **US3 (Phase 6)**: depends on US4 (the advocate actions that create updates) and US1 (dashboard)
- **US5 (Phase 7)**: depends on US1 (case page for the access panel); the Ask changes are independent of US2 to US4
- **Polish (Phase 8)**: depends on all stories

### Within Each Story

- Tests first, confirmed failing
- Models and migration (Phase 2), then services, then endpoints, then screens
- Tasks that touch the same file run in order (`client_status.py` T006, T030, T031; `client.py` T020, T043, T051; `ClientViewPanel.tsx` T035, T047; `ClientCaseDetail.tsx` T024, T046, T063; `CaseDetail.tsx` T035, T036, T038; `AppShell.tsx` T011, T053; `ClientDashboard.tsx` T022, T046, T055)

### Parallel Opportunities

- Foundational: T003, T005, T007, T010, T011, T012 and T013 touch different files
- After Foundational, US1 and US4 backend work can proceed in parallel (separate routers), as can US5's Ask changes
- Within a story, all tasks marked [P]

### Parallel Example: User Story 1

```text
Task: "Contract tests in backend/tests/contract/test_client_view.py"
Task: "Leak-prevention tests in backend/tests/integration/test_client_leaks.py"
Task: "Hearing description unit tests in backend/tests/unit/test_hearing_descriptions.py"
Task: "Content files in backend/src/mrcourt/corpus/data/"
Task: "Timeline component in frontend/src/components/Timeline.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 and Phase 2
2. Phase 3 (US1): a client can see where their case stands
3. **STOP and VALIDATE**: quickstart scenario 1 and the leak tests (T015)
4. Demo

### Incremental Delivery

1. Foundation, then US1 (MVP)
2. US4 so advocates can drive the client view, then US2 for questions
3. US3 for updates, then US5 for the safer Ask and privacy
4. Polish, the content review (T070) and the full regression before release

---

## Notes

- [P] tasks = different files, no dependencies
- The [Story] label maps each task to its user story for traceability
- Never expose notes, internal documents or unshared outcomes through any client endpoint; the leak tests (T015, T041) guard this and must stay green
- Commit after each task or logical group
