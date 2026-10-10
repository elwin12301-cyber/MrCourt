# Research: MrCourt Legal Assistance App

All Technical Context unknowns are resolved below.

## R1. Frontend architecture

- **Decision**: React 18 + TypeScript with Vite, React Router for the nine screens, TanStack Query for server state. Styling is plain CSS: the prototype's variables go into `tokens.css` and its classes into `app.css` unchanged, with a small `Icon` component wrapping the prototype's SVG sprite.
- **Rationale**: The prototype is already hand-written CSS with a token system and light/dark theming. Porting it verbatim is the only way to be pixel-faithful (FR-016) and avoids a second design system.
- **Alternatives**: Tailwind or a component library (rejected: would re-implement the look and drift from the prototype); Next.js (rejected: no server rendering need, adds complexity).

## R2. Backend, database and auth

- **Decision**: FastAPI with Pydantic v2, SQLAlchemy 2 and Alembic over PostgreSQL 16. Passwords hashed with argon2id. Sessions use short-lived access tokens in `HttpOnly`, `Secure`, `SameSite=Lax` cookies with refresh rotation. One-time passcodes are six digits, expire in five minutes, rate limited, and are sent through a pluggable SMS/email provider interface.
- **Rationale**: FastAPI yields an OpenAPI contract automatically and fits the Python requirement. Cookie sessions avoid storing tokens in browser storage.
- **Alternatives**: Django (heavier than needed), JWT in local storage (weaker against XSS), a hosted identity provider (extra dependency; revisit later).

## R3. Grounded question answering (Principle I)

- **Decision**: Retrieval-augmented generation with a hard verifier.
  1. Hybrid retrieval: PostgreSQL full-text search plus `pgvector` embeddings over `legal_sources` passages, merged by reciprocal rank fusion; top passages (about 8) are passed on.
  2. The generation call receives only those passages and must return structured JSON: answer paragraphs, each listing the ids of the passages that support it.
  3. A verifier checks that every paragraph lists at least one retrieved passage id, that quoted section numbers appear in the cited passage, and that a minimum retrieval score is met. Any failure, or an empty retrieval, returns the fixed "could not find a reliable source" response instead.
  4. Citations render as numbered chips such as "Negotiable Instruments Act, 1881 · Section 138".
- **Rationale**: The failure mode that matters is a confident uncited statement. Making refusal the default and verifying mechanically is testable (SC-001, SC-002).
- **Alternatives**: Free-form generation with post-hoc citation (rejected: cannot guarantee grounding); keyword lookup only (rejected: poor recall on natural questions).

## R4. Legal corpus

- **Decision**: An ingestion CLI loads Acts and judgments from licensed or public-domain sources into `legal_sources` (one row per section or passage with Act, section, year, text, source URL, and effective status). Launch scope: BNS, BNSS, BSA, the Constitution, the Negotiable Instruments Act, and the Consumer Protection Act. Repealed provisions carry a pointer to their replacement so answers can cite the current law.
- **Rationale**: The prototype's examples and the edge case on repealed codes require both current and superseded text.
- **Alternatives**: Live scraping at query time (unreliable, licensing risk).

## R5. Draft generation and export

- **Decision**: Each template is a structured outline with slots filled from case data (parties, cheque details, court). A generation call may expand the outline but must keep placeholders for unknown facts in square brackets, as the prototype does. Export uses `python-docx` for Word and `fpdf2` for PDF (pure Python; WeasyPrint was rejected because it needs system graphics libraries that are not available on Windows). Export only runs from an explicit user request; nothing is sent or filed.
- **Rationale**: Slot-based drafts keep invented facts out; two well-known libraries cover both formats without a separate office suite.
- **Alternatives**: WeasyPrint (system library dependency), LibreOffice for PDF conversion (heavy runtime), client-side export (inconsistent output).

## R6. Voice input

- **Decision**: Use the browser's built-in speech recognition where available, feature-detected, falling back to a message that voice is unsupported (spec edge case). No audio is sent to MrCourt servers.
- **Rationale**: Simplest approach with the best privacy posture.
- **Alternatives**: Server-side transcription (cost, DPDP exposure).

## R7. Reminders (WhatsApp and alerts)

- **Decision**: A scheduled backend job finds hearings inside each user's alert window and sends through a provider interface (WhatsApp Business as the first adapter). Reminders are opt-in, per the settings switch, and contain no case details beyond title and time.
- **Rationale**: Keeps provider details behind one interface and limits data shared.
- **Alternatives**: Email only (does not match the settings screen).

## R8. Testing and quality gates

- **Decision**: pytest for backend with a gold set of reviewed questions (cited, partially cited, and out-of-corpus) run in CI; Vitest for components; Playwright for flows, keyboard-only runs, axe accessibility checks in both themes at 360px and 1280px, and screenshot comparison with the prototype.
- **Rationale**: Directly tests Principles I, IV and V and the success criteria.

## R9. Access control

- **Decision**: One `access.py` policy module enforces: Advocate owns cases they create; Petitioner reads only cases with an accepted invitation; Drafts and writes are Advocate-only. Every query on cases is filtered through it, and tests assert that cross-user access returns 404.
- **Rationale**: Centralised checks are easier to audit than per-route logic (SC-009).

## R10. Privacy and retention

- **Decision**: Personal profile data and case data live in separate tables. Deactivation sets the user inactive, deletes question history, preferences and contact details, and keeps case records as decided in the spec. A data-export endpoint returns the user's data as JSON. Logs exclude personal data and question text.
- **Rationale**: Implements FR-015 while making a later change to retention cheap.
- **Open item**: legal review of indefinite case retention (see plan Key Risks).
