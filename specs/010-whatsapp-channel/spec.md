# Feature Specification: WhatsApp channel (consent-based, two-way)

**Feature Branch**: `010-whatsapp-channel`

**Created**: 2026-10-13

**Status**: Draft

**Input**: User description: "WhatsApp integration for MrCourt. Today WhatsApp is used only one way (login codes and hearing reminders) through three adapters (Twilio sandbox, Fast2SMS, Meta Cloud) that were never tested against the live service, and client case updates and advocate messages appear only inside the app. Turn it into a consent-based, two-way channel where people already are: outbound codes, hearing reminders, case updates with delivery status and a text-message fallback; inbound legal questions with cited answers, next hearing and case status, and voice notes; account linking through the existing code check; DPDP-aligned privacy with opt-in per kind of message and STOP; reliability and safety; a provider-neutral design with the free sandbox for testing."

## Current behaviour (baseline)

- **One way only.** WhatsApp (or SMS) carries login and verification codes and hearing reminders (5 days before, 1 day before, on the day). Nobody can write back.
- **Client updates stay inside the app.** When an advocate changes a case status, reschedules a hearing or writes an update, the client sees it only after opening MrCourt. A client who never opens the app learns nothing.
- **One switch.** A single "text message reminders" setting covers everything; there is no choice per kind of message, no per-channel consent record and no "STOP".
- **Untested sending.** Three sending options exist (a free sandbox, an Indian SMS provider with WhatsApp templates, and the WhatsApp Business interface) but none has been proven against the live service. Delivery is fire-and-forget: the product never learns whether a message arrived, and failures are only logged.
- **Questions need the app.** Legal questions, case status and the next hearing can be asked only on the website.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Link my WhatsApp number and choose what I receive (Priority: P1)

A signed-in advocate or petitioner opens Settings, enters (or confirms) the phone number, proves it with a code, and then sees a short list of the kinds of WhatsApp message MrCourt can send: login codes, hearing reminders, case updates (clients) or client activity (advocates). Each kind is off until the person turns it on, and the screen says in one sentence what each contains. They can unlink the number at any time, and a person can also stop everything by replying STOP.

**Why this priority**: nothing else may be sent or read without a verified number and an explicit choice. It is the consent foundation required by the privacy principle, and it is useful alone as a safe way to prove a number.

**Independent Test**: Verify a number, switch "hearing reminders" on and "case updates" off, send a test message, reply STOP, and confirm nothing further is sent and the screen shows everything off.

**Acceptance Scenarios**:

1. **Given** a signed-in person without a linked number, **When** they enter a number and the code that arrives, **Then** the number is linked and every kind of message is still off.
2. **Given** a linked number, **When** the person switches a kind on, **Then** the screen records when they agreed and states what that kind contains.
3. **Given** a number already linked to another account, **When** someone tries to link it, **Then** it is refused with a message that does not say whose number it is.
4. **Given** a linked number, **When** the person unlinks it, **Then** nothing more is sent, inbound messages from it are no longer answered, and the screen offers to link again.
5. **Given** a person sends STOP, **When** the message arrives, **Then** all kinds switch off at once, a single confirmation is sent, and the Settings screen shows them off.
6. **Given** an unverified number, **Then** no message of any kind is ever sent to it.

---

### User Story 2 - Hearing reminders and codes on WhatsApp, with proof of delivery (Priority: P1)

A person who has opted in receives login or verification codes and hearing reminders (5 days before, 1 day before, and on the day) on WhatsApp. The product keeps the status of each message (sent, delivered, read, failed). When a WhatsApp message fails or the number is not on WhatsApp, the same content goes out by text message so the reminder is not lost. Reminders still go once per person per hearing.

**Why this priority**: reminders are the most valuable thing the channel already promises, and today nobody knows whether they arrive.

**Independent Test**: Create a hearing 5 days away for a case with an opted-in advocate and client, run the reminder job, and confirm each gets one WhatsApp message with status "delivered"; mark one number as "not on WhatsApp" and confirm that person receives a text message instead.

**Acceptance Scenarios**:

1. **Given** an opted-in person and a hearing 5, 1 or 0 days away, **When** the reminder job runs, **Then** they receive one WhatsApp message naming only the case and the date and time, and never a duplicate.
2. **Given** WhatsApp reports the message failed or the number is not on WhatsApp, **When** the failure is known, **Then** the same short message is sent once by text message and the record shows both attempts.
3. **Given** a person who has not opted in to hearing reminders, **Then** no reminder is sent to them on either channel. (A code the person has just asked for is always sent, because they requested it.)
4. **Given** a login code is requested, **When** the number is linked, **Then** it goes by WhatsApp first and by text message if that fails, and the screen reply is identical whether or not an account exists.
5. **Given** a hearing is rescheduled, **Then** the reminder schedule restarts, as today.
6. **Given** a delivery update arrives from WhatsApp, **Then** the stored status moves forward (sent, delivered, read) and never backwards.

---

### User Story 3 - Ask a legal question on WhatsApp (Priority: P1)

A person with a linked number sends a question to the MrCourt WhatsApp number, for example "What is Section 138 of the NI Act?". They receive an answer built the same way as in the app: written from the sources, each claim cited, with the "informational, not legal advice" line, and the plain "no reliable source found" reply when nothing fits. Answers are kept short for a phone, list their sources by name, and end with a link to read more in the app.

**Why this priority**: it is the main reason to be on WhatsApp: people can get a cited answer without opening a website.

**Independent Test**: From a linked number, ask a question the sources answer, one they cannot answer, and one naming a section that does not exist; confirm a cited answer, the no-source reply and the "not found in the sources" reply respectively, and that the three also appear in the person's question history in the app.

**Acceptance Scenarios**:

1. **Given** a linked number, **When** the person sends a legal question, **Then** within the response time they receive a cited answer with the disclaimer and a link to the full answer in the app.
2. **Given** no reliable source, **Then** the reply says so plainly and suggests how to rephrase; it never guesses.
3. **Given** a question that names a section the sources do not contain, **Then** the reply says that section was not found and does not pass off another as it.
4. **Given** a petitioner asks for advice about their own case, **Then** the existing client rule applies: general information only, with the reminder to ask their lawyer.
5. **Given** a number that is not linked, **When** it sends any message, **Then** the reply explains how to link a number in the app and contains nothing about any account, and **Given** an unlinked number sends repeated messages, **Then** replies stop after a small number.
6. **Given** the answer service is busy, **Then** the person gets a short "try again in a minute" reply and no wrong answer.
7. **Given** a WhatsApp question, **Then** it is stored as any question is (history, retention and deletion rules identical) and marked as asked by WhatsApp.

---

### User Story 4 - Next hearing and case status by WhatsApp (Priority: P2)

A linked advocate or client sends "next hearing" or "status" (or taps a suggested reply). A client sees only the cases they were invited to and only what the advocate has shared: the client-facing status and next hearing date. An advocate sees their own cases: today's and the next hearings and a short count of open cases. A person with several cases is asked to pick one from a short list.

**Why this priority**: the second most common question after "what does the law say" is "when is my hearing"; it needs no AI and is highly reliable.

**Independent Test**: As a client invited to one of two advocate cases, send "next hearing" and "status"; confirm only the invited case appears; as the advocate, confirm both cases appear.

**Acceptance Scenarios**:

1. **Given** a client with one invited case, **When** they send "next hearing", **Then** they get that case's title, date, time and court.
2. **Given** a client with several invited cases, **When** they ask, **Then** they are offered a numbered list and the next message picks one.
3. **Given** a case the advocate has not shared, or an invitation removed, **Then** it is never mentioned.
4. **Given** an advocate, **When** they send "today", **Then** they get today's hearings across their own cases.
5. **Given** a person asks about a case that is not theirs by name or number, **Then** the reply is the same as for a case that does not exist.

---

### User Story 5 - Clients get a nudge when their advocate posts an update (Priority: P2)

When an advocate changes a case status, schedules or reschedules a hearing, records an outcome, shares a document or replies to the client's question, a client who has opted in to case updates receives a short WhatsApp message that says only that there is news on the named case ("There is a new update on <case title>. Open MrCourt to read it."). The detail stays in the app.

**Why this priority**: it closes the gap where clients never learn about updates; it is kept minimal on purpose so private case detail never travels over WhatsApp.

**Independent Test**: As an advocate, change a case status for a client who opted in and one who did not; confirm only the first gets a message, and that it contains the case title but not the status text, notes or document names.

**Acceptance Scenarios**:

1. **Given** an opted-in client and an advocate's update, **Then** one short message is sent naming the case, with no update text, document name or note.
2. **Given** several updates within a few minutes, **Then** the client gets one message, not one per change.
3. **Given** a client who is not opted in, who unlinked, or whose invitation was removed, **Then** nothing is sent.
4. **Given** the advocate stops sharing an item, **Then** a message already sent reveals nothing about it.

---

### User Story 6 - Send a voice note instead of typing (Priority: P2)

A linked person sends a WhatsApp voice note with a question. MrCourt turns it into text, shows the person what it understood ("I heard: …"), and answers as in Story 3. If the speech cannot be understood, it asks the person to try again or type.

**Why this priority**: many users prefer speaking, in English, Hindi or Tamil; the app already supports this on the website.

**Independent Test**: Send a clear voice question and an unclear one; confirm the first is quoted back and answered, the second gets a polite "could not understand" reply.

**Acceptance Scenarios**:

1. **Given** a voice note in a supported language, **Then** the reply begins with what was understood, followed by the answer.
2. **Given** audio that cannot be turned into text with enough confidence, **Then** no answer is attempted and the person is asked to try again or type.
3. **Given** a voice note, **Then** the audio is deleted after it is converted and only the text is kept.

---

### User Story 7 - Administrators see that it works, without reading messages (Priority: P2)

An administrator opens an "Messages" view showing counts by kind and status (sent, delivered, read, failed, fallback to text) for a chosen period, a list of recent failures with the reason and the affected person's name, and the connection health of the WhatsApp service. The view never shows message text, the questions people asked or the contents of answers. Anything an administrator does here (for example re-sending a failed reminder) is audited.

**Why this priority**: without it nobody can tell whether reminders are reaching people.

**Independent Test**: Send messages that succeed, fail and fall back; confirm the counts and failure list are right and that no message text appears in the page, the data returned or the audit log.

**Acceptance Scenarios**:

1. **Given** a day of messages, **Then** counts per kind and status are correct and totals match the stored records.
2. **Given** a failed message, **Then** it is listed with a plain reason (for example "not on WhatsApp") and the person's name, never the text.
3. **Given** an administrator opens the view, **Then** the screen meets the accessibility rules in both themes and at phone width.

---

### Edge Cases

- A person changes their phone number: the old number stops receiving messages immediately; the new one must be verified and consented to again.
- A number is passed on to someone else by the phone company: the new owner may message the number; because the number is linked to an account they do not control, they get only the "how to link" reply. A verified-number check (a code) is repeated periodically for numbers that stay silent for a long time.
- WhatsApp only allows free-form replies within 24 hours after the person last wrote; outside that window only pre-approved template messages are allowed. Reminders and update nudges always use templates; answers are sent only in reply to a question just asked.
- A person sends the same message twice, or the provider delivers one message twice: it is handled once.
- A very long question or an attachment that is not text, audio or a document: the reply says what is supported (text and voice notes) and nothing else is stored.
- A person sends a picture of a document: not supported in this version; the reply says so and points to the app.
- A message arrives that the provider did not sign correctly: it is ignored, logged without its content, and not acted on.
- Several people share one phone: only one account can link a number; the others are told to use their own.
- A person is deactivated: the number is unlinked, consents and message history are deleted with their personal data, and the audit log keeps only that it happened.
- The WhatsApp service is down: reminders fall back to text message, question replies are not queued for later, and the administrator view shows the service as unhealthy.
- A reminder and an update nudge fall within the same minute for the same case: one combined short message.
- A message contains a legal question that also contains personal details (names, case numbers): it is treated like any question in the app, stored with the person's history only, and never shown to administrators.

## Requirements *(mandatory)*

### Functional Requirements

**Linking and consent**

- **FR-001**: A signed-in person MUST be able to link one phone number to their account by confirming a code sent to it, and unlink it at any time. A number MUST belong to at most one account.
- **FR-002**: Nothing MUST be sent to a number that is not verified and linked. The one exception is the verification or login code the person has just asked for.
- **FR-003**: Each kind of WhatsApp message (login codes, hearing reminders, case updates, client activity for advocates) MUST be off until the person turns it on, with the time of consent recorded and a one-sentence description of its content shown at the switch.
- **FR-004**: Replying STOP (and equivalent words in English, Hindi and Tamil) MUST switch every kind off immediately and send one confirmation. A "START" reply MUST NOT turn anything back on by itself; the person re-enables in Settings.
- **FR-005**: The Settings screen MUST show the linked number (partly masked), each kind with its switch, the date of consent, and the time of the last message sent, and MUST work by keyboard, in both themes and at phone width.

**Outbound messages**

- **FR-006**: Hearing reminders MUST go to opted-in, verified advocates and clients 5 days before, 1 day before and on the day of a hearing, once per person per hearing, using the existing schedule and rescheduling rules.
- **FR-007**: A case-update message MUST be sent to an opted-in client when the advocate changes the case's status, schedules or reschedules a hearing, records an outcome, shares a document or replies to a question. Several changes close together MUST be combined into one message.
- **FR-008**: Outbound content MUST be minimal: a reminder names only the case title and the date and time; an update message names only the case title and says there is news. Documents, notes, outcomes, party names, update text and answers MUST NOT be sent outbound.
- **FR-009**: Outbound messages outside the 24-hour reply window MUST use pre-approved templates; free-form messages MUST be sent only as direct replies within the window.
- **FR-010**: The system MUST keep a status for every outbound message (queued, sent, delivered, read, failed) updated from the provider's delivery reports, which MUST only move forward.
- **FR-011**: When a WhatsApp message fails, or the number is not on WhatsApp, the same minimal content MUST be sent once by text message, and the record MUST show both attempts. A person who turned WhatsApp kinds off MUST NOT receive them by text unless they have also kept text reminders on.

**Inbound messages**

- **FR-012**: A message from a linked number containing a legal question MUST be answered by the same process as in the app: retrieval from the sources the person may use, a written answer from those sources only, every citation verified, the informational disclaimer, and the "no reliable source found" reply when nothing reliable is found.
- **FR-013**: WhatsApp answers MUST use only shared sources in this version (an advocate's private documents MUST NOT be quoted over WhatsApp), MUST be kept short for a phone, MUST name their sources, and MUST end with a link to the full answer in the app.
- **FR-014**: A petitioner's questions MUST follow the existing client rules (general information only, reminder to ask their lawyer for advice about their own case).
- **FR-015**: A linked person MUST be able to ask for the next hearing and case status. Clients MUST receive only cases they were invited to and only what the advocate has shared; advocates only their own cases. A request about a case the person may not see MUST get the same reply as one that does not exist.
- **FR-016**: A voice note from a linked number MUST be converted to text, quoted back to the person, and answered as a typed question; audio MUST be deleted after conversion; low-confidence audio MUST not be answered.
- **FR-017**: A message from a number that is not linked MUST receive only a fixed reply explaining how to link a number in the app. The reply MUST NOT depend on whether an account exists for that number.
- **FR-018**: Every question asked by WhatsApp MUST be stored in the person's question history, marked as asked by WhatsApp, under the same retention and deletion rules.

**Safety and reliability**

- **FR-019**: Every inbound request MUST be checked as genuinely from the provider (signature) before anything is read or stored; unsigned or altered requests MUST be ignored and logged without their content.
- **FR-020**: A message delivered more than once MUST be processed once.
- **FR-021**: The system MUST limit messages per number (for example, a small number of questions per minute and per day) and MUST reply once that the limit was reached rather than staying silent or answering late.
- **FR-022**: Provider credentials MUST NOT appear in the repository, responses, logs or the administrator view; the channel MUST be off, with the existing development outbox in use, when not configured.
- **FR-023**: The WhatsApp provider MUST be replaceable without changing the rest of the product: the channel is defined by what it must do (send a template, send a reply, receive a message, report delivery), with one target provider for production and a free sandbox for testing.

**Privacy and administration**

- **FR-024**: A person MUST be able to see and delete their WhatsApp message history held by MrCourt, and deactivating an account MUST unlink the number and delete consents, history and stored audio.
- **FR-025**: Message content (the text of messages sent or received and the contents of answers) MUST be kept only in the person's own question history and MUST NOT be visible to administrators; the message record kept for delivery tracking MUST hold kind, status, time and person, not text. Delivery records MUST be kept for 90 days and then deleted.
- **FR-026**: Administrators MUST see counts by kind and status, recent failures with reason and the affected person's name, and service health; the view MUST NOT show message text or questions. Administrator actions (for example re-sending a failed reminder) MUST be audited without message content.
- **FR-027**: Linking, unlinking, consent changes, STOP, administrator views of the failure list and re-sends MUST be recorded in the audit trail without message content.
- **FR-028**: New screens MUST use the existing design tokens and components, meet the accessibility rules, and work in both themes at desktop and phone widths.

### Key Entities *(include if feature involves data)*

- **WhatsApp link**: a verified number belonging to exactly one account, with when it was verified, when it last wrote and whether it is currently linked.
- **Consent**: for one account and one kind of message, whether it is on, when it was switched on or off, and what changed it (the person in Settings, a STOP reply, an administrator action on deactivation).
- **Outbound message record**: the kind, the person, the case it concerns (if any), the status over time (queued, sent, delivered, read, failed), whether it fell back to text message, the reason for a failure and the time; no message text.
- **Inbound message record**: provider message id (to ignore duplicates), the person (if linked), kind (question, voice note, status request, STOP, other) and time; the question text itself lives in the question history.
- **Conversation state**: the short-lived memory that a person is choosing from a list of cases, expiring after a few minutes.
- **Question (existing)**: gains the way it was asked (app or WhatsApp).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A person can link a number, turn on reminders and receive a test message in under 3 minutes.
- **SC-002**: At least 95% of hearing reminders to opted-in people reach them (delivered on WhatsApp or by the text message fallback) before the hearing, in a test of at least 50 reminders.
- **SC-003**: A person asking a question on WhatsApp receives an answer, the no-source reply or a "try again" reply within 30 seconds in at least 95% of tests.
- **SC-004**: In tests, every WhatsApp answer has the same citations and the same "no reliable source" behaviour as the same question asked in the app.
- **SC-005**: In tests, nothing is ever sent to a number that is unverified, unlinked, opted out, or belongs to a deactivated account, and STOP switches everything off within 5 seconds.
- **SC-006**: In tests, no outbound message contains anything beyond the case title and the date, time or the fact that there is news; no inbound or outbound message text appears in the administrator view, administrator data or audit trail.
- **SC-007**: In tests, a client never receives information about a case they were not invited to, and an unlinked number never learns whether an account exists.
- **SC-008**: In tests, a repeated, altered or unsigned incoming message never causes a second answer, a stored message or any data change.
- **SC-009**: Administrators can tell, from one screen, how many reminders were delivered, failed or fell back to text message for the last 7 days.

## Assumptions

- **Users**: advocates and petitioners with a verified phone number; administrators for the delivery view. One account per number.
- **Existing parts reused**: the code check for phone numbers, the hearing reminder schedule (5, 1 and 0 days) and job, the question flow with citations and the client advice rule, the speech-to-text service used on the website, the client updates and case invitations, the audit trail, and the development outbox.
- **Provider**: the production target is the WhatsApp Business interface from Meta; the free Twilio sandbox is used for testing (people must send its join phrase first). The Indian text-message provider already used stays the text-message fallback. Registering a WhatsApp Business account, verifying the business and getting message templates approved is the owner's responsibility and may take days; the product works with the channel switched off until then.
- **Cost and limits**: WhatsApp Business charges for template messages after any free allowance, and the free sandbox allows only people who joined it; costs and limits change and must be checked before launch.
- **Languages**: English first; Hindi and Tamil for the stop words and voice notes where the speech service supports them. Answers keep citations verbatim.
- **Out of scope for this version**: pictures and documents sent by the person; group chats; payments; sending an advocate's private documents or notes; WhatsApp replies from a client to their advocate (clients still use the app for that); marketing messages; calls.
- **Private documents**: answers over WhatsApp use shared sources only, because a WhatsApp message is stored by the provider outside MrCourt's control.
- **Retention**: delivery records are kept 90 days; questions follow the existing question-history rules; audio is deleted after conversion.
- **Privacy review**: sending any case-related content through a third-party messaging service must be reviewed against the DPDP Act and the organisation's policy before launch; this version limits content to minimise that exposure.
