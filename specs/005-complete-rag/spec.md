# Feature Specification: Complete RAG (Meaning-Based Search, OCR, Indian-Language Voice)

**Feature Branch**: `005-complete-rag`

**Created**: 2026-10-08

**Status**: Draft

**Input**: User description: "Add everything" from the earlier RAG project's Knowledge Assistant (meaning-based search with embeddings, OCR for scanned English and Tamil documents, server-side speech to text, a Text Assistant tab, a "Both assistants" History filter), using the keys the owner supplied, to make a complete RAG system.

## Clarifications

### Session 2026-10-08

- Q: How are the supplied keys used? → A: They are kept only in the git-ignored `backend/.env` (embeddings and speech to text), never shown in the app or committed. They were pasted into a chat, so the owner should rotate them when convenient.
- Q: Does server-side speech conflict with feature 004's "audio never reaches our servers"? → A: Yes, so it is opt-in. The browser microphone stays the default. A person must choose "Better for Tamil" or use the Text Assistant tab, with a notice that the audio is sent to the speech service and not stored by MrCourt.
- Q: Is OCR available on this machine? → A: No OCR engine is installed here. OCR is built and tested with a stand-in, and when the engine is missing a document fails with a clear reason and how to install it.

## What exists today

Feature 004 gave Ask MrCourt three tabs (Ask, Knowledge Base, History), an assistant, and browser voice. Search is keyword-only and finds the right page and facts for about 72% of the reference questions. Scanned documents are refused. Citations show a label only. This feature closes those gaps and adds the Text Assistant tab from the reference screen.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Loosely worded questions find the right passage (Priority: P1)

A person asks a question in their own words, such as "Who appeared for the parties?" or "What was the final result?". MrCourt finds the passage that answers it even though the passage uses different words ("For Appellant", "dismissed"), by combining keyword ranking with meaning-based ranking. The answer cites that passage. If meaning-based search is not available (no key, or the service is down), search quietly falls back to keywords and the screen says which mode is active.

**Why this priority**: This is the difference between a keyword lookup and a real RAG system, and it is the shortfall measured in feature 004.

**Independent Test**: Run the reference question set and compare with the keyword-only result (72%). Then turn the service off and confirm the fallback and the on-screen note.

**Acceptance Scenarios**:

1. **Given** the reference judgment is in the knowledge base, **When** the reference questions are asked, **Then** at least 90% find the right page and the facts of the expected answer.
2. **Given** a source is added, **When** it becomes Ready, **Then** its passages already have meaning-based search data, so it can be found by meaning straight away.
3. **Given** the embedding service has no key or fails, **When** a question is asked, **Then** the answer still works from keyword ranking, and the mode note says "keyword search only".
4. **Given** passages that existed before this feature, **When** a one-off command is run, **Then** they gain meaning-based search data without being re-added, and running it again does nothing new.
5. **Given** a question, **When** it is searched, **Then** only passages the person may use are considered (private notes stay private), exactly as before.
6. **Given** a question with no relevant source, **Then** the answer still says "no reliable source" and cites nothing; meaning-based search never invents a source.

---

### User Story 2 - Scanned documents become searchable (Priority: P1)

An advocate or administrator adds a scanned PDF or an image (PNG, JPEG, TIFF) in English or Tamil. MrCourt reads the pages with OCR and the document becomes searchable; pages that were read by OCR are marked as such, because OCR can make mistakes. If OCR is not installed on the server, the document fails with a clear reason and how to fix it.

**Why this priority**: Real court papers are often scans; the reference folder has four scanned Tamil documents that could not be used.

**Independent Test**: Add a scanned page (image) containing known words; confirm it becomes Ready, is found by a question about those words, and is marked OCR. Remove the OCR engine and confirm a clear failure.

**Acceptance Scenarios**:

1. **Given** a scanned PDF, **When** it is added, **Then** its pages with no readable text are OCR-read and the document becomes Ready with those pages marked "read by OCR".
2. **Given** an image file, **When** it is added, **Then** it is treated as one page and read by OCR.
3. **Given** OCR is not installed, **When** a scan is added, **Then** it shows Failed with a plain reason that names what to install.
4. **Given** a cited passage from an OCR page, **Then** the answer shows that it came from a scanned page.
5. **Given** a very large scan, **Then** limits (pages and size) apply and a clear message explains them.
6. **Given** Tamil text, **Then** OCR is attempted in English and Tamil together.

---

### User Story 3 - Ask in Tamil and other Indian languages (Priority: P2)

A person types or speaks a question in Tamil. MrCourt searches English and Tamil passages by meaning and answers, saying which language the sources are in. Citations are never translated or altered.

**Why this priority**: Many clients and advocates work in Tamil; meaning-based search makes this possible without a separate Tamil index.

**Independent Test**: Ask the reference questions in Tamil and confirm the right English passages are found and the answer states the sources are in English.

**Acceptance Scenarios**:

1. **Given** a Tamil question, **When** asked, **Then** relevant English or Tamil passages are found and cited.
2. **Given** the sources found are in English, **Then** the answer says so ("The sources are in English").
3. **Given** keyword-only mode (no embeddings), **Then** a Tamil question says honestly that Tamil search needs the meaning-based mode, instead of returning nothing silently.
4. **Given** the "Better for Tamil" voice option, **When** the person speaks Tamil, **Then** the transcript fills the question box for editing.

---

### User Story 4 - Text Assistant: speak, transcribe, keep, share (Priority: P2)

On a new Text Assistant tab a person taps the microphone and speaks. Each turn is sent to the speech service, transcribed, and added as a line in a conversation. They can also type lines, edit or remove lines, download the conversation as a PDF, and (advocates and administrators) add it to the knowledge base as a private note or shared source so it can be searched. A notice says the audio is sent to the speech service and not stored by MrCourt. Conversations are saved in the person's account and can be deleted.

**Why this priority**: It completes the reference screen's tabs and makes meetings and dictated notes searchable.

**Independent Test**: Speak two turns (with a stand-in speech service), edit a line, download the PDF, add it to the knowledge base, and ask a question that its text answers.

**Acceptance Scenarios**:

1. **Given** the Text Assistant tab, **Then** it shows a notice that audio goes to the speech service and is not stored by MrCourt, and nothing is recorded until the person taps the microphone.
2. **Given** a spoken turn, **When** it ends, **Then** the transcript is added as a line marked Voice, in the chosen language.
3. **Given** the speech service is off or fails, **Then** a clear message appears and the person can type lines instead.
4. **Given** a conversation, **Then** lines can be edited and removed, and the conversation can be downloaded as a PDF.
5. **Given** an advocate, **When** they add the conversation to the knowledge base, **Then** it becomes a private note; an administrator can add it as a shared source.
6. **Given** a client, **Then** they can keep and download conversations but cannot add them to the knowledge base.
7. **Given** a conversation, **When** the person deletes it, **Then** it is gone from the Text Assistant tab, but its entry stays in History.
8. **Given** another person, **Then** they cannot see these conversations; administrators have no access except through the audit log rules of feature 003.

---

### User Story 5 - History covers both assistants (Priority: P3)

History gains a filter "Both assistants / Ask and Assistant / Text Assistant" beside the outcome filter, and Text Assistant conversations appear there with Open and Ask again. Entries stay even after the conversation itself is deleted.

**Why this priority**: Matches the reference screen and keeps one place for everything the person asked or dictated.

**Independent Test**: Have an Ask question, an Assistant request and a Text Assistant conversation; filter by each; delete the conversation and confirm its History entry stays.

**Acceptance Scenarios**:

1. **Given** the History tab, **Then** a source filter offers Both, Ask and Assistant, and Text Assistant, and works together with search and the outcome filter.
2. **Given** a Text Assistant conversation, **Then** a History entry shows its first line, date and that it was spoken or typed.
3. **Given** the conversation is deleted, **Then** the History entry remains and can still be opened (with the text it had).
4. **Given** account deletion, **Then** these entries are removed with everything else, as before.

---

### User Story 6 - Open a cited passage (Priority: P3)

From an answer, a person selects a citation and reads the cited passage with its document title and page, and sees whether it was read by OCR.

**Why this priority**: Citations are only trustworthy if the reader can check them.

**Independent Test**: Ask a question, open citation [1], and see the passage text, document and page.

**Acceptance Scenarios**:

1. **Given** an answer with citations, **When** the person selects one, **Then** the passage text, document title, page and OCR marking appear.
2. **Given** a private note, **Then** only its owner can open its passages.
3. **Given** the passage has since been removed, **Then** the person sees the stored label and a message that the source is no longer available.
4. **Given** History, **When** an old answer is opened, **Then** its citations open the same way.

---

### Edge Cases

- The embedding service is rate limited or slow: adding a source still completes (it retries and, if needed, marks passages for later embedding), and questions fall back to keywords for that moment.
- A document is added while the embedding key is missing: it becomes Ready for keyword search and is embedded later by the one-off command.
- OCR returns mostly noise (poor scan): the document is Ready but flagged "low confidence" and the reason is shown; the person can remove it.
- Mixed English and Tamil pages in one document: each page is read with both languages.
- Very long audio turn: limited with a clear message (short turns, 28 seconds each, are the unit).
- Microphone blocked or no speech heard: a clear message; typing continues to work.
- The speech service returns text in another language than selected: the line is kept as returned.
- Concurrent edits to a Text Assistant conversation from two tabs: the last save wins and nothing is lost line by line.
- A question in Tamil, no Tamil or English match: "no reliable source", cited nothing.
- Keys missing: every feature degrades to the previous behaviour with an honest note; nothing errors.

## Requirements *(mandatory)*

### Functional Requirements

**Meaning-based search**

- **FR-001**: Every passage MUST receive meaning-based search data when it becomes Ready, and every question MUST be embedded when asked, when the service is available.
- **FR-002**: Search MUST combine keyword ranking and meaning-based ranking into one ordered list, and MUST keep the minimum-evidence and citation-verification rules, so an answer without a verified source still says "no reliable source".
- **FR-003**: Owner filtering MUST be applied before ranking in both methods; a private passage MUST NOT be reachable through either.
- **FR-004**: If the embedding service has no key or fails, search MUST fall back to keyword ranking without error, and the screen MUST show which mode is active.
- **FR-005**: A one-off, repeatable command MUST add meaning-based search data to existing passages.
- **FR-006**: The retrieval quality script MUST report results for keyword-only and combined search on the reference question set.

**OCR**

- **FR-007**: Scanned PDFs and image files (PNG, JPEG, TIFF) MUST be readable through OCR in English and Tamil, with page and size limits.
- **FR-008**: Pages read by OCR MUST be marked, the marking MUST be shown with cited passages, and poor results MUST be flagged.
- **FR-009**: When OCR is not installed or fails, the document MUST end Failed with a plain reason that says what to install.

**Languages**

- **FR-010**: Questions in Tamil and other Indian languages MUST be accepted and searched by meaning against English and Tamil passages.
- **FR-011**: Answers MUST state the language of the sources used when it differs from the question's language, and citations MUST be shown verbatim.
- **FR-012**: In keyword-only mode a non-English question MUST say that this search needs the meaning-based mode.

**Voice and Text Assistant**

- **FR-013**: Server-side speech to text MUST be opt-in per use, MUST show a notice naming the speech service and that audio is not stored by MrCourt, and MUST NOT keep any audio.
- **FR-014**: The Ask tab MUST keep the browser microphone as the default and offer a "Better for Tamil" option that uses the speech service.
- **FR-015**: The Text Assistant tab MUST let a person speak or type lines, edit and remove lines, download a PDF, and delete the conversation; conversations MUST be private to their owner and saved to their account line by line.
- **FR-016**: Advocates MUST be able to add a conversation to the knowledge base as a private note, and administrators as a shared source; clients MUST NOT.
- **FR-017**: When the speech service is not configured or fails, the screen MUST say so and typing MUST continue to work.

**History and citations**

- **FR-018**: History MUST offer a source filter (Both, Ask and Assistant, Text Assistant) combining with search and outcome, and MUST keep entries after a conversation is deleted.
- **FR-019**: Selecting a citation MUST show the cited passage text, document title, page and OCR marking, to people allowed to see that passage.
- **FR-020**: Text Assistant conversations and their History entries MUST be included in data export and removed on account deletion.

**Cross-cutting**

- **FR-021**: Keys MUST be read only from the environment or the git-ignored `.env`, MUST never be returned by any endpoint, shown on screen, logged or committed.
- **FR-022**: Settings and the README MUST name the third-party services (embeddings, speech) and what is sent to each.
- **FR-023**: All new screens MUST meet the project's accessibility and design-system rules.
- **FR-024**: Calls to the embedding and speech services MUST be rate limited per person and time-limited, with calm messages on failure.

### Key Entities

- **Passage embedding**: The meaning-based search data for one passage, with the model that made it (so it can be redone if the model changes).
- **Page record**: For each page of a document, whether it was read by OCR and how confident the reading was.
- **Text conversation**: A person's private list of lines with title, language, dates, and a deleted marker; lines have text, source (voice or typed), and time.
- **History entry**: Gains a source (Ask, Assistant, Text Assistant) and, for conversations, a stored copy of the text so it can still be opened after deletion.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the reference question set, at least 90% of questions find the right page and the facts of the expected answer (up from 72% with keywords alone).
- **SC-002**: With the embedding service switched off, 100% of questions still receive a cited answer or "no reliable source", and the screen names the active mode.
- **SC-003**: A scanned English or Tamil page added to the knowledge base is found by a question about its content, and its citation shows it was read by OCR.
- **SC-004**: With OCR missing, 100% of scanned uploads fail with a reason that names what to install, and none are partially used.
- **SC-005**: Zero audio is stored: after any number of voice turns, no audio exists on the server or in the database.
- **SC-006**: In privacy tests, no private passage, note or conversation reaches another person through keyword search, meaning-based search, citations or History.
- **SC-007**: A person can open a cited passage in under 10 seconds from the answer.
- **SC-008**: All new screens pass the automated accessibility checks in both themes at desktop and phone widths.

## Assumptions

- Meaning-based search uses the embedding service the owner supplied a key for; speech uses the speech service the owner supplied a key for. Both are third parties; their names are shown on screen and in Settings. Free-tier rate limits apply, so adding large documents can be slow.
- No OCR engine is installed on the development machine. OCR code and tests use a stand-in; real OCR needs the engine installed on the server (Tesseract with English and Tamil language data).
- Keys were pasted into a chat to enable this work and are treated as exposed: rotate them. The speech key was also found earlier in a sample script in the reference project.
- The assistant and answer writing still need a model key (not supplied). Without it, answers repeat cited passages; this feature does not change that.
- Speech turns are short (about 28 seconds each, the speech service's limit for direct transcription); long recordings are out of scope.
- Conversations are text only; no audio is kept. PDFs of conversations are produced on request and not stored.
- Cited passage text is shown in full to anyone allowed to use that passage, as the knowledge list already allows.
- Answers remain informational guidance, never legal advice, and drafts stay editable and flagged for review.
