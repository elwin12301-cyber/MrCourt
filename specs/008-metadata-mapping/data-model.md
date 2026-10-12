# Data model: Metadata mapping

## knowledge_documents (new columns)

| Column | Type | Notes |
|---|---|---|
| `details` | JSON, nullable | field → `{value, confidence, source, alternatives?, by?, at?}` (see below) |
| `doc_type` | String(20), index | statute, judgment, order, petition, deed, deposition, notice, other |
| `court` | String(200), index | normalised court name |
| `case_number` | String(60), index | main case, normalised e.g. "S.A. 1106/2019" |
| `decided_on` | Date, nullable | date of decision or filing |
| `language` | String(10) | en, ta, mixed |
| `text_quality` | String(12) | readable, unreadable |

`details` fields: `doc_type, court, bench, case_numbers (list), cnr, case_title, parties ({petitioner: [],
respondent: []}), judges (list), decided_on (ISO date), acts (list of {act, section}), outcome, language,
text_quality`. `confidence` ∈ found | likely | not_found | confirmed; `source` ∈ text | person.
The indexed columns mirror the current values of their fields.

## document_references (new table)

| Column | Type |
|---|---|
| `id` | UUID PK |
| `document_id` | FK knowledge_documents, cascade delete, index |
| `act` | String(30) (ACTS key from `references.py`, e.g. IPC, BNS, NI, CONSTITUTION) |
| `section` | String(20), nullable |

Unique (document_id, act, section).

## legal_sources (new columns)

| Column | Type | Notes |
|---|---|---|
| `sections` | JSON list, nullable | statute section/article numbers this passage carries |
| `chapter` | String(100), nullable | e.g. "CHAPTER XVII" |

Plus read-only properties `court`, `decided_on`, `doc_type` from the passage's document (used by 009 ranking).

## Rules

- A field with `source = person` is never changed by mapping; `confidence` becomes `confirmed`.
- Correcting a field to empty sets `{value: null, confidence: "confirmed", source: "person"}` (a person said "none").
- Removing a document removes its details and references (cascade).
- Migration `0009_document_details`: idempotent like earlier revisions.
