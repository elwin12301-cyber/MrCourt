# Feature Specification: MrCourt Legal Assistance App

**Feature Branch**: `001-mrcourt-legal-app`

**Created**: 2026-10-07

**Status**: Draft

**Input**: User description: "Build MrCourt, a production web app for Indian legal assistance, reproducing the supplied MrCourt Web Prototype design exactly (navy/ivory/gold tokens, Playfair Display headings and Inter body, light/dark themes, responsive under 900px). Screens: welcome with role choice, login, app shell, dashboard, Ask MrCourt (cited legal Q&A), cases, case detail, drafts, settings. Real persistence replaces the prototype's hardcoded data; legal answers must be grounded in an indexed corpus of Indian law with citations."

## Clarifications

### Session 2026-10-07

- Q: What should a Petitioner be able to do in MrCourt compared with an Advocate? → A: Limited: view-only access to cases they were invited to, plus Ask MrCourt. No drafts, no case creation.
- Q: How should the system confirm an Advocate's Bar Council registration before showing the "Bar Council verified" chip? → A: Administrator review: advocates use the app right away, and the chip appears only after an administrator confirms the registration number.
- Q: How are cases and hearings added to MrCourt in this first version? → A: Manual entry: Advocates create and edit cases, hearings and documents through forms.
- Q: What should "Export" produce when a user exports a draft? → A: Word (.docx) and PDF, user's choice.
- Q: When a user asks MrCourt to delete their data, what should happen to their account and case information? → A: Deactivate the account but keep case records indefinitely for legal reasons.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Get a cited answer to a legal question (Priority: P1)

A signed-in user asks a question about Indian law, by typing or by voice, from the Ask MrCourt screen or the dashboard quick-ask card. They receive an answer where every statement points to a numbered source (Act and section, or judgment). If nothing reliable is found, MrCourt says so instead of guessing.

**Why this priority**: This is the product's core promise ("every answer cites the Act, section or judgment") and the constitution's first principle. Without it nothing else differentiates MrCourt.

**Independent Test**: Ask a question covered by the legal corpus (for example, the punishment for cheque dishonour) and one outside it. The first returns a cited answer with numbered source chips; the second returns the "could not find a reliable source" response.

**Acceptance Scenarios**:

1. **Given** a signed-in user on Ask MrCourt, **When** they ask a question covered by the indexed law, **Then** the answer appears with numbered references, each showing the Act and section (for example "Negotiable Instruments Act, 1881 · Section 138").
2. **Given** a question with no reliable source, **When** it is submitted, **Then** the user sees an explicit "could not find a reliable source" message with advice to rephrase or name the Act or section, and no uncited legal claim.
3. **Given** any answer, **Then** it shows "Informational only, not legal advice".
4. **Given** the suggested-question pills, **When** the user selects one, **Then** that question is asked and answered.
5. **Given** the dashboard quick-ask card, **When** the user submits a question, **Then** they land on Ask MrCourt with that question answered.

---

### User Story 2 - Choose a role, sign in and reach the dashboard (Priority: P1)

A new or returning visitor sees the welcome screen, chooses "I'm an Advocate" or "I'm a Petitioner", signs in with email or phone plus password or with a one-time passcode, and lands on a personalised dashboard.

**Why this priority**: All other features require an identified user whose data is private to them.

**Independent Test**: From the welcome screen choose a role, sign in, and confirm the dashboard greets the user by name with their own data; sign out returns to the welcome screen.

**Acceptance Scenarios**:

1. **Given** the welcome screen, **When** the user chooses a role, **Then** the login screen opens with a back link to the welcome screen.
2. **Given** valid credentials or a valid one-time passcode, **When** the user signs in, **Then** the dashboard opens.
3. **Given** invalid credentials, **When** the user signs in, **Then** a clear error is shown and no account details are revealed.
4. **Given** a new visitor, **When** they choose "Create an account", **Then** they can register with the selected role.
5. **Given** a signed-in user, **When** they choose Sign out in Settings, **Then** the session ends and the welcome screen shows.

---

### User Story 3 - Track cases and upcoming hearings (Priority: P2)

An advocate sees the dashboard summary (active cases, hearings this week, drafts to review, upcoming hearings, recent activity), searches and filters their cases, and opens a case to see its next hearing, parties, documents and tabs.

**Why this priority**: Daily-use value for advocates once sign-in and Q&A exist.

**Independent Test**: With seeded cases, search by party, CNR number and court, apply each status filter, open a case from the table and from a dashboard hearing, and confirm details match.

**Acceptance Scenarios**:

1. **Given** the dashboard, **Then** stat cards, the next three upcoming hearings with date badges, and recent activity reflect the user's own data.
2. **Given** the Cases screen, **When** the user types a party name, CNR number or court, **Then** the table narrows to matches; with none it shows "No cases match your search."
3. **Given** the filter pills All, Active, Hearing soon and Closed, **When** one is selected, **Then** only matching cases show and the pill is marked selected.
4. **Given** a case row, **When** selected by mouse or by pressing Enter on the focused row, **Then** the case detail opens.
5. **Given** a case detail, **Then** it shows title, CNR, court, status chip, next hearing (or "No hearing scheduled"), parties and documents, plus "Ask MrCourt" and "Draft document" actions and the tabs Overview, Hearings, Documents and Notes.

---

### User Story 4 - Prepare and edit an AI-assisted draft (Priority: P2)

An advocate picks a template (Legal Notice, Bail Application, Reply to Notice, Affidavit), reads the generated draft for a case, edits it, and exports it.

**Why this priority**: High-value time saver, but it depends on cases and the legal corpus.

**Independent Test**: Select each template, toggle Edit, change text, leave Edit, and confirm the change is kept and the review flag stays visible.

**Acceptance Scenarios**:

1. **Given** the Drafts screen, **When** a template card is selected, **Then** its draft, title, metadata and version chip show and the card is marked selected.
2. **Given** a draft, **When** the user chooses Edit, **Then** the text becomes editable and the button reads Done; choosing Done saves the edits.
3. **Given** any draft, **Then** "AI-generated draft · review before use" is always visible.
4. **Given** a draft, **When** the user chooses Export, **Then** they pick Word or PDF and the document is produced only through that explicit action; nothing is sent or filed automatically.

---

### User Story 5 - Manage settings, privacy and appearance (Priority: P3)

A user views their profile and verification status, changes language, toggles WhatsApp reminders, sets hearing alert timing, manages their data under the DPDP Act, and switches between light and dark themes.

**Why this priority**: Required for trust and compliance but not for the core workflow.

**Independent Test**: Toggle reminders, switch theme, reload and confirm both persist; open Privacy and data and confirm the user can review and request deletion of their data.

**Acceptance Scenarios**:

1. **Given** Settings, **Then** the profile, "Bar Council verified" chip (for verified advocates), language, WhatsApp reminders switch, hearing alerts, Privacy and data, and Help and support entries show.
2. **Given** the reminders switch, **When** toggled, **Then** the new state is saved and still applies after signing in again.
3. **Given** the theme toggle, **When** used, **Then** the whole app switches between light and dark; with no choice made, the device preference applies.
4. **Given** Privacy and data, **When** opened, **Then** the user can see what is stored, export it, and request account deactivation after being told that case records are retained.

---

### Edge Cases

- A question is empty or only whitespace: nothing is submitted.
- A question mixes covered and uncovered topics: covered parts are cited, uncovered parts say no reliable source was found.
- A cited provision has been repealed or replaced (for example the older criminal codes): the answer cites the current statute and notes the change.
- A user has no cases, no hearings or no drafts: friendly empty states appear and stat cards show zero.
- Voice input is unsupported or microphone permission is denied: the user is told and can type instead.
- A session expires mid-task: the user is returned to sign in without losing unsaved draft edits.
- An advocate or petitioner tries to open another user's case: access is refused.
- A Petitioner opens a case link they were not invited to, or tries to reach Drafts or edit a case: access is refused with a clear message.
- An Advocate removes a Petitioner's invitation: the case disappears from the Petitioner's view at their next page load.
- Narrow screens: the sidebar becomes a top bar and tables scroll horizontally without breaking the page.
- Export fails: the user sees an error and the draft remains intact.
- A deactivated user tries to sign in: access is refused with a message explaining the account is deactivated.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST present a welcome screen with brand messaging, the statement "Informational guidance only. Not legal advice.", and role choices Advocate and Petitioner.
- **FR-002**: The system MUST let users register, sign in with email or phone plus password, or sign in with a one-time passcode, and sign out.
- **FR-003**: The system MUST restrict every user to their own cases, hearings, documents, drafts and settings, and for Petitioners to only the cases they have been invited to.
- **FR-019**: Petitioners MUST have view-only access to cases they were invited to by an Advocate (case details, hearings and documents), and MUST be able to use Ask MrCourt and Settings. Petitioners MUST NOT create or edit cases, hearings, documents or drafts, and the Drafts screen MUST NOT be offered to them.
- **FR-022**: Advocates MUST be able to create, edit and close cases, add and reschedule hearings, and upload documents through forms; there is no bulk import or automatic court-system sync in this version.
- **FR-021**: Advocates MUST be able to enter their Bar Council registration number and use the app immediately; the system MUST show the "Bar Council verified" chip only after an administrator has confirmed the number, and MUST show a "verification pending" state until then.
- **FR-020**: An Advocate MUST be able to invite a Petitioner to a case, and the Petitioner's acceptance MUST appear in the Advocate's recent activity.
- **FR-004**: The system MUST provide an app shell with navigation to Dashboard, Cases, Ask MrCourt, Drafts and Settings, a user card, and a light/dark toggle, collapsing to a top bar below 900px width.
- **FR-005**: The dashboard MUST show a dated greeting, counts of active cases, hearings this week and drafts to review, upcoming hearings linking to their cases, a quick-ask input, and recent activity.
- **FR-006**: The system MUST answer legal questions only from an indexed corpus of Indian law (including BNS, BNSS, BSA, the Constitution of India and other listed Acts), with numbered citations naming the Act and section or the judgment.
- **FR-007**: When no reliable source exists, the system MUST say so and MUST NOT present an uncited answer as fact.
- **FR-008**: Every legal answer MUST display "Informational only, not legal advice".
- **FR-009**: The system MUST offer suggested questions and voice input for asking questions.
- **FR-010**: The system MUST list cases with search by party, CNR number or court, status filters, status chips and next hearing date, with rows operable by keyboard.
- **FR-011**: The case detail MUST show title, CNR, court, status, next hearing, parties, documents, tabbed sections, and shortcuts to Ask MrCourt and Draft document.
- **FR-012**: The system MUST provide drafts from four templates, mark them as AI-generated and requiring review, allow editing and saving, track a version, and allow export as a Word (.docx) or PDF file, chosen by the user, only on explicit user action.
- **FR-013**: The settings MUST include profile and verification status, language, WhatsApp reminders switch, hearing alert timing, privacy and data management, and help and support.
- **FR-014**: The system MUST persist users, roles, cases, hearings, documents, drafts, settings and theme preference.
- **FR-015**: The system MUST honour DPDP Act obligations: stated purpose for data collected, minimal collection, and user ability to access and export their data. A deletion request MUST deactivate the account (no further sign-in) and remove the user's non-case personal data such as question history and preferences, while case records are retained indefinitely for legal record-keeping. The user MUST be told this before confirming.
- **FR-016**: The interface MUST reproduce the supplied prototype's layout, copy, icons, colours and typography in both light and dark themes.
- **FR-017**: The interface MUST be fully usable by keyboard with visible focus, respect reduced-motion preferences, and work on mobile widths.
- **FR-018**: Features not yet available MUST say so to the user rather than appearing to work.

### Key Entities

- **User**: A person with a role (Advocate or Petitioner), contact details, credentials, verification status and preferences.
- **Case Invitation**: An Advocate's invitation for a Petitioner to view a case; has a status (pending, accepted, removed).
- **Case**: A legal matter with title, CNR number, court, status (Active, Hearing soon, Closed), parties and an owner.
- **Hearing**: A dated, timed appearance belonging to a case.
- **Party**: A petitioner or respondent attached to a case.
- **Document**: A file attached to a case, with name and size.
- **Draft**: A generated and user-edited legal document with template type, case link, version and last-edited time.
- **Legal Source**: An indexed provision or judgment (Act, section, text) used for citations.
- **Conversation / Answer**: A user question, the cited answer given, and its citations.
- **Activity Event**: A recent change shown in the dashboard feed.
- **Settings**: Language, reminder switches, alert timing and theme choice for a user.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of legal answers shown include at least one citation or the explicit "no reliable source" message.
- **SC-002**: In review of a sample of 100 covered questions, at least 95% of cited sections correctly support the statements made.
- **SC-003**: A returning user can sign in and see their next hearing in under 30 seconds.
- **SC-004**: Users receive an answer to a typical question within 10 seconds of submitting it.
- **SC-005**: Finding a case by party, CNR or court takes under 15 seconds for 90% of test users.
- **SC-006**: 90% of first-time users complete the path from sign-in to a cited answer without help.
- **SC-007**: Every screen can be completed using only the keyboard and meets WCAG 2.1 AA contrast in both themes.
- **SC-008**: Every screen renders without horizontal page scrolling at 360px width.
- **SC-009**: No user can view another user's case data in any tested scenario.
- **SC-010**: 100% of AI drafts show the review warning, and 0 documents are sent or filed without an explicit user action.

## Assumptions

- The product launches in English; other languages follow later.
- Advocates are the primary users; Petitioners have limited, view-only access as defined in FR-019.
- Case and hearing data is entered manually by Advocates; bulk import and live integration with court systems are out of scope for this version.
- WhatsApp reminders and one-time passcodes depend on third-party messaging services being available.
- Bar Council verification uses the registration number supplied by the advocate and is confirmed manually by an administrator; automated lookup is out of scope for this version.
- The curated legal corpus is prepared and maintained separately; coverage limits are reflected in "no reliable source" responses.
- Sample data in the prototype (names, case numbers, credentials) is fictional and not carried into production.
- The technology choices (React with TypeScript, Python, PostgreSQL) are decided in the planning phase.
