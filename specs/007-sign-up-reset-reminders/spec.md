# Feature Specification: Sign-up with phone check, forgot password, and hearing text reminders

**Feature Branch**: `007-sign-up-reset-reminders`

**Created**: 2026-10-09

**Status**: Draft

**Input**: User description: "create registration flow and forgot password flow, include send text message to advocate, client when the hearing is today send msg, before 7 [days] reminder msg"

## Clarifications

- Q: Which text-message service? → A: Twilio, using free accounts: the trial account for SMS (to verified numbers) and the free WhatsApp sandbox (to people who have joined it). The owner chose free sandbox accounts over a paid Indian SMS service. Until keys are set, messages go to a development outbox that can be read on a development page.
- Q: What does "before 7 years" mean? → A: Taken as 7 days. Reminders go out 7 days before, 1 day before and on the day of the hearing.
- Q: How does someone who forgot their password get back in? → A: A 6-digit code is texted to the phone number on their account, then they choose a new password.
- Q: Is the phone number required at sign-up? → A: Yes in the screen. It is checked with a text-message code. A person may skip the check for now, but then no reminders are sent and a password cannot be reset until the number is verified.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Sign up and confirm my phone (Priority: P1)

An advocate or petitioner fills in the sign-up form (name, email, mobile number, password; advocates also a Bar Council number). The account is created and a 6-digit code is texted to the mobile number. They enter the code on the next screen and land on their dashboard with the phone marked verified. They can choose "Verify later", resend the code, or fix the number.

**Acceptance Scenarios**:

1. **Given** the sign-up form, **When** it is submitted with a mobile number, **Then** the account is created, the person is signed in, and a code is sent to that number.
2. **Given** the code screen, **When** the right code is entered within 10 minutes, **Then** the phone is marked verified.
3. **Given** a wrong code five times, **Then** that code is no longer accepted and a new one must be requested.
4. **Given** "Resend code", **Then** a new code replaces the old one (limited to a few per hour).
5. **Given** "Verify later", **Then** the person continues without a verified phone; Settings shows "Not verified" with a Verify button.
6. **Given** a mobile number already used by another account, **Then** sign-up says so without creating anything.
7. **Given** the phone number is changed in Settings, **Then** it becomes unverified and must be verified again.

### User Story 2 - Forgot password (Priority: P1)

On the sign-in page "Forgot password?" asks for the email or mobile number, then texts a code to the verified phone on that account. The person enters the code and a new password and is told to sign in. The reply never reveals whether an account exists. Resetting signs the person out everywhere.

**Acceptance Scenarios**:

1. **Given** an account with a verified phone, **When** its email or phone is entered, **Then** a code is texted to that phone and the screen says "If an account matches, a code has been sent."
2. **Given** an unknown identifier or an account with no verified phone, **Then** the same message appears and nothing is sent.
3. **Given** the right code and a new password of at least 10 characters, **Then** the password changes, all sessions of that person end, and the old password stops working.
4. **Given** a wrong or expired code (10 minutes), or five wrong tries, **Then** the reset is refused with a generic message.
5. **Given** repeated requests, **Then** they are limited per identifier.
6. **Given** a suspended or deactivated account, **Then** no code is sent.

### User Story 3 - Hearing reminders by text message (Priority: P1)

For every hearing in an open case, the advocate who owns the case and each client who has accepted the invitation receive a text 7 days before, 1 day before and on the morning of the hearing, if their phone is verified and text reminders are on. A hearing added at short notice sends one text that says how soon it is, not three. Each reminder is sent once per person. Texts name the case and the time only.

**Acceptance Scenarios**:

1. **Given** a hearing 7 days away, **When** the reminder job runs, **Then** the advocate and each client get "in 7 days", once.
2. **Given** the day before, **Then** they get a "tomorrow" text; on the day, a "today at [time]" text.
3. **Given** a hearing added 3 days ahead, **Then** one text says "in 3 days" and no 7-day text follows later.
4. **Given** a person without a verified phone, or with reminders switched off, **Then** nothing is sent to them.
5. **Given** a closed case, a past hearing, a suspended or deactivated person, or a client whose invitation is not accepted, **Then** nothing is sent.
6. **Given** the job runs again, **Then** no reminder is sent twice.
7. **Given** a rescheduled hearing, **Then** the reminder schedule restarts for the new time.
8. **Given** Settings, **Then** the person can switch text reminders on or off and sees the fixed schedule described.

### User Story 4 - Messages can be read while no SMS service is set up (Priority: P2)

With no SMS key, development shows each message on a page ("Development messages") so codes and reminders can be read. That page does not exist in production.

## Requirements *(mandatory)*

- **FR-001**: Sign-up MUST collect a mobile number in the screen, send a verification code, and mark the phone verified only after the right code is entered.
- **FR-002**: Codes MUST be 6 digits, expire in 10 minutes, allow five tries, be stored only as hashes, and be limited per person and per number.
- **FR-003**: Forgot-password MUST send a code only to a verified phone of an active account, MUST reply identically whether or not an account matches, and a successful reset MUST end all of that person's sessions.
- **FR-004**: Changing the phone number MUST clear its verification.
- **FR-005**: Reminders MUST go to the case's advocate and to clients with accepted invitations, 7 days before, 1 day before and on the day, once per person per hearing, only to verified phones with reminders on.
- **FR-006**: Reminder texts MUST contain only the case title and the date and time.
- **FR-007**: The sender MUST be Twilio (SMS and/or WhatsApp, whichever numbers are configured) when its account keys are set, otherwise the development outbox; keys MUST NOT appear in the repository, responses or logs.
- **FR-008**: The development messages page and its API MUST be unavailable outside development and test.
- **FR-009**: All new screens MUST meet the project's accessibility rules in both themes at desktop and phone widths.

## Success Criteria

- **SC-001**: A new person can sign up, enter the texted code and reach their dashboard with a verified phone in under 2 minutes.
- **SC-002**: A person who forgot their password can reset it in under 2 minutes, and the old password and old sessions stop working.
- **SC-003**: In tests, every due reminder is sent exactly once to each eligible advocate and client and never to anyone ineligible.
- **SC-004**: Responses to forgot-password are identical for existing and unknown accounts.

## Assumptions

- Free Twilio accounts have limits: a trial account texts only numbers verified in the Twilio console (and adds a trial note to each message), and the WhatsApp sandbox reaches only people who have sent its join phrase from their phone (joins lapse after a while). Production sending in India needs a paid, registered account. The sender is written and tested against a stand-in, not the live service.
- Reminder times use Indian Standard Time; the job should run hourly (`python -m mrcourt.services.reminders`).
- The existing "WhatsApp reminders" setting becomes "Text message reminders" (same stored switch); the per-person "days before" choice is replaced by the fixed 7, 1, 0 schedule.
- Email is not used to deliver codes (no email sender is set up).
