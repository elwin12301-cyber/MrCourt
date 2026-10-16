# Research: WhatsApp channel (feature 010)

Provider facts below come from the providers' public documentation as known when this was written. Prices, free
allowances and limits change: **check them again before launch** (listed under "To verify first").

## Where WhatsApp is needed in MrCourt (touch points)

| # | Place in the product | Direction | Today | After this feature |
|---|---|---|---|---|
| 1 | Login and phone-check codes (`services/auth.py`) | out | WhatsApp/SMS, untested | WhatsApp first if the person chose it, SMS fallback |
| 2 | Hearing reminders (`services/reminders.py`) | out | WhatsApp/SMS, untested, no delivery proof | Template message, status kept, SMS fallback |
| 3 | Case updates to clients (`client_status.py`, `client_questions.py` create `ClientUpdate`) | out | App only | One short nudge naming the case |
| 4 | Advocate alert when a client asks a question or requests an update | out | App only | One short nudge (kind "activity") |
| 5 | Ask MrCourt (`api/questions.py` + `answering.py`) | in | Website only | Ask by text or voice note on WhatsApp |
| 6 | "Next hearing" and "status" (`cases.py`, `client_view.py`) | in | Website only | Ask by keyword |
| 7 | Settings → notifications (`me.py`, `UserSettings`) | UI | One switch "text reminders" | Link number, switch per kind, unlink |
| 8 | Admin console | UI | none | "Messages" view: counts, failures, health |
| 9 | Account deactivation (`privacy.py`) | data | deletes phone | also deletes link, consents, message records, audio |

## Decisions

### D1. A small provider-neutral channel, separate from the SMS notifier

- **Decision**: add `services/whatsapp/` with a `WhatsAppChannel` protocol: `send_template(to, template, variables)`,
  `send_text(to, text)` (inside the 24-hour window), `verify_and_parse(request) -> list[InboundEvent]` (messages and
  delivery reports) and `fetch_audio(media_ref) -> bytes`. Adapters: **Meta Cloud API** (production target),
  **Twilio sandbox** (free testing), and a **development channel** that writes to the existing development outbox.
  `notify.py` stays the SMS notifier; its three half-working WhatsApp paths are removed once the new channel is live.
- **Why**: the existing `Notifier` is fire-and-forget (`send(message) -> None`), has no delivery status, no inbound
  and no consent, and mixes SMS and WhatsApp in one call. Delivery tracking, fallback and replies need a different
  shape. Keeping SMS where it is limits the change.
- **Alternatives rejected**: extending `Notifier` (cannot express statuses, windows or inbound without growing every
  adapter); using only Twilio (the free sandbox cannot run in production and charges per message later); using
  Fast2SMS WhatsApp (outbound templates only, no inbound conversation API we could verify).

### D2. Consent and linking reuse what exists

- **Decision**: "linking" = the person's phone is already verified (`users.phone_verified_at`, existing code check);
  a `whatsapp_links` row records that this verified number is allowed to use the channel, plus `last_inbound_at`
  for the 24-hour window. One number per account already holds (`users.phone` is unique). Changing the phone number
  unlinks it. Consents are per kind in `message_consents`, all **off** until the person switches them on; the old
  `user_settings.whatsapp_reminders` (default on) is not treated as WhatsApp consent.
- **Why**: no new verification flow to build or break; satisfies "only verified numbers receive messages".
- **Alternative rejected**: a second code check just for WhatsApp (extra friction, same proof).

### D3. Webhook: verify first, store, answer afterwards

- **Decision**: one public endpoint `/api/v1/whatsapp/webhook`. The raw body is checked against the provider
  signature **before** parsing (Meta: `X-Hub-Signature-256`, HMAC-SHA256 with the app secret; Twilio:
  `X-Twilio-Signature`, HMAC-SHA1 of URL + sorted form fields with the auth token), compared in constant time.
  Meta's setup call (`GET` with `hub.verify_token` and `hub.challenge`) is answered only when the token matches.
  A valid message is stored in `inbound_messages` (unique on provider + provider message id, which makes repeats
  harmless), the endpoint returns 200 at once, and the work (question answering, speech) runs afterwards in a
  background task. Records left unprocessed are retried by the existing hourly job (at most 3 times).
- **Why**: providers expect a quick 200 and retry otherwise; answering can take many seconds; a retry must not
  cause a second answer.
- **Origin check**: the existing cross-site check in `main.py` only refuses a write that *carries* a foreign
  `Origin`; webhook calls carry none, so no exemption is needed. A test pins this.

### D4. Same answer path as the website

- **Decision**: move the body of `api/questions.py` (ask, apply the client advice rule, store question, answer and
  citations) into `services/ask.py` and call it from both the API and the WhatsApp handler. The question gets a
  `channel` column (`app` | `whatsapp`). WhatsApp answers use **shared sources only** (the call passes no user for
  retrieval, but the person for the advice rule and for storing history).
- **Why**: SC-004 requires identical citations and "no reliable source" behaviour; two copies would drift.
- **Format**: at most about 1,000 characters, paragraphs trimmed at a sentence, "Sources:" with the labels,
  the disclaimer line, a link to History (`/ask/history`; the site has no page per question, and the full answer opens from there). The no-source and "not found in the sources" replies
  are the same texts as the website.

### D5. Intents without AI

- **Decision**: a small rule table maps keywords in English, Hindi and Tamil (for example "next hearing", "status",
  "today", "help", "stop", and a bare number while a list is open) to actions; anything else is a question. A
  conversation state (a few minutes) holds "choose a case" lists.
- **Why**: reliable, free, testable; hearings and status need no model.

### D6. Outbound pipeline with status and fallback

- **Decision**: every send goes through `services/whatsapp/outbox.py`: check link + consent → create a `messages`
  row (no text) → `send_template` → store the provider message id. Delivery reports (webhook) move the status
  forward only (queued < sent < delivered < read; failed is final). On `failed` (or "not on WhatsApp", or an
  immediate send error) one SMS with the same minimal text goes out through the existing notifier in SMS-only
  mode, linked to the first record. Update nudges wait about 3 minutes (`send_after`) so changes merge into one
  message; a nudge for a case that already has a reminder queued for the same person is dropped.
- **Templates** (approved in the provider's console, names in settings): `mrcourt_code` (1 variable, authentication
  category), `mrcourt_hearing_reminder` (case, when), `mrcourt_case_update` (case), `mrcourt_activity` (case).
  Replies to a person's own message use free text inside the 24-hour window.

### D7. Voice notes

- **Decision**: download the audio from the provider, convert to text with the existing speech service, send
  "I heard: …", then answer. Audio is held in memory only and never written to disk.
- **Outcome (2026-10-13)**: the speech SDK's list of accepted audio codecs includes `ogg` and `opus`, so
  `SpeechToText.transcribe(audio, language, codec)` now passes the codec through and **no ffmpeg conversion was added**.
  Not yet proven end to end: a real WhatsApp voice note has to be sent from a phone (quickstart §3, step 5). If the
  live service refuses OGG, add the ffmpeg conversion described below.
- **Original open point**: WhatsApp voice notes are OGG/Opus; `SarvamSpeech.transcribe` currently sends WAV
  with `input_audio_codec="wav"`. First try passing the codec through (the provider's API lists OGG/Opus among its
  accepted formats); if refused, convert with ffmpeg (adds a system package to the Docker image).

### D8. Limits and privacy

- **Per-number rate limit** from the database, not memory (restart-safe, works with several instances): count
  `inbound_messages` for the sender in the last minute and day. Strangers are tracked by an HMAC of the number
  (`sender_hash`), never the raw number.
- **Stored**: delivery records (kind, status, time, person) for 90 days; question text only in the person's
  question history; no message text in `messages`, `inbound_messages` or the audit log.
- **Administrators** see counts, failure reasons and names, never text (the existing rule that administrators may
  read private case content does not extend to WhatsApp message text, because none is stored there).

### D9. Fast2SMS as a third adapter (added after the first build)

- **Decision**: `services/whatsapp/fast2sms.py` implements the same channel interface for Fast2SMS, the Indian provider the
  owner already pays for: templates by `GET /dev/whatsapp` (template id, number id, recipient, values joined by `|`), replies
  by `POST /dev/whatsapp-session`, and inbound messages and delivery reports through webhooks (`incoming_message` and
  `status_update`) whose body is a template the owner writes in the Fast2SMS panel (the README gives it).
- **Weaker verification**: Fast2SMS webhooks are not signed. Each carries a fixed secret in the `webhook_secret_key` header,
  compared in constant time. This is shared-secret authentication, not an integrity check of the body; anyone who learns the
  secret can forge a call. Mitigations: constant-time comparison, secret only in environment, never logged, rotate on
  suspicion, HTTPS only. Because a forged call could also carry a media address, audio is fetched only from `https` addresses
  on `fast2sms.com`, and the API key is never sent elsewhere.
- **Unverified, to settle in the first live test**: whether status reports carry the `request_id` returned when sending (the
  report's `message_id` may differ; the app then matches the newest message of that provider to that recipient in the last
  3 days, a best guess when two are in flight), the exact status words, whether the webhook escapes quotes in JSON, whether
  voice-note media addresses are on `fast2sms.com` and fetchable, and the recipient number format the template call wants
  (ten digits are sent for Indian numbers).
- **Source**: Fast2SMS's help articles (WhatsApp message API, webhooks, chatbot and session messages), not a formal reference.

## To verify first (before building the live adapter)

1. Meta WhatsApp Business account, business verification time, phone number registration, and template approval time
   (utility and authentication categories). Whether an **authentication** template can carry our 5-minute code text.
2. Current per-message charges and any free allowance; whether a reply within 24 hours is free.
3. Twilio sandbox behaviour today: join phrase, how long a join lasts, whether it can call our webhook from a public
   tunnel (needs a public HTTPS URL for local testing, for example a tunnel tool).
4. Whether the speech provider accepts OGG/Opus directly (D7).
5. Hindi and Tamil template and STOP-word handling on the chosen provider.
6. A DPDP review of sending case titles and hearing dates through a third-party messaging service.

## Risks

| Risk | Mitigation |
|---|---|
| Template approval takes days or is refused | Build and test on the sandbox first; switch on per kind as templates are approved |
| Provider outage or quota | SMS fallback for outbound; "try again in a minute" for questions; admin health indicator |
| A recycled phone number reaches the wrong person | Messages only go to a verified, linked number; unlinked senders get one fixed reply; re-verify numbers silent for a long time |
| Free Voyage/Gemini limits slow answers | Same behaviour as the website: passages-only fallback with a note |
| In-process background tasks lost on restart | Inbound rows persist; the hourly job retries unprocessed ones |
| Cost surprises | Per-person and global daily send caps, counts shown to administrators |
