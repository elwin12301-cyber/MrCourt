# Quickstart: Validating MrCourt End to End

A run-and-check guide. API shapes are in [contracts/openapi.yaml](contracts/openapi.yaml) and tables in
[data-model.md](data-model.md).

## Prerequisites

- Python 3.12, Node 22, PostgreSQL 16 with the `pgvector` extension
- Environment variables (names only, never commit values): `DATABASE_URL`, `SESSION_SECRET`,
  `ANTHROPIC_API_KEY`, `EMBEDDING_API_KEY`, optional `SMS_PROVIDER_*` and `WHATSAPP_PROVIDER_*`
- The prototype saved at `design/MrCourt Web Prototype.html` for visual comparison

## Setup

1. Backend: create a virtual environment in `backend/`, install the project, then run database migrations.
2. Load sample data: run the corpus ingestion command on the bundled sample set (Negotiable Instruments Act s.138 and s.142, BNSS s.480 and s.483) and the seed command for fictional users and cases.
3. Start the API and the frontend dev server.

## Validation scenarios

Each maps to a user story in the spec.

1. **Cited answer (Story 1, SC-001)**: sign in as the sample advocate, open Ask MrCourt, select the "Cheque bounce, S.138" pill. Expect an answer with numbered chips for Section 138 and Section 142 and the line "Informational only, not legal advice".
2. **No reliable source (Story 1, FR-007)**: ask a question outside the sample corpus (for example about patent licensing). Expect the "could not find a reliable source" message and no legal claim.
3. **Sign in and roles (Story 2)**: from the welcome screen choose each role and sign in with password and with a one-time passcode; confirm wrong credentials show a generic error and sign out returns to the welcome screen.
4. **Cases (Story 3)**: search by a party name, a CNR number and a court; apply each filter pill; open a case with the mouse and with Enter on a focused row; confirm a closed case shows "No hearing scheduled".
5. **Petitioner limits (FR-019)**: sign in as the sample petitioner. Expect only invited cases, no Drafts entry, and a 404 when requesting another user's case.
6. **Drafts (Story 4)**: select each template, press Edit, change text, press Done, reload and confirm the text and version persist; export Word and PDF and confirm both open; confirm the "review before use" flag is always visible.
7. **Settings and privacy (Story 5)**: toggle reminders and theme, reload to confirm persistence; request a data export; start deactivation and confirm the retention notice must be acknowledged.
8. **Verification (FR-021)**: register a new advocate, confirm "verification pending", then confirm as administrator and see the "Bar Council verified" chip.

## Automated checks

- Backend: unit, contract and integration tests, including the reviewed gold set of questions and cross-user access tests (expect 404).
- Frontend: component tests.
- End to end: Playwright flows for the scenarios above, keyboard-only runs, axe accessibility scans in light and dark themes at 360px and 1280px, and screenshot comparison with the prototype for each screen.

## Expected outcomes

- Every answer is cited or refused; no answer lacks the disclaimer.
- No axe violations at AA; no horizontal scroll at 360px.
- Screenshots of each screen match the prototype within the agreed visual threshold.
