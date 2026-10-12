# Implementation Plan: Metadata mapping for the knowledge base

**Branch**: `008-metadata-mapping` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/008-metadata-mapping/spec.md`

## Summary

A rule-based extractor (`services/metadata.py`) reads the text MrCourt already has for a document and maps it to
standard details: type, court, case number/CNR, title and parties, judges, date, Acts and sections referred to,
outcome, language, and whether the text is readable at all. Every field carries a confidence state (found /
likely / not found / confirmed by a person); nothing is guessed, and a person's corrections survive re-mapping.
Statute pages also get their section numbers. Details are stored on the document (one JSON column plus a few
indexed columns used by filters, and a small table of Acts/sections referred to), shown and edited in the
Knowledge base, used as filters there and when asking, shown on citations, and read by the 009 ranker (court,
date, document type). Visibility follows the documents exactly: private details only for their owner.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5 / React 18 (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2, Alembic; no new libraries and no outside service

**Storage**: PostgreSQL 16 (development and production), SQLite (tests); migration 0009

**Testing**: pytest (unit on fictional sample texts, contract, privacy integration), Vitest, Playwright + axe

**Target Platform**: Linux container (Render), local Windows development

**Project Type**: Web application (backend + frontend)

**Performance Goals**: mapping a 600-page document in under 10 s; filters answer in under 1 s for 10,000 passages

**Constraints**: no value without text evidence (FR-003); private details never leave their owner (FR-010)

**Scale/Scope**: about 50 documents and 5,200 passages today

## Constitution Check

| Principle | How this plan complies | Status |
|---|---|---|
| I. Grounded, cited answers | Filters only narrow the sources; answers stay cited and verified, and "no reliable source" when nothing matches (FR-007). Details come only from document text or a person (FR-003). | Pass |
| II. Not legal advice | No change to answer wording or disclaimers. | Pass |
| III. Privacy (DPDP) | Details are stored with the document and served with the same visibility rules; private names are never in shared lists, counts or filters (FR-010); corrections to shared documents are audited (FR-012). No text leaves the system for mapping. | Pass |
| IV. Accessibility | Details panel and filter bar use labelled form controls; confidence shown in words, not colour only; axe-tested both themes, both widths (FR-013). | Pass |
| V. Design system | Existing `.ka-*`, `.field`, chip styles and tokens. | Pass |
| VI. Simplicity | Regular expressions and keyword rules; no language model, no new dependency. | Pass |

Re-checked after design: pass.

## Project Structure

### Documentation (this feature)

```text
specs/008-metadata-mapping/
├── plan.md, research.md, data-model.md, quickstart.md
├── contracts/metadata-api.md
└── tasks.md
```

### Source Code

```text
backend/
├── alembic/versions/0009_document_details.py
├── src/mrcourt/
│   ├── models/knowledge.py           # + details JSON, doc_type, court, case_number, decided_on, language,
│   │                                 #   text_quality; DocumentReference table
│   ├── models/legal.py               # + LegalSource.sections (JSON list), chapter; document relationship;
│   │                                 #   court / decided_on properties read by the 009 ranker
│   ├── services/metadata.py          # NEW: extract(), apply(), remap(), short_label(), corrections
│   ├── services/knowledge.py         # map details after a document is read; list filters
│   ├── services/retrieval.py         # optional source filters; references also match LegalSource.sections
│   ├── services/references.py        # match() accepts a list of sections
│   ├── api/knowledge.py              # details GET/PATCH, remap POST, list filters, citation/passsage details
│   ├── api/questions.py, schemas/*   # question filters; citation `details` short label
└── tests/ unit/test_metadata.py, contract/test_document_details.py, integration/test_details_privacy.py
frontend/
├── src/services/knowledge.ts, questions.ts
├── src/components/DocumentDetails.tsx   # NEW: view/correct details with confidence
├── src/components/SourceFilters.tsx     # NEW: type/court/year/Act/section/case filters
├── src/pages/ask/KnowledgeTab.tsx, AskTab.tsx, components/PassageViewer.tsx
└── tests/e2e/document-details.spec.ts
```

**Structure Decision**: existing web-application layout; the extractor is a pure module so it can be unit
tested on fictional texts without a database.

## Complexity Tracking

None. One deliberate extra: `text_quality` ("readable" / "unreadable") is mapped too, because several real
documents have a broken text layer (legacy Tamil font encoding): mapping them would produce nonsense, so their
fields stay empty and the document is flagged for OCR instead.
