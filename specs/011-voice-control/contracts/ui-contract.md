# Contract: Voice control interface

How voice control looks and behaves on screen, and the markup rules that keep every control reachable. It uses the existing design tokens, fonts and components; the reference image the product owner supplied (a dark-theme layout with a large microphone tile, a headline, instructions, a status line and an "I heard you say" card) is the model for the dashboard panel.

## Voice panel (dashboards of all three roles)

Shown on the advocate dashboard, the client dashboard and the administrator overview, near the top.

| Part | Content |
|---|---|
| Eyebrow | "Voice-controlled workspace" |
| Microphone tile | Large button, a real `button` with `aria-pressed`; tap to start, tap to stop. Shows a gentle pulse while listening (none under reduced motion). |
| Headline | "Your voice is the remote" |
| Instructions | "Tap the microphone and tell the app where to go. Keep this tab open and allow the microphone when asked. Say 'stop listening' to turn it off." |
| Status line | "Microphone is off" (grey dot) / "Listening…" (live dot) / "Paused – another tab or call has the microphone" / "Waiting for your answer – say confirm or cancel" |
| "I heard you say" card | Last phrase heard, the result line, and a suggestion such as "Try 'Go to dashboard'" (in the chosen language). Also: "Works best in Chrome or Edge over a secure connection or localhost." |
| Language | The existing language choice for voice; a plain note when cloud recognition is used ("sent as short phrases, not stored") |
| Help link | "What can I say?" opens the help list |

First use: pressing the tile before consent opens the **notice** (below) and does not start the microphone until the person agrees.

## Compact voice bar (every other screen, while on)

A fixed bar at the bottom edge of the content area (above the phone's bottom edge): microphone button, status dot and word, last phrase heard (trimmed), result line, "Numbers" toggle, "Help" and "Stop" buttons. It never covers the main controls of the page: the page gets bottom spacing while the bar is shown.

## Consent notice

Plain-language text shown before first use and from Settings: what is listened to and when; that audio is not stored by MrCourt; that by default the browser's own speech recognition does the listening (in Chrome and Edge the browser's maker may process the audio under its own terms) and MrCourt never receives it; that, only if the person chooses the cloud option for a language the browser cannot handle, short phrases are sent to the speech service and not stored; that it can be turned off any time; that mouse and keyboard still work. Buttons: "Agree and turn on" and "Not now". Closing the notice agrees to nothing.

## Settings section "Voice control"

Switch to agree/withdraw consent; switch for the cloud option (disabled until consent, with its own sentence); language choice; link to the help list. Changes save at once and are announced.

## Number labels

- A small numbered badge drawn beside the top-left corner of each visible clickable control, on a layer that ignores the pointer and is hidden from assistive technology.
- Uses an existing token pair with at least 4.5:1 contrast in both themes; never covers the control's text; moves with scroll and resize; at phone width labels sit just outside the control's edge or inside its padding if there is no room.
- Shown on "show numbers" and, automatically, only on the controls that matched an ambiguous phrase.
- With reduced motion, no fade or movement.

## Confirmation prompt

A dialog-style prompt (`role="alertdialog"`, focus moved to it) that says what is about to happen with two buttons "Confirm" and "Cancel", spoken aloud as well. A mouse or keyboard user can answer it too. Expires after 15 s.

## Help list

A dialog listing global commands and the commands for this screen (control names found on the page, grouped as menu, tabs, buttons), in the chosen language, with a "Try saying" example for each group. Reachable by button and keyboard, not only by voice.

## Keyboard and screen readers

- Shortcut to start/stop: a single documented shortcut (shown in the help list and Settings) that does not clash with the browser or screen readers.
- Status changes announced politely (`role="status"`); confirmations announced assertively.
- Every voice control is a native button or a standard form control with a visible name and visible focus.
- Nothing becomes voice-only.

## Markup rules for the rest of the app

| Rule | Why |
|---|---|
| Every clickable control has an accessible name (text, `aria-label` or label). | The finder and screen readers both depend on it. A test fails otherwise. |
| Icon-only buttons have `aria-label`. | Same. |
| Delete, remove, log out, deactivate, send, resend, verification and private-document actions carry `data-voice-risk`. | Confirmation (a name-word check backs this up). |
| An answer's container carries `data-voice-read`. | "Read the answer" reads it, with sources and disclaimer. |
| Password, code and similar fields carry `autocomplete` values or `data-voice-no-dictate`. | Never dictated. |
| Repeated lists use a list or `role="list"` / `listitem` or a table. | Position commands. |

## Both themes, phone width

Panel, bar, labels, notice, confirmation and help are checked in light and dark and at 360 px width; the bar collapses to the microphone, status and Stop at phone width, with the rest in a menu.
