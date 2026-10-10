# Quickstart validation results

Run on 2026-10-07 against SQLite (no Docker or PostgreSQL was available) with the extractive answer
writer (no model API key). Automated evidence is cited by test file; "not verified" items are called
out rather than assumed.

| # | Scenario | Result | Evidence |
|---|----------|--------|----------|
| 1 | Cited answer (Story 1, SC-001) | Pass | `frontend/tests/e2e/ask.spec.ts` (pill gives numbered chips for s.138 and the disclaimer); `backend/tests/integration/test_answers_gold.py` |
| 2 | No reliable source (FR-007) | Pass | `ask.spec.ts` (no chips, plain message, disclaimer); gold set (3 out-of-corpus questions); `tests/unit/test_answering.py` (bad generator output is discarded) |
| 3 | Sign in and roles (Story 2) | Pass for password sign-in. OTP delivery not verified | `auth.spec.ts`; `tests/integration/test_auth_flows.py` (generic errors, expiry, single use, lockout, rate limits). OTP codes only reach a development outbox; no real SMS/email adapter exists |
| 4 | Cases (Story 3) | Pass | `cases.spec.ts` (search by party/CNR/court, filters, open with Enter, closed case shows "No hearing scheduled") |
| 5 | Petitioner limits (FR-019) | Pass | `cases.spec.ts` (petitioner), `drafts.spec.ts`, `tests/integration/test_case_access.py` (another user's case is 404; petitioners are read-only; notes hidden) |
| 6 | Drafts (Story 4) | Pass | `drafts.spec.ts` (each template, edit/save, version, reload, Word and PDF downloads, review flag); `tests/integration/test_drafts_flows.py` (nothing exported unless requested; failed export leaves draft unchanged) |
| 7 | Settings and privacy (Story 5) | Pass | `settings.spec.ts` (toggles, theme, data download, deactivation notice and confirmation); `tests/integration/test_privacy.py` (personal data removed, case records kept) |
| 8 | Verification (FR-021) | Pass | `settings.spec.ts` (pending chip, administrator confirms, verified chip) |

## Automated checks

| Check | Result |
|-------|--------|
| Backend (pytest) | 119 passed |
| Frontend unit (Vitest) | 9 passed |
| Types (tsc) and lint (ESLint, jsx-a11y) | Clean |
| Browser tests (Playwright, desktop 1280px and phone 360px) | 102 passed, two consecutive full runs |
| Accessibility (axe, WCAG 2.1 A and AA) | No violations on every screen in light and dark themes at both widths (after two small light-theme colour changes, see README) |
| No horizontal scrolling at 360px | Pass on welcome and sign-in (`auth.spec.ts`); other screens are covered by the axe and layout runs at 360px but have no dedicated overflow assertion |
| Visual comparison with the prototype | Welcome, sign-in brand panel and navigation chrome: 0.000% of pixels differ in both themes at both widths. Data screens are not pixel-compared |
| Answer latency (SC-004) | Our own pipeline p95 well under 2 s (asserted). A live model's latency is not measured |

## Not verified

- PostgreSQL, `pgvector` and the full-text search query (the migration and the PostgreSQL branch of
  retrieval have never been executed).
- Model-written answers with a real `ANTHROPIC_API_KEY`.
- WhatsApp delivery and any real SMS/email delivery.
- Legal correctness of the sample passages (marked UNVERIFIED) and of retaining case records after
  deactivation (task T101, pending legal review).
- SC-002 (95% of cited sections correct on 100 reviewed questions), SC-006 (90% of first-time users
  succeed unaided) and SC-005 (finding a case within 15 seconds): these need real reviewers or users.
