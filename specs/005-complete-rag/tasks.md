# Tasks: Complete RAG

**Input**: [spec.md](spec.md), [plan.md](plan.md). Builds on features 001 to 004. Tests are written before the code they check. Tests never call the real services: they use stand-ins (`set_embedder`, `set_ocr_engine`, `set_speech`); `conftest.py` and the end-to-end server blank the keys so `.env` is ignored.

## Phase 1: Foundation

- [X] T001 Record the baseline in `specs/005-complete-rag/baseline.md` (backend 412, unit 15, end-to-end 354)
- [X] T002 Add settings `voyage_api_key`, `sarvam_api_key`, `ocr_languages`, `embedding_model`, `stt_model`, `min_vector_score` in `backend/src/mrcourt/config.py`; blank the keys in `backend/tests/conftest.py` and `backend/scripts/e2e_server.py`
- [X] T003 Add `read_by_ocr`, `ocr_confidence`, `embedding_model` to `LegalSource`, `ocr_pages` to `KnowledgeDocument`, `conversation_id` to `Question`, and the `TextConversation` and `TextLine` models in `backend/src/mrcourt/models/`
- [X] T004 Write Alembic revision `0005` (idempotent) in `backend/alembic/versions/0005_complete_rag.py`

## Phase 2: User Story 1 - Meaning-based search (P1)

- [X] T005 [US1] Tests: fake and scripted embedders, fusion order, keyword fallback with `search_mode`, owner filter in both lists, no-source safety with vectors, in `backend/tests/unit/test_retrieval_fusion.py`
- [X] T006 [US1] Implement embedding providers (Voyage with batching and rate-limit retry, deterministic fake, `set_embedder`) in `backend/src/mrcourt/services/embeddings.py`
- [X] T007 [US1] Implement the vector list and reciprocal rank fusion, and return the search mode, in `backend/src/mrcourt/services/retrieval.py`; pass `search_mode` through `backend/src/mrcourt/services/answering.py`, `api/questions.py` and `schemas/questions.py`
- [X] T008 [US1] Embed passages in the background after add (files and pasted text) in `backend/src/mrcourt/services/knowledge.py` and `backend/src/mrcourt/api/knowledge.py`
- [X] T009 [US1] Implement the one-off `embed_missing` command and the sample corpus embedding in `backend/src/mrcourt/services/embed_missing.py` and `backend/src/mrcourt/corpus/ingest.py`
- [X] T010 [US1] Extend `GET /assistant/status` with `search`, `speech`, `ocr`, and show the mode note on the Ask tab in `backend/src/mrcourt/api/assistant.py`, `frontend/src/services/assistant.ts`, `frontend/src/pages/ask/AskTab.tsx`
- [X] T011 [US1] Extend `backend/scripts/import_reference.py` to report keyword-only and combined results, cache vectors outside the repository, and print similarity ranges for relevant and off-topic questions
- [X] T012 [US1] Run it against the live embedding service, set `MIN_VECTOR_SCORE` from the numbers, and record results in `specs/005-complete-rag/quality-results.md`

## Phase 3: User Story 2 - OCR (P1)

- [X] T013 [US2] Tests: scanned PDF pages and images read with a stand-in engine, OCR marking and confidence, missing engine message, limits, English plus Tamil languages passed to the engine, in `backend/tests/unit/test_ocr.py` and `backend/tests/contract/test_knowledge_ocr.py`
- [X] T014 [US2] Implement the engine interface and Tesseract engine (availability check, language packs, rendering with pypdfium2) in `backend/src/mrcourt/services/ocr.py`
- [X] T015 [US2] Add `read_document` with OCR pages, image types and TIFF frames, keep `read_pages` for text, in `backend/src/mrcourt/services/ingest.py`; accept image files and mark passages in `backend/src/mrcourt/services/knowledge.py`
- [X] T016 [US2] Show OCR marking and low-confidence notes in the Knowledge tab and accept image files in the add form in `frontend/src/pages/ask/KnowledgeTab.tsx`, `frontend/src/services/knowledge.ts`

## Phase 4: User Story 3 - Tamil and other languages (P2)

- [X] T017 [US3] Tests: script detection, source-language note, keyword-only honest message, Tamil question found by a scripted embedder, in `backend/tests/unit/test_language.py` and `backend/tests/contract/test_ask_language.py`
- [X] T018 [US3] Implement script detection and the notes in `backend/src/mrcourt/services/language.py` and apply them in `backend/src/mrcourt/api/questions.py` and `backend/src/mrcourt/api/assistant.py`; show the note in `frontend/src/components/ChatMessage.tsx`

## Phase 5: Speech and User Story 4 - Text Assistant (P2)

- [X] T019 [US4] Tests: transcription endpoint (no storage, size, rate limit, unavailable), conversations (private, lines, edit, remove, soft delete keeps History entry, export and deletion), PDF, add to knowledge by role, in `backend/tests/contract/test_speech.py` and `backend/tests/contract/test_text_assistant.py`
- [X] T020 [US4] Implement the speech providers and `set_speech` in `backend/src/mrcourt/providers/speech.py` and `POST /speech/transcribe` in `backend/src/mrcourt/api/speech.py`
- [X] T021 [US4] Implement conversations, lines, PDF and add-to-knowledge in `backend/src/mrcourt/services/text_assistant.py` and `backend/src/mrcourt/api/text.py`, with the History row kept in step
- [X] T022 [US4] Include conversations in export and deletion in `backend/src/mrcourt/services/privacy.py`
- [X] T023 [US4] Build the WAV recorder (16 kHz mono) and the transcription hook in `frontend/src/services/wav.ts` and `frontend/src/hooks/useRecorder.ts`
- [X] T024 [US4] Build the Text Assistant tab (notice, language, mic, lines, edit, remove, PDF, add to knowledge, delete) in `frontend/src/pages/ask/TextAssistantTab.tsx`, `frontend/src/services/text.ts`, and add the tab in `frontend/src/pages/Ask.tsx`
- [X] T025 [US4] Add the "Better for Tamil" option to the Ask voice controls in `frontend/src/components/VoiceButton.tsx` and `frontend/src/pages/ask/AskTab.tsx`
- [X] T026 [US4] End-to-end tests with a fake microphone and the stand-in speech service in `frontend/tests/e2e/text-assistant.spec.ts`; give the end-to-end server a fake speech service and fake embedder in `backend/scripts/e2e_server.py`

## Phase 6: User Stories 5 and 6 - History filter and citations (P3)

- [X] T027 [US5] Tests: source filter, text entries, entry kept after deletion, in `backend/tests/contract/test_history_text.py`; implement in `backend/src/mrcourt/services/history.py` and `backend/src/mrcourt/api/history.py`
- [X] T028 [US5] Add the source filter and text entries (open shows lines) to `frontend/src/pages/ask/HistoryTab.tsx` and `frontend/src/services/history.ts`
- [X] T029 [US6] Tests and implementation of `GET /knowledge/passages/{id}` (visibility, removed passage) in `backend/tests/contract/test_passage_view.py` and `backend/src/mrcourt/api/knowledge.py`
- [X] T030 [US6] Make citations openable (dialog with text, title, page, OCR marking, removed-source message) in `frontend/src/components/PassageViewer.tsx` and `frontend/src/components/ChatMessage.tsx`
- [X] T031 [US5] End-to-end tests for History source filter and openable citations in `frontend/tests/e2e/history-sources.spec.ts`

## Phase 7: Polish and verification

- [X] T032 Accessibility checks for the Text Assistant tab, passage dialog, History filter and Knowledge tab with OCR rows in `frontend/tests/e2e/a11y.spec.ts`
- [X] T033 Settings and README: name the embedding and speech services and what is sent, document `.env`, Tesseract install (English and Tamil data), the embed command, rotating the keys, in `frontend/src/pages/Settings.tsx` and `README.md`
- [X] T034 Migrate the dev database, run `embed_missing`, restart the dev servers, and check the screens
- [X] T035 Run the full regression twice in a row and write `specs/005-complete-rag/quickstart-results.md`
- [ ] T036 Legal and policy review by a person: sending question and passage text to the embedding service and audio to the speech service, OCR accuracy on real documents (cannot be done by the build; leave open)

## Order and strategy

- Phase 1 first. Phase 2 is the core and the MVP. OCR, language, and the Text Assistant are independent after Phase 1. Phase 6 needs Phases 2 and 5. Polish last.
- Within a phase, tests come before the code they check.
