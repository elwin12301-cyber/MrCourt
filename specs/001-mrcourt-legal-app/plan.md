# Implementation Plan: MrCourt Legal Assistance App

**Branch**: `001-mrcourt-legal-app` | **Date**: 2026-10-07 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-mrcourt-legal-app/spec.md`

## Summary

Build MrCourt as a web application with a React + TypeScript single-page frontend and a Python
(FastAPI) backend over PostgreSQL. The frontend reproduces the supplied "MrCourt Web Prototype" pixel
for pixel by porting its CSS design tokens and component classes unchanged. The backend provides
authentication (password and one-time passcode), role-scoped case management, and a
retrieval-grounded question-answering service: answers are generated only from passages retrieved
from an indexed corpus of Indian law, and any answer whose citations cannot be matched to retrieved
passages is replaced with the "could not find a reliable source" response. Drafts are generated from
templates plus case data, edited by the user, and exported to Word or PDF on explicit request.
Research decisions are in [research.md](research.md).

## Technical Context

**Language/Version**: TypeScript 5.x (frontend, Node 22 LTS tooling), Python 3.12 (backend)

**Primary Dependencies**: React 18, React Router, TanStack Query, Vite (frontend); FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, argon2-cffi, python-docx, fpdf2 (backend); Anthropic Claude API for answer and draft generation; an embedding model for retrieval

**Storage**: PostgreSQL 16 with `pgvector` (semantic search) and built-in full-text search; object storage for uploaded case documents (local disk in development)

**Testing**: pytest + httpx (backend unit, contract, integration); Vitest + React Testing Library (frontend); Playwright with axe-core (end-to-end, accessibility, visual comparison against prototype)

**Target Platform**: Modern evergreen browsers (desktop and mobile, 360px and up); Linux containers for the backend

**Project Type**: web application (frontend + backend)

**Performance Goals**: cited answer within 10 s at p95 (SC-004); page navigation and case search under 1 s; sign-in to next hearing visible under 30 s (SC-003)

**Constraints**: every answer cited or refused (FR-006/007); WCAG 2.1 AA in both themes; no horizontal scroll at 360px; DPDP-aligned data handling; no secrets or real personal data in the repository

**Scale/Scope**: launch target about 5,000 users, 50,000 cases, a legal corpus of about 100,000 provisions and judgment passages; 9 screens

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Grounded, cited answers only | Answers are built only from retrieved passages; a verifier rejects any claim without a matching citation; "no reliable source" path is a first-class response with tests | PASS (design in research.md R3, contract `POST /questions`) |
| II. Informational, not legal advice | Disclaimer is a required field in every answer payload and rendered by a single shared component; drafts carry a mandatory review flag; export is a user-initiated endpoint only | PASS |
| III. Privacy by design (DPDP) | Minimal data model, purpose notices, data export endpoint, deactivation flow, no PII in logs, secrets via environment | PASS WITH NOTE: spec Clarification 5 keeps case records after deactivation; legal review required before launch (tracked in Risks) |
| IV. Accessible and responsive | Semantic HTML ported from prototype, axe checks in CI, keyboard tests, both themes, reduced-motion | PASS |
| V. Design system consistency | Prototype tokens ported 1:1 into one CSS token file; components reuse prototype classes; visual regression against prototype | PASS |
| VI. Simplicity and prototype-first | Two deployable units only; one database; no message queue or microservices; features not built yet say so | PASS |

**Post-design re-check (after Phase 1)**: all gates still pass. No complexity violations.

## Project Structure

### Documentation (this feature)

```text
specs/001-mrcourt-legal-app/
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
design/
└── MrCourt Web Prototype.html     # Visual source of truth, kept unmodified

backend/
├── pyproject.toml
├── alembic/                       # Database migrations
├── src/mrcourt/
│   ├── main.py                    # FastAPI app factory
│   ├── config.py                  # Environment-based settings
│   ├── db/                        # Session, base model
│   ├── models/                    # SQLAlchemy models (users, cases, hearings, ...)
│   ├── schemas/                   # Pydantic request/response models
│   ├── api/                       # Routers: auth, me, cases, hearings, documents, drafts, questions, settings, admin
│   ├── services/
│   │   ├── auth.py                # Passwords, sessions, one-time passcodes
│   │   ├── access.py              # Role and ownership checks (advocate/petitioner)
│   │   ├── retrieval.py           # Hybrid search over the legal corpus
│   │   ├── answering.py           # Grounded generation and citation verifier
│   │   ├── drafting.py            # Template + case data -> draft text
│   │   ├── export.py              # Draft -> .docx / .pdf
│   │   └── privacy.py             # Data export, deactivation
│   └── corpus/                    # Ingestion CLI for Acts and judgments
└── tests/
    ├── contract/
    ├── integration/
    └── unit/

frontend/
├── package.json
├── index.html
├── src/
│   ├── styles/
│   │   ├── tokens.css             # Prototype CSS variables, light and dark
│   │   └── app.css                # Prototype component classes
│   ├── components/                # Icon, Chip, Pill, Card, Sidebar, SourceChip, Disclaimer, ...
│   ├── pages/                     # Welcome, Login, Dashboard, Ask, Cases, CaseDetail, Drafts, Settings
│   ├── services/                  # API client, auth, theme
│   └── main.tsx
└── tests/
    ├── unit/
    └── e2e/                       # Playwright, axe, visual comparison
```

**Structure Decision**: Web application layout (Option 2): a `frontend/` single-page app and a
`backend/` API in one repository, plus `design/` holding the untouched prototype for visual
comparison. Two deployable units keep operations simple (Principle VI) while matching the requested
React + TypeScript and Python split.

## Key Risks

- **Retention vs. erasure**: keeping case records after deactivation (spec Clarification 5) may not satisfy the DPDP Act; obtain legal review before launch. The data model isolates case records from personal profile data so the policy can change without a redesign.
- **Corpus coverage and licensing**: citation quality depends on a curated, licensed corpus; coverage limits surface as "no reliable source" answers.
- **Generated-text accuracy**: mitigated by the verifier and by a reviewed set of gold questions run in CI.

## Complexity Tracking

No constitution violations to justify.
