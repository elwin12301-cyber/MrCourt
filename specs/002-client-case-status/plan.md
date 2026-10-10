# Implementation Plan: Client Case Status ("My Lawyer, My Case")

**Branch**: `002-client-case-status` | **Date**: 2026-10-07 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-client-case-status/spec.md`

## Summary

Give petitioners (clients) their own experience on top of feature 001: a client dashboard, "My cases" list, a plain-language case page (status, next hearing with an automatic general description, timeline, shared documents, "My lawyer"), an Updates list with unread counts, private questions to the lawyer, and a safer Ask MrCourt. Advocates keep their screens and gain a "Client view" panel to set one of four statuses, post short updates, mark documents, outcomes and notes as shared, answer client questions, and fill in an optional contact card.

The design adds a small set of tables (timeline entries, client updates, client questions) and a few columns (client status on cases, share flags on documents and hearing outcomes, a contact card on the advocate's settings). Client screens read only through dedicated client endpoints that return a purpose-built "client view", so private data (notes, internal documents, unshared outcomes) is never fetched on the client path, which makes leaks structurally hard. Hearing descriptions come from a reviewed, static content file keyed by the hearing's purpose or case stage, not from a model, so they cannot invent facts. Research decisions are in [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.x with React 18 (frontend), as in feature 001

**Primary Dependencies**: Existing stack only (FastAPI, SQLAlchemy 2, Alembic, Pydantic v2; React, React Router, TanStack Query). No new runtime dependencies.

**Storage**: Same database (PostgreSQL target, SQLite in development and tests). New Alembic revision `0002` adds tables and columns; the 001 initial migration is left untouched.

**Testing**: pytest (contract, integration, unit), Vitest, Playwright with axe and screenshot checks, as in 001. New tests focus on leak prevention and role separation.

**Target Platform**: Evergreen browsers from 360px up; Linux containers for the API

**Project Type**: web application (existing `backend/` and `frontend/`)

**Performance Goals**: client dashboard and case page data in under 1 s; updates visible within 1 minute of the advocate's change (SC-004) using periodic refresh of the unread count every 30 seconds

**Constraints**: private notes, internal documents and unshared outcomes never returned by any client endpoint; clients see only their own questions and read states; no new legal claims written by a model; WCAG 2.1 AA in both themes at 360px; DPDP deletion rules from 001 extended to the new personal data

**Scale/Scope**: about 5,000 users, 50,000 cases, up to 3 clients per case, tens of updates per case; 4 new client screens and one new advocate panel

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Grounded, cited answers only | Ask MrCourt for clients keeps citation verification unchanged. Hearing descriptions are static reviewed content, not generated claims; any reference to law in them carries a citation label from the corpus | PASS |
| II. Informational guidance, not legal advice | Every description and answer carries the disclaimer; clients asking about their own case get "ask your lawyer"; descriptions are general, never predict outcomes; client questions to the lawyer are marked as not an advice channel | PASS, with the residual risk that the question detector is heuristic (see Key Risks) |
| III. Privacy by design (DPDP) | Dedicated client read model, share flags default to private, per-client privacy of questions, deactivation removes client questions and updates, no personal data in logs | PASS |
| IV. Accessible and responsive | New screens reuse existing components; unread counts are text, not colour alone; axe scans extended to the new screens in both themes | PASS |
| V. Design system consistency | Existing tokens and classes; new styles limited to a few additions documented in `app.css` | PASS |
| VI. Simplicity and prototype-first | No new services, queues or providers; in-app updates only; four fixed statuses; periodic refresh instead of push | PASS |

**Post-design re-check (after Phase 1)**: all gates still pass. No complexity violations.

## Project Structure

### Documentation (this feature)

```text
specs/002-client-case-status/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── openapi.yaml
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/0002_client_case_status.py       # new tables and columns
├── src/mrcourt/
│   ├── models/client.py                              # TimelineEntry, ClientUpdate, ClientQuestion
│   ├── models/case.py                                # + client_status fields, shared flags
│   ├── schemas/client.py                             # client read model and advocate request bodies
│   ├── services/
│   │   ├── client_view.py                            # builds the client-safe case view (the only client read path)
│   │   ├── client_status.py                          # four statuses, timeline entries, update fan-out
│   │   ├── client_questions.py                       # private questions and replies
│   │   ├── hearing_descriptions.py                   # picks a general description for a hearing
│   │   ├── advice_guard.py                           # detects "about my own case" questions
│   │   └── privacy.py                                # + removes client questions and updates
│   ├── corpus/data/hearing_descriptions.json         # reviewed general descriptions (UNVERIFIED until reviewed)
│   ├── corpus/data/glossary.json                     # plain-language term explanations
│   └── api/
│       ├── client.py                                 # /client/* endpoints for petitioners
│       ├── client_admin.py                           # advocate-side status, updates, sharing, questions
│       └── glossary.py
└── tests/ (contract, integration, unit as in 001)

frontend/
├── src/
│   ├── pages/
│   │   ├── ClientDashboard.tsx                       # replaces Dashboard for petitioners
│   │   ├── ClientCases.tsx                           # "My cases"
│   │   ├── ClientCaseDetail.tsx                      # status, next hearing, timeline, lawyer, questions
│   │   └── Updates.tsx                               # updates list with unread state
│   ├── components/
│   │   ├── ClientStatusChip.tsx, Timeline.tsx, LawyerCard.tsx, AskLawyer.tsx, Explain.tsx
│   │   └── ClientViewPanel.tsx                       # advocate-side controls on the case page
│   └── services/client.ts
└── tests/e2e/ (client.spec.ts, client-privacy.spec.ts, plus extended a11y.spec.ts)
```

**Structure Decision**: Extend the existing web application layout. Client-facing reads live in their own router and service so the access rule is "petitioners only ever call `/client/*`", which keeps the privacy boundary in one place and easy to test. Advocate-side controls are added to the existing case page rather than a new area.

## Key Risks

- **Hearing descriptions need legal review.** The content file is general information written by us; it is flagged UNVERIFIED and refused in production until reviewed (same rule as the sample legal corpus).
- **The "about my own case" detector is heuristic.** Phrases like "my case", "should I", "will I win" are matched; unusual wording can slip through. Mitigation: every client Ask answer also shows a short standing reminder to ask their lawyer for case-specific advice, so the protection does not depend on the detector alone.
- **Updates are in-app only and refreshed periodically.** A client who never opens the app will not see them; only existing hearing reminders reach the phone.
- **Multi-client privacy.** Each client's questions are filtered by client id at query time; a regression here would leak messages between clients, so it has dedicated tests.

## Complexity Tracking

No constitution violations to justify.
