# Data Model: Voice Control

Only three per-person settings are stored. Everything else exists for seconds in the page and is never saved.

## Stored (backend)

### `user_settings` (existing table, three new columns, migration 0011)

| Column | Type | Meaning |
|---|---|---|
| `voice_consent_at` | timestamp with time zone, null | When the person agreed to the microphone and notice. Null means they have not agreed or have withdrawn. |
| `voice_cloud_opt_in` | boolean, default false | The person allows short phrases to be sent to the cloud speech service for languages the browser cannot recognise. Can be true only while `voice_consent_at` is set. |
| `voice_language` | string(8), null | Recognition language code (for example `en-IN`, `hi-IN`, `ta-IN`). Null uses the app default. |

Rules:
- Withdrawing consent (`voice_consent_at` to null) also sets `voice_cloud_opt_in` to false.
- Setting `voice_cloud_opt_in` to true without consent is refused.
- The values are removed with the person's account, like their other settings.
- Migration is idempotent like the earlier ones; existing rows get null, false, null.

### Audit entries (existing table)

New actions, with no content: `voice.consent.on`, `voice.consent.off`, `voice.cloud.on`, `voice.cloud.off` (actor and time only). Actions done **by** voice produce the same audit entries as the same action done by mouse; no voice-specific entry, no transcript.

## Not stored

- Audio. It is kept in memory for the length of one phrase on the cloud path and discarded; on the browser path it is never seen by the app.
- Transcripts of commands. A phrase lives in memory until it has been handled and is then dropped; it is not logged, sent to analytics, or written to the audit log. (The "last heard" line on screen is a display of the most recent phrase and is cleared when voice control is turned off.)

## In the page (frontend state, not persisted)

| Name | Fields | Lifetime |
|---|---|---|
| Voice session | `status` (off, starting, listening, paused, confirming, dictating), `language`, `engine` (browser or cloud), `lastHeard`, `lastResult`, `numbersShown` | Until turned off or the page is closed |
| Control | `element`, `name`, `aliases`, `kind` (link, button, tab, switch, checkbox, radio, option, input, other), `visible`, `enabled`, `risk` (none, confirm), `number`, `listIndex` | Recomputed whenever the page changes |
| Command | `intent`, `target`, `confidence`, `phrase` | Until handled |
| Pending confirmation | `controlOrAction`, `description`, `expiresAt` (15 s) | Seconds |
| Language pack | see below | Loaded with the app |

### Language pack shape

```text
code                 'en' | 'hi' | 'ta'            (recognition code e.g. 'ta-IN')
label                name shown in Settings
actions              { go, click, set_on, set_off, scroll_up, scroll_down, top, bottom, back, forward,
                       refresh, close, cancel, confirm, show_numbers, hide_numbers, dictate, stop_dictating,
                       clear_field, read_answer, read_screen, stop_reading, help, stop_listening, next_page }
                     each: list of phrases (native script and romanised)
fillers              words removed around a target ("the", "please", "ku", "ko", "to", "seyyu", "kijiye" …)
positions            first, second, third … last, as words and digits
numbers              digit words for "click seven"
names                { screens and common controls → list of spoken names (native + romanised) }
riskWords            words that make a control risky (delete, remove, log out, send …)
help                 short lines for the "what can I say" panel
```

A pack is plain data; a new language is added by a new file and one line registering it (FR-003b). Citation text and legal content are never translated by a pack.

## Relationships

`user_settings` 1—1 `users` (existing). No other new relationships.
