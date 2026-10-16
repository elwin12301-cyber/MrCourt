# Implementation Plan: WhatsApp channel (consent-based, two-way)

**Branch**: `010-whatsapp-channel` | **Date**: 2026-10-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/010-whatsapp-channel/spec.md`

## Summary

Add a provider-neutral WhatsApp channel next to the existing SMS notifier. **Outbound**: codes, hearing reminders and
short "there is news on <case>" nudges go through one pipeline that checks the person's verified link and per-kind
consent, sends an approved template, keeps a delivery record (no text), follows delivery reports from the provider
and falls back once to SMS. **Inbound**: a signed webhook stores each message (duplicates ignored), then a background
step routes it: STOP, "next hearing"/"status" (role-scoped), voice notes (speech to text) and legal questions, which
use the **same answer service as the website** (moved to `services/ask.py`) with shared sources only, a short
WhatsApp format and a link to the full answer. **People** link and unlink a number and switch kinds on in Settings
(everything off by default); **administrators** see counts, failures and service health, never message text.
Provider target is Meta's WhatsApp Business interface; the free Twilio sandbox is used for testing; a development
channel keeps working with no account at all. `WHATSAPP_PROVIDER=none` is the rollback.

### Where WhatsApp is needed (see research.md for the full table)

Codes and reminders (outbound, exist today), client updates and advocate alerts (outbound, new), asking questions,
next hearing and status (inbound, new), Settings (link and consent), the admin "Messages" view, and account
deactivation (delete everything).

### Workflow at a glance

```
OUTBOUND  event (reminder due / advocate update / code asked)
            └► linked + consent on? ──no──► nothing (a just-requested code still goes by SMS)
                   │yes
                   ▼
            messages(queued) ─► template via provider ─► sent ─► delivered ─► read
                   │                                       │
                   └─ send error / not on WhatsApp ────────┴─ failed ─► ONE SMS (fallback_of = first record)

INBOUND   provider ─► POST /whatsapp/webhook ─► signature ok? ──no──► 403, ignored
                                  │yes
                      duplicate? ─yes─► ignored        │no
                                  ▼
                      store inbound row ─► 200 at once ─► background:
                      unknown number ► fixed "how to link" reply     STOP ► consents off + 1 confirmation
                      "next hearing/status" ► role-scoped case answer
                      voice note ► transcribe ► "I heard: …" ► question
                      question ► services/ask.py (shared sources) ► short cited answer + link
```

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5 / React 18 (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2, Alembic, httpx (already installed; provider calls), Sarvam speech (existing); **no new Python dependency**. Possible system package: ffmpeg, only if the speech service refuses OGG/Opus (research D7)

**Storage**: SQLite (dev/tests), PostgreSQL 16 (production); four new tables and one new column (see data-model.md); no message text stored

**Testing**: pytest (unit with fake channel, contract for webhook and settings, integration for consent, fallback, idempotency, privacy), Vitest, Playwright (Settings card, admin Messages, axe in both themes at desktop and phone)

**Target Platform**: Linux container (Render, public HTTPS needed for the webhook) and local Windows development with a tunnel for live tests

**Project Type**: Web application (backend + frontend)

**Performance Goals**: webhook returns 200 in under 1 s; a text question answered within 30 s in 95% of tests (SC-003); reminder job unchanged in cost

**Constraints**: provider rate and template rules (24-hour window, approved templates); free Voyage (3 requests/min) and Gemini limits (answers fall back to passages with a note, as on the website); stateless replies (no queued answers after an outage); in-process background tasks, so inbound rows persist and the hourly job retries them

**Scale/Scope**: tens to low hundreds of people; a few hundred messages a day; four message kinds, four templates

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | How this plan complies | Status |
|---|---|---|
| I. Grounded, cited answers only | WhatsApp questions go through the same `services/ask.py` as the website: retrieval, written answer from the passages, every citation verified, "no reliable source" and "not found in the sources" replies unchanged. Answers show their source names. A test asserts equal citations for the same question on both channels (SC-004). | Pass |
| II. Informational only, not legal advice | The disclaimer line ends every WhatsApp answer; the client advice rule (general information, ask your lawyer) is applied by the shared function. Nothing is filed or sent for the user; outbound messages only announce. | Pass |
| III. Privacy by design (DPDP) | Opt-in per kind, off by default, recorded; STOP works at once; messages carry only case title and date or "there is news"; no message text stored (delivery records hold kind, status, time); private documents never quoted over WhatsApp; administrators never see text; 90-day purge; deletion on deactivation; strangers tracked only by hash; keys only in env. A DPDP review of third-party message storage is a launch gate (research). | Pass, with launch gate |
| IV. Accessible and responsive | Settings card and admin Messages page use existing components, keyboard operable, visible focus, both themes, phone width; checked with axe in e2e. | Pass |
| V. Design system consistency | Reuses `ui.tsx` pieces (cards, chips, switches as in the reminders setting), tokens only. | Pass |
| VI. Simplicity | One small channel interface with two real adapters and a development one; rule-based intents (no AI); DB tables instead of a queue service; background tasks plus the existing hourly job instead of a worker system; no new dependency. The old, untested WhatsApp code inside `notify.py` is removed, not kept alongside. | Pass |

Product constraints: both roles are named per story; answers use the indexed corpus only; English first, Hindi and
Tamil for STOP words and voice notes only where supported, citations verbatim; disclaimers are never dropped.

Post-design re-check (after Phase 1): still passes. The largest new surface is the public webhook; it is guarded by
signature checks, idempotency and rate limits and is covered by contract tests.

## Project Structure

### Documentation (this feature)

```text
specs/010-whatsapp-channel/
├── plan.md              # This file
├── research.md          # Touch points, decisions D1–D8, what to verify first, risks
├── data-model.md        # whatsapp_links, message_consents, messages, inbound_messages, conversation_state
├── quickstart.md        # Automated, development, Twilio sandbox and Meta live checks
├── contracts/
│   └── whatsapp-api.md  # Settings, webhook, admin and template contracts
├── checklists/requirements.md
└── tasks.md             # Created by /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/0010_whatsapp_channel.py        # NEW: tables, questions.channel
├── scripts/whatsapp_dev_send.py                     # NEW: send a signed sample message in development
├── src/mrcourt/
│   ├── models/whatsapp.py                           # NEW: WhatsAppLink, MessageConsent, Message, InboundMessage, ConversationState
│   ├── schemas/whatsapp.py                          # NEW: settings, admin summary/failures
│   ├── api/whatsapp.py                              # NEW: webhook (GET, POST)
│   ├── api/me.py                                    # CHANGED: /me/whatsapp endpoints
│   ├── api/admin.py                                 # CHANGED: /admin/messages/*
│   ├── api/questions.py                             # CHANGED: thin wrapper over services/ask.py
│   ├── services/ask.py                              # NEW: ask + advice rule + store, shared by website and WhatsApp
│   ├── services/whatsapp/
│   │   ├── channel.py                               # NEW: protocol, InboundEvent, templates, window rule
│   │   ├── meta.py                                  # NEW: Meta Cloud adapter (send, verify, parse, media)
│   │   ├── twilio_sandbox.py                        # NEW: Twilio adapter (send, verify, parse, media)
│   │   ├── development.py                           # NEW: development channel (outbox)
│   │   ├── consent.py                               # NEW: link, unlink, consent, STOP
│   │   ├── outbox.py                                # NEW: send pipeline, status moves, SMS fallback, merge
│   │   ├── inbound.py                               # NEW: store, dedupe, route, rate limit
│   │   ├── intents.py                               # NEW: keywords (en/hi/ta), case answers, conversation state
│   │   ├── format.py                                # NEW: short WhatsApp answers, sources, link
│   │   ├── voice.py                                 # NEW: fetch audio, transcribe, quote back
│   │   └── jobs.py                                  # NEW: send due nudges, retry unprocessed, purge (python -m …)
│   ├── services/notify.py                           # CHANGED: SMS only; legacy WhatsApp paths removed
│   ├── services/auth.py                             # CHANGED: codes by WhatsApp first when chosen, SMS fallback
│   ├── services/reminders.py                        # CHANGED: reminders through outbox
│   ├── services/client_status.py, client_questions.py  # CHANGED: queue an update / activity nudge
│   ├── services/speech.py                           # CHANGED: accept a codec (OGG/Opus), research D7
│   ├── services/privacy.py                          # CHANGED: delete link, consents, records on deactivation
│   ├── config.py                                    # CHANGED: WHATSAPP_* settings
│   └── main.py                                      # CHANGED: register router, start job loop pieces
└── tests/
    ├── unit/        test_whatsapp_signatures.py, _intents.py, _format.py, _status.py, _consent.py
    ├── contract/    test_whatsapp_webhook.py, test_whatsapp_settings.py, test_admin_messages.py
    └── integration/ test_whatsapp_outbound.py, _inbound.py, _privacy.py, _parity.py (same answer as website)

frontend/
├── src/
│   ├── components/WhatsAppCard.tsx                  # NEW: link, kinds, unlink, masked number
│   ├── pages/Settings.tsx                           # CHANGED: renders the card; label "Text message reminders" stays
│   ├── pages/AdminMessages.tsx                      # NEW: counts, failures, service health
│   ├── pages/DevMessages.tsx                        # CHANGED: shows channel and kind
│   ├── components/AppShell.tsx                      # CHANGED: admin nav "Messages"
│   ├── services/whatsapp.ts, admin.ts               # NEW / CHANGED: hooks and types
│   └── styles/app.css                               # CHANGED: a few .wa-* rules using tokens
└── tests/e2e/   whatsapp-settings.spec.ts, admin-messages.spec.ts (+ axe scans in a11y.spec.ts)

README.md, render.yaml                               # CHANGED: WhatsApp setup, secrets, webhook URL
```

**Structure Decision**: web application layout as in the earlier features. WhatsApp code lives in one new package
(`services/whatsapp/`) with a thin API module; SMS stays in `notify.py`. The only refactor of existing behaviour is
moving the ask flow into `services/ask.py` so both channels share it.

## Delivery order (phases, each independently testable)

1. **Foundation**: models and migration; channel protocol, development channel, signature checks for Meta and
   Twilio; webhook with idempotency (tests with signed samples).
2. **US1 Link and consent**: Settings API and card, STOP, audit, deactivation cleanup. *(MVP of consent)*
3. **US2 Outbound with status and fallback**: outbox, reminders and codes through it, delivery reports, SMS
   fallback, purge job, removal of legacy WhatsApp code in `notify.py`.
4. **US3 Questions**: `services/ask.py` refactor, inbound routing, short format, rate limits, parity tests.
5. **US4 Case answers**: next hearing, status, today, case choice state.
6. **US5 Update nudges**: queue and merge, advocate activity nudge.
7. **US6 Voice**: audio fetch, codec check (D7), quote-back.
8. **US7 Admin view**: summary, failures, health, resend, audit.
9. **Polish**: README and render.yaml, quickstart run on the sandbox, accessibility, privacy review checklist,
   regression of all suites, `results.md`.

Live provider checks (research "To verify first") run as soon as phase 1 and 2 exist, in parallel with the owner's
account and template setup, so that approval delays do not block building.

## Complexity Tracking

| Item | Why needed | Simpler alternative rejected because |
|---|---|---|
| Public webhook endpoint | Inbound messages and delivery reports can only arrive this way | Polling the provider would need a different API per provider and still would not give replies in real time |
| Five new tables | Consent, link, delivery proof, duplicates and short conversation memory are distinct facts with different lifetimes | Storing them on `users` would mix personal data with 90-day delivery records and make deletion and purge error-prone |
| A channel interface with two adapters | Production target and free test provider differ in signatures, payloads and templates | One hard-coded provider could not be tested for free or replaced |
| Background processing after the 200 | Answers can take many seconds; providers retry slow webhooks | Answering inside the request would cause duplicate replies on retries |
| Removing legacy WhatsApp code in `notify.py` | Two WhatsApp paths would double-send and nobody can test the old ones | Keeping both is the more complex and riskier option |

## Open decisions for the owner (do not block planning)

1. **Provider account**: who creates and verifies the Meta WhatsApp Business account, and when (days of lead time)?
2. **Budget**: monthly cap for template messages (the plan includes `WHATSAPP_DAILY_SEND_CAP`).
3. **Languages**: add Hindi and Tamil template texts in the first release, or English only at first?
4. **Private documents over WhatsApp**: the plan keeps them out entirely; revisit only after the DPDP review.
