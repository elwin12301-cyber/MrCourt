# Contract: document details (metadata)

All under `/api/v1/knowledge`. "May see" = the document is shared, or it is the caller's own private document.

## GET /documents  (existing, new query parameters and fields)

Query: `type`, `court`, `year` (decision/filing year), `act` (ACTS key, e.g. IPC), `section`, `case` (case number or
CNR, partial). Each item gains:

```json
{"details": {"doc_type": "judgment", "court": "Madras High Court", "case_number": "S.A. 1106/2019",
             "decided_on": "2025-04-07", "language": "en", "text_quality": "readable",
             "short": "Judgment · Madras High Court · 07 Apr 2025 · S.A. 1106/2019"}}
```

## GET /documents/filters

Values for the filter bar from the documents the caller may see only: `{types: [], courts: [], years: [], acts: []}`.

## GET /documents/{id}/details

404 unless the caller may see the document. Returns every field:

```json
{"document_id": "uuid", "can_edit": true, "text_quality": "readable",
 "fields": {"court": {"value": "Madras High Court", "confidence": "found", "source": "text", "alternatives": []},
            "judges": {"value": ["R. Hemalatha"], "confidence": "found", "source": "text"},
            "outcome": {"value": null, "confidence": "not_found", "source": "text"}}}
```

## PATCH /documents/{id}/details

Body: `{"fields": {"court": "Madras High Court", "decided_on": "2025-04-07", "outcome": null}}`. Owner of a private
document, or an administrator for a shared one (403 otherwise; 404 if not visible). Values are validated per
field (dates ISO, type from the list, lists for judges/case_numbers/acts). Each corrected field becomes
`confirmed / person`. Corrections to shared documents write audit `knowledge.details.edit`.

## POST /documents/remap

Administrator: all shared documents. Advocate: their own private documents. Others 403.
Returns `{"documents": 12, "fields_found": {"court": 9, ...}, "unreadable": 3}`. Corrected fields are kept.

## Questions

`POST /api/v1/questions` accepts optional `filters` with the same keys as the list (`type, court, year, act,
section, case`). Citations gain `details` (the short label) when the cited passage's document has details.

## GET /passages/{id}  (existing)

Adds `details` (the same object as GET /documents/{id}/details `fields`, values only) when the caller may see it.
