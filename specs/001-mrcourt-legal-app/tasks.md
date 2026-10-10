---

description: "Task list for the MrCourt Legal Assistance App"
---

# Tasks: MrCourt Legal Assistance App

**Input**: Design documents from `/specs/001-mrcourt-legal-app/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml, quickstart.md

**Tests**: Included. The constitution requires tests for both the cited and the "no reliable source" paths, and the plan commits to access-control, accessibility and visual checks. Write each story's tests first and confirm they fail before implementing.

**Organization**: Tasks are grouped by user story. Phase 3 is the sign-in story (US2) and Phase 4 is the Q&A story (US1): both are P1, but Q&A needs a signed-in user, so sign-in is built first.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1 to US5)
- All paths are relative to the repository root

## Path Conventions

- Backend: `backend/src/mrcourt/`, tests in `backend/tests/`
- Frontend: `frontend/src/`, tests in `frontend/tests/`
- Design reference: `design/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create the directory structure from plan.md: `backend/src/mrcourt/{db,models,schemas,api,services,corpus}`, `backend/tests/{contract,integration,unit}`, `frontend/src/{styles,components,pages,services,hooks}`, `frontend/tests/{unit,e2e}`, `design/`
- [X] T002 Copy the prototype HTML, unmodified, to `design/MrCourt Web Prototype.html` (visual source of truth for all UI tasks and screenshot comparison)
- [X] T003 Initialize the Python 3.12 backend in `backend/pyproject.toml` with FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, psycopg, argon2-cffi, python-docx, WeasyPrint, anthropic, pgvector, pytest, httpx
- [X] T004 [P] Initialize the Vite + React 18 + TypeScript frontend in `frontend/package.json` with react-router, @tanstack/react-query, vitest, @testing-library/react, @playwright/test, @axe-core/playwright
- [X] T005 [P] Configure linting and formatting: ruff and mypy in `backend/pyproject.toml`, ESLint and Prettier in `frontend/.eslintrc.cjs` and `frontend/.prettierrc`
- [X] T006 [P] Add `.gitignore` (covering `.env`, `.claude/`, `node_modules`, `__pycache__`, `uploads/`) and `.env.example` listing variable names only (`DATABASE_URL`, `SESSION_SECRET`, `ANTHROPIC_API_KEY`, `EMBEDDING_API_KEY`, `SMS_PROVIDER_*`, `WHATSAPP_PROVIDER_*`) at the repository root
- [X] T007 [P] Add `docker-compose.yml` at the repository root running PostgreSQL 16 with the pgvector extension for development

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T008 Implement environment-based settings in `backend/src/mrcourt/config.py`
- [X] T009 Implement the SQLAlchemy engine, session and declarative base with UUID and timestamp mixins in `backend/src/mrcourt/db/base.py`
- [X] T010 Set up Alembic in `backend/alembic/` with `env.py` reading `DATABASE_URL`
- [X] T011 Create `users`, `user_settings` and `otp_challenges` models per data-model.md in `backend/src/mrcourt/models/user.py`
- [X] T012 [P] Create `cases`, `parties`, `hearings`, `documents` and `case_invitations` models in `backend/src/mrcourt/models/case.py`
- [X] T013 [P] Create `legal_sources`, `questions`, `answers` and `answer_citations` models in `backend/src/mrcourt/models/legal.py`
- [X] T014 [P] Create `drafts`, `draft_exports` and `activity_events` models in `backend/src/mrcourt/models/draft.py` and `backend/src/mrcourt/models/activity.py`
- [X] T015 Generate the initial Alembic migration in `backend/alembic/versions/` covering all models, the pgvector extension, the full-text search vector column and indexes (depends on T011 to T014)
- [X] T016 Implement the FastAPI app factory with router registration and error handlers in `backend/src/mrcourt/main.py`; resources not visible to the user MUST return 404
- [X] T017 Implement password hashing (argon2id) and signed cookie session issue/validate helpers in `backend/src/mrcourt/services/session.py`
- [X] T018 Implement role and ownership policies (advocate owns cases; petitioner reads only cases with an accepted invitation) in `backend/src/mrcourt/services/access.py`
- [X] T019 Implement request dependencies `get_current_user` and `require_advocate` in `backend/src/mrcourt/api/deps.py` (depends on T017, T018)
- [X] T020 [P] Configure structured logging that excludes personal data and question text in `backend/src/mrcourt/logging_config.py`
- [X] T021 [P] Implement a seed command creating fictional users (an advocate, a petitioner, an administrator), cases and hearings in `backend/src/mrcourt/seed.py`
- [X] T022 [P] Port the prototype's CSS variables (light, dark and system theme rules) into `frontend/src/styles/tokens.css`
- [X] T023 [P] Port the prototype's component classes and responsive rules unchanged into `frontend/src/styles/app.css`
- [X] T024 [P] Create the `Icon` component and SVG sprite from the prototype's symbols in `frontend/src/components/Icon.tsx`
- [X] T025 [P] Create shared components `Chip`, `Pill`, `Card`, `Button` and `Disclaimer` in `frontend/src/components/`
- [X] T026 [P] Create the API client (fetch wrapper with cookies and typed errors) in `frontend/src/services/api.ts`
- [X] T027 [P] Implement light/dark/system theme handling with safe persistence in `frontend/src/services/theme.ts`
- [X] T028 Set up routes and an authentication guard in `frontend/src/App.tsx` and `frontend/src/main.tsx` (depends on T026)
- [X] T029 [P] Add Playwright configuration plus helpers for axe scans and screenshot comparison in `frontend/tests/e2e/support/`

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 2 - Choose a role, sign in and reach the dashboard (Priority: P1) 🎯 MVP (with US1)

**Goal**: A visitor picks a role, registers or signs in (password or one-time passcode), reaches the app shell and dashboard, and can sign out.

**Independent Test**: From the welcome screen choose a role, sign in, see the greeting with the user's name, then sign out and return to the welcome screen.

### Tests for User Story 2

- [X] T030 [P] [US2] Contract tests for `/auth/register`, `/auth/login`, `/auth/otp/request`, `/auth/otp/verify`, `/auth/logout` and `GET /me` in `backend/tests/contract/test_auth.py`
- [X] T031 [P] [US2] Integration tests: generic error on bad credentials, 403 for deactivated users, OTP expiry and attempt limit, rate limiting in `backend/tests/integration/test_auth_flows.py`

### Implementation for User Story 2

- [X] T032 [P] [US2] Create request and response schemas in `backend/src/mrcourt/schemas/auth.py`
- [X] T033 [P] [US2] Create the notification provider interface with a console adapter for development in `backend/src/mrcourt/services/notify.py`
- [X] T034 [US2] Implement register, password login, OTP issue/verify and rate limiting in `backend/src/mrcourt/services/auth.py` (depends on T032, T033)
- [X] T035 [US2] Implement the auth endpoints in `backend/src/mrcourt/api/auth.py`
- [X] T036 [US2] Implement `GET /me` and `PATCH /me` in `backend/src/mrcourt/api/me.py`
- [X] T037 [P] [US2] Build the Welcome screen (brand panel, role buttons, disclaimer) matching the prototype in `frontend/src/pages/Welcome.tsx`
- [X] T038 [P] [US2] Build the Login screen (quote panel, password form, "Continue with OTP", back link) in `frontend/src/pages/Login.tsx`
- [X] T039 [P] [US2] Build the account creation form with role selection and Bar Council number for advocates in `frontend/src/pages/Register.tsx`
- [X] T040 [US2] Build the app shell: navy sidebar, nav items, user card, theme toggle, and top bar below 900px in `frontend/src/components/AppShell.tsx`
- [X] T041 [US2] Build the Dashboard greeting header (name and today's date) in `frontend/src/pages/Dashboard.tsx`
- [X] T042 [US2] Wire sign-out and session expiry handling to return to the welcome screen in `frontend/src/services/auth.ts`
- [X] T043 [US2] End-to-end test: welcome, role, login, dashboard, sign out, plus keyboard-only run in `frontend/tests/e2e/auth.spec.ts`

**Checkpoint**: Users can register, sign in and out and see the shell

---

## Phase 4: User Story 1 - Get a cited answer to a legal question (Priority: P1) 🎯 MVP

**Goal**: A signed-in user asks a question and receives an answer where every paragraph has numbered citations, or an explicit "could not find a reliable source" response.

**Independent Test**: Ask a covered question (cheque dishonour) and an uncovered one; the first shows numbered chips and the disclaimer, the second shows the no-source message.

### Tests for User Story 1

- [X] T044 [P] [US1] Contract test for `POST /questions` (outcome, disclaimer always present, empty text returns 422) in `backend/tests/contract/test_questions.py`
- [X] T045 [P] [US1] Unit tests for the citation verifier: missing citation, unmatched section number, low retrieval score, empty retrieval all yield `no_reliable_source` in `backend/tests/unit/test_citation_verifier.py`
- [X] T046 [P] [US1] Reviewed gold set of questions (cited, mixed, out-of-corpus, repealed-law) in `backend/tests/integration/test_answers_gold.py`

### Implementation for User Story 1

- [X] T047 [P] [US1] Create sample corpus files for NI Act s.138 and s.142 and BNSS s.480 and s.483, each with `citation_label` and `source_url`, in `backend/src/mrcourt/corpus/data/sample/*.json`; verify every text against official sources before use
- [X] T048 [P] [US1] Implement the ingestion CLI (parse, embed, store, record `replaced_by` for repealed provisions) in `backend/src/mrcourt/corpus/ingest.py`
- [X] T049 [US1] Implement hybrid retrieval (full-text plus vector, reciprocal rank fusion) in `backend/src/mrcourt/services/retrieval.py`
- [X] T050 [US1] Implement the citation verifier in `backend/src/mrcourt/services/citations.py`
- [X] T051 [US1] Implement grounded answer generation using only retrieved passages with structured output, the verifier fallback and the fixed no-source message, in `backend/src/mrcourt/services/answering.py` (depends on T049, T050)
- [X] T052 [P] [US1] Create question and answer schemas in `backend/src/mrcourt/schemas/questions.py`
- [X] T053 [US1] Implement `POST /questions`, persisting the question, answer and citations, in `backend/src/mrcourt/api/questions.py`
- [X] T054 [P] [US1] Build `SourceChip` and chat message components in `frontend/src/components/SourceChip.tsx` and `frontend/src/components/ChatMessage.tsx`
- [X] T055 [P] [US1] Create the voice input hook with feature detection and a clear fallback message in `frontend/src/hooks/useSpeechInput.ts`
- [X] T056 [US1] Build the Ask MrCourt screen (chat with live region, suggestion pills, input bar, voice button) in `frontend/src/pages/Ask.tsx`
- [X] T057 [US1] Add the dashboard quick-ask card that opens Ask MrCourt with the answered question in `frontend/src/pages/Dashboard.tsx`
- [X] T058 [US1] End-to-end test of cited, no-source, pill, empty-input and voice-unsupported paths in `frontend/tests/e2e/ask.spec.ts`

**Checkpoint**: Cited Q&A works with a signed-in user (MVP complete with US2)

---

## Phase 5: User Story 3 - Track cases and upcoming hearings (Priority: P2)

**Goal**: Advocates manage cases, hearings and documents; the dashboard shows stats, upcoming hearings and activity; Petitioners view invited cases read-only.

**Independent Test**: With seeded data, search and filter cases, open a case from the table and from a dashboard hearing, and confirm a petitioner sees only invited cases.

### Tests for User Story 3

- [X] T059 [P] [US3] Contract tests for `/dashboard`, `/cases`, `/cases/{id}`, hearings, documents and invitations in `backend/tests/contract/test_cases.py`
- [X] T060 [P] [US3] Integration tests for cross-user 404, petitioner read-only access, invitation accept/remove and the `hearing_soon` status derivation in `backend/tests/integration/test_case_access.py`

### Implementation for User Story 3

- [X] T061 [P] [US3] Create case, hearing, document, invitation and dashboard schemas in `backend/src/mrcourt/schemas/cases.py`
- [X] T062 [US3] Implement case CRUD, search by party, CNR number and court, status filter and derived status in `backend/src/mrcourt/services/cases.py`
- [X] T063 [P] [US3] Implement hearing add and reschedule in `backend/src/mrcourt/services/hearings.py`
- [X] T064 [P] [US3] Implement document upload with size and type limits in `backend/src/mrcourt/services/documents.py`
- [X] T065 [P] [US3] Implement invitations, including the owner activity event on acceptance, in `backend/src/mrcourt/services/invitations.py`
- [X] T066 [US3] Implement dashboard stats, upcoming hearings and recent activity in `backend/src/mrcourt/services/dashboard.py`
- [X] T067 [US3] Implement the cases, hearings, documents, invitations and dashboard routers in `backend/src/mrcourt/api/cases.py` and `backend/src/mrcourt/api/dashboard.py`
- [X] T068 [US3] Complete the Dashboard: stat cards, upcoming hearings with date badges, recent activity, empty states, in `frontend/src/pages/Dashboard.tsx`
- [X] T069 [US3] Build the Cases screen (search bar, filter pills, table, keyboard-operable rows, empty message) in `frontend/src/pages/Cases.tsx`
- [X] T070 [US3] Build the Case detail screen (title, CNR, court, status chip, actions, tabs, next hearing, parties, documents) in `frontend/src/pages/CaseDetail.tsx`
- [X] T071 [P] [US3] Build the case, hearing and document upload forms for advocates in `frontend/src/components/CaseForm.tsx`, `frontend/src/components/HearingForm.tsx` and `frontend/src/components/DocumentUpload.tsx`
- [X] T072 [US3] Add the invite-petitioner action for advocates and hide edit controls for petitioners in `frontend/src/pages/CaseDetail.tsx`
- [X] T073 [US3] End-to-end tests for search, filters, open-by-Enter, empty states and petitioner view in `frontend/tests/e2e/cases.spec.ts`

**Checkpoint**: Case tracking works independently

---

## Phase 6: User Story 4 - Prepare and edit an AI-assisted draft (Priority: P2)

**Goal**: Advocates generate drafts from four templates, edit and save them, and export Word or PDF on request.

**Independent Test**: Select each template, edit, save, reload, confirm persistence, the review flag, and both export formats.

### Tests for User Story 4

- [X] T074 [P] [US4] Contract tests for `/drafts`, `/drafts/{id}` and `/drafts/{id}/export` in `backend/tests/contract/test_drafts.py`
- [X] T075 [P] [US4] Integration tests: petitioner gets 403, version increments on save, no export record without an explicit request, export failure leaves the draft unchanged in `backend/tests/integration/test_drafts.py`

### Implementation for User Story 4

- [X] T076 [P] [US4] Define the Legal Notice, Bail Application, Reply to Notice and Affidavit templates with slots and bracketed placeholders for unknown facts in `backend/src/mrcourt/services/draft_templates.py`
- [X] T077 [US4] Implement draft generation from template and case data in `backend/src/mrcourt/services/drafting.py` (depends on T076)
- [X] T078 [P] [US4] Implement Word and PDF export in `backend/src/mrcourt/services/export.py`
- [X] T079 [P] [US4] Create draft schemas in `backend/src/mrcourt/schemas/drafts.py`
- [X] T080 [US4] Implement the drafts router, recording each export in `draft_exports`, in `backend/src/mrcourt/api/drafts.py`
- [X] T081 [US4] Build the Drafts screen (template picker, draft card, version chip, Edit/Done, review flag) in `frontend/src/pages/Drafts.tsx`
- [X] T082 [P] [US4] Build the export format chooser and error state in `frontend/src/components/ExportDialog.tsx`
- [X] T083 [US4] Hide the Drafts nav item for petitioners and open Drafts with the case preselected from Case detail in `frontend/src/components/AppShell.tsx` and `frontend/src/pages/CaseDetail.tsx`
- [X] T084 [US4] End-to-end test for templates, edit/save, reload, and both exports in `frontend/tests/e2e/drafts.spec.ts`

**Checkpoint**: Drafts work independently

---

## Phase 7: User Story 5 - Manage settings, privacy and appearance (Priority: P3)

**Goal**: Users manage profile, verification, reminders, alerts, privacy and theme.

**Independent Test**: Toggle reminders and theme and confirm they persist; export data; start deactivation and confirm the retention notice must be acknowledged; confirm administrator verification shows the chip.

### Tests for User Story 5

- [X] T085 [P] [US5] Contract tests for `/me/settings`, `/me/data-export`, `/me/deactivate` and `/admin/verifications` in `backend/tests/contract/test_settings_privacy.py`
- [X] T086 [P] [US5] Integration tests: deactivation clears personal data and keeps case records, deactivated users cannot sign in, only administrators can verify in `backend/tests/integration/test_privacy.py`

### Implementation for User Story 5

- [X] T087 [P] [US5] Implement data export and deactivation in `backend/src/mrcourt/services/privacy.py`
- [X] T088 [P] [US5] Implement the settings update endpoint and the data-export and deactivate endpoints in `backend/src/mrcourt/api/me.py`
- [X] T089 [P] [US5] Implement the administrator verification endpoints in `backend/src/mrcourt/api/admin.py`
- [X] T090 [P] [US5] Implement the reminder scheduler and a WhatsApp adapter behind the notification interface in `backend/src/mrcourt/services/reminders.py`
- [X] T091 [US5] Build the Settings screen (profile, verification chip or pending state, sign out, language, reminders switch, alerts, privacy, help) in `frontend/src/pages/Settings.tsx`
- [X] T092 [P] [US5] Build the deactivation dialog with the case-retention notice in `frontend/src/components/DeactivateDialog.tsx`
- [X] T093 [P] [US5] Build the administrator verification page in `frontend/src/pages/AdminVerifications.tsx`
- [X] T094 [US5] End-to-end test for toggles, theme persistence, data export, deactivation notice and verification in `frontend/tests/e2e/settings.spec.ts`

**Checkpoint**: All user stories are independently functional

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [X] T095 [P] Screenshot comparison of every screen against `design/MrCourt Web Prototype.html` in light and dark themes in `frontend/tests/e2e/visual.spec.ts`
- [X] T096 [P] Axe accessibility scans of every screen at 360px and 1280px in both themes in `frontend/tests/e2e/a11y.spec.ts`
- [X] T097 Security hardening: CSRF protection, secure headers, request rate limits, upload scanning hook, in `backend/src/mrcourt/main.py`
- [X] T098 Measure answer latency against the 10 second p95 target and tune retrieval in `backend/tests/integration/test_answer_latency.py`
- [X] T099 Make sure any feature not yet available tells the user so (FR-018), reviewing every screen in `frontend/src/pages/`
- [X] T100 [P] Write setup and operations documentation in `README.md`
- [ ] T101 Obtain legal review of indefinite case-record retention against the DPDP Act and record the outcome in `specs/001-mrcourt-legal-app/research.md` (R10)
- [X] T102 Run the full quickstart.md validation and record results

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Setup; blocks all user stories
- **US2 (Phase 3)**: depends on Foundational
- **US1 (Phase 4)**: depends on Foundational and on US2 (needs a signed-in user)
- **US3 (Phase 5)**: depends on Foundational and US2; extends the Dashboard started in US2 and US1
- **US4 (Phase 6)**: depends on Foundational, US2 and US3 (drafts attach to cases)
- **US5 (Phase 7)**: depends on Foundational and US2; independent of US1, US3 and US4
- **Polish (Phase 8)**: depends on the stories being complete

### Within Each Story

- Tests first, confirmed failing
- Models (Phase 2) before services, services before endpoints, endpoints before screens
- Tasks touching the same file (`Dashboard.tsx`, `AppShell.tsx`, `CaseDetail.tsx`, `me.py`) run in order, not in parallel

### Parallel Opportunities

- Setup tasks T004 to T007; foundational models T012 to T014; style and component tasks T022 to T027
- After US2, US1 and US5 can proceed in parallel; US3 can start alongside them
- Within a story, all tasks marked [P]

### Parallel Example: User Story 1

```text
Task: "Unit tests for the citation verifier in backend/tests/unit/test_citation_verifier.py"
Task: "Reviewed gold set in backend/tests/integration/test_answers_gold.py"
Task: "Sample corpus files in backend/src/mrcourt/corpus/data/sample/"
Task: "Ingestion CLI in backend/src/mrcourt/corpus/ingest.py"
Task: "SourceChip and chat components in frontend/src/components/"
```

---

## Implementation Strategy

### MVP First (US2 then US1)

1. Complete Phase 1 and Phase 2
2. Complete Phase 3 (sign-in and shell), then Phase 4 (cited Q&A)
3. **STOP and VALIDATE**: quickstart scenarios 1, 2 and 3
4. Demo

### Incremental Delivery

1. Foundation, then US2 and US1 (MVP)
2. US3 (cases), then US4 (drafts), both independently testable
3. US5 (settings and privacy), which can run in parallel with US3
4. Polish and the legal retention review before launch

---

## Notes

- [P] tasks = different files, no dependencies
- The [Story] label maps each task to its user story for traceability
- Never commit secrets or real personal data; sample data is fictional
- Commit after each task or logical group
