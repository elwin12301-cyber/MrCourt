# Quickstart: validating the WhatsApp channel (feature 010)

Contracts: [contracts/whatsapp-api.md](contracts/whatsapp-api.md). Data: [data-model.md](data-model.md).

## 1. Automated checks (no WhatsApp account needed)

```text
cd backend && python -m pytest tests/unit/test_whatsapp_*.py tests/contract/test_whatsapp_*.py tests/integration/test_whatsapp_*.py -q
cd frontend && npx playwright test whatsapp-settings.spec.ts admin-messages.spec.ts a11y.spec.ts
```

The tests use a fake channel and signed sample webhooks for Meta and Twilio. They cover: signature refused,
duplicate ignored, consent and STOP, nothing sent to unverified/unlinked/opted-out numbers, fallback to SMS, status
only moves forward, answers equal the website's, no message text in the administrator data or audit log.

## 2. Development without a provider

With `WHATSAPP_PROVIDER=none` the development messages page lists each message that would be sent. To act as the
person sending a message, post a signed sample to the webhook:

```text
python backend/scripts/whatsapp_dev_send.py --from +919000000001 --text "What is Section 138 of the NI Act?"
```

(the script signs the request with the development secret and prints the reply the app would send).

## 3. Free live test with the Twilio sandbox

1. Create a free Twilio account; in the console open Messaging, Try it out, Send a WhatsApp message. Send the shown
   `join …` phrase from your own WhatsApp to the sandbox number (the join lapses after a few days).
2. Put `WHATSAPP_PROVIDER=twilio` and the Twilio keys in `backend/.env`.
3. Expose the backend over a public HTTPS tunnel (any tunnel tool) and set the sandbox "When a message comes in" and
   "Status callback" URLs to `https://<tunnel>/api/v1/whatsapp/webhook`.
4. Sign in, Settings → WhatsApp → **Link**, switch **Hearing reminders** on.
5. From the joined phone:
   - send "What is Section 138 of the NI Act?" → a cited short answer with sources and a link;
   - send "next hearing" → the case, date and time (as a client: only invited cases);
   - send "Section 999 IPC" → "Not found in the sources: Section 999 IPC…";
   - send a voice note with a question → "I heard: …" then the answer;
   - send STOP → one confirmation, Settings shows everything off.
6. As the administrator open **Messages**: counts and the delivery of your test messages, no text anywhere.

## 4b. Live test with Fast2SMS

1. In the Fast2SMS panel: connect the WhatsApp number, create the four templates and wait for approval; create the
   webhooks (README, "Production with Fast2SMS") and note the number id, template ids and webhook secret.
2. Put them in `backend/.env` with `WHATSAPP_PROVIDER=fast2sms`, expose the backend on a public HTTPS address and give the
   panel that address plus `/api/v1/whatsapp/webhook`.
3. Link your own number in Settings and switch on "Hearing reminders". Create a hearing 5 days away and run the reminder job:
   one template message arrives. In the administrator's Messages view the status should move to delivered. **If it stays
   "sent", the report's id differs from the stored one**; the recipient matching should still update it, so check which.
4. From your phone send: a question, `next hearing`, a question containing a double quote (`What is "bail"?`), a voice note
   and STOP. Each should be answered as in section 3.
5. Record what differed from the documentation in `results.md`.

## 4. Live test with Meta's WhatsApp Business interface

Only after the owner has a verified business account, a registered number and approved templates (names in
`contracts/whatsapp-api.md`):

1. `WHATSAPP_PROVIDER=meta` with phone number id, access token, app secret and verify token; set the webhook URL and
   verify token in the app dashboard (Meta calls the `GET` challenge once).
2. Repeat step 5 above using a real phone; additionally create a hearing 5 days away and run the reminder job:
   one template message arrives, status moves to delivered and read in the administrator view.
3. Turn the phone's WhatsApp off, create another reminder: the person gets the SMS fallback and the failure shows
   in the administrator list as "not on WhatsApp" or "failed" with the SMS marked as fallback.

## 5. Privacy checks

- Settings: every kind starts off; unlinking switches all off; deactivating the account removes the link and records.
- Administrator page, its data and the audit log contain no message text, question or number.
- A different person's number sending "next hearing" or a question gets the single "not linked" reply.
- An advocate's private document is never quoted in a WhatsApp answer.

## Rollback

Set `WHATSAPP_PROVIDER=none`: nothing is sent or answered over WhatsApp; codes and reminders go by SMS as before;
consents and records stay.
