# Tasks: Admin Console

**Input**: [spec.md](spec.md), [plan.md](plan.md). Builds on features 001 and 002. Tests are included and written before the code they check.

## Phase 1: Foundation

- [X] T001 Record the baseline (backend, unit and browser test counts) in `specs/003-admin-console/baseline.md`
- [X] T002 Add `session_epoch` to `User` in `backend/src/mrcourt/models/user.py` and create the `AuditEntry` model in `backend/src/mrcourt/models/audit.py`, exported from `backend/src/mrcourt/models/__init__.py`
- [X] T003 Write Alembic revision `0003` (new column and table, safe on fresh and old databases) in `backend/alembic/versions/0003_admin_console.py`
- [X] T004 Put the session epoch into the signed cookie and check it on every request in `backend/src/mrcourt/services/session.py` and `backend/src/mrcourt/api/deps.py`
- [X] T005 Make `admin` a real role: `require_admin` by role in `backend/src/mrcourt/api/deps.py`, role value in `backend/src/mrcourt/schemas/auth.py`, seed the administrator with that role in `backend/src/mrcourt/seed.py`, and refuse suspended accounts at sign-in in `backend/src/mrcourt/services/auth.py`
- [X] T006 Create the audit helper (records in the caller's transaction, never stores message text or document contents) in `backend/src/mrcourt/services/audit.py`

## Phase 2: User Story 1 - Admin area, menu and overview (P1)

- [X] T007 [US1] Tests: roles are separated both ways, overview counts, non-admins refused, in `backend/tests/contract/test_admin_overview.py`
- [X] T008 [US1] Implement `GET /admin/overview` in `backend/src/mrcourt/api/admin.py` and `backend/src/mrcourt/services/admin_users.py`
- [X] T009 [US1] Add the administrator sign-in page (`/login/admin`), a small link to it on the welcome screen, and the three-way role check, in `frontend/src/pages/Login.tsx` and `frontend/src/pages/Welcome.tsx`
- [X] T010 [US1] Give administrators their own menu and hide advocate and client screens in `frontend/src/components/AppShell.tsx` and `frontend/src/App.tsx`
- [X] T011 [US1] Build the admin overview in `frontend/src/pages/AdminOverview.tsx` with data hooks in `frontend/src/services/admin.ts`
- [X] T012 [US1] End-to-end test for sign-in, menu and overview in `frontend/tests/e2e/admin.spec.ts`

## Phase 3: User Story 2 - Manage advocates and clients (P1)

- [X] T013 [US2] Tests: list, search, filter, detail, edit, suspend, reactivate, force sign-out, verification, protections, uniqueness, immediate effect, in `backend/tests/contract/test_admin_users.py` and `backend/tests/integration/test_admin_sessions.py`
- [X] T014 [US2] Implement the user services (including epoch bump and admin-target protection) in `backend/src/mrcourt/services/admin_users.py`
- [X] T015 [US2] Implement the user endpoints and audit each change in `backend/src/mrcourt/api/admin.py`
- [X] T016 [US2] Show the right message when a suspended account signs in, in `backend/src/mrcourt/services/auth.py` and `frontend/src/pages/Login.tsx`
- [X] T017 [US2] Build the Advocates and Clients lists and the person page in `frontend/src/pages/AdminUsers.tsx` and `frontend/src/pages/AdminUserDetail.tsx`
- [X] T018 [US2] End-to-end tests for managing accounts in `frontend/tests/e2e/admin-users.spec.ts`

## Phase 4: User Story 3 - See any case in full, accountably (P1)

- [X] T019 [US3] Tests: full view shows private content, each open and download is audited, lists are not, no edit endpoints exist, in `backend/tests/contract/test_admin_cases.py` and `backend/tests/integration/test_admin_audit_coverage.py`
- [X] T020 [US3] Implement list and full-view services in `backend/src/mrcourt/services/admin_cases.py`
- [X] T021 [US3] Implement the case endpoints and the audited document download in `backend/src/mrcourt/api/admin.py`
- [X] T022 [US3] Build the Cases list and the full case view, with the "this is recorded" notice, in `frontend/src/pages/AdminCases.tsx` and `frontend/src/pages/AdminCaseView.tsx`
- [X] T023 [US3] End-to-end tests in `frontend/tests/e2e/admin-cases.spec.ts`

## Phase 5: User Story 4 - Audit log (P2)

- [X] T024 [US4] Tests: entries appear with the right details, newest first, paging, admin-only, immutable, no sensitive values, in `backend/tests/contract/test_admin_audit.py`
- [X] T025 [US4] Implement `GET /admin/audit` in `backend/src/mrcourt/api/admin.py`
- [X] T026 [US4] Build the Audit log page in `frontend/src/pages/AdminAudit.tsx`
- [X] T027 [US4] End-to-end test in `frontend/tests/e2e/admin-audit.spec.ts`

## Phase 6: Polish

- [X] T028 Update existing tests and helpers that signed the administrator in through the advocate page, in `frontend/tests/e2e/support/helpers.ts`, `frontend/tests/e2e/settings.spec.ts` and `frontend/tests/e2e/a11y.spec.ts`
- [X] T029 [P] Accessibility scans of every admin screen in both themes at 360px and 1280px in `frontend/tests/e2e/a11y.spec.ts`
- [X] T030 [P] Document the admin console, the audit log and the privacy note in `README.md`
- [X] T031 Full regression twice in a row and record results in `specs/003-admin-console/quickstart-results.md`
- [ ] T032 Review the breadth of administrator access against the DPDP Act and the organisation's policy (a person with legal expertise must do this)
