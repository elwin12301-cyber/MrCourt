# Tasks: Metadata mapping for the knowledge base

**Input**: `/specs/008-metadata-mapping/` (plan.md, spec.md, research.md, data-model.md, contracts/metadata-api.md, quickstart.md)

**Tests**: Included (privacy and grounding rules of the constitution; every earlier feature has them).

## Phase 1: Setup

- [X] T001 Migration `backend/alembic/versions/0009_document_details.py`: knowledge_documents + `details` JSON, `doc_type`, `court`, `case_number` (indexed), `decided_on` Date, `language`, `text_quality`; new table `document_references` (id, document_id FK cascade, act, section, unique); legal_sources + `sections` JSON, `chapter`; idempotent
- [X] T002 Models: new columns in `backend/src/mrcourt/models/knowledge.py`, `DocumentReference` model (registered in `models/__init__.py`), `LegalSource.sections`, `chapter`, `document` relationship and read-only `court`, `decided_on`, `doc_type` properties in `backend/src/mrcourt/models/legal.py`
- [X] T003 [P] Fictional sample documents for tests in `backend/tests/data/metadata/` (a High Court second appeal judgment, a writ order, a district court suit judgment, a sale deed, a cross-examination, a petition, a statute page, a Tamil Unicode page, a broken-encoding page) with an `expected.json` of the right fields; no real names

## Phase 2: Foundational

- [X] T004 [P] Unit tests `backend/tests/unit/test_metadata.py` driven by T003: each field found/likely/not_found as expected; no value without text evidence; unreadable text ⇒ empty fields; statute headings ⇒ passage sections; contents pages skipped; court names normalised
- [X] T005 Create `backend/src/mrcourt/services/metadata.py`: `text_quality(text)`, `extract(title, pages, kind) -> dict[field, Field]`, `statute_sections(text) -> (sections, chapter)`, `short_label(details)`, `apply(db, doc, extracted)` (keeps person-confirmed fields, mirrors indexed columns, rebuilds `document_references`, sets passage `sections`/`section`/`chapter`), `remap(db, documents) -> summary`, `main()` with `--remap` for every document

**Checkpoint**: extractor passes on the fictional set.

## Phase 3: User Story 1 - Mapped details I can check and correct (P1) 🎯 MVP

- [X] T006 [US1] Map details automatically after a document is read in `backend/src/mrcourt/services/knowledge.py` (`publish_pages` / `process_document`) and in `ensure_documents`
- [X] T007 [P] [US1] Contract tests `backend/tests/contract/test_document_details.py`: GET details (owner, shared, 404 for others), PATCH (owner / admin for shared, 403 others, validation, confirmed+person, audit for shared), remap keeps corrections
- [X] T008 [US1] Endpoints in `backend/src/mrcourt/api/knowledge.py` + schemas in `backend/src/mrcourt/schemas/knowledge.py`: GET/PATCH `/documents/{id}/details`, POST `/documents/remap`; `details` summary on each document in GET `/documents`
- [X] T009 [P] [US1] Frontend service functions in `frontend/src/services/knowledge.ts` (getDetails, saveDetails, remap)
- [X] T010 [US1] `frontend/src/components/DocumentDetails.tsx`: fields with confidence in words ("Found in the text", "Likely – please check", "Not found", "Confirmed by you"), edit form for those allowed, alternatives offered, unreadable notice; open from each row in `frontend/src/pages/ask/KnowledgeTab.tsx` with the short label in the row
- [X] T011 [US1] Run the remap on the development database (shared + private) and record counts in `specs/008-metadata-mapping/results.md`

## Phase 4: User Story 2 - Filter search and questions (P1)

- [X] T012 [P] [US2] Integration tests `backend/tests/integration/test_details_privacy.py`: list filters alone and combined; question filters restrict citations; nothing matching ⇒ no answer made up; a client's filters see shared only; filter options never list private values to others
- [X] T013 [US2] List filters + GET `/documents/filters` in `backend/src/mrcourt/services/knowledge.py` and `api/knowledge.py`
- [X] T014 [US2] Optional `filters` in `search()` (`backend/src/mrcourt/services/retrieval.py`) joining documents/references; `QuestionIn.filters` in `backend/src/mrcourt/schemas/questions.py`; passed through `answer_question` and `api/questions.py`; the "no source matches these filters" message
- [X] T015 [US2] `references.match()` treats a number in `LegalSource.sections` as exact (`backend/src/mrcourt/services/references.py`, `retrieval._matches`)
- [X] T016 [US2] `frontend/src/components/SourceFilters.tsx` (type, court, year, Act, section, case; labelled, keyboard friendly) used in `KnowledgeTab.tsx` and as "Limit sources" in `AskTab.tsx`; `frontend/src/services/questions.ts` sends filters

## Phase 5: User Story 3 - Details on citations and in the passage viewer (P2)

- [X] T017 [US3] Citation `details` short label in `backend/src/mrcourt/api/questions.py` (+ schema) and passage details in GET `/passages/{id}`
- [X] T018 [US3] Show the short label under each citation and the details list in `frontend/src/components/PassageViewer.tsx`; unknown fields left out

## Phase 6: User Story 4 - Map existing documents again in bulk (P2)

- [X] T019 [US4] "Map details again" button in `KnowledgeTab.tsx` (administrator: shared; advocate: own) showing the returned summary
- [X] T020 [US4] Tests: admin remap never touches private documents; summary counts (in `test_document_details.py`)

## Phase 7: Polish

- [X] T021 [P] Playwright `frontend/tests/e2e/document-details.spec.ts` (details shown, correction kept after remap, filters, citation label) and axe scans in `frontend/tests/e2e/a11y.spec.ts`
- [X] T022 [P] `backend/scripts/check_metadata.py` accuracy report (SC-001/SC-002) and results in `specs/008-metadata-mapping/results.md`
- [X] T023 [P] README section "Document details (metadata)"
- [X] T024 Full regression (backend, Vitest, tsc, ESLint, Playwright) recorded in `specs/008-metadata-mapping/results.md`

## Dependencies

Setup → Foundational → US1 (MVP) → US2 → US3, US4 → Polish. T015 also improves 009's exact-reference pins.
Parallel: T003; T004 with T005 drafting; T007 with T009; T012 with T013.

## Strategy

MVP = Phases 1–3 (details mapped, shown, corrected). Then filters (US2), labels (US3), bulk remap UI (US4).
