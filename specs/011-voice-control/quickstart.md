# Quickstart: Verify Voice Control

How to try it and to prove it works. Links: [spec](spec.md), [command grammar](contracts/command-grammar.md), [UI contract](contracts/ui-contract.md), [settings API](contracts/voice-settings-api.md).

## Prerequisites

- The app running (`docker`-based PostgreSQL on 5433, API on 8000, frontend on 5173) and the new migration applied: `alembic upgrade head` in `backend`.
- Chrome or Edge, on `http://localhost:5173`, with a microphone.
- Demo accounts from the seed: an advocate, a client and the administrator (all fictional).

## 1. Automated checks

```text
cd backend  && .venv/Scripts/pytest tests/contract/test_voice_settings.py tests/unit/test_voice_audit.py
cd frontend && npm run lint && npx tsc -b && npm test && npx playwright test voice-control voice-coverage
```

Expected: all pass. The coverage test fails with the screen and the control name if any clickable control lacks an accessible name or a risky control lacks confirmation.

## 2. Try it by hand (English)

1. Sign in as the advocate. On the dashboard tap the large microphone. The notice appears; choose "Agree and turn on". Status reads "Listening…".
2. Say, with pauses, without tapping again: "open cases", "go to Ask MrCourt", "open the history tab", "go to dashboard". Each opens; the "I heard you say" card shows the phrase and the result.
3. Say "show numbers"; say "click 3"; say "hide numbers".
4. On Settings say "turn on hearing reminders" (it switches on), then say it again (it says already on).
5. Say "scroll down", "top", "go back".
6. On Ask say "click question box", "dictate", speak a question, "stop dictating", "click ask". Then "read the answer": the answer, its sources and the disclaimer are read; say "stop reading".
7. Say "log out". The app asks to confirm. Say "cancel": nothing happens. Say it again and "confirm": you are signed out.
8. Say "what can I say" on Cases and on Settings: the lists differ.
9. Say "stop listening": the microphone stops within a second; the status reads "Microphone is off". Wait a minute: it must not restart.

## 3. Mixed languages

Set the language to Tamil (Settings or the panel). Say "dashboard ku po", "chella to dashboard", "settings kholo" (Hindi word, English name), "cases open pannu". Each opens. Repeat with Hindi ("dashboard par jao"). Say a phrase that matches nothing ("blah blah"): it says what it heard and does nothing.

## 4. Safety checks

- Mumble or say two commands: "open cases and delete the first": only "open cases" runs; the rest is said back.
- Two controls with the same name: the app shows numbers on them and asks.
- As the client, say "open admin console": not available. As the administrator, say "remove document" on a private document: the prompt names the owner and says it cannot be undone; "cancel" leaves it.
- Say "confirm" with no prompt pending: nothing happens.

## 5. Privacy checks

- With the browser path, open the browser's network tool while speaking: no audio requests to MrCourt.
- Turn the cloud option on in Settings (only offered after consent); switch to a language the browser cannot recognise; say a command: one short request per phrase to the speech endpoint, nothing stored.
- Withdraw consent in Settings: voice control stops; the cloud option turns off; the audit log shows the two entries with no phrase.
- Look at the API log and the audit log after a session: no phrases.

## 6. Accessibility and layout

- Keyboard only: reach the microphone, numbers toggle, help and stop; operate a confirmation with Tab and Enter; Escape cancels it.
- Screen reader: the status changes and results are announced; the number labels are not read.
- Light and dark themes; 360 px width (the bar collapses); reduced motion on (no pulse or fade).
- Run the axe checks in the e2e suite (included in step 1).

## 7. Record results

Write what differed from this guide, the measured results of the phrase tables (at least 50 phrases per language, 20 unclear ones that must not act), and the recognition limits seen on each browser in `results.md`.
