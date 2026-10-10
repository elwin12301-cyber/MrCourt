# Feature Specification: Client Case Status ("My Lawyer, My Case")

**Feature Branch**: `002-client-case-status`

**Created**: 2026-10-07

**Status**: Draft

**Input**: User description: "Client (petitioner) experience for MrCourt. Today a petitioner who signs in sees the same advocate-style screens in read-only form. Redesign it so a client sees their own matters from their own point of view: who my lawyer is, what the status of my case is, what happens next, updates, privacy and control, and Ask MrCourt for clients. Advocates keep their current screens, plus controls to set the client-facing status, choose what to share, and write short client updates."

## Clarifications

### Session 2026-10-07

- Q: How is the client-facing status chosen? → A: The advocate picks it from a fixed list; the client's screen shows it in plain language. (Assumed from the description; to be confirmed in `/speckit-clarify` if wrong.)
- Q: Which case events should a client see automatically, without the advocate having to share each one? → A: Status changes and hearing dates and times are always visible to the client. Hearing outcomes, documents and timeline notes stay internal until the advocate explicitly shares them.
- Q: Can more than one client be invited to the same case, and can they see each other's names and questions? → A: Several clients per case. They share the same case view (status, hearings, shared items), but each client's questions and the advocate's replies are private to that client.
- Q: Which statuses should the advocate be able to choose from for the client-facing status? → A: Four statuses: Notice stage, Hearing scheduled, Awaiting order, Closed.
- Q: How quickly should an advocate be expected to answer a client's question, and what does the client see while waiting? → A: No expectation is shown. The client sees only "Sent" until a reply arrives.
- Q: What should "what will happen at the hearing" show for a client, and who writes it? → A: MrCourt writes a description for every hearing automatically, using general legal information.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See where my case stands (Priority: P1)

A client signs in and lands on a page made for them: a greeting, each of their cases with a plain-language status (for example "Notice stage", "Hearing scheduled", "Awaiting order", "Closed"), the next hearing with its date, time, court and what will happen at it, and when the status last changed. They open a case and see a simple timeline of what has happened and what comes next.

**Why this priority**: "What is the status of my case?" is the main reason a client uses MrCourt. Nothing else matters if this is unclear.

**Independent Test**: Sign in as a client with one invited case that has a status, a next hearing and a few past events. Confirm the dashboard and case page answer "where does my case stand and what happens next" without any legal jargon.

**Acceptance Scenarios**:

1. **Given** a client with invited cases, **When** they sign in, **Then** the dashboard shows each case with its plain-language status, the next hearing (date, time, court, what will happen) and the date the status last changed.
2. **Given** a case with no upcoming hearing, **Then** the client sees "No hearing scheduled yet" and, where the advocate has said so, what is expected next.
3. **Given** a case the client opens, **Then** they see a timeline of past events and the next expected step, newest first, in plain language.
4. **Given** a closed case, **Then** it shows as "Closed" with the closing date and is kept out of the "active" count.
5. **Given** a client with no invited cases, **Then** the dashboard explains that their advocate will invite them and shows how that works.

---

### User Story 2 - Know who my lawyer is and ask them something (Priority: P1)

For every case, the client sees their advocate: name, whether the advocate's Bar Council registration is verified, the court, and any contact details the advocate has chosen to share. The client can send their lawyer a question or ask for an update, and sees the answer when it arrives.

**Why this priority**: Clients mostly want to reach their lawyer. Seeing who that is and getting an answer inside the app reduces phone chasing.

**Independent Test**: As a client, open a case, view the advocate's details, send a question, and confirm the advocate sees it and can reply, and the client sees the reply.

**Acceptance Scenarios**:

1. **Given** a case, **Then** the client sees "My lawyer" with the advocate's name, verified status and only the contact details the advocate has chosen to share.
2. **Given** an unverified advocate, **Then** the client sees "Verification pending" rather than a verified badge.
3. **Given** a client on a case page, **When** they send a question or tap "Ask for an update", **Then** it is delivered to the advocate and the client sees it listed as sent.
4. **Given** the advocate replies, **Then** the reply appears under the question and is marked as new to the client.
5. **Given** an empty or very long message, **Then** it is not sent and the client is told why.

---

### User Story 3 - Be told when something changes (Priority: P2)

When the advocate changes the status, schedules or reschedules a hearing, records a hearing outcome, shares a document, or replies to a question, the client sees it in an updates list with a clear unread indicator. Hearing reminders keep working through the client's existing reminder preference.

**Why this priority**: Without this the client must keep checking. It builds on the status view (Story 1).

**Independent Test**: As an advocate, change a case's status and reschedule a hearing; as the client, confirm both appear as unread updates, and the unread indicator clears once viewed.

**Acceptance Scenarios**:

1. **Given** the advocate changes the status, schedules or reschedules a hearing, records an outcome, shares a document or replies to a question, **Then** the client gets a short update naming the case and what changed.
2. **Given** unread updates, **Then** the dashboard and navigation show an unread count, and viewing an update marks it read.
3. **Given** a client who has reminders switched on and a phone number, **Then** they receive the existing hearing reminders.
4. **Given** an update about an item the advocate has since stopped sharing, **Then** the client no longer sees the item itself.

---

### User Story 4 - Advocate controls what the client sees (Priority: P1)

An advocate sets the client-facing status of each case from a fixed list, writes short plain-language updates, and decides item by item what is shared with the client: hearing outcomes, documents and timeline notes. Private notes and internal documents are never shown to clients.

**Why this priority**: The client view only works if advocates can feed it and are confident nothing private leaks. It is required for Stories 1 and 3 to have content.

**Independent Test**: As an advocate, mark one document shared and one internal, set a status and write an update; as the client, confirm only the shared document, the status and the update are visible, and private notes never appear.

**Acceptance Scenarios**:

1. **Given** a case, **When** the advocate picks a client-facing status from the list, **Then** the client sees that wording and the date it changed.
2. **Given** a document, hearing outcome or timeline note, **Then** the advocate can mark it "Share with client" or leave it internal, and the default is internal.
3. **Given** the advocate writes a short update, **Then** the client sees it in the timeline and updates list.
4. **Given** private notes or internal documents, **Then** they are never visible to the client by any route.
5. **Given** the advocate unshares an item, **Then** it disappears from the client's view.

---

### User Story 5 - Know my privacy and ask general legal questions safely (Priority: P2)

A client can see which advocate can view their data for each case, and can ask MrCourt general legal questions with citations as today. Anything that looks like a request for advice on their own case is answered with general information only and a prompt to ask their lawyer.

**Why this priority**: Protects the client and the product's rule that MrCourt gives information, not legal advice.

**Independent Test**: As a client, view the "Who can see my case" information; ask a general question and a "should I accept this settlement" question; confirm the first is answered with citations and the second gets general information plus a pointer to their lawyer, with the disclaimer on both.

**Acceptance Scenarios**:

1. **Given** a case, **Then** the client can see which advocate can view their data and since when.
2. **Given** a general legal question, **Then** the answer cites its sources as today, with the disclaimer.
3. **Given** a question about the client's own situation (for example whether to accept an offer), **Then** the answer states that MrCourt cannot advise on their case and suggests asking their lawyer, with a one-step way to do so.
4. **Given** the client uses Ask MrCourt from within a case, **Then** the case is not used to give case-specific advice.

---

### Edge Cases

- A client invited to several cases with different advocates: each case shows its own advocate, and the list groups clearly.
- The advocate changes the status several times quickly: the client sees the latest status, the timeline shows each change.
- A document is shared, then unshared: the client's earlier update refers only to "a document" and the link stops working.
- A case's real stage does not fit one of the four statuses neatly (for example it is in evidence): the advocate picks the closest one and explains the detail in a short client update.
- The advocate never sets a client-facing status: the client sees "Your lawyer has not shared a status yet" instead of a blank.
- The advocate removes the client's invitation: the case and its updates disappear from the client's view.
- A client's account is deactivated: their questions and updates are removed with their personal data; the advocate's case records stay.
- A question stays "Sent" for a long time: nothing changes on the client's screen; the client can send a follow-up or use "Ask for an update".
- The client sends a question after the advocate deactivated: the client is told their lawyer is no longer available on MrCourt.
- Two clients are invited to the same case: both see the same shared case information; neither sees the other's questions, replies or unread state. If one is removed, the other keeps access.
- Very small screens: status, next hearing and unread count remain readable without horizontal scrolling.
- A hearing has no recorded purpose and the case stage does not tell us what kind of hearing it is: the client sees only the date, time and court, not a guess.
- A hearing outcome contains something the advocate considers sensitive: it stays internal unless explicitly shared, while the hearing's date and time remain visible.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Signed-in petitioners MUST see a client dashboard instead of the advocate dashboard, showing a greeting, their cases with plain-language status, the next hearing for each, latest updates and their lawyer.
- **FR-002**: Each case MUST carry a client-facing status chosen by the advocate from exactly four options: Notice stage, Hearing scheduled, Awaiting order and Closed, with the date it last changed. Anything more specific is given through the advocate's short client updates, not through extra statuses.
- **FR-003**: The client case page MUST show the next hearing (date, time, court) and, for every hearing, a short plain-language description of what usually happens at that kind of hearing, written automatically by MrCourt from general legal information (see FR-021), or say that no hearing is scheduled.
- **FR-004**: The client case page MUST show a timeline of what has happened and what comes next, in plain language, ordered newest first.
- **FR-005**: The client case page MUST show the hearing history (dates and times) and MUST show a hearing's outcome only where the advocate has shared it.
- **FR-006**: Status changes and hearing dates and times MUST always be visible to the client. Hearing outcomes, documents and timeline notes MUST be visible only after the advocate explicitly shares them; their default is not shared.
- **FR-007**: Advocate private notes and internal documents MUST NOT be visible to clients through any screen or download.
- **FR-008**: The client case page MUST show "My lawyer": name, verification status and only the contact details the advocate has chosen to share.
- **FR-009**: Clients MUST be able to send their advocate a question or request an update from a case, and see the advocate's reply. While waiting, the client sees the question marked "Sent"; the product shows no promised response time and sends the advocate no overdue reminders.
- **FR-010**: The system MUST tell the client when the advocate changes the status, schedules or reschedules a hearing, records a shared outcome, shares a document or replies, as an update with an unread indicator that clears when viewed.
- **FR-011**: Hearing reminders MUST continue to follow the client's existing reminder preference and phone number.
- **FR-012**: Clients MUST be able to see which advocate can view their data for each case and since when, and that other clients on the same case can see the shared case information.
- **FR-013**: Ask MrCourt for clients MUST keep citations and the disclaimer, MUST NOT give advice on the client's own case, and MUST point to their lawyer for case-specific advice.
- **FR-014**: Advocates MUST be able to set the client-facing status, write short client updates, and mark each document, outcome and timeline note as shared or internal.
- **FR-015**: Advocates MUST keep all current screens and abilities.
- **FR-016**: Clients MUST only ever see their own cases, and a removed invitation MUST remove the case and its updates from the client's view.
- **FR-020**: A case MAY have several invited clients. They MUST see the same status, hearings and shared items, but each client's questions and the advocate's replies to them MUST be visible only to that client and the advocate; clients MUST NOT see other clients' questions, replies or update read states.
- **FR-017**: Client messages and updates MUST be removed when the client deactivates their account, while the advocate's case records are kept.
- **FR-018**: Client screens MUST use the existing design system, work by keyboard, meet WCAG 2.1 AA in light and dark themes, and work at 360px width.
- **FR-019**: Client-facing wording MUST avoid legal jargon where possible, and legal terms that remain MUST have a plain-language explanation available.
- **FR-021**: The automatic hearing description MUST be general information about that kind of hearing, never about the client's particular case; MUST be labelled as general information with the "Informational only, not legal advice" line; MUST be based on the hearing's recorded purpose or the case's stage and on cited legal sources where the law is referred to; MUST NOT predict outcomes, advise what to do, or state facts about the case that the advocate has not recorded; and, when there is no reliable basis, MUST be replaced by the date, time and court alone.

### Key Entities

- **Client Status**: A case's client-facing status (one of Notice stage, Hearing scheduled, Awaiting order, Closed), the date it changed, and who changed it.
- **Timeline Entry**: A dated event on a case (status change, hearing, outcome, update, document shared) with a plain-language description and a shared-or-internal setting.
- **Client Update**: A notice to a client about a change, linked to a case and timeline entry, with a read or unread state.
- **Client Question**: A message from one client to their advocate about a case, with the advocate's reply and read states. Private to that client and the advocate.
- **Sharing Setting**: For each document, hearing outcome or note, whether it is shared with the client (default: not shared). Status changes and hearing dates and times are not subject to this setting.
- **Advocate Contact Card**: The details an advocate has chosen to show clients (name, verification, optional phone and email, optional office address).
- **Term Explanation**: A short plain-language explanation of a legal term shown beside it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A client can find the status of their case and its next hearing within 15 seconds of signing in, without help, in at least 90% of test sessions.
- **SC-002**: In reviews of 30 client-facing screens, no private note or internal document is ever visible to a client (0 leaks).
- **SC-003**: A client can send their lawyer a question in under 30 seconds from the dashboard.
- **SC-004**: 90% of client updates appear on the client's screen within 1 minute of the advocate's change.
- **SC-005**: At least 80% of surveyed clients can say what happens next in their case after viewing the case page.
- **SC-006**: Every client-facing screen passes WCAG 2.1 AA checks in light and dark themes at 360px and 1280px widths.
- **SC-007**: 100% of Ask MrCourt answers to clients carry the disclaimer, and 100% of questions about the client's own case get the "ask your lawyer" prompt.
- **SC-008**: An advocate can set a client-facing status and write an update in under 1 minute.

## Assumptions

- This feature builds on feature 001: the same sign-in, roles, invitations, reminders and design system.
- The status list is fixed at four options for this version (no custom statuses and no per-case wording); the advocate chooses the one that fits and adds detail through short client updates.
- Questions to the advocate are simple messages with a reply, not live chat; they are not an advice channel and carry the same disclaimer. No response time is promised or enforced; an advocate who wants to be faster can use short client updates.
- Updates appear inside MrCourt; sending update alerts through WhatsApp or SMS is out of scope, other than existing hearing reminders.
- Advocates decide what contact details clients see; by default only name and verification status are shared.
- Plain-language explanations of terms come from a maintained glossary. Hearing descriptions are written automatically from general legal information under the guardrails in FR-021; advocates cannot edit them in this version but can add their own short client updates alongside.
- A case has one advocate (its owner) and may have several invited clients; clients with several advocates see each case separately.
- Status changes and hearing dates and times are always visible to the client. Documents, outcomes and timeline notes default to internal; sharing them is always an explicit advocate action.
- English only for this version.
