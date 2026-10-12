# Research: Metadata mapping

## 1. How to extract

- **Decision**: Rules and regular expressions over the first pages (header details) and the last pages (outcome),
  plus the whole text for Acts and sections. Indian court documents have stable headers: "IN THE HIGH COURT OF
  JUDICATURE AT MADRAS", "RESERVED ON / DELIVERED ON / DATED :", "CORAM: THE HONOURABLE MR. JUSTICE ...",
  "... Appellant / Petitioner / Plaintiff", "Vs", "... Respondents / Defendants", case numbers such as
  "S.A.No.1106 of 2019", "W.P.No.11944 of 2013", CNR codes.
- **Rationale**: Deterministic, explainable, no outside service (privacy, cost), and FR-003 is easy to keep: a
  value is stored only with the matched text behind it.
- **Alternatives**: a language model (could invent values; sends private text out; cost); a trained tagger
  (no labelled data).

## 2. Confidence

- **found**: matched a labelled pattern (e.g. "DELIVERED ON : 07.04.2025", "IN THE HIGH COURT OF ...").
- **likely**: unlabelled or ambiguous evidence (first date in the document; several candidate values; type
  inferred from the title only). Alternatives are kept so the owner can pick.
- **not_found**: nothing matched; value empty.
- **confirmed**: set or confirmed by a person; never overwritten by re-mapping.

## 3. Unreadable text

- **Decision**: `text_quality = "unreadable"` when the text has almost no English function words and almost no
  Tamil Unicode letters (the signature of a broken legacy-font text layer). Then every field stays `not_found`,
  except type/case number taken from the title as `likely`, and the Knowledge base shows "Text could not be read:
  needs OCR". Measured on the real documents: 7 of 9 private case PDFs are unreadable this way.
- **Alternatives**: map anyway (nonsense values); drop the document (loses keyword search on the title).

## 4. Statute pages

- **Decision**: For shared `act_section` documents, headings like "21. Protection of life and personal liberty.—"
  or "Section 299" on a page give that passage its section numbers (`sections` list; `section` when exactly one).
  Pages that look like a list of contents (more than 4 headings in a row) are skipped. CHAPTER headings give
  `chapter`. The 009 reference matcher treats a number in `sections` as the passage *being* that section.

## 5. Court names

- **Decision**: Normalise to one spelling: "High Court of Judicature at Madras" → "Madras High Court",
  "Supreme Court of India", "<Place> District Court", "Sub Court, <Place>", "District Munsif Court, <Place>".
  Unknown forms are kept as written (found) so nothing is lost.

## 6. Filters

- **Decision**: Indexed columns on `knowledge_documents` (doc_type, court, case_number, decided_on, language) and
  a `document_references (document_id, act, section)` table. Search filters join passages to documents; statute
  sections also match passage `sections`. The same filters are accepted by the Knowledge base list and by
  questions.

## 7. Privacy

- **Decision**: Details live on the document row and are returned only where the document itself may be seen
  (shared to all signed-in users who can use the knowledge base; private to the owner). Filter options (lists
  of courts, years) are computed per person from the documents they can see, so private values never appear in
  anyone else's options. Administrators see shared details and edit them (audited); they do not get private
  details through these endpoints.
