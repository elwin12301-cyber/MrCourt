# Research: Client Case Status

All Technical Context unknowns are resolved below. Feature 001's stack and conventions are reused.

## R1. A separate client read model

- **Decision**: Petitioners use only `/client/*` endpoints. A single service (`services/client_view.py`) builds the client's view of a case from an explicit allow-list of fields. The existing `/cases` endpoints stay advocate-only for writes and are no longer used by the client screens.
- **Rationale**: In 001, petitioners read the same detail endpoint as advocates and a field is hidden by an `if`. A purpose-built view returns only what is meant to be seen, so adding a new private field later cannot leak by default.
- **Alternatives**: Keep one endpoint and filter fields (easy to forget a field); a separate database view (more moving parts than needed).

## R2. Client-facing status vs the existing case status

- **Decision**: Add `client_status` (one of `notice_stage`, `hearing_scheduled`, `awaiting_order`, `closed`, or empty) with `client_status_changed_at`. The existing `status` (`active` or `closed`) keeps driving the advocate's filters. Setting the client status to Closed closes the case; reopening a closed case sets the client status to the one the advocate picks.
- **Rationale**: The two have different audiences and vocabularies; four fixed values (spec Clarification) is simple to validate and display. Tying Closed to the case state avoids a case that is "closed" for the client but active for the advocate.
- **Alternatives**: Derive the client status automatically (wrong whenever the advocate's real stage differs); replace the case status (breaks 001 filters).

## R3. Timeline and visibility rules

- **Decision**: A `timeline_entries` table stores events. Automatic kinds (`status_change`, `hearing_scheduled`, `hearing_rescheduled`) are always client-visible. Kinds the advocate controls (`outcome`, `document_shared`, `update`, `note`) carry `shared_with_client`, default false, except `update`, which is created shared because writing a client update is an explicit act of sharing. The client view reads only visible entries.
- **Rationale**: Matches spec Clarification 1 and FR-006. One table gives a single ordered timeline and one place to apply the rule.
- **Alternatives**: Derive the timeline from other tables at read time (slow and scatters the visibility rule); store visibility on each source table only (duplicated logic).

## R4. Sharing flags on existing records

- **Decision**: Add `shared_with_client` (default false) to documents and `outcome_shared` (default false) to hearings. Sharing a document or outcome also writes a timeline entry and notifies clients; unsharing hides the item and its timeline entry without creating a notice.
- **Rationale**: Keeps one source of truth per item and makes "unshare" immediate (edge case: link stops working). Client document downloads go through a client-specific route that re-checks the flag.
- **Alternatives**: A generic sharing table (more joins, no benefit at this scale).

## R5. Updates and unread state

- **Decision**: `client_updates` rows are created per accepted client when a visible change happens (status change, hearing scheduled or rescheduled, shared outcome, shared document, advocate update, reply to a question). Each row has `read_at`. The frontend refreshes the unread count every 30 seconds and when the window regains focus.
- **Rationale**: Per-client rows give independent read states (required by multi-client privacy) and make the unread count a simple count. Periodic refresh satisfies "within 1 minute" (SC-004) without sockets.
- **Alternatives**: WebSockets or server-sent events (extra infrastructure); email, SMS or WhatsApp alerts (out of scope in the spec).

## R6. Private questions to the lawyer

- **Decision**: `client_questions` has one row per question: case, client, text, optional reply text and times, and `reply_read_at`. Clients list only their own rows; advocates list all rows for their case and reply once per question. No threads, attachments or live chat.
- **Rationale**: Matches the spec's "simple messages with a reply" and per-client privacy. Filtering by `client_id` in one query function keeps the rule testable.
- **Alternatives**: Full threads or chat (larger scope, moderation and retention questions).

## R7. Automatic hearing descriptions

- **Decision**: A reviewed JSON content file maps hearing kinds (first hearing, evidence, arguments, orders or judgment, bail, mediation, and a generic fallback not shown) to a general description. The service picks one from the hearing's `purpose` by keyword, then from the case `stage`; if neither matches, it returns nothing and the client sees only date, time and court. Each description is labelled "General information" and shows the disclaimer.
- **Rationale**: Satisfies "MrCourt writes automatically" and FR-021 while guaranteeing the text never states case facts, predicts outcomes or advises. Static text can be reviewed by a lawyer once, which a model output cannot.
- **Alternatives**: Model-written descriptions per hearing (cannot guarantee the guardrails, needs per-output verification); advocate-written only (not what was chosen).

## R8. Spotting questions about the client's own case

- **Decision**: `services/advice_guard.py` flags a question as case-specific when it contains first-person case language (for example "my case", "my lawyer", "should I accept", "will I win", "can I get"). For clients, the answer still includes any cited general information, plus a notice "MrCourt cannot advise on your case. Please ask your lawyer." with a link to the question box. Independently, every client answer shows a short standing reminder to ask the lawyer about their own case.
- **Rationale**: Meets FR-013 and SC-007 without depending on perfect detection: the standing reminder covers misses, and the heuristic avoids burying general answers.
- **Alternatives**: A model classifier (cost, latency, another thing that can be wrong); blocking all first-person questions (frustrating and over-broad).
- **Residual risk**: unusual wording can bypass the detector; it is mitigated by the standing reminder and tracked in the plan's Key Risks.

## R9. The advocate's contact card

- **Decision**: Store an optional `client_contact` JSON (phone, email, office address) in the advocate's settings, empty by default. Clients see the verified status and name always, and the contact card only for fields the advocate has filled in.
- **Rationale**: Meets "contact details the advocate chooses to share" with the smallest change.
- **Alternatives**: Per-field toggles (the empty-means-hidden rule gives the same control with less UI).

## R10. Plain-language explanations

- **Decision**: A static `glossary.json` of common terms (for example CNR, notice, hearing, evidence, adjournment, order) served by `GET /glossary`, shown beside client wording through a small "What does this mean?" disclosure.
- **Rationale**: Reviewed, general, and cheap; avoids calling the answer pipeline for definitions.
- **Alternatives**: Generating definitions on demand (unverified).

## R11. Migration and deletion

- **Decision**: A real Alembic revision `0002` adds the new tables and columns for both SQLite and PostgreSQL. `privacy.deactivate` is extended to delete a client's questions, updates and their timeline read states, while keeping the advocate's timeline and case records. If an advocate deactivates, clients' questions to them stay with the case and clients are told the lawyer is no longer available.
- **Rationale**: Extends the 001 retention decision consistently; the new personal data (messages) is removed with the person.
- **Alternatives**: Editing the 001 initial migration (breaks any database already created).

## R12. Testing focus

- **Decision**: Leak-prevention tests walk every client endpoint and assert that private fields never appear (notes, internal documents, unshared outcomes, other clients' questions); role-separation tests assert that petitioners cannot call advocate endpoints; Playwright covers the client journey, keyboard use and axe scans of the new screens in both themes at 360px and 1280px.
- **Rationale**: The riskiest failure here is exposing something private, so tests are weighted to that.
