# Results: WhatsApp channel (feature 010)

Date: 2026-10-13. Development database: PostgreSQL 16 (Docker), migrated to revision 0010.

## Status of the tasks

66 of the 69 first tasks are done and the regression below is recorded; the Fast2SMS addendum (T070 to T075) adds 5 done and 1 open. Not done, and why:

| Task | Why it is open |
|---|---|
| T066 Run the quickstart on the Twilio sandbox | Needs a Twilio account and a public tunnel. The development-channel flow (quickstart section 2) was run instead, see below. |
| T067 Meta WhatsApp Business account, templates, live test | **Owner task**: account verification and template approval take days. |
| T068 Data-protection (DPDP) review | **Owner task**: a decision about sending case titles and dates through a third-party messaging service. |

## Regression (T069)

- Backend: **912 passed** (the suite now also refuses any test that tries to reach the real internet).
- Frontend: TypeScript and ESLint clean; Vitest 15 passed.
- Browser (Playwright, desktop and phone): the full run gave **448 passed, 2 failed** (10.6 minutes). The two failures were the
  administrator menu test, which lists the menu exactly and did not yet know the new "Messages" entry. After updating it,
  the administrator and accessibility specs were run again (104 passed, desktop and phone). The whole suite was not run a
  second time, so **450 of 450** is the expected total rather than a single recorded run.

## Live check in the running app (development database)

Run with the SMS and WhatsApp providers blanked, so nothing real was sent, on a fictional demo advocate that was
deactivated afterwards (which also checked that deactivation removes the WhatsApp data):

| Step | Result |
|---|---|
| A verified number that is not linked sends a question | One fixed reply: "This number is not linked to a MrCourt account. Open MrCourt, go to Settings and choose Link WhatsApp." |
| Link the number and switch "Hearing reminders" on | Linked; the number shown as +91 ••••• ••xxx; other kinds off |
| Ask "What does Section 138 of the Negotiable Instruments Act say about cheque dishonour?" | Cited answer written by Gemini, [1] [2], "Sources:" with Section 138 and the class notes, the disclaimer and the History link |
| "next hearing" | "You have no open cases on MrCourt." (the demo advocate has none) |
| STOP | One confirmation; every kind off; still linked; Settings shows them off |
| History | The question is marked as asked on WhatsApp |
| Administrator summary | "Not connected" (no provider set up), as expected |

## Found and fixed while building and checking

- **Hindi and Tamil STOP words never matched**: the clean-up removed the combining marks inside those scripts. Found by a
  unit test; now matched in three languages.
- **A cut answer lost its citation mark**: now each paragraph is cut first and its mark added after.
- **Tests were reaching Meta's real server**: unknown senders' replies were really sent from the webhook tests. Replies
  are stubbed in those tests and a guard now fails any test that tries the real network.
- **PostgreSQL rejected a value the SQLite tests accepted**: the incoming-message label "unknown_sender" (14 characters)
  did not fit a 12-character column, so the first message from a number that was not linked failed on PostgreSQL only.
  Found by this live check. The column is wider, a test pins the widths, and the id columns got generous room too.
- A batch of mistakes in my own tests and scripts (list order, per-minute limit, encoding), all on the test side.

## What is proven and what is not

Proven by tests (fake channel, signed sample payloads, fake HTTP transport): the signature checks for Meta and Twilio,
duplicate handling, consent and STOP in three languages, nothing sent to unlinked, unverified or opted-out people, delivery
status that only moves forward, one SMS fallback, the daily cap, nudges merged and dropped when not wanted, question parity
with the website (same outcome, answer text and citations), role-scoped hearing and status answers, voice notes with the
audio never written to disk, the administrator view and resend, and that no message words, codes, numbers or keys are kept
or logged outside the person's own History.

**Not proven**: anything against the live Meta or Twilio services (sending, the webhook, templates); a real WhatsApp voice
note (OGG) through the speech service; message speed and cost at real volumes; the Hindi and Tamil replies (only the STOP
and request words are handled in those languages, answers follow the question's sources).

## Decisions made while building (all recorded in the spec documents)

- A login code that WhatsApp reports as failed later is not re-sent by text (the code is not kept); an immediate refusal
  falls back to SMS.
- The "read more" link goes to History (the site has no page per question).
- WhatsApp text replies can be cut at a sentence to fit a phone; the sources, disclaimer and, for clients, the reminder to
  ask their lawyer are never dropped.
- The WhatsApp channel needs no change to the existing text reminders: a person who does not opt in keeps getting them by
  text as before.

## Open for the owner

1. Create and verify the Meta WhatsApp Business account and get the four templates approved (texts in the contract file).
2. Decide the DPDP question and the monthly budget for template messages.
3. Send a real voice note and a real question from a phone through the Twilio sandbox (quickstart section 3) before
   switching on Meta.

## Addendum: Fast2SMS adapter (2026-10-13)

`WHATSAPP_PROVIDER=fast2sms` sends templates and replies and receives messages and delivery reports through Fast2SMS.
Backend suite after adding it: **944 passed** (32 new tests: the adapter's sending and receiving, the secret check, voice
media restricted to `fast2sms.com`, and the webhook end to end including delivery reports matched by recipient and the single
SMS fallback). The frontend and browser suites were not changed by it and were not run again.

Two things came out of it:

- Fast2SMS webhooks are **not signed**: they carry a fixed secret in a header. That is weaker than Meta's and Twilio's
  signatures. It is checked in constant time and the README says to keep it out of logs and chats and to rotate it.
- A test exposed that the network guard did not cover `urllib` (the SMS senders use it), so one test had briefly tried a
  real Fast2SMS address with a fake key. The guard now blocks that too.

**Not proven**, for the first live test (T075): the template and number ids, whether status reports carry the id we stored
(otherwise they are matched by recipient, a best guess), the exact status words, that quotes in a message survive the webhook
body, whether voice-note media addresses are fetchable, and the recipient number format. All are listed in research D9.

