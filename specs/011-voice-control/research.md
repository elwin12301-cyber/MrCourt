# Research: Voice Control for the Whole App

Decisions that shape the plan. No open questions remain.

## D1. Find controls by scanning the live page, not by a list of screens

**Decision**: At any moment the app scans the page for visible, enabled, clickable elements (links, buttons, tabs, switches, check boxes, radios, select options, menu items, list rows that act as links or buttons) and takes each one's **accessible name** (its label, `aria-label`, text, title or image text). Commands are matched against this live list. When a modal dialog is open, only controls inside it count.

**Rationale**: This covers every screen and all three roles at once; a client never "sees" the administrator links, so permissions are respected for free (FR-005). New controls are covered automatically as long as they have an accessible name, which the app needs anyway for screen readers (FR-022). It also keeps the code small (principle VI).

**Alternatives considered**:
- A hand-written command table per screen: precise, but it would drift and miss new controls, which is what the request forbids.
- Registering controls through a special React wrapper: needs every control rewritten and still misses third-party markup.
- An AI model reading the page: slower, costs money, sends page content out, and can guess wrongly (violates "never act on unclear commands").

## D2. Deterministic phrase matching, no AI model

**Decision**: A phrase is normalised (lower case, Unicode normalised, punctuation and filler removed), split into an **action part** (verbs and postpositions from the language packs) and a **target part** (what to act on). The target is matched to control names in three steps: exact, then all-words-present, then a small edit-distance match for longer words. The result is one of: exactly one match with enough confidence, several matches (ask, show numbers), or none (say what was heard, offer the closest).

**Rationale**: Predictable, testable with tables of phrases, fast (well under the 1.5 s target), private, and it can be told to refuse. Confidence and "never guess" rules (FR-009, FR-018) are easy to state and test this way.

**Alternatives considered**: Intent classification by a language model (rejected as above); a general fuzzy search library (adds a dependency and tends to guess).

## D3. Language packs that are all active at once, so mixed phrases work

**Decision**: Each language has a pack (`lang/en.ts`, `hi.ts`, `ta.ts`) listing: action words ("go to", "open", "click", "press", "turn on", "turn off", "scroll", "back", "stop listening", "what can I say"…), the **words that follow or surround a target** ("ku po", "chella", "kholo", "par jao", "ko", "seyyu"), the names of screens and common controls in that language, and the help text. Matching removes the action words and surrounding words of **all** packs together, whichever voice language is chosen, then matches the target against names in English **and** the chosen language. Romanised forms (as the recogniser often writes them for mixed speech, for example "dashboard ku po") are listed beside the native-script forms.

**Rationale**: People mix languages ("dashboard ku po", "chella to dashboard", "settings kholo"), and the recogniser usually writes the English word in Latin letters and the rest in the chosen language's script or in Latin letters. Treating all packs as one vocabulary makes this work without guessing which language each word is in. A new language is one new file (FR-003b).

**Alternatives considered**: Switching grammar by the chosen language only (fails on mixed speech); translating the whole phrase to English first (needs a translation service, adds delay and sends text out).

**Risk and mitigation**: The recogniser can mis-hear Tamil or Hindi words. The packs include common variants and romanisations; a phrase that matches nothing is never acted on; the number mode is the fallback. Accuracy is measured with a table of at least 50 phrases per language (SC-003) and the pack is extended from what that table shows.

## D4. The browser's own recognition by default; the cloud service is an opt-in fallback for short phrases

**Decision**: Use the browser's recognition in continuous mode, restarting it whenever the browser ends a turn while the person still wants to listen (browsers end turns after silence or about a minute). If the browser reports that the chosen language is not supported, and only if the person opted in to the cloud service in Settings, the app records **short phrases** (starting on detected speech, ending on silence, at most about 8 seconds), sends each to the existing speech endpoint, uses the text, and discards the audio at once. Without the opt-in, that language is not offered.

**Rationale**: Matches the clarification: MrCourt never receives audio by default; the cloud path never streams. Note: Chrome's and Edge's built-in recognition is run by the browser's maker, so the notice does not claim that audio stays on the device. The speech endpoint, its language list and its "no storage" rule exist already (feature: voice questions).

**Alternatives considered**: Streaming everything to the cloud (rejected: privacy and cost); a wake word (rejected by the product owner); a recogniser running in the browser itself such as a downloadable model (large download, extra dependency, not needed for the launch languages).

**Risks and mitigations**: (1) Browser recognition is Chrome and Edge only in practice, so the panel states this. (2) The speech endpoint allows 20 turns per minute per person; phrase capture only sends detected speech, and a person rarely speaks more than that; if the limit is reached the app says so and pauses the cloud path rather than failing silently. (3) Phrase detection uses the microphone level; it needs tuning, covered by the e2e fake and a manual check in the quickstart.

## D5. Safety: classify risk by tag and by words, confirm by voice, never combine

**Decision**: A control is **risky** if it carries `data-voice-risk` (set on delete, remove, log out, deactivate, send, resend, verification accept and reject, and administrator private-document actions), or, as a safety net for any untagged control, if its name contains a risky word in any pack (delete, remove, log out, sign out, deactivate, send, resend, approve, reject, and their Hindi and Tamil forms). Risky means: say what will happen, wait up to 15 s for "confirm" (or "yes, confirm"), cancel on "cancel", silence, any other command, or the Escape key. One action per phrase; only the first command of a multi-command phrase runs, and never a risky one. A confirmation word is accepted only from the **next** recognition result after the prompt, so a word already in the same phrase cannot confirm.

**Rationale**: Misheard speech must not delete or send anything (SC-004). Using both a tag and words means a forgotten tag fails safe. A test lists every control whose name matches risky words and checks it is tagged or confirmed.

**Alternatives considered**: Confirming every action (too slow, rejected by the product owner); confirming only tagged controls (a forgotten tag would be unsafe).

## D6. Number labels and list positions are computed from the scan

**Decision**: "Show numbers" draws a small numbered badge beside each visible control from an overlay layer that ignores the pointer and is hidden from screen readers; numbering follows reading order and is recomputed (throttled) when the page scrolls, resizes or changes. "Click 7" refers to the numbering **last shown**; if control 7 has gone, nothing happens and the app says so. List position commands ("first", "second", "last") apply to the repeated items of the main list on screen (rows with the same structure) and also work by item name.

**Rationale**: Numbers are the universal fallback for controls with no good name or with duplicate names (FR-007, FR-009). A pointer-less overlay never blocks clicks and needs no change to screens.

**Alternatives considered**: Putting number attributes into every component (invasive); highlighting by colour only (not accessible).

## D7. Dictation and reading aloud use what the browser provides

**Decision**: Dictation fills the focused text field through the field's normal input events so the app reacts as if typed (the question box, search, forms), refuses password fields, one-time-code fields and anything marked `data-voice-no-dictate`, and treats commands said in dictation as words until "stop dictating". Reading uses the browser's speech output on the text of the answer (`data-voice-read`) or of the main area, in the voice language, with its citations and disclaimer, and stops on "stop", any key or the person speaking. If the browser has no voice for the language, the app says so and leaves the text on screen.

**Rationale**: No new dependency, nothing sent out, and the app's normal text rules (privacy of questions, drafts) apply to dictated text (FR-033).

**Alternatives considered**: Server-side text to speech (cost, sends case text out, rejected).

## D8. Where voice settings are kept

**Decision**: Three columns on `user_settings`: `voice_consent_at` (when the person agreed to the microphone and notice, null if not), `voice_cloud_opt_in` (boolean), `voice_language` (recognition language code, null for the app default). Consent changes and cloud changes are audited as `voice.consent.on/off` and `voice.cloud.on/off` with no content. Whether voice control is **on** is not stored: it starts off every time, and a browser page load needs a fresh tap anyway because the microphone cannot start by itself.

**Rationale**: DPDP calls for a record of consent and a way to withdraw it (principle III); a per-person setting follows the person across devices, like the theme. Nothing about what was said is kept.

**Alternatives considered**: Browser storage only (no record of consent, not shared across devices); remembering "on" across visits (the person asked for opt-in and an easy off switch; starting on by itself would also be blocked by the browser).

**Before sign-in**: the login and welcome screens are part of "the whole app". There, the consent and language live only in the browser and are copied to the person's settings the first time they sign in, if they agree.

## D9. How coverage is proven and kept

**Decision**: A browser test signs in as an advocate, a client and an administrator, visits every route, opens each tab, menu and dialog it can, and uses the same control scan as the app. It fails when a visible clickable control has no accessible name, when two controls on one screen share a name and cannot be told apart by position, or when a control whose name matches a risky word has no confirmation. A second test drives a fake recogniser through "go to" for every menu item and tab, in each language and in the mixed style.

**Rationale**: This is what makes "everything is voice controlled" stay true over time (SC-008, FR-022).

## D10. Fit with the existing voice question feature

**Decision**: Keep the existing microphone button in the question bar. In dictation mode, the voice control uses the same recognition helpers and language list (exported from the existing hook), and the language the person chooses is shared. While voice control is on, the existing button still works and does not conflict: starting it pauses command listening until it ends, so the two never listen at once.

**Rationale**: Avoids two microphones and two language settings; keeps the current behaviour for people who do not use voice control.

## Not changed

- The WhatsApp channel and its voice notes (feature 010).
- The ranking, answers and drafts logic.
- Permissions, audit rules and rate limits: a spoken click calls the same code as a mouse click.
