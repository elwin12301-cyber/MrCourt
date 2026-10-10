# Research: AI Assistant Upgrade

No open clarifications remained after the spec; this records the choices behind the plan.

## R1. How to model knowledge

- **Decision**: `knowledge_documents` (what people manage) plus the existing `legal_sources` rows as passages (what search uses), linked by `document_id`, with `owner_id` and `page` on passages.
- **Rationale**: Reuses retrieval, citation verification and the answer pipeline, which already take `LegalSource`. Existing data backfills as one document per passage.
- **Alternatives**: a new passages table (duplicates working code); one row per document with the whole text (cannot cite pages, poor ranking).

## R2. Ranking and embeddings

- **Decision**: Keep candidate loading and the minimum-evidence rule; score with BM25 (term frequency, inverse document frequency, length normalisation) computed over the candidates, with the owner filter applied in the query. No embeddings yet.
- **Rationale**: Simplicity (principle VI). The current "share of terms" score favours short passages and cannot rank within a 14-page judgment. The evaluation script (R7) gives a number; embeddings are added only if SC-001 is missed.
- **Alternatives**: Voyage embeddings with fusion as in the reference RAG project (better recall, new paid key and a stored vector per passage); asking the model to rerank (cost per question, harder to test).

## R3. Reading files

- **Decision**: Plain text and text PDFs (`pypdf`), up to 10 MB and 300 pages. A PDF whose pages yield almost no text is marked Failed with "looks like a scan; scanned documents are not supported yet".
- **Rationale**: Matches the reference data: two English text PDFs work, four scanned Tamil ones do not.
- **Alternatives**: OCR now (Tesseract or model vision): large scope, separate feature.

## R4. Background work

- **Decision**: FastAPI background task after upload; status polled by the Knowledge tab.
- **Rationale**: Documents are small; no queue service needed. A task lost on restart leaves a document stuck in Processing, so a document still Processing after 10 minutes is shown as Failed ("did not finish") and can be removed.
- **Alternatives**: a job table and worker (reference project): overkill here.

## R5. Removing a source while keeping history

- **Decision**: `answer_citations` stores a `label` snapshot (and keeps `source_url`); `source_id` becomes nullable with set-null on delete. Removal deletes file, passages and document.
- **Rationale**: Removing a private note really erases its text, while old answers still show what they cited.
- **Alternatives**: soft delete (keeps text, unacceptable for private notes).

## R6. Assistant design

- **Decision**: Claude tool use, max 6 turns, tools bound to the user, final reply as typed paragraphs. Writes only via `proposed_actions` confirmed by a separate request.
- **Rationale**: The model never holds a write capability; ids and role come from the session; tests can replace the model with a scripted fake and assert tool calls, steps and confirmation rules without network.
- **Alternatives**: giving the model a create-draft tool guarded by a prompt (not a control); a hand-written planner without a model (cannot handle open requests).

## R7. Measuring answer quality

- **Decision**: `scripts/import_reference.py` takes `--source <folder>` (default the RAG project's `docs`), imports the text PDFs as shared documents, parses the English question file (`Qn. ... A: ... [page]`), and reports, per question, whether the best passages are on the expected page and contain most of the answer's significant terms. It prints a percentage and the misses. With a model key it can also run full answers; without, it measures retrieval only.
- **Rationale**: Retrieval is where lexical search can fail and is testable without a model or network. The Tamil file is reported separately (questions in Tamil against English passages are expected to score lower).
- **Alternatives**: a model-graded evaluation (costly and not repeatable).

## R8. Voice

- **Decision**: Keep the Web Speech API in a hook; add status states, a language list (en-IN, hi-IN, ta-IN, te-IN, kn-IN, ml-IN, mr-IN, bn-IN, gu-IN), `interimResults`, a live region, and `usedVoice` per question.
- **Rationale**: Honours the owner's choice (no audio to our servers). Browser support is the limit, and the screen says so.
- **Alternatives**: server transcription (the reference project's Sarvam service): more accurate for Tamil but transmits voice and costs money; recorded as a possible later upgrade.

## R9. Admin and history

- **Decision**: Admin history access is one endpoint under the person's page with an audit entry `history.view` (no text). The admin menu gains "Knowledge base" using the same tab content.
- **Rationale**: Satisfies FR-020 and the owner's earlier "everything, with a log" decision from feature 003.
