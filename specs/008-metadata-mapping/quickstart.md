# Quickstart: validating metadata mapping

## Setup

```text
cd backend
alembic upgrade head                         # adds 0009 (details columns, document_references)
python -m mrcourt.services.metadata --remap  # map every existing document (shared and private)
```

## Checks

1. Knowledge base, as the advocate who owns the S.A. 1106/2019 judgment: its row shows
   "Judgment · Madras High Court · 07 Apr 2025 · S.A. 1106/2019"; Details lists the judge and parties as
   **found**; outcome is filled only if the text states it.
2. A Tamil PDF with a broken text layer shows "Text could not be read: needs OCR"; its fields are empty.
3. Correct the court of a document, then run the remap again: the correction is kept and marked
   "Confirmed by you".
4. Filter the Knowledge base by type = judgment, year = 2025: only matching documents the user may see.
5. Ask with filters "Act: Constitution, section 21": every citation is the Article 21 text or refers to it;
   with a filter matching nothing, the answer says no source matches.
6. Sign in as a client: the filter options never list a private court, case or year; private documents never
   appear.
7. Administrator: remap covers shared documents only; correcting a shared document appears in the audit log.

## Tests

```text
cd backend && python -m pytest tests/unit/test_metadata.py tests/contract/test_document_details.py tests/integration/test_details_privacy.py -q
cd frontend && npx playwright test document-details.spec.ts a11y.spec.ts
```

## Accuracy (SC-001, SC-002)

`python scripts/check_metadata.py` prints, for the fictional test documents in `tests/data/metadata/`, each
expected field against the mapped one, and the share of "found" fields that are correct; and for the shared
statutes, the share of passages with a section number.
