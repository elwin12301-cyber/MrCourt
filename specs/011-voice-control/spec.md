# Feature Specification: Voice Control for the Whole App

**Feature Branch**: `011-voice-control` (work stays on `main`; the directory name is the identifier)

**Created**: 2026-10-26

**Status**: Draft

**Input**: User description: "Voice control for the entire MrCourt web application. A person can operate the whole app by speaking, hands-free. Examples: 'go to dashboard', 'open cases', 'open Ask MrCourt', 'go to settings', 'log out'. Every menu, sub-menu, tab and clickable control must be reachable by voice: by its visible name, by a number shown next to each clickable item, or by position in a list. Also scroll, go back, close dialog, read the screen or the current answer aloud, dictate into text fields, and 'what can I say' help. English, Hindi and Tamil. Opt-in, easy to switch off, clear listening indicator and what was heard, confirmation before risky actions, never act on unclear commands, DPDP-respecting. Works for advocates, clients and administrators, desktop and mobile, existing design system and accessibility rules. New controls become voice-controllable automatically."

## Roles served

Advocate, Client (petitioner) and Administrator. The same spoken commands work for all three; what each person can reach is exactly what they can already reach with a mouse or keyboard. Voice control never gives access to anything a person cannot already open.

## Clarifications

### Session 2026-10-26

- Amendment (found while building, same day): the first draft said recognition "happens on the device" and "nothing leaves the device". That is not true of Chrome's and Edge's built-in recognition, which the browser's maker may process. The wording now says what is true: MrCourt never receives the audio, and the notice names the browser's own speech service.

- Q: How should the microphone start listening once voice control is switched on? → A: Continuously, hands-free, until the person stops it (tapping the microphone, the keyboard shortcut or saying "stop listening"). No wake word and no push-to-talk. A voice panel like the supplied reference image shows the state and what was heard.
- Q: Which languages must commands work in? → A (product owner, free text): as many languages as possible, including everyday mixed speech where an Indian-language phrase is combined with English screen names, for example "dashboard ku po" or "chella to dashboard" (Tamil with English) and the same style in Hindi ("dashboard par jao"). Decision: launch with English, Hindi and Tamil, each also accepting mixed phrases with English names; other languages are added by supplying their phrase lists, with no change to the rest of the app. A phrase that cannot be matched is never acted on.
- Q: May the always-on microphone send speech to the cloud speech service? → A: The browser's own speech recognition is the default, and MrCourt never receives the audio. Where the browser cannot handle the chosen language, the person may opt in, after a plain notice, to the cloud speech service, which then receives short spoken phrases only (never a continuous stream), with nothing stored. Cloud use is a separate, withdrawable choice in Settings.
- Q: Which actions should always need a spoken "confirm"? → A: Deletes and removals, log out, deactivate account, sending or resending a message, accepting or rejecting a verification, and administrator actions on private documents. Saving, toggles, form submits, navigation and filters run without confirmation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Move around the app by saying where to go (Priority: P1)

A person turns voice control on once, then says "go to dashboard", "open cases", "open Ask MrCourt", "go to settings" or "go back". Every item in the main menu and in each sub-menu or tab (for example the Ask MrCourt tabs, the Settings sections, the administrator console pages) opens when its name is spoken.

**Why this priority**: Moving between screens is the base of hands-free use. With only this, a person who cannot use a mouse can already reach every screen. It is the smallest slice that delivers the core promise.

**Independent Test**: With voice control on, an advocate says each menu name in turn, then each tab name on the Ask page. Each time the matching screen or tab opens. Repeat as a client and as an administrator with the menus each of them has.

**Acceptance Scenarios**:

1. **Given** voice control is on and the person is anywhere in the app, **When** they say "go to dashboard", **Then** the dashboard opens and the app confirms what it did ("Opened Dashboard").
2. **Given** the Ask MrCourt page is open, **When** the person says "open the history tab", **Then** the History tab is selected.
3. **Given** a client is signed in, **When** they say "open admin console", **Then** nothing opens and the app says that this is not available to them.
4. **Given** the person says "go back", **When** there is a previous screen, **Then** the app returns to it.
5. **Given** the person says the name of a screen in Hindi or Tamil (for example the equivalent of "settings"), **When** their voice language is set to that language, **Then** the Settings screen opens.

---

### User Story 2 - Click anything by name, number or position (Priority: P1)

On any screen the person can press any clickable control by speaking its visible name ("click save", "turn on hearing reminders"), by the small number shown next to every clickable item ("click 7"), or by position in a list ("open the first case", "open the third document"). They can ask "show numbers" to display the numbers, and "hide numbers" to remove them.

**Why this priority**: The request is that all clickable things are voice controlled, not only the menus. Names cover the common controls, and numbers cover everything else, including controls with no clear name or with the same name repeated. Without this the feature is only navigation.

**Independent Test**: On each main screen, say "show numbers", then pick several different controls by number, by name and by list position (buttons, links, toggles, tabs, filters, list items, form buttons). Each one acts as if it had been clicked.

**Acceptance Scenarios**:

1. **Given** a screen with a Save button, **When** the person says "click save", **Then** the button acts as if clicked.
2. **Given** two controls have the same name on the screen, **When** the person says that name, **Then** the app does not guess: it shows numbers on the matching controls and asks which one.
3. **Given** numbers are shown, **When** the person says "click 7", **Then** control number 7 acts, and the numbers stay in step with what is on screen if the screen changes.
4. **Given** a list of cases, **When** the person says "open the first case", **Then** the first case opens.
5. **Given** a toggle for hearing reminders that is off, **When** the person says "turn on hearing reminders", **Then** it becomes on; **When** it is already on and they say the same, **Then** the app says it is already on and changes nothing.
6. **Given** a control that is disabled or hidden, **When** the person names it, **Then** the app says it is not available now and does nothing.

---

### User Story 3 - Dictate into text fields and control reading (Priority: P2)

The person says "click question box" or "dictate", then speaks a question, a search phrase, a draft paragraph or a form value; the words appear in the field. They can say "stop dictating", "clear field", "read the answer" or "read the screen", and the app speaks it back. They can say "scroll down", "scroll up", "top", "bottom", "close dialog" and "cancel".

**Why this priority**: These make the app usable beyond clicking: asking questions and filling forms by voice. They matter, but a person can already use the existing voice question button, so this follows navigation and clicking.

**Independent Test**: Open Ask MrCourt, say "dictate" and speak a question, then say "stop dictating" and "click ask". The question is asked and the answer can be read aloud. Open a form and fill two fields by voice. Open a dialog and close it by voice.

**Acceptance Scenarios**:

1. **Given** a text field has focus, **When** the person says "dictate" and speaks, **Then** their words are placed in the field, and commands such as "go to dashboard" said during dictation are typed as words, not run, until the person says "stop dictating".
2. **Given** an answer with sources is on screen, **When** the person says "read the answer", **Then** the answer is spoken, including its citations and disclaimer, and "stop" ends the speech at once.
3. **Given** a long page, **When** the person says "scroll down", **Then** the page moves down by about one screen.
4. **Given** a dialog is open, **When** the person says "close dialog", **Then** it closes without making any change.
5. **Given** a password field, **When** dictation is requested, **Then** the app declines and asks the person to type it.

---

### User Story 4 - Stay safe: confirmations and no guessing (Priority: P1)

Risky actions never run on a single spoken command. Before any delete, remove, log out, send, resend, deactivate-account, or any administrator action on a private document, the app says what it is about to do and waits for "yes, confirm" or "cancel". Unclear or low-confidence commands are never acted on; the app says what it heard and asks the person to repeat or to choose.

**Why this priority**: Speech is often misheard and a wrong deletion cannot be undone. This is required before the feature can be released, so it ranks with the P1 stories.

**Independent Test**: Say each risky command; confirm that nothing happens until a spoken confirmation, that "cancel" and silence both stop it, and that a mumbled or ambiguous phrase leads to a question, not an action.

**Acceptance Scenarios**:

1. **Given** the person says "log out", **When** the command is understood, **Then** the app asks "Log out of MrCourt? Say yes, confirm or cancel" and logs out only after confirmation.
2. **Given** a confirmation is pending, **When** the person stays silent for 15 seconds or says "cancel", **Then** nothing happens and the app says it was cancelled.
3. **Given** the speech is unclear, **When** the app cannot match it to exactly one command, **Then** it shows and says what it heard and offers the closest options, without acting.
4. **Given** an administrator says "remove document", **When** the document is private, **Then** the confirmation names the document's owner and states that the removal cannot be undone, and the action is recorded in the audit log as it is today.
5. **Given** the confirmation word is spoken by background noise or by another voice, **When** it was not clearly "confirm", **Then** the action does not run.

---

### User Story 5 - Control it, see it, and ask for help (Priority: P2)

Voice control is off by default. A person turns it on from a visible control (and from Settings), consents to the microphone and to the speech service, chooses a language, and can turn it off at any time by button, keyboard or by saying "stop listening". A clear indicator always shows when the microphone is listening and the last words heard. Saying "what can I say" lists the commands that work on the current screen.

**Why this priority**: Consent, visibility and help make the feature trustworthy and learnable, but they build on stories 1 to 4.

**Independent Test**: Turn voice control on and off by mouse, by keyboard and by voice; confirm that after one tap it keeps listening through several commands and screen changes until stopped; confirm the voice panel and the compact indicator are visible and announced to screen readers; ask "what can I say" on three different screens and see screen-specific lists.

**Acceptance Scenarios**:

1. **Given** voice control has never been used, **When** the person opens the voice control switch, **Then** they see a plain explanation (what is listened to, that no audio is kept, which service hears it) and must agree before the microphone starts.
2. **Given** voice control is on, **When** the microphone is listening, **Then** a persistent indicator says so and shows the last phrase heard, and a screen reader announces state changes politely; the dashboard shows the voice panel with "Listening…" and the "I heard you say" box.
2a. **Given** the person tapped the microphone once, **When** they speak several commands over several minutes, with pauses between them and across screen changes, **Then** every command is heard without tapping again, until they say "stop listening" or tap the microphone, after which the status reads "Microphone is off".
3. **Given** voice control is on, **When** the person says "stop listening" or presses the switch or its keyboard shortcut, **Then** the microphone stops and the indicator disappears.
4. **Given** the person says "what can I say", **When** they are on the Cases page, **Then** the help shows commands for that page plus the global ones, in their chosen language.
5. **Given** the microphone is blocked or the browser has no speech input, **When** the person tries to turn voice control on, **Then** the app explains why and that mouse and keyboard still work.

---

### User Story 6 - New controls are covered automatically (Priority: P3)

When the team adds a new screen, menu item, tab or button, it is voice-controllable without a separate voice change, as long as it follows the app's normal component and labelling rules. A check in the test suite fails if any visible clickable control on a main screen cannot be reached by voice.

**Why this priority**: It protects the promise "everything is voice controlled" over time but delivers no new user capability by itself.

**Independent Test**: Add a sample new button to a screen using the standard components; it can be chosen by name and by number without extra work. Add one with no label; the automated check fails and names it.

**Acceptance Scenarios**:

1. **Given** a new labelled button is added to any screen, **When** voice control is on, **Then** "click" plus its label acts on it, and it gets a number.
2. **Given** a control has no accessible name, **When** the automated coverage check runs, **Then** it fails and lists that control and its screen.

---

### Edge Cases

- A person speaks while the app is itself speaking (reading an answer): the app stops speaking and listens.
- Two commands in one phrase ("open cases and delete the first"): only the first safe command is run, never a risky one; the rest is ignored and said back.
- Text on screen that looks like a command (a case titled "log out"): "click log out" with two matches asks which one; risky matches still ask for confirmation.
- A screen changes while a number is being spoken: the number refers to what was on screen when numbers were last shown; if it has gone, the app says so and does nothing.
- Very long lists: numbers apply to what is visible, and "next page" / "scroll" reveal more; position commands support "the last one".
- Noisy places, accents and mixing of English with Hindi or Tamil: mixed phrases ("dashboard ku po") are expected and understood; low-confidence matches ask again; the person can switch language by voice ("speak Tamil") or in Settings.
- The same screen name said differently by different people ("settings", "setting", "settings page", or the local word): common variants must work; unknown variants never trigger a guess.
- A language whose speech the recognition cannot understand well on the person's device: the app says so and does not pretend to listen; mouse and keyboard still work.
- Names of Acts, sections and case numbers spoken aloud ("section 138 N I Act") are dictated as words into the field and are never treated as commands.
- The session expires or the app is offline during a command: the app says so; no half-done action is left.
- Two tabs open: only the active tab listens.
- Phone call or other app takes the microphone: voice control pauses, shows that it is paused, and offers to resume.
- A person with a speech difference or no speech at all: voice control is optional; every function still works by keyboard and mouse (nothing becomes voice-only).
- Reduced-motion setting: indicator and number labels appear without animation.
- Number labels must not cover or hide the control they refer to, in light and dark themes and on a narrow screen.

## Requirements *(mandatory)*

### Functional Requirements

**Control and consent**

- **FR-001**: Voice control MUST be off by default and MUST start only after the person turns it on and agrees to the microphone and speech-service notice (FR-030). It MUST be possible to turn it on and off from a visible control on every screen, from Settings, by keyboard, and (off only) by voice.
- **FR-002**: While the microphone is listening, the app MUST show a persistent indicator and the last phrase heard, and MUST expose the state to screen readers. When not listening, no audio is captured and the indicator says the microphone is off.
- **FR-002a**: Once started, listening MUST continue without any further tap until the person stops it (microphone button, keyboard shortcut or "stop listening"), including across screens and after short silences or the browser ending a recognition turn. It MUST NOT need a wake word. It MUST stop when the person signs out, closes the tab, or leaves the app, and MUST NOT restart by itself after being stopped.
- **FR-002b**: A **voice panel** MUST be shown on the dashboard of every role, in the style of the supplied reference image: a large microphone button, a headline ("Your voice is the remote"), one line of plain instructions (tap the microphone, keep the tab open, allow the microphone when asked), a status line ("Microphone is off" / "Listening…" / "Paused"), and an "I heard you say" box showing the last phrase heard, the result ("Opened Dashboard", a question, or "not understood"), and a suggestion such as "Try 'Go to dashboard'". The box MUST also state where recognition works best (for example, Chrome or Edge over a secure connection or localhost). On every other screen a compact version (microphone button, status and last phrase) MUST stay visible while voice control is on.
- **FR-002c**: The voice panel MUST use the existing design tokens and fonts and work in the light and dark themes; the reference image is a dark-theme example of the layout, not a new palette.
- **FR-003**: The person MUST be able to choose the voice language (English, Hindi, Tamil at launch) in the same way as the existing voice question feature, and the choice MUST be remembered per person.
- **FR-003a**: Commands MUST also be understood when spoken in everyday mixed speech: an Indian-language action word or phrase combined with the English name of a screen or control (for example "dashboard ku po", "chella to dashboard", "settings kholo", "dashboard par jao"), in each supported language, whichever voice language is chosen. The same screen or control names MUST work in English, in the person's language, and mixed.
- **FR-003b**: Adding another language MUST need only a new list of command phrases and screen names for that language (and a recognition language), with no change to screens or controls. Until a language has its list, it MUST NOT be offered, and phrases that match nothing MUST NOT cause any action (FR-018).

**Navigation**

- **FR-004**: Every item in the main menu, every sub-menu, tab and section of every screen, for all three roles, MUST be openable by speaking its visible name, in each supported language.
- **FR-005**: "Go back", "go forward", "go home" (dashboard) and "refresh" MUST work. A person MUST NOT be able to reach a screen by voice that they cannot reach by mouse (for example, a client cannot open the administrator console).

**Clicking and choosing**

- **FR-006**: Every visible clickable control (buttons, links, tabs, toggles, check boxes, radio buttons, drop-downs and their options, filters, list items, dialog buttons, menu items) MUST be activatable by voice by its visible or accessible name.
- **FR-007**: The app MUST be able to show a number beside every visible clickable control ("show numbers") and MUST activate the control when the number is spoken ("click 7"). Numbers MUST be removable ("hide numbers") and MUST stay correct as the screen changes.
- **FR-008**: Controls in lists MUST be reachable by position ("first", "second", … "last") and by the name of the item.
- **FR-009**: When a spoken name matches more than one control, the app MUST NOT choose; it MUST show numbers on the matches and ask which one.
- **FR-010**: For toggles and check boxes, "turn on/off" and "check/uncheck" MUST set the stated state, and MUST say so when it is already in that state.
- **FR-011**: Disabled or hidden controls MUST NOT be activated; the app MUST say they are not available.

**Text, reading and screen movement**

- **FR-012**: The person MUST be able to dictate into any text field (questions, search, drafts, forms) and stop dictating by voice. Words said during dictation MUST NOT be run as commands. Password fields and one-time-code fields MUST NOT be dictated.
- **FR-013**: The person MUST be able to say "scroll up/down", "top", "bottom", "next page" where a list is paged, and "close dialog" / "cancel".
- **FR-014**: "Read the answer", "read the screen" and "read this section" MUST speak the content aloud in the voice language, including source citations and the informational-only disclaimer for any legal answer, and MUST be stoppable at once by "stop", by any key, or by the person speaking.
- **FR-015**: "What can I say" MUST list the commands that work on the current screen and the global ones, in the voice language, and the list MUST be reachable without voice too.

**Safety**

- **FR-016**: Risky actions MUST require an explicit spoken confirmation, and cancel by "cancel" or by 15 seconds of silence. Risky actions are at least: delete or remove anything, log out, deactivate account, send or resend a message, any administrator action on a private document (see, search, correct, map again, remove), accepting or rejecting a verification, and anything that cannot be undone. Saving, toggles, form submits, navigation, filters and scrolling MUST run without a confirmation.
- **FR-017**: The confirmation prompt MUST state what will happen, and for removals MUST name the item and say it cannot be undone.
- **FR-018**: The app MUST NOT act on a command it cannot match to exactly one action with enough confidence; it MUST show and say what it heard and offer the closest options.
- **FR-019**: Only one action MUST be run per spoken phrase; a phrase with several commands MUST run only the first if safe, and never a risky one.
- **FR-020**: Voice control MUST NOT bypass any existing rule: permissions, rate limits, confirmations and audit entries apply exactly as for a mouse click. An action done by voice MUST be recorded in the audit log like any other, with no audio or transcript.
- **FR-021**: AI drafts and legal answers MUST keep their "review before use" flag and informational-only disclaimer when read aloud or acted on by voice. Voice control MUST NOT send, file or export a document without the existing confirmation.

**Coverage and quality**

- **FR-022**: The app MUST make a new screen, menu, tab or control voice-controllable automatically when it follows the app's standard components and labelling, and an automated check MUST fail the build when a visible clickable control on a main screen has no accessible name or cannot be reached by voice.
- **FR-023**: Voice control MUST work on desktop and mobile layouts, in light and dark themes, with number labels and the indicator meeting the app's contrast and focus rules, never hiding the control they label, and respecting reduced motion.
- **FR-024**: Mouse and keyboard operation MUST remain complete and unchanged; no function may become voice-only.
- **FR-025**: When the microphone is denied or unavailable, or the browser cannot do speech input, the app MUST say so plainly and continue to work by mouse and keyboard.

**Privacy**

- **FR-030**: Before first use the person MUST see a plain-language notice stating what is listened to, that MrCourt does not receive or store audio, who does the listening (the browser's own speech service, which in Chrome and Edge may be run by the browser's maker under its own terms) and what is sent to MrCourt's speech service if the cloud option is chosen, and MUST agree. The agreement MUST be withdrawable in Settings.
- **FR-031**: Audio MUST NOT be stored by the app. Transcripts of commands MUST NOT be kept after the command is handled or sent to logs or analytics. The audit log MUST record only the action taken, as it does for a click.
- **FR-032**: Recognition MUST be done by the browser's own speech recognition by default, and MrCourt MUST NOT receive the audio (the browser's maker may process it, and the notice says so). Where the browser cannot handle the chosen language, the person MAY opt in, as a separate choice withdrawable in Settings and after a notice that says what is sent and to which service, to the cloud speech service. It MUST then receive only short spoken phrases, never a continuous stream, and MUST NOT keep them. Nothing is sent while voice control is off. Without that opt-in, a language the browser cannot handle MUST NOT be offered for voice control.
- **FR-033**: Spoken text dictated into case or question fields MUST follow the same rules as typed text (for example, the same privacy rules for questions and drafts).

### Key Entities *(include if feature involves data)*

- **Voice setting (per person)**: Whether voice control is on, the chosen language, whether the person has agreed to the microphone and speech-service notice, and when. Kept with the person's other settings; deleted with their account.
- **Command**: A spoken phrase understood as one action, such as "go to a screen", "click a control", "set a switch", "scroll", "dictate", "read" or "help". It exists only while being handled and is not stored.
- **Control (as heard by the app)**: Anything clickable on the screen, with its visible or accessible name, its type, whether it is on screen and enabled, its position in a list and its temporary number.
- **Pending confirmation**: A risky action waiting for "confirm" or "cancel", with what it will do and when it expires. Exists for seconds and is not stored.
- **Audit entry (existing)**: Actions done by voice are recorded like any other action, without audio or transcript.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A person can reach every main-menu screen and every tab, sub-menu and section for their role by voice alone, with a 100% success rate in the test checklist, in each of English, Hindi and Tamil, and in the mixed style ("dashboard ku po") for each.
- **SC-002**: On every main screen, 100% of visible clickable controls can be activated by number, and at least 95% can also be activated by their spoken name on the first try in a quiet room in English.
- **SC-003**: In a test of 50 mixed commands per language, at least 95% of clear commands are carried out correctly, and none of the unclear ones (at least 20 mumbled, partial or ambiguous phrases) causes an action.
- **SC-004**: No risky action (delete, remove, log out, deactivate, send, resend, private-document action) ever runs without a spoken confirmation; verified for every risky action in the app, including with a wrong, late or missing confirmation.
- **SC-005**: A new person turns voice control on, agrees to the notice, opens their cases and opens one case, all by voice, in under 2 minutes without help in at least 8 of 10 trials.
- **SC-006**: Turning voice control off stops the microphone within 1 second, and no audio or transcript of commands is stored or logged, verified in tests. After one tap, listening continues for at least 10 minutes of normal use (with pauses and screen changes) without the person tapping again, and never restarts after being stopped.
- **SC-007**: The listening indicator, number labels, help list and confirmation prompts pass the app's accessibility checks on desktop and phone in both themes, and every function still works by keyboard alone.
- **SC-008**: An automated check covers every main screen for all three roles and fails when a clickable control cannot be reached by voice; adding a standard labelled control needs no voice-specific change.
- **SC-009**: A spoken command shows its result (or a question) within 1.5 seconds of the end of speech in at least 90% of cases for browser recognition.

## Assumptions

- Voice control is a mode the person switches on, listening continuously until they stop it (hands-free) with a clear indicator; it does not use a wake word, and there is no push-to-talk mode (decided in clarification, 2026-10-26).
- The existing voice question feature (browser speech recognition, and the speech service for Tamil and other Indian languages) is reused for recognition. English, Hindi and Tamil are the launch languages, as today, each with mixed-with-English phrases; further languages are added later by command lists (FR-003b) and are not part of the first release.
- Commands are understood from a fixed, documented set of phrases per language, matched to the labels on screen. Open-ended spoken requests to an AI ("find me a case about…") are out of scope for this feature; the existing Ask MrCourt question flow covers questions once dictated.
- Voice control is for the web application, on desktop and phone browsers. The WhatsApp channel (feature 010) already has its own text and voice-note handling and is not changed.
- Voice control does not replace keyboard or mouse use and gives no access beyond a person's existing permissions.
- Spoken phrases are recognised by the browser's own speech recognition (MrCourt never receives that audio; in Chrome and Edge the browser's maker's service may process it, which the notice states); where MrCourt's speech service is used, the audio is sent for that single phrase only, not stored, and only after the person has chosen it and agreed to the notice.
- Number labels and the help list are described in the existing design tokens; no new colour palette or fonts are introduced.
- Measured accuracy targets assume a quiet room and a typical laptop or phone microphone; noisy conditions are handled by asking again, not by guessing.
- Reading answers aloud uses the browser's built-in speech output, whose voice and language availability depend on the device; where a language voice is missing, the app says so and offers to show the text.
- Principle check against the constitution: grounded answers (I) and the informational-only flag (II) are kept when reading aloud; privacy by design (III) is met by opt-in, consent, no stored audio and no transcripts in logs; accessibility (IV) by keeping keyboard operation complete and adding screen-reader announcements; design system (V) by reusing tokens; simplicity (VI) by a fixed command set and reuse of the existing recognition.
