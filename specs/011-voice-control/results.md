# Results: Voice control

Date: 2026-10-26. Development database: PostgreSQL 16 + pgvector (Docker); migration 0011 applied.

## What was built

- **Backend:** three settings on `user_settings` (voice consent time, cloud option, language), refusal of the cloud option
  without consent, withdrawing consent also turns the cloud option off, four content-free audit actions
  (`voice.consent.on/off`, `voice.cloud.on/off`).
- **Frontend (`frontend/src/voice/`):** control finder, command parser, matcher, safety layer (confirmation state machine),
  continuous recogniser, opt-in cloud phrase listener, dictation, reader, engine, provider; interface in
  `VoiceBar`, `VoicePanel`, `VoiceNumbers`, `VoiceConfirm`, `VoiceHelp`, `VoiceNotice`, `VoiceSettingsCard`.
- **Screens changed:** the voice panel on the three dashboards; the Voice control section in Settings; risky controls
  tagged `data-voice-risk`; answers tagged `data-voice-read`; a few links given distinct names.

## Checks

| Check | Result |
|---|---|
| Backend voice settings and audit tests | 13 + 5 passed |
| Backend, whole suite | see "Regression" below |
| Frontend unit tests (voice): commands, controls, matcher, safety, recogniser, engine, phrase tables | 124 passed in the whole unit suite (10 files) |
| Phrase tables: English, Hindi, Tamil navigation phrases (50+ each, 15+ mixed each), 31 unclear phrases that must not act | pass (none of the unclear phrases acts) |
| Browser: navigation for advocate, client and administrator (desktop and phone) | pass |
| Browser: clicking by name, number, list place; switches; drop-down choices | pass |
| Browser: confirmations (logout, remove a client, administrator removing a private document), Escape, other command cancels, same-phrase cannot confirm | pass (desktop) |
| Browser: dictation, reading with sources and disclaimer, scrolling, closing dialogs | pass (desktop and phone) |
| Browser: consent, continuous listening through 10 commands and restarts, stop by voice, button and shortcut, blocked microphone, no support, language change, hidden tab, withdrawal | pass |
| Browser: opt-in cloud phrases with a fake microphone and a stubbed speech endpoint (one short phrase per request, nothing sent while off, busy service) | pass |
| Browser: panel on all three dashboards; axe in light and dark for panel, bar, notice, number labels, help, Settings, confirmation; 360 px; reduced motion; keyboard only | pass |
| Browser: coverage check over every main screen for the three roles (no unnamed controls, no mouse-only controls, no untagged risky controls, no unexplained duplicate names) | pass, and shown to fail correctly on an unnamed button and a mouse-only element |

## Found and fixed while building

- **Recognition is not "on the device".** The first draft of the spec said so. Chrome's and Edge's built-in recognition is run
  by the browser's maker. The spec, plan, notice and Settings text now say what is true: MrCourt never receives the audio, and
  the browser's own speech service listens.
- **Clickable table rows were invisible to voice** (Cases rows are `tr` with `tabindex` and a click handler). The finder now
  includes focusable custom elements, and the lists give "first / last" places for rows, list items and card links.
- **Select options were missing** from the finder. Added.
- **"log out" has no action word.** Whole-phrase shortcuts were added ("log out", "sign out", in the three languages).
- **A name such as "Knowledge" matched the menu item "Ask MrCourt"** through its alias "knowledge assistant" and made a tie
  against the tab "Knowledge Base". A phrase that says "tab", "button", "link" or "menu" now wins ties for that kind of
  control.
- **A reverse alias made "Ask" (a tab) equal to "Ask MrCourt".** Removed.
- **Noise around a command** ("ok google open cases please") acted. Two or more unexplained words now mean no match.
- **A browser confirm box** (removing a client from a case) would have needed the mouse after a spoken confirmation. It is
  accepted for that one click only, after the person has confirmed by voice.
- **Speech output feeding the microphone:** the confirmation prompt is read with listening set aside, then listening
  resumes; while an answer is being read, only "stop" is heard.
- **The question-bar microphone and voice control** no longer listen at the same time.
- **Duplicate names** ("My cases" back link and menu item, "Audit log" card link and menu item) were given distinct names.
- **"Send" in the question bar** is marked `data-voice-risk="none"` (a question to the assistant is not a message to a
  person); "Send update", "Send reply", "Send question" (to a lawyer) and "Send invitation" ask first.
- **A test that depended on today's date** (a hearing on 20 Oct 2026) failed once the real date passed it; fixed earlier in
  the WhatsApp work.

## Not done, or not possible here

- **T055 (accuracy on real speech):** the phrase tables run on text, so they measure the command pack, not the
  recogniser. Accuracy with real voices, accents and rooms (target 95% of clear commands, none of the unclear ones acting)
  and the recognition limits per browser still need people speaking to Chrome and Edge. Results from that go here.
- **T056 (owner):** the Hindi and Tamil wording, including "stop listening" and the mixed forms, needs a native speaker of
  each. Every phrase in `frontend/src/voice/lang/hi.ts` and `ta.ts` is unreviewed (`needsReview: true`).
- **T060 (quickstart by hand with a microphone):** not run; it needs a person.
- **Dialogs reachable only after an action** (for example the deactivate dialog's second step) are checked by the browser
  tests that open them, not by the screen-by-screen coverage walk.
- **Question-bar microphone on phones:** the pause/resume between the two microphones is tested in code paths but not on a
  real phone.
- **Timing:** the 1.5 s result target (SC-009) is met trivially for the matching itself (it is synchronous); the recogniser's
  own delay is the browser's.

## Regression (T059)

- **Backend:** 976 tests (975 passed on the full run; the one failure, a settings-shape expectation that did not know the
  three new fields, was updated and passes). Includes 18 new tests.
- **Frontend:** TypeScript and ESLint clean; Vitest 124 passed (10 files; 109 are new voice tests).
- **Browser (Playwright, desktop and phone):** **542 passed, 1 skipped, 2 flaky, 1 failed** in 8.6 minutes (about 95 of
  these are new voice tests across the six voice spec files).
  - The one failure is `sign-up-reset › a wrong code is refused…` on desktop. It also fails about one run in two **on its own**
    with no other test running, and it was already listed as flaky before this feature; the sign-up screens it uses are not
    part of the voice changes.
  - Flaky, passed on retry: `client-privacy › the advocate can set what clients see about them` and
    `sign-up-reset › forgot password: a code is texted…` (an "Internal Server Error" from the development text-message route).
  - Skipped on purpose: the administrator private-document removal by voice on the phone project (see below).
- Several voice tests had to be made independent of shared accounts and of how fast the machine is: tests that change voice
  settings use a fresh account, the seeded accounts have agreed to voice control in the global setup, and the audio tests
  repeat their "speaking" until the answer arrives.

### Things the runs showed that are not about voice

- **The administrator's Knowledge Base table is wider than a phone.** The page shrinks to fit, so a fixed button sits where
  the test browser will not click it (a real phone shows it). The voice dock is anchored to the left on phones for this
  reason. Making that table fit a phone is a separate piece of work.
- **The earlier whole-suite totals** (448 passed, 2 failed) were before the WhatsApp and voice features; the suite is now
  546 tests.
