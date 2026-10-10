# Tasks: Sign-up with phone check, forgot password, hearing text reminders

- [ ] T001 Backend data: `users.phone_verified_at`, `otp_challenges.purpose`, `reminder_log` table, migration `0006` (`backend/src/mrcourt/models/`, `backend/alembic/versions/0006_*.py`)
- [ ] T002 Settings and notifier: MSG91 settings, phone normalising, `Msg91Notifier`, outbox with kind and time, chosen from configuration (`config.py`, `services/notify.py`, `main.py`)
- [ ] T003 Auth service: generic code send and check by purpose; phone verification and password reset functions (`services/auth.py`)
- [ ] T004 Auth API and schemas: `/auth/phone/request|verify`, `/auth/password/forgot|reset`, `phone_verified` in `/me`, clear verification on phone change (`api/auth.py`, `api/me.py`, `schemas/auth.py`, `services/account` code)
- [ ] T005 Development messages API (`api/dev.py`) available only in development and test
- [ ] T006 Reminders: schedule 7, 1, 0, advocates and clients, once each, verified and opted in only (`services/reminders.py`)
- [ ] T007 Backend tests for T001 to T006 (`backend/tests/contract/test_phone_verification.py`, `test_password_reset.py`, `test_dev_messages.py`, `backend/tests/unit/test_reminders_sms.py`, `test_msg91.py`) and update older tests
- [ ] T008 Frontend: sign-up with mobile number and the code step; "Forgot password?" link; forgot-password page; development messages page; routes (`frontend/src/pages/Register.tsx`, `Login.tsx`, `ForgotPassword.tsx`, `DevMessages.tsx`, `App.tsx`)
- [ ] T009 Frontend Settings: phone verification status and code step; text reminder switch and schedule text (`frontend/src/pages/Settings.tsx`, services)
- [ ] T010 End-to-end tests: sign-up with verification, skip and resend, forgot password, settings, development messages page; update tests that named the old settings rows or the sign-up form (`frontend/tests/e2e/`)
- [ ] T011 Accessibility checks for the new screens (`frontend/tests/e2e/a11y.spec.ts`)
- [ ] T012 README and Settings text: MSG91 setup, templates, running the reminder job hourly, fixed schedule; migrate dev database
- [ ] T013 Full regression twice in a row; write `specs/007-sign-up-reset-reminders/results.md`
- [ ] T014 Review by a person: MSG91 account, DLT template approval, and a live test (cannot be done by the build; leave open)
