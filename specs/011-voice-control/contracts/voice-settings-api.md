# Contract: Voice settings (backend)

The existing `PATCH /api/v1/me/settings` and the `settings` object returned by `GET /api/v1/me` gain three fields. No new endpoint. Voice recognition itself stays in the browser, or on the existing `POST /api/v1/speech/transcribe` for the opt-in cloud path.

## Read

`settings` in `GET /api/v1/me` and in the `PATCH` response:

```json
{
  "language": "en",
  "whatsapp_reminders": true,
  "hearing_alert_days": 1,
  "theme": "system",
  "voice_consent": true,
  "voice_cloud_opt_in": false,
  "voice_language": "ta-IN"
}
```

- `voice_consent` is true when `voice_consent_at` is set. The time itself is not returned.
- `voice_language` is null or one of `en-IN`, `hi-IN`, `ta-IN` (the launch languages that have a command pack).

## Change

`PATCH /api/v1/me/settings` accepts any of:

| Field | Type | Rule |
|---|---|---|
| `voice_consent` | boolean | true stamps the consent time (if not already set); false clears it and also turns the cloud opt-in off. |
| `voice_cloud_opt_in` | boolean | true needs consent; otherwise `422` with "Agree to voice control first". |
| `voice_language` | string or null | must be a launch code or null; otherwise `422`. |

Responses: `200` with the new settings; `401` if not signed in; `422` as above.

## Audit

A change of `voice_consent` writes `voice.consent.on` or `voice.consent.off`; a change of `voice_cloud_opt_in` writes `voice.cloud.on` or `voice.cloud.off`. Entries carry the actor and time and nothing else (no language, no phrase). A request that changes nothing writes nothing. Turning consent off writes both the consent entry and, if it was on, the cloud entry.

## Speech endpoint (unchanged), used by the cloud path

`POST /api/v1/speech/transcribe` (existing): one short audio turn up to the existing limit, nothing stored, 20 turns per minute per person. Voice control sends only phrases it detected, at most about 8 seconds each. A `429` is shown as "Voice is busy, paused for a moment", and the cloud path pauses until the window passes.

## Privacy checks (tests)

- Neither the settings response nor any audit entry contains a phrase or audio.
- Turning consent off turns the cloud opt-in off in the same call.
- No log line at the default level contains a phrase.
