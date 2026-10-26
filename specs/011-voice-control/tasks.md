# Tasks: Voice control for the whole app

**Input**: `/specs/011-voice-control/` (plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md)

**Tests**: Included. The constitution requires keyboard, theme and narrow-width checks for UI changes, and the spec sets measurable accuracy and safety targets (SC-003, SC-004, SC-008). Write each group's tests first and see them fail.

**Paths**: frontend `frontend/src/`, unit tests `frontend/tests/unit/`, browser tests `frontend/tests/e2e/`, backend `backend/src/mrcourt/`, backend tests `backend/tests/`. Tasks marked **(owner)** need something only the product owner can do (native-speaker review).

**Story map** (from the spec): US1 move around by voice (P1), US2 click by name, number or position (P1), US3 dictate, read aloud, scroll (P2), US4 confirmations and never guess (P1), US5 consent, controls, panel, help, cloud option (P2), US6 coverage that stays true (P3).

## Phase 1: Setup

- [X] T001 Create the folder `frontend/src/voice/` with `types.ts` (`VoiceStatus`, `Intent`, `Command`, `VoiceControl`, `LanguagePack`, `ActionResult`) exactly as in data-model.md, and an `index.ts` that exports them
- [X] T002 [P] Add a driveable fake recogniser for browser tests in `frontend/tests/e2e/support/voice.ts`: `say(...phrases)` with optional confidence, `endTurn()` (the browser ending a turn, so the app must restart it), modes `works`, `denied`, `missing`, `language-unsupported`, a fake speech output that records what was read and can be interrupted, and a fake microphone for the cloud path; build on the pattern in `frontend/tests/e2e/voice.spec.ts`
- [X] T003 [P] Add the voice test setup to `frontend/tests/unit/setup.ts` (fake `SpeechRecognition`, fake `speechSynthesis`, `matchMedia`, layout stubs so visibility checks work under jsdom) so the voice unit tests can run with `npm test`

## Phase 2: Foundational (blocks every story)

**Backend: three settings and their audit** (tests first)

- [X] T004 [P] Contract tests in `backend/tests/contract/test_voice_settings.py`: `voice_consent` true stamps consent and returns true; false clears it and turns the cloud option off in the same call; `voice_cloud_opt_in` true without consent is `422`; `voice_language` accepts `en-IN`, `hi-IN`, `ta-IN` and null, refuses others with `422`; `401` when signed out; the response and every audit entry hold no phrase or audio; unchanged values write no audit entry
- [X] T005 [P] Unit test in `backend/tests/unit/test_voice_audit.py`: audit actions `voice.consent.on/off` and `voice.cloud.on/off` exist with plain labels, carry only actor and time, and withdrawing consent while the cloud option is on writes both entries
- [X] T006 Alembic migration `backend/alembic/versions/0011_voice_control_settings.py` (idempotent like 0008 to 0010): add `voice_consent_at` (timestamptz, null), `voice_cloud_opt_in` (boolean, default false) and `voice_language` (string 8, null) to `user_settings`
- [X] T007 Add the three columns to `UserSettings` in `backend/src/mrcourt/models/user.py`
- [X] T008 Add `voice_consent`, `voice_cloud_opt_in`, `voice_language` to `SettingsOut` and `SettingsPatch` in `backend/src/mrcourt/schemas/auth.py` (consent returned as a boolean, never the time; language validated against the three launch codes)
- [X] T009 Implement the change rules in `patch_settings` in `backend/src/mrcourt/api/me.py` (stamp or clear consent, clear the cloud option with it, refuse cloud without consent) and write the four audit actions through `backend/src/mrcourt/services/audit.py`, adding their labels there

**Frontend: the engine every story uses** (tests alongside)

- [X] T010 Add the three voice fields to the `Settings` type and the settings update call in `frontend/src/services/auth.ts`
- [X] T011 [P] Control finder in `frontend/src/voice/controls.ts`: scan the page for visible, enabled, not-hidden clickable elements (links, buttons, tabs, switches, check boxes, radios, select options, menu items, rows that act as links or buttons), compute the accessible name (label, `aria-label`, text, title, image alt), kind, list index among repeated items, `data-voice-risk`; restrict to the open dialog when one exists; cache and refresh within 100 ms of a page change; unit tests in `frontend/tests/unit/voice-controls.test.tsx` (hidden, disabled, dialog scope, icon-only with label, duplicate names, list positions)
- [X] T012 [P] Language pack scaffolding in `frontend/src/voice/lang/index.ts` (registry, `activePacks()`, a pack check that every required action key is present) and a first complete `lang/en.ts` (all actions, fillers, positions, digit words, names of every menu item and common control for the three roles, risk words, help lines)
- [X] T013 [P] Hindi and Tamil packs `frontend/src/voice/lang/hi.ts` and `frontend/src/voice/lang/ta.ts`: same keys as English, native script and romanised forms side by side, including mixed-phrase fillers (for example "ku po", "chella", "kholo", "par jao", "ko jao"); mark every phrase that still needs a native speaker's check with a `review: true` flag
- [X] T014 Matcher in `frontend/src/voice/matcher.ts` per contracts/command-grammar.md: normalise, remove fillers of all packs, split action and target, match exact then all-words then one-edit-for-long-words, return `one`, `several` (with the matching controls) or `none` with a confidence; navigation words beat control words; unit tests in `frontend/tests/unit/voice-matcher.test.ts` (exact, partial, ambiguous, no match, low confidence refuses, never picks between equals)
- [X] T015 Command parsing in `frontend/src/voice/commands.ts`: turn a phrase into one `Command` (go, click, number, position, set, choose, scroll, history, close, numbers, dictate, read, help, language, stop, confirm, cancel); only the first action of a multi-command phrase is used and the rest is returned as "ignored"; unit tests in `frontend/tests/unit/voice-commands.test.ts`
- [X] T016 Safety core in `frontend/src/voice/safety.ts`: risk test (`data-voice-risk` or a risk word from any pack), the confirmation state machine (15 s expiry, "confirm" accepted only from a later recognition result, cancel by word, silence, Escape or any other command), the rule that a risky control is never activated by a single phrase; unit tests in `frontend/tests/unit/voice-safety.test.ts` (same-phrase confirm refused, timeout, cancel, multi-command phrase never runs a risky one)
- [X] T017 Recogniser in `frontend/src/voice/recognizer.ts`: continuous browser recognition built on the helpers exported from `frontend/src/hooks/useSpeechInput.ts` (export `getCtor` and the language list), restart whenever the browser ends a turn while the person still wants to listen (with a short back-off), stop at once on request, never restart after a stop, pause when the tab is hidden or the microphone is taken and resume on request, report denied, unsupported and language-unsupported plainly; unit tests in `frontend/tests/unit/voice-recognizer.test.ts` (auto-restart, no restart after stop, pause and resume, errors)
- [X] T018 Executor and provider in `frontend/src/voice/VoiceProvider.tsx`: holds the session state (`off`, `starting`, `listening`, `paused`, `confirming`, `dictating`), receives phrases from the recogniser, runs parse, match and safety, performs the click, navigation or scroll, and produces one short result line per phrase; refuses to start without consent (the notice, T020) and stops on sign-out; mount it above the router outlet in `frontend/src/App.tsx`
- [X] T019 [P] Compact bar and launcher in `frontend/src/components/VoiceBar.tsx` with `.vc-*` styles in `frontend/src/styles/app.css` (existing tokens only; microphone button as a real `button` with `aria-pressed`, status dot and word, last phrase heard, result line, Stop; collapses to microphone, status and Stop at phone width; reduced motion honoured); render it from `frontend/src/components/AppShell.tsx` as a small microphone launcher when off and the full bar when on, with page bottom spacing while shown
- [X] T020 [P] Consent notice in `frontend/src/components/VoiceNotice.tsx` (plain-language text from contracts/ui-contract.md, "Agree and turn on" and "Not now"; closing agrees to nothing); on agree call the settings update (signed in) or keep the choice in the browser until sign-in, then send it

**Checkpoint**: with a fake recogniser a signed-in person can turn voice control on after agreeing, say a phrase, and see it matched and shown; no screen-specific commands yet.

## Phase 3: User Story 1 - Move around the app by saying where to go (Priority: P1) 🎯 MVP

**Goal**: every menu item, sub-menu, tab and section opens by name for all three roles, in English, Hindi, Tamil and mixed phrases.

**Independent test**: with voice control on, say each menu name and each tab name for an advocate, a client and an administrator; each opens; "go back" returns; a client saying "open admin console" gets "not available".

- [X] T021 [P] [US1] Phrase tables in `frontend/tests/unit/voice-phrases.test.ts`: at least 50 navigation phrases per language (English, Hindi, Tamil), including at least 15 mixed ones each (for example "dashboard ku po", "chella to dashboard", "settings kholo", "dashboard par jao") and 20 unclear ones that must match nothing; each phrase has an expected screen or "nothing"
- [X] T022 [P] [US1] Browser test `frontend/tests/e2e/voice-control-navigate.spec.ts`: as an advocate, a client and an administrator, desktop and phone, say each menu name, each Ask MrCourt tab, each Settings section and each admin page in turn; "go back", "go forward", "refresh", "go home"; the client cannot reach admin pages; the result line and the status are announced
- [X] T023 [US1] Add the screen, tab and section names for every route and tab in `frontend/src/App.tsx`, `AppShell.tsx` and the Ask, Settings and admin pages to the packs' `names` (English, Hindi, Tamil, mixed forms) until T021 passes; list in `specs/011-voice-control/results.md` any name a native speaker still has to confirm
- [X] T024 [US1] Implement the Go, History and Home intents in `frontend/src/voice/VoiceProvider.tsx`: activate the matching navigation control (so permissions are respected as for a mouse), `history.back/forward`, refresh, and the dashboard link for "go home"; say "not available to you" when no eligible control matches but a known screen name was heard

**Checkpoint**: navigation works hands-free for all roles and languages; this is the MVP.

## Phase 4: User Story 2 - Click anything by name, number or position (Priority: P1)

**Goal**: every visible clickable control can be pressed by name, by number, or by list position; toggles can be set.

**Independent test**: on each main screen say "show numbers", then pick controls by number, by name and by position; duplicates trigger numbers and a question.

- [X] T025 [P] [US2] Unit tests in `frontend/tests/unit/voice-numbers.test.ts`: numbering in reading order, stability on scroll and change, a number that has gone is refused, labels only on the matches of an ambiguous phrase
- [X] T026 [P] [US2] Browser test `frontend/tests/e2e/voice-control-click.spec.ts`: on Cases, a case, Ask, Settings, Drafts, Updates and the admin pages: "click save", "show numbers", "click 7", "hide numbers", "open the first case", "open the last one", "turn on hearing reminders" then again ("already on"), a disabled control ("not available now"), two controls with one name (numbers shown, question asked, no action)
- [X] T027 [US2] Number overlay in `frontend/src/components/VoiceNumbers.tsx`: a pointer-ignoring layer hidden from assistive technology that draws a numbered badge beside each visible control, recomputed (throttled) on scroll, resize and page change, placed so it never covers the control's text, existing tokens with at least 4.5:1 contrast in both themes, no animation under reduced motion; `.vc-num` styles in `frontend/src/styles/app.css`
- [X] T028 [US2] Implement Click, Number, Position, Set and Choose in `frontend/src/voice/VoiceProvider.tsx` using `controls.ts` and `matcher.ts`: ambiguity shows numbers on the matches only and asks; a toggle is set to the stated state or reported as already in it; drop-down options and radios are chosen by name; list position uses the repeated items of the main list and also item names
- [X] T029 [P] [US2] Make sure repeated lists expose list semantics so positions work: add `role="list"` / `listitem` or table rows where cases, documents, users, verifications and history entries are rendered in `frontend/src/pages/Cases.tsx`, `ClientCases.tsx`, `pages/ask/KnowledgeTab.tsx`, `pages/ask/HistoryTab.tsx`, `AdminUsers.tsx`, `AdminCases.tsx`, `AdminVerifications.tsx`, `AdminMessages.tsx`

**Checkpoint**: US1 and US2 together let a person operate every screen's controls by voice.

## Phase 5: User Story 4 - Stay safe: confirmations and no guessing (Priority: P1)

**Goal**: risky actions never run on one phrase; unclear phrases never act.

**Independent test**: say every risky command; nothing happens until "confirm"; "cancel", silence and Escape stop it; mumbled and ambiguous phrases lead to a question.

- [X] T030 [P] [US4] Browser test `frontend/tests/e2e/voice-control-safety.spec.ts`: "log out" asks, "cancel" leaves you signed in, "confirm" signs out; timeout after 15 s; "open cases and delete the first" runs only "open cases"; "confirm" with nothing pending does nothing; an administrator's "remove document" on a private document names the owner and says it cannot be undone and is audited as today; a mumbled phrase and a low-confidence phrase do nothing; the confirm word in the same phrase does not confirm
- [X] T031 [P] [US4] Unit test `frontend/tests/unit/voice-risk-audit.test.tsx`: every control found on every main screen whose name contains a risk word in any pack either has `data-voice-risk` or is shown to be confirmed by the name check (lists any that rely only on the name check, so they can be tagged)
- [X] T032 [US4] Confirmation prompt in `frontend/src/components/VoiceConfirm.tsx` (`role="alertdialog"`, focus moved in, says what will happen, names the item and says "cannot be undone" for removals, "Confirm" and "Cancel" buttons, spoken aloud as well, 15 s expiry, Escape cancels) wired to `safety.ts` and the provider
- [X] T033 [US4] Add `data-voice-risk` to every risky control: log out in `frontend/src/pages/Settings.tsx`, deactivate in `frontend/src/components/DeactivateDialog.tsx` and `AdminUserDetail.tsx`, remove client in `ClientsOnCase.tsx`, delete or remove in `pages/ask/KnowledgeTab.tsx`, `pages/ask/TextAssistantTab.tsx` and the case, draft and hearing screens, resend and send in `AdminMessages.tsx` and any send action, verification accept and reject in `AdminVerifications.tsx`, administrator private-document actions; values `delete`, `logout`, `deactivate`, `send`, `verify`, `private-doc`
- [X] T034 [US4] Make the provider refuse to run any risky control except through the confirmation (no code path clicks it directly), and make the "ignored rest of the phrase" feedback say what was dropped; run T030 and T031 until they pass

**Checkpoint**: nothing risky or unclear can run by a single spoken phrase.

## Phase 6: User Story 3 - Dictate, read aloud, scroll (Priority: P2)

**Goal**: speak into text fields, hear answers read with citations and disclaimer, scroll and close dialogs by voice.

**Independent test**: on Ask say "dictate", speak a question, "stop dictating", "click ask", then "read the answer"; fill two form fields by voice; close a dialog by voice.

- [X] T035 [P] [US3] Unit tests in `frontend/tests/unit/voice-dictation.test.ts` (words land in the field through normal input events, commands said while dictating are typed as words, "stop dictating" ends it, password, one-time-code and `data-voice-no-dictate` fields are refused with "please type it", "clear field") and `frontend/tests/unit/voice-reader.test.ts` (reads the marked answer including sources and disclaimer, "stop", any key or the person speaking stops it at once, no voice for the language gives a plain message)
- [X] T036 [P] [US3] Browser test `frontend/tests/e2e/voice-control-dictate.spec.ts`: dictate and send a question on Ask; fill a form; "read the answer" (fake speech output records the answer, its sources and the disclaimer); "stop reading"; "scroll down", "scroll up", "top", "bottom", "next page"; "close dialog" and "cancel" close a dialog without change; the phone-code field cannot be dictated
- [X] T037 [US3] Dictation in `frontend/src/voice/dictation.ts` and the Dictate, Clear field and Stop dictating intents in the provider (text enters through the field's normal input events so the app reacts as if typed; same privacy rules as typed text)
- [X] T038 [US3] Reader in `frontend/src/voice/reader.ts` using the browser's speech output in the voice language, with the Read answer, Read screen and Stop reading intents; add `data-voice-read` to the answer container in `frontend/src/components/ChatMessage.tsx` and the answer areas in `frontend/src/pages/ask/AskTab.tsx`, `TextAssistantTab.tsx` and the client answer view, so citations and the disclaimer are read with it
- [X] T039 [P] [US3] Mark fields that must never be dictated with `data-voice-no-dictate` or the right `autocomplete` value: `frontend/src/components/PhoneCodeStep.tsx`, `frontend/src/components/PasswordInput.tsx`, the sign-up and reset code fields in `Register.tsx` and `ForgotPassword.tsx`
- [X] T040 [US3] Implement Scroll (up, down, top, bottom, next page), Close dialog and Cancel in the provider; the app stops speaking and listens when the person speaks

**Checkpoint**: questions can be asked and answers heard entirely by voice.

## Phase 7: User Story 5 - Control it, see it, and ask for help (Priority: P2)

**Goal**: opt-in with consent, a dashboard voice panel like the reference, continuous listening until stopped, help, language switching and the opt-in cloud path.

**Independent test**: turn it on by mouse, keyboard and voice; it keeps listening through many commands and screen changes until stopped; the panel and bar show state and last phrase; "what can I say" differs by screen; withdraw consent in Settings and everything stops.

- [X] T041 [P] [US5] Browser test `frontend/tests/e2e/voice-control-session.spec.ts`: first use shows the notice and nothing listens until "Agree and turn on"; after one tap it keeps listening through ten commands, silences and several `endTurn()` events and screen changes (a simulated 10 minutes) without another tap; "stop listening" and the button and the keyboard shortcut each stop it within a second and it does not restart; microphone denied and no browser support give plain messages and mouse and keyboard still work; "speak Tamil" changes the language; the tab hidden pauses it; withdrawing consent in Settings stops it
- [X] T042 [P] [US5] Browser test `frontend/tests/e2e/voice-control-panel.spec.ts`: the voice panel on the advocate dashboard, client dashboard and administrator overview shows the headline, instructions, status line and "I heard you say" card with the last phrase, result and suggestion; the compact bar elsewhere; light and dark themes; 360 px width; axe checks on panel, bar, notice, labels, help and confirmation; reduced motion removes the pulse and fade
- [X] T043 [P] [US5] Browser test `frontend/tests/e2e/voice-control-cloud.spec.ts` (fake microphone and a stubbed speech endpoint): the cloud option is offered only after consent; with it on and a language the browser cannot recognise, each detected phrase makes one short request to the speech endpoint, nothing is kept, a `429` pauses it with a plain message; without the option that language is not offered; no request is made while voice control is off
- [X] T044 [US5] Voice panel in `frontend/src/components/VoicePanel.tsx` per contracts/ui-contract.md (eyebrow, microphone tile, headline "Your voice is the remote", instructions, status line, "I heard you say" card with suggestion in the chosen language and the best-in-Chrome-or-Edge note, language choice, "What can I say?" link); show it in `frontend/src/pages/Dashboard.tsx`, `ClientDashboard.tsx` and `AdminOverview.tsx`; `.vc-panel` styles with existing tokens in `frontend/src/styles/app.css`
- [X] T045 [P] [US5] Help list in `frontend/src/components/VoiceHelp.tsx`: global commands plus the control names found on the current screen grouped as menu, tabs and buttons, in the chosen language, with a "Try saying" example per group; reachable by button and keyboard; the Help intent opens it
- [X] T046 [US5] Settings section "Voice control" in `frontend/src/pages/Settings.tsx`: agree or withdraw consent, the cloud option (disabled until consent, with its own sentence), language choice, link to help; saves at once and announces the change; withdrawing consent stops listening
- [X] T047 [US5] Keyboard shortcut for start and stop (documented in the help list and Settings, not clashing with the browser or screen readers), Pause and resume when the tab is hidden or the microphone is taken, and the "speak <language>" intent, in `frontend/src/voice/VoiceProvider.tsx` and `recognizer.ts`
- [X] T048 [US5] Cloud short-phrase path in `frontend/src/voice/cloudPhrases.ts` (only when the person opted in and the browser cannot handle the language): start recording on detected speech, end on silence or after about 8 seconds, send the phrase to the existing speech endpoint through `frontend/src/services/text.ts`, use the text, discard the audio at once, pause on `429`; hook it into the recogniser as the alternative engine and show "sent as short phrases, not stored" in the panel
- [X] T049 [US5] Make the existing question-bar microphone and voice control never listen at once: starting the existing button pauses command listening until it ends, and both share the language choice, in `frontend/src/hooks/useSpeechInput.ts` and `frontend/src/voice/recognizer.ts`

**Checkpoint**: a person can turn voice control on safely, see what is happening, and stop it any time.

## Phase 8: User Story 6 - New controls are covered automatically (Priority: P3)

**Goal**: the promise "everything is voice controlled" stays true as the app grows.

**Independent test**: add a labelled control and it works by name and number with no voice change; add an unlabelled one and the check fails and names it.

- [X] T050 [US6] Coverage test `frontend/tests/e2e/voice-coverage.spec.ts`: sign in as an advocate, a client and an administrator, visit every route, open every tab, menu and dialog it can reach, run the same control scan the app uses, and fail on any visible clickable control with no accessible name, on two controls with one name that cannot be told apart by position, and on any risk-word control that is neither tagged nor confirmed; print the screen and the control for each failure
- [X] T051 [US6] Run T050 and fix every finding in the screens: add `aria-label` to icon-only buttons, labels to unlabelled inputs, distinct names for repeated controls (for example "Open case, <title>"), in the components under `frontend/src/components/` and `frontend/src/pages/`, without changing what mouse and keyboard users see
- [X] T052 [P] [US6] Demonstration test in `frontend/tests/e2e/voice-coverage.spec.ts`: a sample labelled button added in a test page is reachable by name and by number with no voice-specific code, and a sample unlabelled button makes the coverage check fail and name it
- [X] T053 [US6] Document the markup rules (accessible names, `data-voice-risk`, `data-voice-read`, `data-voice-no-dictate`, list semantics) for people adding screens, in the README section "Voice control" and a short comment at the top of `frontend/src/voice/controls.ts`

**Checkpoint**: coverage is enforced by the build.

## Phase 9: Polish and cross-cutting

- [X] T054 [P] Privacy tests: assert no phrase or audio appears in the settings response, the audit log, the API log at the default level or the browser's local storage after a voice session (`backend/tests/contract/test_voice_settings.py`, `frontend/tests/e2e/voice-control-session.spec.ts`), and that nothing is sent while voice control is off
- [ ] T055 [P] Accuracy run: execute the phrase tables (T021) and a spoken-phrase check on real browsers for English, Hindi and Tamil; record accuracy on clear commands (target 95%), the unclear set (target: none acts), and recognition limits per browser in `specs/011-voice-control/results.md`; extend the packs from the failures
- [ ] T056 **(owner)** Have a native Hindi speaker and a native Tamil speaker review every phrase flagged `review: true` in `frontend/src/voice/lang/hi.ts` and `ta.ts` (including "stop listening" and the mixed forms) and record the decision in `specs/011-voice-control/results.md`
- [X] T057 [P] Keyboard, screen reader, both themes, 360 px and reduced-motion pass over the panel, bar, notice, labels, help and confirmation (constitution quality gate), recorded in `specs/011-voice-control/results.md`
- [X] T058 [P] README section "Voice control" in `README.md` (what it does, how to turn it on, languages and mixed phrases, privacy and the cloud option, browser support, the markup rules) and a note in the Privacy text of the app that describes the voice notice
- [X] T059 Full regression: backend `pytest`, frontend `eslint`, `tsc -b`, `vitest`, the whole Playwright suite on desktop and phone; fix anything the new bar, labels or aria-labels disturb in the existing tests (for example duplicate names in selectors); record the totals in `specs/011-voice-control/results.md`
- [ ] T060 Run `specs/011-voice-control/quickstart.md` end to end by hand on Chrome and Edge with a microphone, tick each step, and write what differed in `results.md`; re-check the constitution principles I to VI against the finished feature

## Dependencies and order

- **Phase 1** then **Phase 2** (blocks everything). Inside Phase 2, the backend group (T004 to T009) is independent of the frontend engine (T010 to T020) and the two can run in parallel; T018 needs T011 to T017, and T019 and T020 need T018.
- **US1** (Phase 3) needs Phase 2 only: this is the MVP.
- **US2** (Phase 4) needs Phase 2; it can run in parallel with US1 but shares `VoiceProvider.tsx`, so edit it one story at a time.
- **US4** (Phase 5) needs Phase 2 and should land before the feature is shown to anyone: US1 and US2 already refuse risky controls (T016, T018) but the prompt and tagging come here.
- **US3** needs Phase 2 and US2's controls; **US5** needs Phase 2, and T044 to T046 can start once T018 and T020 exist; **US6** needs the screens to be named (US1, US2) and runs last before polish.
- **Polish** needs all stories.

## Parallel examples

- Phase 2: T004, T005 (tests) together; then T011, T012, T013 together while T006 to T009 run on the backend.
- US1: T021 and T022 together, then T023 and T024.
- US2: T025, T026, T029 together, then T027 and T028.
- US5: T041, T042, T043 together; T045 beside T044.

## Implementation strategy

1. **MVP** (Phases 1 to 3): consent, continuous listening, bar, and navigation by name for all roles and the three languages. Stop and try it.
2. **Add clicking and safety** (Phases 4 and 5) before anyone relies on it: numbers, positions, toggles, and the confirmation prompt with every risky control tagged.
3. **Add dictation and reading** (Phase 6), then **the panel, help, Settings and the cloud option** (Phase 7).
4. **Lock in coverage** (Phase 8), then polish, measure accuracy, get the native-speaker review, and run the quickstart.
5. Each phase ends with a checkpoint that can be shown on its own.
