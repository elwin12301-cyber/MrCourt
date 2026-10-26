# Implementation Plan: Voice Control for the Whole App

**Branch**: `011-voice-control` (work on `main`) | **Date**: 2026-10-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/011-voice-control/spec.md`

## Summary

A person switches on voice control once (after a consent notice) and the app listens continuously, hands-free, until they stop it. Spoken phrases are turned into one of a small set of actions: go to a screen, click a control by name, by number or by list position, set a toggle, scroll, go back, dictate, read aloud, help, stop. Everything works for the three roles because commands act on **what is actually on the screen**, found by looking at the page's own clickable elements and their accessible names, not on a hand-kept list of screens. That is also what makes new controls voice-controllable automatically (FR-022).

Approach (details in [research.md](research.md)):

- **Almost all frontend.** A voice-control module in `frontend/src/voice/` with: a control finder (live scan of the page), language packs (English, Hindi, Tamil; mixed phrases), a deterministic phrase matcher (no AI model), a safety layer (risky-action confirmation, never guess), a recognition runner (browser recognition, continuous, auto-restart), dictation, reading aloud, and the UI (dashboard voice panel, compact bar, number labels, help, confirmation prompt).
- **The browser's own speech recognition by default** (MrCourt never receives the audio; the browser's maker may process it, and the notice says so). The cloud speech service already used by the voice question feature is an **opt-in** fallback for languages the browser cannot handle, receiving short phrases only.
- **Small backend change:** three per-person settings (voice consent time, cloud opt-in, voice language), added to the existing settings endpoint, with audit entries for consent changes. No audio and no transcripts are stored anywhere.
- **Automatic coverage check:** one browser test walks every main screen for each role and fails when a visible clickable control has no usable name or cannot be reached by voice.

## Technical Context

**Language/Version**: TypeScript 5 / React 18 (frontend, Vite); Python 3.13 / FastAPI (backend, small change)

**Primary Dependencies**: React Router (existing navigation), the browser's speech recognition and speech synthesis (no new libraries), existing `useRecorder` and `/speech` endpoint for the opt-in cloud path. No new runtime dependency is planned.

**Storage**: PostgreSQL: three columns on `user_settings` (migration 0011). Browser storage only for pre-sign-in convenience (language, consent shown). Nothing about commands or audio is stored.

**Testing**: Vitest (language packs, matcher, safety, state machine, name finder); Playwright with a driveable fake speech recognition (extending the pattern in `tests/e2e/voice.spec.ts`), desktop and mobile, axe; pytest contract tests for settings and audit.

**Target Platform**: Desktop and phone browsers; recognition quality is best in Chrome and Edge over HTTPS or localhost (the screen says so). Other browsers: the app says voice control is unavailable and keeps working by mouse and keyboard.

**Project Type**: Web application (frontend + backend), existing layout.

**Performance Goals**: A recognised command shows its result within 1.5 s of the end of speech in at least 90% of cases (SC-009); finding controls on a screen under 50 ms; turning off stops the microphone within 1 s (SC-006).

**Constraints**: No audio stored; no command transcripts in logs, analytics or the audit log; MrCourt never receives audio while voice control uses browser recognition; keyboard and mouse stay complete and unchanged; no new colours or fonts; works in light and dark themes and at phone width; reduced motion respected.

**Scale/Scope**: About 28 routes across three roles, all menus, tabs, dialogs and forms. Three launch languages, each with mixed-with-English phrases; a language is added by one data file.

## Constitution Check

*GATE: passed before research; re-checked after design.*

| Principle | Check | Result |
|---|---|---|
| I. Grounded, cited answers | Reading an answer aloud reads the text on screen as it is, including source marks, sources and the disclaimer; the commands never change an answer. Dictated questions go through the normal question flow. | Pass |
| II. Informational guidance, not legal advice | Disclaimer and "review before use" flags are read with the content (FR-014, FR-021). Voice cannot send, file or export without the existing confirmation. | Pass |
| III. Privacy by design (DPDP) | Opt-in, consent notice with purpose, withdrawable in Settings; recognition by the browser's own service by default (never received by MrCourt); cloud path is a separate opt-in and short phrases only; no audio, no command transcripts stored or logged (FR-030 to FR-033). Consent changes are audited without content. | Pass |
| IV. Accessible and responsive | Keyboard stays complete; indicator and status are announced politely; number labels meet contrast, never hide the control, are hidden from screen readers (the control already has its own name); reduced motion respected; works at phone width. | Pass |
| V. Design system consistency | Voice panel, bar, labels and prompts use the existing tokens, fonts and components; the reference image is used for layout only. | Pass |
| VI. Simplicity and prototype-first | Deterministic phrase matching and a live page scan instead of per-screen command tables or an AI model; reuses the existing recognition and speech endpoint; no new dependency. | Pass |
| Constraints: roles, language | All three roles are served and named; a language is added only with a phrase list; citations are never translated or altered. | Pass |

No violations, so the Complexity Tracking table is empty.

## Project Structure

### Documentation (this feature)

```text
specs/011-voice-control/
├── plan.md              # This file
├── research.md          # Phase 0: decisions and alternatives
├── data-model.md        # Phase 1: settings, in-page state, language pack shape
├── quickstart.md        # Phase 1: how to try and verify it
├── contracts/
│   ├── voice-settings-api.md   # settings and audit contract
│   ├── command-grammar.md      # commands, phrases, matching and safety rules
│   └── ui-contract.md          # panel, bar, number labels, prompts, markup rules
├── checklists/requirements.md
└── tasks.md             # Created by /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/0011_voice_control_settings.py   # three columns on user_settings
├── src/mrcourt/
│   ├── models/user.py                  # UserSettings: voice_consent_at, voice_cloud_opt_in, voice_language
│   ├── schemas/auth.py                 # SettingsOut / SettingsPatch gain the three fields
│   ├── api/me.py                       # patch_settings stamps consent time; audits consent changes
│   └── services/audit.py               # labels for voice.consent.on/off, voice.cloud.on/off
└── tests/
    ├── contract/test_voice_settings.py
    └── unit/test_voice_audit.py

frontend/
├── src/
│   ├── voice/
│   │   ├── VoiceProvider.tsx           # state: off | starting | listening | paused | confirming | dictating
│   │   ├── controls.ts                 # find visible clickable controls, accessible names, numbers, list positions
│   │   ├── matcher.ts                  # normalise, strip verbs, match name/number/position, confidence, ambiguity
│   │   ├── commands.ts                 # intent parsing: go, click, set, scroll, back, dictate, read, help, stop, confirm
│   │   ├── safety.ts                   # risk rules, confirmation state machine, one command per phrase
│   │   ├── recognizer.ts               # continuous browser recognition, auto-restart, pause/resume, tab rules
│   │   ├── cloudPhrases.ts             # opt-in short-phrase capture for the speech service
│   │   ├── dictation.ts                # fill text fields (not passwords or codes)
│   │   ├── reader.ts                   # speak answers or the screen, stop at once
│   │   └── lang/{en,hi,ta}.ts          # language packs: verbs, screen aliases, mixed-phrase words, help text
│   ├── components/
│   │   ├── VoicePanel.tsx              # dashboard panel (reference layout)
│   │   ├── VoiceBar.tsx                # compact bar on every other screen
│   │   ├── VoiceNumbers.tsx            # number labels overlay
│   │   ├── VoiceHelp.tsx               # "what can I say"
│   │   └── VoiceConfirm.tsx            # spoken-and-visible confirmation
│   ├── pages/Dashboard.tsx, ClientDashboard.tsx, AdminOverview.tsx   # show the panel
│   ├── pages/Settings.tsx              # voice control section (consent, cloud opt-in, language)
│   ├── components/AppShell.tsx         # mounts bar and provider
│   ├── App.tsx                         # provider above the router outlet
│   └── styles/app.css                  # .vc-* classes using existing tokens
└── tests/
    ├── unit/voice-*.test.ts            # packs, matcher, safety, controls
    └── e2e/voice-control*.spec.ts, voice-coverage.spec.ts
```

**Structure Decision**: The existing web-application layout. Voice control lives in its own `frontend/src/voice/` folder so it can be read, tested and removed as a unit; the screens change only to show the panel, to tag a few risky controls (`data-voice-risk`) and answers (`data-voice-read`), and to fix any control that has no accessible name.

## Complexity Tracking

No constitution violations to justify.
