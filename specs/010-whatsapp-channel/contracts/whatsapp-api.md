# Contract: WhatsApp channel (feature 010)

All paths are under `/api/v1`. Signed-in endpoints use the session cookie and the existing cross-site check. The
webhook is public and protected by the provider signature.

## 1. Settings (signed-in advocate or petitioner)

### `GET /me/whatsapp`

```json
{
  "available": true,
  "linked": true,
  "number": "+91 ••••• ••172",
  "can_link": true,
  "kinds": [
    {"kind": "codes", "enabled": false, "changed_at": null, "describes": "Your sign-in and verification codes."},
    {"kind": "reminders", "enabled": true, "changed_at": "2026-10-13T08:00:00Z",
     "describes": "The case title and the date and time of a hearing, 5 days before, 1 day before and on the day."},
    {"kind": "updates", "enabled": false, "changed_at": null,
     "describes": "A short note that there is news on a case, with the case title only. The detail stays in MrCourt."}
  ],
  "last_sent_at": "2026-10-13T08:00:04Z"
}
```

- `available` is false when no provider is configured (the development outbox is in use).
- `can_link` is false until the phone is verified (the screen then links to the existing phone check).
- Clients see `codes`, `reminders`, `updates`; advocates see `codes`, `reminders`, `activity`.

### `POST /me/whatsapp/link` → 200 same body as GET

Errors: `409 phone_not_verified`, `409 number_in_use` (message does not say whose). Audited `whatsapp.link`.

### `DELETE /me/whatsapp` → 204 (unlink)

Switches every kind off, deactivates the link. Audited `whatsapp.unlink`.

### `PUT /me/whatsapp/consents/{kind}` body `{"enabled": true}` → 200 same body as GET

Errors: `404` for a kind the role does not have, `409 not_linked`. Audited `whatsapp.consent` (kind and new value).

### `DELETE /me/whatsapp/history` → 204

Deletes the person's delivery records and stored WhatsApp-asked questions are left to the normal history controls.

## 2. Webhook (provider → MrCourt)

### `GET /whatsapp/webhook` (Meta setup)

Query `hub.mode=subscribe&hub.verify_token=…&hub.challenge=…`. Returns the challenge as plain text when the token
matches `WHATSAPP_VERIFY_TOKEN`, otherwise `403`. Nothing else is revealed.

### `POST /whatsapp/webhook`

| Provider | Signature header | Body |
|---|---|---|
| Meta Cloud API | `X-Hub-Signature-256: sha256=<hex HMAC of the raw body with the app secret>` | JSON `entry[].changes[].value` with `messages[]` and `statuses[]` |
| Twilio sandbox | `X-Twilio-Signature: <base64 HMAC-SHA1 of the full URL + sorted form fields>` | form fields (`From`, `Body`, `MessageSid`, `NumMedia`, `MediaUrl0`, `MessageStatus`) |

Behaviour (the same whatever the provider):

1. The signature is checked on the raw body in constant time. **Invalid or missing → `403`, nothing parsed or
   stored, a log line without the body.**
2. Each message or delivery report is turned into an `InboundEvent`.
3. A message whose `(provider, provider_message_id)` already exists is ignored.
4. Delivery reports update the matching `messages` row, moving the status forward only. A `failed` report starts the
   SMS fallback.
5. A message is stored in `inbound_messages` and the endpoint returns `200 {}` at once; processing continues in the
   background.

Never returns whether a number has an account. Body size limit 1 MB.

### Inbound routing (background)

```
number not linked ─────────────► fixed reply: how to link (identical for every unknown number); capped per sender_hash
STOP / रोकें / நிறுத்து ───────► all consents off, one confirmation
"help" ────────────────────────► list of what can be asked
"next hearing" / "status" / "today", or a number while a case list is open
                               ► case answers (role rules, shared items only for clients)
voice note ────────────────────► transcribe → "I heard: …" → treat as a question
image / document / other ──────► "I can read text and voice notes. Open MrCourt to add documents."
anything else ─────────────────► question (answered like Ask MrCourt, shared sources, short form)
```

Replies are free text sent inside the 24-hour window.

### Reply texts (fixed, no account information)

| Situation | Text |
|---|---|
| Unknown number | "This number is not linked to a MrCourt account. Open MrCourt, go to Settings and choose Link WhatsApp." |
| Rate limit | "You have sent a lot of messages. Please try again in a few minutes." |
| Answer service busy | "I could not answer just now. Please try again in a minute." |
| STOP | "You will not get WhatsApp messages from MrCourt. You can switch them on again in Settings." |
| Question answer | up to about 1,000 characters, "Sources: …", "Informational only, not legal advice.", a link to History in the app (`PUBLIC_APP_URL/ask/history`, where the full answer opens) |

## 3. Administrator (signed-in administrator only)

### `GET /admin/messages/summary?days=7`

```json
{"days": 7, "service": {"provider": "meta", "healthy": true, "last_ok_at": "2026-10-13T08:00:04Z"},
 "totals": [{"kind": "reminder", "channel": "whatsapp", "queued": 0, "sent": 2, "delivered": 40, "read": 31, "failed": 3},
            {"kind": "reminder", "channel": "sms", "queued": 0, "sent": 3, "delivered": 0, "read": 0, "failed": 0}]}
```

### `GET /admin/messages/failures?days=7&limit=50&before=…`

Rows: `id`, `time`, `kind`, `person` (name only), `reason` (plain code), `fell_back_to_sms` (bool). **No text, no
number, no question.** Audited `whatsapp.admin.failures.view` (count only).

### `POST /admin/messages/{id}/resend` → 202

Only for a failed reminder or update whose person is still linked and opted in; creates a new record. Audited
`whatsapp.admin.resend`. `409` otherwise.

## 4. Outbound templates (provider side; names from settings)

| Setting | Default name | Variables | Category |
|---|---|---|---|
| `WHATSAPP_TEMPLATE_CODE` | `mrcourt_code` | code | authentication |
| `WHATSAPP_TEMPLATE_REMINDER` | `mrcourt_hearing_reminder` | case title, when | utility |
| `WHATSAPP_TEMPLATE_UPDATE` | `mrcourt_case_update` | case title | utility |
| `WHATSAPP_TEMPLATE_ACTIVITY` | `mrcourt_activity` | case title | utility |

Texts to submit for approval (English; Hindi and Tamil versions later):

- code: "Your MrCourt code is {{1}}. Do not share it with anyone." (sign-in codes live 5 minutes and phone and reset codes 10, so the template does not state a time)
- reminder: "Announcement from MrCourt: your hearing in {{1}} is {{2}}."
- update: "MrCourt: there is a new update on {{1}}. Open MrCourt to read it."
- activity: "MrCourt: your client sent a message about {{1}}. Open MrCourt to read it."

## 5. Settings (environment)

`WHATSAPP_PROVIDER` (`meta` \| `twilio` \| `none`), `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN`,
`WHATSAPP_APP_SECRET`, `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_TEMPLATE_*` (above), `TWILIO_WHATSAPP_FROM` (sandbox,
existing), `PUBLIC_APP_URL` (for links), `WHATSAPP_DAILY_SEND_CAP`. Secrets only in `backend/.env` or the host's
secret store; never in responses or logs.
