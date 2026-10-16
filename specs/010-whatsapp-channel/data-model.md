# Data model: WhatsApp channel (feature 010)

One Alembic migration `0010_whatsapp_channel.py` (idempotent, as the earlier ones). SQLite for tests and
development, PostgreSQL in production. **No column stores message text.**

## New tables

### `whatsapp_links`

| Column | Type | Notes |
|---|---|---|
| `user_id` | UUID PK, FK users, cascade | one link per account |
| `msisdn` | String(32), unique, index | the verified number, digits with country code; equals `users.phone` normalised |
| `linked_at` | DateTime tz | when the person linked |
| `last_inbound_at` | DateTime tz, null | last message from the person; opens the 24-hour free-reply window |
| `last_sent_at` | DateTime tz, null | shown in Settings |
| `unlinked_at` | DateTime tz, null | set on unlink; a row with `unlinked_at` is inactive |

Rules: created only when `users.phone_verified_at` is set; deactivated when the phone changes or the account is
deactivated; `msisdn` unique so a number belongs to one account.

### `message_consents`

| Column | Type | Notes |
|---|---|---|
| `user_id` | UUID FK users, cascade | PK part |
| `kind` | String(20) | PK part: `codes` \| `reminders` \| `updates` \| `activity` |
| `enabled` | Boolean | default false |
| `changed_at` | DateTime tz | when it last changed |
| `changed_by` | String(12) | `person` \| `stop` \| `system` (deactivation, number change) |

`updates` applies to clients, `activity` to advocates; the API refuses the other role's kind.

### `messages` (outbound delivery records)

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID FK users, cascade, index | recipient |
| `kind` | String(20) | `code` \| `reminder` \| `update` \| `activity` |
| `channel` | String(10) | `whatsapp` \| `sms` |
| `status` | String(10) | `queued` → `sent` → `delivered` → `read`; or `failed` |
| `provider` | String(12) | `meta` \| `twilio` \| `fast2sms` \| `development` |
| `provider_message_id` | String(255), index, null | to match delivery reports |
| `case_id` | UUID FK cases, null, set null | the case it concerns |
| `hearing_id` | UUID FK hearings, null, set null | reminders |
| `fallback_of` | UUID FK messages, null | the WhatsApp record this SMS replaced |
| `failure_reason` | String(60), null | short plain code, for example `not_on_whatsapp`, `template_missing`, `provider_down` |
| `send_after` | DateTime tz, null | update nudges wait to be merged |
| `created_at`, `updated_at` | DateTime tz | |

Index `(status, send_after)` for the sender job; index `(created_at)` for the 90-day purge. A status may only move
forward (enforced in one function, tested).

### `inbound_messages`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `provider` | String(12) | |
| `provider_message_id` | String(255) | **unique with `provider`**: duplicates are ignored |
| `user_id` | UUID FK users, null, set null | null for an unlinked number |
| `sender_hash` | String(64), index | HMAC-SHA256 of the number with the session secret; never the raw number of a stranger |
| `kind` | String(16) | `text` \| `audio` \| `other` (as received), then `question` \| `voice` \| `status` \| `stop` \| `unknown_sender` once handled |
| `status` | String(10) | `received` → `processed` \| `failed`; `attempts` int |
| `question_id` | UUID FK questions, null, set null | link to the stored question, where the text lives |
| `created_at` | DateTime tz, index | |

### `conversation_state`

| Column | Type | Notes |
|---|---|---|
| `user_id` | UUID PK, FK users, cascade | |
| `awaiting` | String(20) | `case_choice` |
| `options` | JSON | list of case ids offered, in order (ids only) |
| `expires_at` | DateTime tz | a few minutes ahead; expired rows are ignored and purged |

## Changed tables

| Table | Change |
|---|---|
| `questions` | `channel` String(10), default `app` (`app` \| `whatsapp`) |
| `user_settings` | none; `whatsapp_reminders` keeps meaning "text message reminders" (UI label already changed) |
| `audit_log` | no schema change; new actions: `whatsapp.link`, `whatsapp.unlink`, `whatsapp.consent`, `whatsapp.stop`, `whatsapp.admin.failures.view`, `whatsapp.admin.resend` |

## Lifecycle

```
Person: verifies phone (existing) ──► Settings: "Link WhatsApp" ──► whatsapp_links row, all consents off
        switches a kind on ─────────► message_consents(enabled=true, changed_by=person)
        sends STOP ─────────────────► all consents off (changed_by=stop), one confirmation
        changes phone / deactivates ► link inactive, consents off (changed_by=system), records deleted on deactivation

Outbound: event ► consent + link ok? ► messages(queued) ► send template ► sent
          provider report ► delivered / read      or      failed ► one SMS (messages, channel=sms, fallback_of=…)

Inbound: webhook ► signature ok? ► inbound_messages(received, unique id) ► 200
         background ► link? ► STOP | status | question | voice ► reply ► processed
Purge:   messages and inbound_messages older than 90 days deleted; expired conversation_state deleted
```

## Validation rules

- A number may be linked only if verified and not linked elsewhere; the reply never says whose number it is.
- No send to a number without an active link **and** an enabled consent (the code just asked for is the one exception).
- `messages` never holds text; the question text is held only by `questions` (owner's history rules).
- Deleting a user deletes `whatsapp_links`, `message_consents`, `messages`, `conversation_state`; `inbound_messages`
  keeps no personal reference (`user_id` set null) and is purged at 90 days.

## Decisions made while building

- `messages` has no `variables` column: the words of a queued nudge or an SMS fallback are rebuilt from `kind`, `case_id` and
  `hearing_id` when they are sent, so no case title is stored. A **login code cannot be rebuilt**, so its SMS fallback happens
  only when WhatsApp refuses the message at once; if WhatsApp reports failure later, the person asks for a new code.
- `inbound_messages` has a nullable `payload` (the text, or the voice note's reference) that exists **only while the message is
  waiting to be processed** and is cleared when it is processed or after the last retry. Administrators never see these rows.
