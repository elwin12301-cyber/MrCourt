# Feature Specification: Admin Console

**Feature Branch**: `003-admin-console`

**Created**: 2026-10-08

**Status**: Draft

**Input**: User description: "Admin has full control and can see all: advocates and clients. Create separate menus for admin, and every change is saved in the database."

## Clarifications

### Session 2026-10-08

- Q: How much of a case's private content should an admin be able to see (private notes, internal documents, unshared hearing outcomes, clients' messages to their lawyer)? → A: Everything, with a log. Every time an admin opens private content it is written to an audit log (who, what, when) that only admins can read.
- Q: What should an admin be able to change? → A: Accounts only: suspend or reactivate advocates and clients, approve or reject Bar Council numbers, correct names and contact details, and force a sign-out. Admins cannot edit cases, delete data permanently, or reset passwords.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See everything at a glance, in an admin area of its own (Priority: P1)

An administrator signs in on a separate administrator sign-in page and lands on an admin overview with its own menu: Overview, Advocates, Clients, Cases, Verifications, Audit log and Settings. The overview shows how many advocates, clients and cases there are, how many verifications are waiting, how many accounts are suspended, and the latest audit entries. Advocate and client menus never appear for an administrator.

**Why this priority**: Everything else lives inside this area. Without a clear overview and its own menu the admin has nowhere to work.

**Independent Test**: Sign in as the administrator and confirm the menu, the counts, and that no advocate-only or client-only screens are offered.

**Acceptance Scenarios**:

1. **Given** the administrator sign-in page, **When** an administrator signs in, **Then** they land on the admin overview with the admin menu only.
2. **Given** an advocate or a client account, **When** it tries the administrator sign-in, **Then** it is refused with a message pointing to its own sign-in.
3. **Given** an administrator account, **When** it tries the advocate or petitioner sign-in, **Then** it is refused with a message pointing to the administrator sign-in.
4. **Given** the overview, **Then** it shows counts of advocates, clients, open cases, pending verifications and suspended accounts, and the five latest audit entries.
5. **Given** any non-administrator, **When** they request an admin address or admin data, **Then** access is refused.

---

### User Story 2 - Find and manage every advocate and client (Priority: P1)

The administrator lists all advocates and all clients, searches by name, email or phone, and filters by status (active, suspended, deactivated, waiting for verification). Opening a person shows their details and how they are linked (an advocate's cases, a client's cases and lawyers). The administrator can correct a name, email, phone or Bar Council number, suspend or reactivate the account, force a sign-out, and approve or reject a pending Bar Council number. Every change is saved at once and recorded in the audit log.

**Why this priority**: Managing accounts is the admin's core job and the scope the owner chose.

**Independent Test**: Suspend an advocate and confirm they can no longer use the app and clients see their lawyer as unavailable; reactivate and confirm they can sign in again.

**Acceptance Scenarios**:

1. **Given** the Advocates or Clients menu, **Then** the administrator sees a searchable, filterable list with name, contact, status and linked case counts.
2. **Given** a person's page, **When** the administrator corrects a detail and saves, **Then** the change is stored and shown on the next load, and an audit entry records what changed.
3. **Given** an active account, **When** the administrator suspends it with a reason, **Then** the person is signed out at once and cannot sign in again, and the sign-in explains the account is suspended.
4. **Given** a suspended account, **When** the administrator reactivates it, **Then** the person can sign in again.
5. **Given** a signed-in person, **When** the administrator forces a sign-out, **Then** that person's existing sessions stop working immediately, and they can sign in again normally.
6. **Given** a pending Bar Council number, **When** the administrator approves or rejects it, **Then** the advocate's verification status updates and the decision is logged.
7. **Given** the administrator's own account or another administrator's, **Then** it cannot be suspended or signed out from here.
8. **Given** an email or phone already used by someone else, **When** the administrator tries to save it, **Then** it is refused with a clear message and nothing changes.

---

### User Story 3 - See any case in full, accountably (Priority: P1)

The administrator lists all cases with search, and opens any case to see everything: details, parties, hearings with all outcomes (shared or not), all documents (shared or internal) with download, the full timeline including private entries, the clients on the case, and every client's questions and the lawyer's replies. Opening a case in full and downloading a document are each written to the audit log with the administrator's name, the case and the time. The page says so. The administrator cannot edit anything on a case.

**Why this priority**: This is the "see everything" the owner asked for, made accountable so private content is not silently exposed.

**Independent Test**: Open a case holding a private note, an internal document and a client's message; confirm all are visible to the administrator and that exactly the right audit entries exist.

**Acceptance Scenarios**:

1. **Given** the Cases menu, **Then** the administrator sees every case with its advocate, number of clients, status and next hearing, and can search.
2. **Given** a case, **When** the administrator opens it, **Then** all of its content including private notes, internal documents, unshared outcomes and clients' messages is shown, and an audit entry "viewed case in full" is written.
3. **Given** a document, **When** the administrator downloads it, **Then** the file is delivered and an audit entry is written.
4. **Given** the case page, **Then** it shows a notice that opening it is recorded, and offers no way to edit, delete or reassign.
5. **Given** the case list or the user lists, **When** they are only listed or searched, **Then** no audit entry is written (they show overview data only).

---

### User Story 4 - Read the audit log (Priority: P2)

The administrator opens an audit log showing who did what, to whom or what, and when, newest first. It records every account change, every verification decision, every full case view and every document download by an administrator. Only administrators can read it, and nobody can change or delete entries.

**Why this priority**: It is what makes full visibility acceptable, but it is useful only once the other stories produce entries.

**Independent Test**: Perform several admin actions and confirm each appears once, with the right details, and that no screen or request can alter an entry.

**Acceptance Scenarios**:

1. **Given** admin actions, **When** the administrator opens the audit log, **Then** each action appears with the administrator's name, action, target and time, newest first.
2. **Given** a change to a person's details, **Then** the entry names the fields changed but does not store passwords or full contact details.
3. **Given** any non-administrator, **Then** the audit log is refused.
4. **Given** the audit log, **Then** there is no way to edit or delete an entry.

---

### Edge Cases

- The administrator suspends an advocate who has clients: the clients see "Your lawyer is no longer available on MrCourt" and keep their case records.
- The administrator suspends a client: the client is signed out and cannot sign in; the advocate's records and the client's invitation remain.
- A suspended person's open session: it stops working on the next request.
- Two administrators change the same person at once: the last save wins and both changes are logged.
- Reactivating a deactivated (self-deleted) account: not offered, because their personal data was removed.
- An email or phone is cleared: refused if it would leave the account without any way to sign in.
- A very large number of audit entries: the log shows the newest first and loads more on request.
- An administrator opens a case that has been closed or whose advocate is suspended: it is still shown in full and logged.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide an administrator role, separate from advocates and clients, with its own sign-in page and its own menu: Overview, Advocates, Clients, Cases, Verifications, Audit log and Settings.
- **FR-002**: Administrators MUST NOT see advocate-only or client-only screens, and advocates and clients MUST NOT reach any admin screen or data.
- **FR-003**: The overview MUST show counts of advocates, clients, open cases, pending verifications and suspended accounts, and the latest audit entries.
- **FR-004**: Administrators MUST be able to list, search and filter all advocates and all clients by name, email, phone and status.
- **FR-005**: A person's page MUST show their details and links: for an advocate, their cases; for a client, their cases and lawyers.
- **FR-006**: Administrators MUST be able to correct a person's name, email, phone and, for advocates, Bar Council number, with email and phone kept unique.
- **FR-007**: Administrators MUST be able to suspend a person with a reason and reactivate them. A suspended person MUST be signed out at once and refused at sign-in with a clear message.
- **FR-008**: Administrators MUST be able to force a sign-out, ending all of a person's current sessions immediately.
- **FR-009**: Administrators MUST be able to approve or reject pending Bar Council numbers.
- **FR-010**: Administrators MUST NOT be able to suspend, sign out or edit themselves or other administrators from this area.
- **FR-011**: Administrators MUST be able to list and search all cases and open any case to see all of its content, including private notes, internal documents, unshared outcomes, the full timeline and every client's questions and replies.
- **FR-012**: Administrators MUST NOT be able to edit, delete, reassign or close cases, delete data permanently, or reset passwords.
- **FR-013**: Every administrator action that changes an account, every verification decision, every full case view and every document download MUST be written to an audit log with the administrator, action, target and time.
- **FR-014**: Audit entries MUST NOT contain passwords, one-time codes, message text or document contents, and MUST record changed field names rather than full personal values where those are sensitive.
- **FR-015**: Only administrators MUST be able to read the audit log, and no one MUST be able to edit or delete entries.
- **FR-016**: Every change MUST be saved in the database at once and be visible on the next load.
- **FR-017**: Admin screens MUST use the existing design system, work by keyboard, meet WCAG 2.1 AA in light and dark themes, and work at 360px width.
- **FR-018**: Screens that show private content MUST tell the administrator that opening them is recorded.

### Key Entities

- **Administrator**: A user with the admin role. Not created through sign-up.
- **Account Status**: active, suspended (by an administrator, reversible), or deactivated (by the person themselves, final).
- **Session Epoch**: A counter on each account; increasing it ends all of that person's current sessions.
- **Audit Entry**: Who (administrator), what (action), to what (target type and id), details that are safe to keep, and when.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An administrator can find any advocate or client within 20 seconds of signing in.
- **SC-002**: 100% of administrator account changes, verification decisions, full case views and document downloads appear in the audit log.
- **SC-003**: A suspended or signed-out person is refused on their very next request (0 requests succeed after the action).
- **SC-004**: 0 advocate or client accounts can reach any admin screen or admin data in any tested scenario.
- **SC-005**: Every admin screen passes WCAG 2.1 AA checks in light and dark themes at 360px and 1280px widths.
- **SC-006**: Every saved change is shown unchanged after a reload.

## Assumptions

- This builds on features 001 and 002: same sign-in, roles, cases, messages and design system.
- Administrators are created by the people running the system (seeded or added directly), never through public sign-up.
- Administrator sign-in uses the same email or phone and password as everyone else, on its own page.
- Suspending is reversible; a person's own deactivation is final and cannot be undone by an administrator.
- "Everything with a log" means the audit log is the control; there is no second approval step.
- Audit entries are kept indefinitely in this version.
- English only.
