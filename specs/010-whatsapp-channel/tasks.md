# Tasks: WhatsApp channel (consent-based, two-way)

**Input**: `/specs/010-whatsapp-channel/` (plan.md, spec.md, research.md, data-model.md, contracts/whatsapp-api.md, quickstart.md)

**Tests**: Included (the constitution requires tests for cited and "no reliable source" answers; privacy and consent rules need proof; every earlier feature has them). Write each story's tests first and see them fail.

**Paths**: backend `backend/src/mrcourt/`, backend tests `backend/tests/`, frontend `frontend/src/`, browser tests `frontend/tests/e2e/`. Tasks marked **(owner)** need something only the product owner can do.

## Phase 1: Setup

- [X] T001 Add the WhatsApp settings to `backend/src/mrcourt/config.py`: `whatsapp_provider` (`none`/`meta`/`twilio`, default `none`), `whatsapp_phone_number_id`, `whatsapp_access_token`, `whatsapp_app_secret`, `whatsapp_verify_token`, `whatsapp_template_code/reminder/update/activity` (defaults from contracts §4), `whatsapp_daily_send_cap`, `whatsapp_nudge_delay_seconds` (default 180), `whatsapp_questions_per_minute` / `_per_day`, `public_app_url`; blank every `WHATSAPP_*` key in `backend/tests/conftest.py` and `backend/scripts/e2e_server.py` so tests never use real keys
- [X] T002 [P] Create the package `backend/src/mrcourt/services/whatsapp/__init__.py` and add sample provider payloads with FICTIONAL numbers in `backend/tests/data/whatsapp/` (`meta_text.json`, `meta_audio.json`, `meta_status_delivered.json`, `meta_status_failed.json`, `twilio_text.txt`, `twilio_status.txt`)
- [X] T003 [P] Add a test helper `backend/tests/helpers_whatsapp.py` that builds signed Meta and Twilio requests from those samples and a `FakeChannel` that records sends and returns queued inbound events

## Phase 2: Foundational (blocks every story)

- [X] T004 Alembic migration `backend/alembic/versions/0010_whatsapp_channel.py` (idempotent like 0008/0009): tables `whatsapp_links`, `message_consents`, `messages`, `inbound_messages` (unique `provider`+`provider_message_id`), `conversation_state`; `questions.channel` default `app`; indexes from data-model.md
- [X] T005 [P] Models in `backend/src/mrcourt/models/whatsapp.py` (`WhatsAppLink`, `MessageConsent`, `Message`, `InboundMessage`, `ConversationState`), export them in `backend/src/mrcourt/models/__init__.py`, add `Question.channel` in `backend/src/mrcourt/models/legal.py`
- [X] T006 [P] Channel protocol and types in `backend/src/mrcourt/services/whatsapp/channel.py`: `WhatsAppChannel` (`send_template`, `send_text`, `verify_and_parse`, `fetch_audio`), `InboundEvent` (message or delivery report), `DeliveryReport`, template keys, the 24-hour window rule, `get_channel()` chosen by `WHATSAPP_PROVIDER` (`none` → development channel), `set_channel()` test hook
- [X] T007 [P] Development channel in `backend/src/mrcourt/services/whatsapp/development.py`: keeps each message in the existing development outbox (`services/notify.py` `OUTBOX`) with channel and kind, never touches the network
- [X] T008 [P] Signature unit tests in `backend/tests/unit/test_whatsapp_signatures.py`: Meta `X-Hub-Signature-256` (valid, altered body, missing header, wrong secret) and Twilio `X-Twilio-Signature` (URL + sorted fields), constant-time comparison used, nothing parsed before the check
- [X] T009 Meta adapter receive side in `backend/src/mrcourt/services/whatsapp/meta.py`: `verify_and_parse` (HMAC-SHA256 over the raw body, parse `messages[]` and `statuses[]` into events), setup-challenge check against `WHATSAPP_VERIFY_TOKEN`
- [X] T010 [P] Twilio adapter receive side in `backend/src/mrcourt/services/whatsapp/twilio_sandbox.py`: `verify_and_parse` (HMAC-SHA1 over URL + sorted form fields, `From`, `Body`, `MessageSid`, `NumMedia`, `MediaUrl0`, `MessageStatus`)
- [X] T011 Inbound storage in `backend/src/mrcourt/services/whatsapp/inbound.py`: `sender_hash` (HMAC of the number with the session secret), `store(event)` that ignores a repeated `(provider, provider_message_id)`, returns whether it is new
- [X] T012 [P] Webhook contract tests in `backend/tests/contract/test_whatsapp_webhook.py`: invalid or missing signature → 403 and nothing stored; valid signature → 200; the same message twice → one row; Meta `GET` challenge only with the right token; a request with no `Origin` header is accepted by the existing cross-site check; body over 1 MB refused; response never reveals whether a number has an account
- [X] T013 Webhook endpoints `GET` and `POST /api/v1/whatsapp/webhook` in `backend/src/mrcourt/api/whatsapp.py`, register the router in `backend/src/mrcourt/main.py`; check signature on the raw body, store new events, return `200 {}` at once, hand processing to a background task (stub until US3), log failures without the body

**Checkpoint**: a signed sample is accepted, a bad one refused, a repeat ignored; nothing can be sent yet.

## Phase 3: User Story 1 - Link my WhatsApp number and choose what I receive (Priority: P1) 🎯 MVP

**Goal**: a signed-in person links a verified number, switches kinds of message on one by one (all off by default), unlinks, and can reply STOP.

**Independent Test**: verify a number, switch "hearing reminders" on and "case updates" off, reply STOP, confirm everything is off and nothing further is sent.

### Tests for User Story 1

- [X] T014 [P] [US1] Unit tests in `backend/tests/unit/test_whatsapp_consent.py`: link needs a verified phone, a number is linked to one account only (error does not say whose), all kinds off after linking, role kinds (clients: codes/reminders/updates; advocates: codes/reminders/activity), unlink switches all off, STOP words in English, Hindi and Tamil switch all off and START turns nothing on
- [X] T015 [P] [US1] Contract tests in `backend/tests/contract/test_whatsapp_settings.py`: GET/POST/DELETE `/me/whatsapp`, PUT `/me/whatsapp/consents/{kind}`, `409 phone_not_verified`, `409 number_in_use`, `404` for another role's kind, masked number, audit entries without message content, changing the phone number unlinks

### Implementation for User Story 1

- [X] T016 [US1] `backend/src/mrcourt/services/whatsapp/consent.py`: `link`, `unlink`, `set_consent`, `stop_all`, `kinds_for(role)`, descriptions (the one-sentence text per kind from contracts §1); audit `whatsapp.link`, `.unlink`, `.consent`, `.stop` via `services/audit.py` (no content)
- [X] T017 [P] [US1] Schemas in `backend/src/mrcourt/schemas/whatsapp.py` (settings view, consent body)
- [X] T018 [US1] Settings endpoints in `backend/src/mrcourt/api/me.py` per contracts §1 (GET, link, unlink, consent, delete delivery history)
- [X] T019 [US1] STOP handling in `backend/src/mrcourt/services/whatsapp/inbound.py`: a message whose text is a stop word from a linked number calls `stop_all` and sends one confirmation (confirmation text from contracts §2); an unknown number sending STOP gets nothing
- [X] T020 [US1] Unlink when the phone number changes: hook the place that saves a new phone (`backend/src/mrcourt/services/auth.py` or `api/me.py` phone update) to call `consent.unlink` with `changed_by=system`
- [X] T021 [US1] Account deactivation deletes the link, consents, delivery records and conversation state in `backend/src/mrcourt/services/privacy.py`; test in `backend/tests/integration/test_whatsapp_privacy.py`
- [X] T022 [P] [US1] Frontend hooks and types in `frontend/src/services/whatsapp.ts`
- [X] T023 [US1] `frontend/src/components/WhatsAppCard.tsx`: masked number, Link / Unlink, one switch per kind with its sentence and consent date, unavailable and "verify your phone first" states, keyboard operable, tokens only, styles `.wa-*` in `frontend/src/styles/app.css`
- [X] T024 [US1] Show the card in `frontend/src/pages/Settings.tsx` below the phone block (the "Text message reminders" switch stays as it is)
- [X] T025 [P] [US1] Browser tests `frontend/tests/e2e/whatsapp-settings.spec.ts` (link, switch kinds, unlink, desktop and phone) and axe scans of the card in both themes in `frontend/tests/e2e/a11y.spec.ts`

**Checkpoint**: consent works end to end with the development channel; STOP works; deactivation cleans up.

## Phase 4: User Story 2 - Hearing reminders and codes on WhatsApp, with proof of delivery (Priority: P1)

**Goal**: opted-in people get codes and reminders on WhatsApp; each message has a status; failures fall back once to SMS.

**Independent Test**: hearing 5 days away, opted-in advocate and client, run the job: one message each with status delivered; mark one number "not on WhatsApp": that person gets an SMS instead.

### Tests for User Story 2

- [X] T026 [P] [US2] Unit tests in `backend/tests/unit/test_whatsapp_status.py`: status only moves forward (queued < sent < delivered < read), `failed` is final, a late "sent" after "delivered" is ignored
- [X] T027 [P] [US2] Integration tests in `backend/tests/integration/test_whatsapp_outbound.py`: nothing sent to unverified, unlinked or opted-out people or deactivated accounts; a just-requested code is always sent (by SMS when WhatsApp codes are off); reminders once per person per hearing at 5, 1, 0 days; reschedule restarts; failure or "not on WhatsApp" → exactly one SMS linked by `fallback_of`; a person with WhatsApp off and text reminders on still gets the SMS; daily send cap; login code reply identical whether or not the account exists

### Implementation for User Story 2

- [X] T028 [US2] Meta send side in `backend/src/mrcourt/services/whatsapp/meta.py`: `send_template` and `send_text` through the Graph API with `httpx`, short timeouts, provider message id returned, failures mapped to plain reason codes (`not_on_whatsapp`, `template_missing`, `provider_down`)
- [X] T029 [P] [US2] Twilio sandbox send side in `backend/src/mrcourt/services/whatsapp/twilio_sandbox.py` (reuses the existing Twilio settings; sandbox needs no template)
- [X] T030 [US2] `backend/src/mrcourt/services/whatsapp/outbox.py`: `send_kind(db, user, kind, case, hearing, variables)` (link + consent check, `messages` row without text, send, store provider id), `apply_report(db, report)` (forward-only status, `failed` starts the SMS fallback), `send_sms_fallback`, `WHATSAPP_DAILY_SEND_CAP`
- [X] T031 [US2] Make `backend/src/mrcourt/services/notify.py` SMS-only: add an SMS-only send, remove the legacy WhatsApp paths of the Twilio, Fast2SMS and WhatsApp Cloud adapters (the README section is updated in T068), keep the development outbox and `delivers_for_real`
- [X] T032 [US2] Reminders through the outbox in `backend/src/mrcourt/services/reminders.py` (template variables `case`, `when`; `ReminderLog` still records "once"); keep SMS for people who kept text reminders on
- [X] T033 [US2] Codes in `backend/src/mrcourt/services/auth.py`: WhatsApp first when the person turned "codes" on and is linked, otherwise SMS; keep `_deliver` swallowing failures so the reply never reveals the account
- [X] T034 [US2] Delivery reports in the webhook: route status events to `outbox.apply_report` in `backend/src/mrcourt/api/whatsapp.py`
- [X] T035 [US2] Jobs in `backend/src/mrcourt/services/whatsapp/jobs.py` (`python -m mrcourt.services.whatsapp.jobs`): purge `messages` and `inbound_messages` older than 90 days and expired `conversation_state`; hook into the existing in-app loop in `backend/src/mrcourt/main.py`
- [X] T036 [P] [US2] Development messages page shows channel and kind in `frontend/src/pages/DevMessages.tsx` and `backend/src/mrcourt/api/dev.py`

**Checkpoint**: reminders and codes work through the development channel and the Twilio sandbox, with status and SMS fallback.

## Phase 5: User Story 3 - Ask a legal question on WhatsApp (Priority: P1)

**Goal**: a linked person asks by text and gets the same cited answer as the website, in short form.

**Independent Test**: ask a question the sources answer, one they cannot, and one naming a missing section; get a cited answer, the no-source reply and the "not found in the sources" reply; all three appear in the history marked as asked by WhatsApp.

### Tests for User Story 3

- [X] T037 [P] [US3] Integration tests in `backend/tests/integration/test_whatsapp_inbound.py`: cited answer with disclaimer and link; no reliable source; "Not found in the sources: Section 999 IPC…"; petitioner gets the client advice rule; unknown number gets only the fixed "how to link" reply (identical for every number) and replies stop after a few; per-number rate limit reply; busy answer service gives the "try again" reply and no wrong answer; stored in history with `channel=whatsapp`; a private document is never quoted; duplicate delivery gives one answer
- [X] T038 [P] [US3] Parity test `backend/tests/integration/test_whatsapp_parity.py`: for a set of questions the citations and outcome over WhatsApp equal those of `POST /questions` (SC-004)

### Implementation for User Story 3

- [X] T039 [US3] Move the ask flow (advice rule, `answer_question`, store question, answer, citations, ranking) from `backend/src/mrcourt/api/questions.py` into `backend/src/mrcourt/services/ask.py` with a `channel` argument; `api/questions.py` becomes a thin wrapper; all existing question tests must still pass unchanged
- [X] T040 [P] [US3] Short WhatsApp format in `backend/src/mrcourt/services/whatsapp/format.py`: about 1,000 characters cut at a sentence, "Sources:" with labels, disclaimer line, link `{PUBLIC_APP_URL}/ask/history/{question_id}`; unit tests in `backend/tests/unit/test_whatsapp_format.py`
- [X] T041 [US3] Routing in `backend/src/mrcourt/services/whatsapp/inbound.py`: unknown sender reply, unsupported content reply, question path using shared sources only; replies sent as free text only inside the 24-hour window (`last_inbound_at`)
- [X] T042 [US3] Per-number limits from the database (count of `inbound_messages` per `sender_hash` in the last minute and day) with the single "try again later" reply in `backend/src/mrcourt/services/whatsapp/inbound.py`
- [X] T043 [US3] Run processing in the background after the 200, mark `inbound_messages` `processed` or `failed`, and retry `received` rows older than a minute at most 3 times in `backend/src/mrcourt/services/whatsapp/jobs.py`
- [X] T044 [P] [US3] Show "Asked on WhatsApp" in the history: add `channel` to the history schema in `backend/src/mrcourt/schemas/` and `backend/src/mrcourt/services/history.py`, and a small chip in `frontend/src/pages/ask/HistoryTab.tsx`

**Checkpoint**: asking on WhatsApp works through the development channel and the sandbox, with parity to the website.

## Phase 6: User Story 4 - Next hearing and case status by WhatsApp (Priority: P2)

**Goal**: "next hearing", "status", "today" answered from the person's own cases, role-scoped.

**Independent Test**: as a client invited to one of two advocate cases, "next hearing" and "status" show only the invited case; as the advocate both appear.

- [X] T045 [P] [US4] Integration tests in `backend/tests/integration/test_whatsapp_cases.py`: client sees only invited and shared items; removed invitation hides the case; several cases give a numbered list and the next number picks one; advocate "today"; a case that is not the person's gets the same reply as one that does not exist
- [X] T046 [P] [US4] Keyword table (English, Hindi, Tamil) and parser in `backend/src/mrcourt/services/whatsapp/intents.py` with unit tests in `backend/tests/unit/test_whatsapp_intents.py` (help, next hearing, status, today, stop, a bare number); anything else is a question
- [X] T047 [US4] Case answers in `backend/src/mrcourt/services/whatsapp/intents.py` reusing `services/cases.py` (`next_hearing`), `services/client_view.py` and `services/access.py` visibility rules; client answers contain only the client-facing status and next hearing
- [X] T048 [US4] Case-choice conversation state (ids only, expires in a few minutes) in `backend/src/mrcourt/services/whatsapp/intents.py` and `models/whatsapp.py`, purged by T035

## Phase 7: User Story 5 - Clients get a nudge when their advocate posts an update (Priority: P2)

**Goal**: one short "there is news on <case>" message, merged, never carrying the detail.

**Independent Test**: advocate changes a case status for an opted-in and a not-opted-in client; only the first gets a message and it contains the case title only.

- [X] T049 [P] [US5] Integration tests in `backend/tests/integration/test_whatsapp_nudges.py`: opted-in only; content is the template with the case title only (no status text, notes or document names); several updates within the delay give one message; dropped when a reminder for the same case is queued for that person; nothing after unlink or removed invitation; advocate "activity" nudge when a client asks a question
- [X] T050 [US5] Queue nudges where updates are created: `backend/src/mrcourt/services/client_status.py` (status, hearing, outcome, shared document, update) and `backend/src/mrcourt/services/client_questions.py` (advocate reply → client; client question → advocate activity) call `outbox.queue_nudge` with `send_after`
- [X] T051 [US5] Merge and send due nudges in `backend/src/mrcourt/services/whatsapp/outbox.py` and `jobs.py` (one message per person and case; drop when a reminder for the same case is queued)

## Phase 8: User Story 6 - Voice notes (Priority: P2)

**Goal**: a voice note is turned into text, quoted back and answered.

**Independent Test**: a clear voice question is quoted and answered; an unclear one gets a polite "could not understand".

- [X] T052 [P] [US6] Integration tests in `backend/tests/integration/test_whatsapp_voice.py` with `FakeSpeech`: quoted back then answered; empty or low-confidence text is not answered; audio never written to disk; unsupported language reply
- [X] T053 [US6] **Verify first** whether the speech provider accepts OGG/Opus directly: add a `codec` argument to `SpeechToText.transcribe` in `backend/src/mrcourt/services/speech.py` and try it with a sample voice note; record the outcome in `specs/010-whatsapp-channel/research.md` (D7) *(SDK accepts `ogg`/`opus` and the codec is passed through; the live check with a real voice note is part of T066)*
- [X] T054 [US6] If T053 shows OGG is refused: convert with ffmpeg in `backend/src/mrcourt/services/whatsapp/voice.py` and add ffmpeg to `Dockerfile`; otherwise skip this task and note it *(skipped: not needed unless the live check in T066 shows the service refuses OGG)*
- [X] T055 [P] [US6] `fetch_audio` in `backend/src/mrcourt/services/whatsapp/meta.py` (media id → URL → bytes with the token) and `twilio_sandbox.py` (`MediaUrl0` with basic auth), size and length limits
- [X] T056 [US6] `backend/src/mrcourt/services/whatsapp/voice.py`: fetch, transcribe in memory, "I heard: …", then the question path; routed from `inbound.py`

## Phase 9: User Story 7 - Administrators see that it works (Priority: P2)

**Goal**: counts, failures and service health, never message text.

**Independent Test**: send messages that succeed, fail and fall back; counts and the failure list are right and no text appears in the page, the data or the audit log.

- [X] T057 [P] [US7] Contract tests in `backend/tests/contract/test_admin_messages.py`: summary counts per kind, channel and status; failures list with person name and plain reason but no text or number; resend only for a failed reminder or update of a still-linked, opted-in person; only administrators; audit entries (`whatsapp.admin.failures.view` with a count, `whatsapp.admin.resend`) contain no message content
- [X] T058 [P] [US7] Schemas for summary and failures in `backend/src/mrcourt/schemas/whatsapp.py`
- [X] T059 [US7] Queries and service health (last successful provider call, recent failure rate) in `backend/src/mrcourt/services/whatsapp/outbox.py` or `backend/src/mrcourt/services/whatsapp/admin.py`
- [X] T060 [US7] Endpoints `GET /admin/messages/summary`, `GET /admin/messages/failures`, `POST /admin/messages/{id}/resend` in `backend/src/mrcourt/api/admin.py`
- [X] T061 [US7] `frontend/src/pages/AdminMessages.tsx` (counts table, failures list, health chip, resend button), route and "Messages" entry in `frontend/src/components/AppShell.tsx`, hooks in `frontend/src/services/admin.ts`
- [X] T062 [P] [US7] Browser tests `frontend/tests/e2e/admin-messages.spec.ts` and axe scans in both themes at desktop and phone widths in `frontend/tests/e2e/a11y.spec.ts`

## Phase 10: Polish and launch checks

- [X] T063 [P] `backend/scripts/whatsapp_dev_send.py`: sign and post a sample inbound message to the local webhook and print the reply (quickstart §2)
- [X] T064 [P] Privacy tests in `backend/tests/integration/test_whatsapp_privacy.py`: no message text in `messages`, `inbound_messages`, the administrator data or the audit log; deactivation removes link, consents, records; strangers stored only as hashes; keys never in responses or logs
- [X] T065 [P] README sections "WhatsApp channel" (setup for the sandbox and for Meta, webhook URL, templates to submit, secrets, rollback `WHATSAPP_PROVIDER=none`, cost and privacy notes) and update "Known gaps"; add the secret names (no values) to `render.yaml`
- [ ] T066 Run the quickstart on the Twilio sandbox through a public tunnel (quickstart §3) and record results in `specs/010-whatsapp-channel/results.md`
- [ ] T067 **(owner)** Create and verify the Meta WhatsApp Business account, register the number, get the four templates approved (texts in contracts §4), then run quickstart §4 and record results
- [ ] T068 **(owner)** DPDP review of sending case titles and dates through a third-party messaging service; record the decision in `specs/010-whatsapp-channel/results.md`
- [X] T069 Full regression: backend pytest, Vitest, `tsc`, ESLint, full Playwright; measure that the website answer path is unchanged (parity tests) and record counts in `specs/010-whatsapp-channel/results.md`

## Addendum: Fast2SMS adapter (requested after the first build)

- [X] T070 Settings and channel selection for `WHATSAPP_PROVIDER=fast2sms` in `backend/src/mrcourt/config.py` and `backend/src/mrcourt/services/whatsapp/channel.py`; blank the new keys in tests and `backend/scripts/e2e_server.py`
- [X] T071 `backend/src/mrcourt/services/whatsapp/fast2sms.py`: template send, session reply, webhook secret check, `incoming_message` and `status_update` parsing (JSON or form), audio fetched only from `https` addresses on `fast2sms.com`
- [X] T072 Delivery reports that do not carry our message id are matched by recipient (`outbox._latest_to`, `DeliveryReport.recipient`)
- [X] T073 Tests: `backend/tests/unit/test_whatsapp_fast2sms.py` (25) and `backend/tests/integration/test_whatsapp_fast2sms_flow.py` (7); the network guard now also blocks `urllib`
- [X] T074 README and `render.yaml`: setup, the webhook payloads to paste in the panel, the secret and its limits; research D9
- [ ] T075 **(owner)** Provide the phone number id, the four template ids and the webhook secret, then run the first live test (quickstart section 4b) and record the results, including the unverified points in research D9

## Dependencies and order

- Phase 1 → Phase 2 (blocks all stories) → stories.
- **US1** needs Phase 2. **US2** needs US1 (consent and link). **US3** needs US1 (linked sender) and T039. **US4** needs US3 (routing). **US5** needs US2 (outbox). **US6** needs US3 (question path). **US7** needs US2 (records).
- Within a story: tests, then models/services, then endpoints and screens.
- T031 (remove legacy WhatsApp from `notify.py`) must wait until T030 and T032–T033 work, so codes and reminders never go dark.
- T039 changes shared behaviour: run the whole question test suite before and after.

### Parallel examples

```text
Phase 2:  T005 models  ‖  T006 channel protocol  ‖  T007 development channel  ‖  T008 signature tests
          then T009 Meta receive ‖ T010 Twilio receive; T012 webhook tests ‖ T013 endpoint
US1:      T014 unit tests ‖ T015 contract tests ‖ T017 schemas ‖ T022 frontend service
US2:      T026 status tests ‖ T027 outbound tests ‖ T029 Twilio send ‖ T036 dev page
US3:      T037 inbound tests ‖ T038 parity test ‖ T040 format ‖ T044 history chip
US4/US5/US6 can proceed in parallel once US3 (routing) and US2 (outbox) exist
US7:      T057 ‖ T058, then T059–T062
```

## Strategy

- **MVP = Phases 1 and 2 plus US1**: a safe, consent-based link that proves the webhook and settings, using the development channel. Nothing is sent to the public yet.
- **First useful release = MVP + US2 + US3**: reminders and codes with proof of delivery, and questions by WhatsApp. This needs the Twilio sandbox (free) and can go live on Meta once T067 is done.
- Then US4 (hearings), US5 (nudges), US6 (voice) and US7 (admin view), each shippable on its own.
- Start T067 and T068 (owner tasks) immediately: approval takes days and does not depend on code.
- Stop at each checkpoint, run the quickstart steps for that story, and commit.
