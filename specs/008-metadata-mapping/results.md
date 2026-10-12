# Results: Metadata mapping (feature 008)

Date: 2026-10-12. Development database: PostgreSQL 16 + pgvector (Docker).

## Mapping the development data (T011)

`python -m mrcourt.services.metadata --remap` over 49 documents:

| | Count |
|---|---|
| Shared law documents typed as statutes | 40 |
| Statute passages with section numbers | 288 of 4,958 |
| Private case documents readable / unreadable | 2 / 7 |
| Fields found (documents) | type 48, Acts 8, case numbers 3, court 2, date 2, judges 1, parties 1, outcome 1 |

- The two readable case documents (a second-appeal judgment and a writ order) map to Madras High Court with
  case number and date; the judgment also gets judge, parties and title. The order's date line is garbled in the
  PDF ("DAIED"), so its date is offered as **likely** for the owner to confirm.
- 7 private PDFs have a broken text layer (legacy Tamil font encoding): flagged "Text could not be read: needs
  OCR", nothing mapped. They also cannot be searched meaningfully until they are scanned with OCR.

## Accuracy (SC-001, SC-002; `scripts/check_metadata.py`)

- Fictional test set (9 documents in court-paper layout): **40/40** expected fields right; fields marked
  "found" correct **31/31 (100%)**; no value invented (every unknown field empty). SC-001 met on this set; the set
  is small and fictional, so real-world accuracy should be re-checked on more real, readable documents.
- Statute passages with a section: **288 of 4,958 (6%)**. **SC-002 (95%) is not met**: most "law" PDFs in the
  corpus are class-room notes arranged by topic, not section-by-section statute text. Real statute texts (bare
  Acts) would map far better; that is a data gap, not a mapping rule gap.

## Tests

- Backend: 637 passed (adds unit `test_metadata.py` 45, contract `test_document_details.py` 7, integration
  `test_details_privacy.py` 5, `test_postgres_queries.py` 1).
- Browser: `document-details.spec.ts` 6 passed (desktop and phone), including axe scans in both themes.
- Full regression (T024): backend 637 passed; TypeScript, ESLint clean; Vitest 15 passed; Playwright
  **439 passed, 1 flaky** (desktop and phone, about 4.6 minutes). The flaky test is the phone-code check in
  `sign-up-reset.spec.ts` ("Your mobile number is verified" not shown in time); it passed on retry, and that
  flow is not changed by this feature.

## Found while building

- **Meaning search was broken on PostgreSQL** (the embedding column's type gave no vector distance operator).
  Fixed in `retrieval.meaning_query`, with a test that compiles the PostgreSQL query.

## Open

- OCR for the 7 unreadable PDFs (Tesseract with Tamil is not installed on this computer).
- Assistant answers do not yet record a ranking explanation (009 T027).
