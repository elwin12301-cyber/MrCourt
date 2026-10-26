# Contract: Commands and matching

What a person can say, how it is understood, and when the app refuses to act. Phrases below are English examples; each language pack lists its own words and romanised forms, and **all packs are active together** so mixed phrases work.

## Intents

| Intent | Examples (English) | Examples (mixed) | Acts on |
|---|---|---|---|
| Go | "go to dashboard", "open cases", "open Ask MrCourt" | "dashboard ku po", "chella to dashboard", "settings kholo", "dashboard par jao" | A navigation control (menu item, tab, link) matching the name |
| Click | "click save", "press add case", "open the history tab" | "save click pannu", "save dabao" | Any control matching the name |
| By number | "click 7", "seven" (when numbers are shown) | "7 click pannu" | The control with that number from the last display |
| By position | "open the first case", "click the third document", "the last one" | "first case open pannu" | The n-th repeated item in the main list |
| Set | "turn on hearing reminders", "turn off dark mode", "check remember me" | "reminders on pannu" | A switch, check box or radio; says so if already in that state |
| Choose | "select Tamil", "choose Madras High Court" | | A drop-down option or radio |
| Scroll | "scroll down", "scroll up", "top", "bottom", "next page" | | The page, a list, or its next page |
| History | "go back", "go forward", "refresh", "go home" | "back po" | Browser history, or the dashboard link |
| Dialog | "close dialog", "cancel" | | Closes the open dialog without a change |
| Numbers | "show numbers", "hide numbers" | | The number overlay |
| Dictate | "dictate", "click question box then dictate", "stop dictating", "clear field" | | The focused or named text field |
| Read | "read the answer", "read the screen", "stop reading" | | The marked answer or main area |
| Help | "what can I say", "help" | | The help list for this screen |
| Language | "speak Tamil", "speak Hindi", "speak English" | | Changes the voice language (if offered) |
| Stop | "stop listening" | the equivalent phrase in each language pack (to be written and checked with native speakers) | Turns voice control off |
| Confirm / cancel | "confirm", "yes confirm", "cancel" | | Only while a confirmation is pending |

## Matching rules

1. Normalise: lower case, Unicode normalisation, punctuation removed, digits words turned into digits, filler words of every pack removed.
2. Split the phrase into **action words** and **target words** using all packs' action lists; if two actions appear, only the first is used (one action per phrase, FR-019).
3. For Go, Click, Set and Choose, compare the target with each eligible control's names in order: exact name; all target words present in the name; words within one edit of the name for words of five letters or more.
4. Result:
   - **One best match** with the gap to the next one large enough, and recognition confidence not low: act (or confirm if risky).
   - **Several close matches**: show numbers on those controls only and ask "Which one?". Never act.
   - **No match, or low recognition confidence**: show and say what was heard, with the closest options. Never act.
5. Eligible controls: visible, enabled, not hidden from assistive technology, and, if a dialog is open, inside it.
6. Navigation words beat control words: "settings" with both a menu item and a button called "Settings" prefers the menu item; if still tied, ask.
7. A phrase that **sounds like** a command but contains legal text is not a command while dictating (FR-012) and never when it is longer than the command pattern allows (about eight words for non-dictation).

## Risk and confirmation

- A control is **risky** if it has `data-voice-risk`, or its name contains a risk word from any pack (delete, remove, log out, sign out, deactivate, send, resend, approve, reject, and the Hindi and Tamil forms).
- Risky: say and show "About to <what>. Say 'confirm' or 'cancel'." For removals name the item and say it cannot be undone. Wait up to 15 s.
- Accepted: "confirm" or "yes confirm", only in a **later** recognition result than the prompt, with normal confidence.
- Cancelled by: "cancel", silence for 15 s, Escape, or any other command.
- Never confirmed by the same phrase that started it.
- Not risky (run at once): navigation, filters, tabs, saving, toggles, form submits, scrolling, reading.

## Never acted on

- A low-confidence phrase; a phrase matching nothing; ambiguous matches; a control that is disabled or hidden ("not available now"); a number that no longer exists; a second command in the same phrase (the first safe one runs, the rest is said back).
- Dictation into password, one-time-code or `data-voice-no-dictate` fields (the app asks the person to type).

## Feedback

Every handled phrase produces one short result line (shown in the panel or bar and announced politely): "Opened Dashboard", "Turned on Hearing reminders", "Which one? Say a number", "Did not understand 'xyz'", "Not available to you". The last phrase heard is shown until the next one or until voice control is turned off, and is never stored.

## Performance

Matching and acting complete within 1.5 s of the end of speech in at least 90% of cases for the browser path (SC-009); the scan of controls is cached and refreshed within 100 ms of a page change.
