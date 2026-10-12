# Feature Specification: Metadata mapping for the knowledge base

**Feature Branch**: `008-metadata-mapping`

**Created**: 2026-10-12

**Status**: Draft

**Input**: User description: "Metadata mapping for the MrCourt knowledge base. When a legal document is added (law PDFs, judgments, orders, petitions, sale deeds, cross-examinations, uploaded by an administrator as shared sources or by an advocate as private case documents), MrCourt extracts structured metadata and maps it to standard fields [...] can be used to filter search [...] existing documents can be mapped again in bulk. Privacy: metadata of private case documents is visible only to their owner [...] Extraction must not invent values: an unknown field stays empty."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every document gets mapped details I can check and correct (Priority: P1)

An advocate adds a judgment to their private knowledge. When it is ready, the document shows its mapped details: document type, court, case number, case title, parties, judges, date, Acts and sections referred to, outcome and language. Each detail shows how sure MrCourt is (found in the text / likely / not found). The advocate corrects a wrong court name and fills in a missing date; the corrections are kept, and mapping the document again never overwrites them.

**Why this priority**: Everything else (filters, better citations, ranking) depends on reliable details, and the person who added the document is the only one who can confirm them.

**Independent Test**: Add one judgment and one statute PDF; check that the expected details appear with confidence marks, that unknown fields stay empty, and that a correction survives a re-map.

**Acceptance Scenarios**:

1. **Given** a judgment PDF is added, **When** processing finishes, **Then** its type, court, case number, parties, judges, date, Acts/sections and outcome are shown where the text states them, each with a confidence mark.
2. **Given** a detail is not stated in the document, **Then** the field is empty and marked "not found"; nothing is guessed.
3. **Given** the owner corrects a field, **When** the document is mapped again, **Then** the corrected value is kept and marked "confirmed by you".
4. **Given** a statute (for example the Indian Penal Code), **Then** each passage is mapped to its Act, chapter and section number.
5. **Given** a passage of a judgment, **Then** it is linked to its case (title, court, date) so a citation can name the case.

---

### User Story 2 - Filter search and questions by these details (Priority: P1)

In the Knowledge base an advocate filters by document type, court, year, Act/section and case. When asking a question, they can limit the answer to, for example, "judgments of the Madras High Court" or "Section 420 IPC"; answers then cite only matching passages.

**Why this priority**: This is the main benefit users feel: finding the right source fast and getting answers from the right kind of document.

**Independent Test**: With mapped documents in place, apply each filter alone and together and check that only matching documents and passages appear and are cited.

**Acceptance Scenarios**:

1. **Given** filters for type = judgment and year = 2013, **Then** only 2013 judgments the person may see are listed.
2. **Given** a question limited to "Section 420 IPC", **Then** every citation in the answer is a passage mapped to that section or a case referring to it.
3. **Given** a filter that matches nothing, **Then** the person is told no source matches and no answer is made up.
4. **Given** a client (petitioner), **Then** filters work only over shared sources, never over any advocate's private documents.

---

### User Story 3 - Details shown on citations and in the passage viewer (Priority: P2)

Every citation shows the mapped details in short form (for example "Judgment · Madras High Court · 12 Mar 2013 · W.P. 11944/2013" or "IPC s. 379"). Opening the passage shows all mapped details of its document.

**Why this priority**: Makes answers easier to trust and check, but depends on Story 1.

**Independent Test**: Ask a question answered from a mapped judgment and a mapped statute; check both citation forms and the viewer.

**Acceptance Scenarios**:

1. **Given** an answer cites a judgment passage, **Then** the citation shows type, court, date and case number where known.
2. **Given** an answer cites a statute passage, **Then** the citation shows the Act and section.
3. **Given** a field is unknown, **Then** it is left out of the citation (never shown as "unknown" text in the middle).

---

### User Story 4 - Map existing documents again in bulk (Priority: P2)

An administrator runs mapping over all shared documents, and an advocate over all their private documents, for documents added before this feature or after the mapping rules improve. Progress is shown; corrected fields are kept.

**Independent Test**: Run bulk mapping on the existing law PDFs and the private case documents; check counts of mapped documents, passages and fields, and that earlier corrections are unchanged.

**Acceptance Scenarios**:

1. **Given** documents without details, **When** bulk mapping runs, **Then** each gets mapped and a summary shows how many fields were found per type.
2. **Given** an administrator, **Then** bulk mapping covers only shared documents, never advocates' private documents.

---

### Edge Cases

- Scanned (image) documents: mapping uses the text read from them; low reading confidence lowers field confidence.
- Tamil or mixed-language documents: the language is mapped; fields are read in either language where stated.
- Old and new criminal laws: IPC/CrPC/Evidence Act sections and BNS/BNSS/BSA sections are kept as written, never converted automatically.
- Several case numbers in one document (for example a connected appeal): all are kept; one is marked as the main case.
- Contradictory values in the text (two dates): the field is marked "likely" and both values are offered to the owner.
- Very long documents: mapping finishes within the same limits as reading the document; it never blocks the document from being searchable.
- Private documents name real people: those names are shown only to the owner and are never used in shared filters, lists or statistics.
- A document is removed: its details are removed with it.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Each added document MUST be mapped to these fields: document type (statute, judgment, order, petition, deed, deposition/cross-examination, notice, other), court and bench, case number(s) and CNR, case title, parties by side, judge(s), date of decision or filing, Acts and sections referred to, outcome, language.
- **FR-002**: Each passage MUST be mapped to its own Act, chapter and section for statutes, and to its document's case for other types.
- **FR-003**: Mapping MUST NOT invent values: a field is filled only from text in the document (or a correction by a person); otherwise it stays empty.
- **FR-004**: Each field MUST carry a confidence state: found, likely, not found, or confirmed by a person.
- **FR-005**: The person who added a document (and, for shared documents, administrators) MUST be able to view, correct and complete the fields; corrections MUST survive later re-mapping.
- **FR-006**: The Knowledge base MUST offer filters by type, court, year, Act/section and case, alone and combined.
- **FR-007**: Asking a question MUST allow the same filters, and citations MUST then come only from matching passages; with no match the answer says so.
- **FR-008**: Citations and the passage viewer MUST show the mapped details in short form, leaving out unknown fields.
- **FR-009**: Mapping MUST run automatically for new documents and on request in bulk for existing ones, with a progress summary.
- **FR-010**: Details of private documents MUST be visible only to their owner; they MUST NOT appear in shared filters, lists, counts or answers for anyone else, and the existing rule that clients see only shared sources MUST hold.
- **FR-011**: Sections MUST be recorded as written in the document (old or new criminal law), with the Act named.
- **FR-012**: Corrections to shared documents MUST be recorded in the administrator audit log.
- **FR-013**: All new screens MUST meet the project's accessibility rules in both themes at desktop and phone widths.

### Key Entities

- **Document details**: one per document; the fields of FR-001, each with its value(s), confidence state and source (text or person).
- **Passage details**: one per passage; Act, chapter and section for statutes, or a link to the document's case.
- **Correction**: a field value set by a person; who, when, old and new value (audited for shared documents).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a test set of at least 20 real-format documents (statutes, judgments, orders, deeds), at least 90% of fields marked "found" are correct, and no field is filled with a value absent from the document.
- **SC-002**: At least 95% of statute passages are mapped to the right Act and section.
- **SC-003**: Using a filter, an advocate finds a known judgment among 50+ documents in under 30 seconds.
- **SC-004**: With a section filter, 100% of citations in tested answers belong to that section or to a case referring to it.
- **SC-005**: No private document detail is ever returned to another user in tests of lists, filters, counts and answers.

## Assumptions

- Mapping uses the text MrCourt already reads from documents; no new outside service is required. If a language model is later used to help, it may only propose values that are then checked against the text (FR-003).
- The existing 35 law PDFs and the private case documents are mapped by bulk mapping after release.
- Filters on questions reuse the existing answer rules: grounded, cited answers only, and "no reliable source" when nothing matches.
- Court names are normalised to one spelling per court (for example "High Court of Judicature at Madras" and "Madras High Court" become one value).
- The confidence states are shown in words and icons, not only colour.
