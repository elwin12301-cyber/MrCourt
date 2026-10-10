# Implementation Plan: Admin Console

**Branch**: `003-admin-console` | **Date**: 2026-10-08 | **Spec**: [spec.md](spec.md)

## Summary

Add a third role, `admin`, with its own sign-in page, menu and screens, on the existing stack. Admin endpoints live under `/admin/*` and every one requires the admin role. Full-visibility reads (opening a case, downloading a document, opening a person's page) write an audit entry in the same request. Account changes (edit details, suspend, reactivate, force sign-out, verification decisions) are saved immediately and audited. No admin endpoint can edit a case, delete data or reset a password, so those powers do not exist rather than being switched off.

## Technical Context

Same as features 001 and 002 (FastAPI, SQLAlchemy, Alembic; React, TypeScript; SQLite in tests, PostgreSQL target). No new dependencies.

**Key design decisions**

- **Role, not a flag.** `users.role` gains the value `admin`. Existing checks (`require_advocate`, `require_client`) already refuse anyone whose role differs, so an admin cannot reach advocate or client endpoints and the reverse. `is_admin` is kept and set true for admins so older code keeps working.
- **Ending sessions.** Session cookies are signed, not stored, so a person cannot be signed out by deleting something. Each user gets `session_epoch`; the cookie carries it; bumping it invalidates every cookie for that person. Suspending also bumps it. A request whose epoch is stale, or whose account is not active, is refused.
- **Audit log.** Table `audit_log` (admin, action, target type, target id, safe details, time). Written through one helper, in the same transaction as the action, so an action and its entry succeed or fail together. No update or delete endpoint exists.
- **Reads that are logged vs not.** Lists and searches return overview fields only and are not logged. Opening a case in full, downloading a document and opening a person's page are logged.
- **Personal data in the log.** Entries store field names and, for non-sensitive fields (name, Bar number), old and new values; email and phone changes record only that they changed. Message text and document contents are never stored.
- **Admin cannot manage admins.** Suspend, sign-out and edit refuse admin targets.

**Source layout (new files)**

```text
backend/src/mrcourt/models/audit.py            # AuditEntry
backend/src/mrcourt/services/audit.py          # record()
backend/src/mrcourt/services/admin_users.py    # list, detail, edit, suspend, reactivate, sign-out
backend/src/mrcourt/services/admin_cases.py    # list, full view
backend/src/mrcourt/schemas/admin.py
backend/alembic/versions/0003_admin_console.py
frontend/src/pages/Admin{Overview,Users,UserDetail,Cases,CaseView,Audit}.tsx
frontend/src/services/admin.ts
```

## Constitution Check

| Principle | Gate | Status |
|-----------|------|--------|
| I. Grounded, cited answers | Unaffected | PASS |
| II. Not legal advice | Unaffected | PASS |
| III. Privacy by design (DPDP) | Admin sees private content, which widens exposure. Mitigation: access limited to the admin role, every open of private content audited, audit entries free of message text and document contents, notice shown to the admin, admins cannot be created by sign-up | PASS WITH NOTE: broad administrator access should be reviewed against the DPDP Act and the organisation's own policy before launch |
| IV. Accessible and responsive | Existing components, axe scans extended | PASS |
| V. Design system | Existing tokens and classes | PASS |
| VI. Simplicity | One new table, one new column, no new services | PASS |

## Key Risks

- Broad visibility is a privacy decision the owner chose; the audit log is the control, and it is only as good as how often it is reviewed.
- A forgotten audit call would hide an access. Tests walk every admin endpoint that returns private content and assert an entry exists.
- Stale cookies after the epoch change force everyone to sign in once after upgrading.
