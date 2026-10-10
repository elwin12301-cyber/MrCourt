# Tasks: AI Assistant Upgrade

**Input**: [spec.md](spec.md), [plan.md](plan.md), [data-model.md](data-model.md), [contracts/assistant-api.md](contracts/assistant-api.md), [research.md](research.md). Builds on features 001 to 003. Tests are included and written before the code they check. Browser tests use a scripted model, so they need no key and no network.

## Phase 1: Foundation

- [X] T001 Record the baseline (backend, unit and browser test counts) in `specs/004-ai-assistant-upgrade/baseline.md`
- [X] T002 Add `pypdf` to `backend/pyproject.toml` and install it in `backend/.venv`
- [X] T003 Add the `KnowledgeDocument` and `ProposedAction` models in `backend/src/mrcourt/models/knowledge.py`, extend `LegalSource` (document_id, owner_id, page), `Question` (input_method, mode), `Answer` (answer_mode, steps) and `AnswerCitation` (label, nullable source_id) in `backend/src/mrcourt/models/legal.py`, and export them from `backend/src/mrcourt/models/__init__.py`
- [X] T004 Write Alembic revision `0004` (new tables and columns, backfill one shared ready document per existing passage and a citation label snapshot, safe on fresh and old databases) in `backend/alembic/versions/0004_ai_assistant.py`
- [X] T005 Add settings `knowledge_dir`, `max_knowledge_bytes` (10 MB), `max_knowledge_pages` (300), `assistant_max_steps` (6), `assistant_model` in `backend/src/mrcourt/config.py` and document them in `backend/.env.example`
- [X] T006 Add `GET /assistant/status` (mode and whether the assistant is on, per role) in `backend/src/mrcourt/api/assistant.py`, `backend/src/mrcourt/schemas/assistant.py`, and register the router in `backend/src/mrcourt/main.py`
- [X] T007 Update the test fixtures so tests can create shared and private documents and plug in a scripted model, in `backend/tests/conftest.py`

## Phase 2: User Story 1 - Cited answers from the knowledge base (P1)

**Independent test**: ask covered and uncovered questions and see cited and "no reliable source" answers; private passages are never retrieved for anyone else.

- [X] T008 [US1] Tests: owner filter (shared plus own private only), private passage never cited for others, BM25 ranks the right passage in a long document first, minimum-evidence rule still returns nothing for unrelated questions, in `backend/tests/unit/test_retrieval_owner.py`
- [X] T009 [US1] Make retrieval user-aware with the owner filter inside the query and BM25 scoring over candidates, ready documents only, in `backend/src/mrcourt/services/retrieval.py`
- [X] T010 [US1] Tests: answers carry `answer_mode`, passages-only note without a key, injection text in a question or a passage does not change behaviour, client replies keep the lawyer reminder, in `backend/tests/contract/test_ask_upgrade.py`
- [X] T011 [US1] Pass the asker into answering, record `answer_mode`, snapshot citation labels, keep the constant system prompt, in `backend/src/mrcourt/services/answering.py`
- [X] T012 [US1] Accept `input_method`, return `question_id`, `answer_mode` and paragraph `kind`, in `backend/src/mrcourt/api/questions.py` and `backend/src/mrcourt/schemas/questions.py`
- [X] T013 [US1] Turn Ask into the tabbed shell (Ask, Knowledge Base, History) using the existing tab pattern, routes `/ask`, `/ask/knowledge`, `/ask/history`, in `frontend/src/pages/Ask.tsx`, `frontend/src/pages/ask/AskTab.tsx` and `frontend/src/App.tsx`
- [X] T014 [US1] Show the mode note ("Running with cited passages only") and the privacy line about the AI service in the Ask tab, with hooks in `frontend/src/services/assistant.ts`
- [X] T015 [US1] End-to-end test: tabs, cited answer, no-source answer, passages-only note, in `frontend/tests/e2e/ask-tabs.spec.ts`

## Phase 3: User Story 3 - Build and manage the knowledge base (P1)

**Independent test**: an administrator adds a shared source and sees it Ready and cited; an advocate's private note is used only for that advocate; removal stops use and keeps old citation labels.

- [X] T016 [US3] Tests: add text and PDF, status transitions, failed reasons (empty, scan-like, too large, unsupported), duplicates, who may add or remove what, removal deletes file and passages, old answers keep labels, audit entries for shared add and remove, in `backend/tests/contract/test_knowledge.py` and `backend/tests/integration/test_knowledge_removal.py`
- [X] T017 [US3] Implement extraction and page-aware chunking (about 1,000 characters, no page crossing, overlap) in `backend/src/mrcourt/services/ingest.py`
- [X] T018 [US3] Implement add, list, remove and the stale-processing rule in `backend/src/mrcourt/services/knowledge.py`
- [X] T019 [US3] Implement `/knowledge/documents` endpoints with a background task, upload limits, per-role rules, rate limit and audit entries, in `backend/src/mrcourt/api/knowledge.py` and `backend/src/mrcourt/schemas/knowledge.py`
- [X] T020 [US3] Add audit labels for `knowledge.add` and `knowledge.remove` in `backend/src/mrcourt/services/audit.py` (never store file contents)
- [X] T021 [US3] Build the Knowledge Base tab (list, search, add form for text or file, status with polling, remove with confirmation) in `frontend/src/pages/ask/KnowledgeTab.tsx` and `frontend/src/services/knowledge.ts`
- [X] T022 [US3] Add the administrator "Knowledge base" menu item and page reusing the tab content in `frontend/src/components/AppShell.tsx`, `frontend/src/App.tsx` and `frontend/src/pages/AdminKnowledge.tsx`
- [X] T023 [US3] End-to-end tests: administrator shared source, advocate private note invisible to others, removal, failed upload, client read-only, in `frontend/tests/e2e/knowledge.spec.ts`

## Phase 4: User Story 2 - The assistant that works in steps (P1)

**Independent test**: an advocate asks for next week's hearings and gets the right list with steps; a draft proposal creates nothing until confirmed; a client's assistant sees only the client view.

- [X] T024 [US2] Tests with a scripted model: steps recorded in order; advocate tools return only own data; client tools use only the client view and never private notes, internal documents or other cases; tool arguments cannot name another user; prompt injection in a question, passage or case field does not widen access; 6-step cap; failure produces an honest message; law paragraphs without verified citations are dropped, in `backend/tests/contract/test_assistant.py` and `backend/tests/integration/test_assistant_privacy.py`
- [X] T025 [US2] Tests: proposal creates no draft; confirm creates one editable draft flagged for review; decline, expiry, reuse, other user's id and clients all change nothing, in `backend/tests/contract/test_assistant_actions.py`
- [X] T026 [US2] Implement the tool set bound to the user (advocate and client variants, contact details left out) in `backend/src/mrcourt/services/assistant_tools.py`
- [X] T027 [US2] Implement the loop with an injectable model, typed final reply, citation verification and step recording in `backend/src/mrcourt/services/assistant.py`
- [X] T028 [US2] Implement proposals, confirm and decline using the existing draft creation in `backend/src/mrcourt/services/assistant_actions.py`
- [X] T029 [US2] Implement `/assistant/requests`, `/assistant/actions/{id}/confirm` and `/decline` with rate limits and role rules in `backend/src/mrcourt/api/assistant.py`
- [X] T030 [US2] Build the Assistant mode in the Ask tab: toggle, disabled note without a key, steps list, law and case paragraphs, in `frontend/src/components/AssistantSteps.tsx` and `frontend/src/pages/ask/AskTab.tsx`
- [X] T031 [US2] Build the confirmation card (what will be created, Confirm and Decline, result link to the draft) in `frontend/src/components/ProposedAction.tsx`
- [X] T032 [US2] End-to-end tests with the scripted model: advocate hearings and draft confirmation, decline leaves Drafts unchanged, client has no draft proposals, in `frontend/tests/e2e/assistant.spec.ts`

## Phase 5: User Story 4 - Question history (P2)

**Independent test**: ask typed, voice and no-answer questions; search, filter, open and ask again; only the asker sees them; export and deletion include them.

- [X] T033 [US4] Tests: list is own-only, newest first, search, outcome and input filters, pagination, open returns stored answer with labels of removed passages, other person's id is 404, export includes questions and own private notes, deactivation removes them, in `backend/tests/contract/test_history.py`
- [X] T034 [US4] Tests: administrator list of a person's questions writes `history.view` with no text, non-admins are refused, in `backend/tests/contract/test_admin_history.py`
- [X] T035 [US4] Implement history list and open in `backend/src/mrcourt/services/history.py`, `backend/src/mrcourt/api/history.py` and `backend/src/mrcourt/schemas/history.py`
- [X] T036 [US4] Extend export and deactivation to cover questions, steps, proposed actions and private documents in `backend/src/mrcourt/services/privacy.py`
- [X] T037 [US4] Implement `GET /admin/users/{id}/questions` with the audit entry in `backend/src/mrcourt/api/admin.py` and `backend/src/mrcourt/services/admin_users.py`, and the audit label in `backend/src/mrcourt/services/audit.py`
- [X] T038 [US4] Build the History tab (search, two filters, rows with Open and Ask again, empty state) in `frontend/src/pages/ask/HistoryTab.tsx` and `frontend/src/services/history.ts`
- [X] T039 [US4] Add the "Questions asked" card with a "Show questions" button on the person page in `frontend/src/pages/AdminUserDetail.tsx` and `frontend/src/services/admin.ts`
- [X] T040 [US4] End-to-end tests for history and the administrator view in `frontend/tests/e2e/history.spec.ts`

## Phase 6: User Story 5 - Voice to text (P2)

**Independent test**: with a faked recognition engine, speech fills the box with clear states; unsupported and denied cases show messages; keyboard operation works; the question is recorded as Voice.

- [X] T041 [US5] Tests (Vitest): hook states idle, listening, unsupported, denied, error; interim text; language choice; `usedVoice` stays true after editing; stop on second press, in `frontend/src/hooks/useSpeechInput.test.ts`
- [X] T042 [US5] Rework the hook with states, languages, interim results and `usedVoice` in `frontend/src/hooks/useSpeechInput.ts`
- [X] T043 [US5] Build the labelled microphone button, language select and polite live-region announcements, and use it in Ask and the dashboard quick-ask, in `frontend/src/components/VoiceButton.tsx`, `frontend/src/pages/ask/AskTab.tsx` and `frontend/src/pages/Dashboard.tsx`
- [X] T044 [US5] Send `input_method` with each question and show the privacy line about browser speech recognition in the voice help text in `frontend/src/services/assistant.ts`
- [X] T045 [US5] End-to-end tests with a faked `SpeechRecognition` (granted, unsupported, denied, keyboard only) in `frontend/tests/e2e/voice.spec.ts`

## Phase 7: Reference data and quality

- [X] T046 Write the import and evaluation script (`--source`, `--questions`; imports text PDFs as shared documents, reads the Q and A file, reports the retrieval hit rate and misses; refuses to write into the repository) in `backend/scripts/import_reference.py`
- [X] T047 Run it on the reference documents and the English question file, record the hit rate and misses in `specs/004-ai-assistant-upgrade/quality-results.md`; if below 90%, record the finding and propose adding embeddings

## Phase 8: Polish and verification

- [X] T048 Accessibility checks for the three tabs, assistant steps, confirmation card, voice button and admin knowledge page in both themes at desktop and mobile widths, in `frontend/tests/e2e/a11y.spec.ts`
- [X] T049 Add "your question and any case details it needs are sent to the AI service" to the privacy section of Settings and to the README, plus the setup notes (key, `pypdf`, migration, reference import), in `frontend/src/pages/Settings.tsx` and `README.md`
- [X] T050 Rebuild the dev database (`alembic upgrade head`, seed, ingest) and restart the dev API, then check the screens by hand against [quickstart.md](quickstart.md)
- [X] T051 Run the full regression twice in a row (backend, Vitest, tsc, eslint, Playwright desktop and mobile) and write `specs/004-ai-assistant-upgrade/quickstart-results.md`
- [ ] T052 Legal and policy review by a person: sending questions and case details to a third-party AI service, retention of question history, and administrator access to it, against the DPDP Act and the organisation's policy (cannot be done by the build; leave open and flag)

## Dependencies and order

- Phase 1 first. Phase 2 needs T003 to T006. Phase 3 needs Phase 1 and T009 (retrieval) and can start once T009 is done. Phase 4 needs Phase 2 and the knowledge search from T009. Phase 5 needs Phase 1 and T012. Phase 6 is independent after T013. Phase 7 needs Phases 2 and 3. Phase 8 last.
- Within a phase, tests come before the code they check.

## Parallel opportunities

- T008 and T010 (different test files) together; T016 and T033 and T041 are independent test files.
- Frontend tabs T021, T038 and T043 touch different files once T013 exists.
- T046 can be written while Phase 4 is built.

## Implementation strategy

- **MVP**: Phases 1 to 3 (cited answers and a managed knowledge base). This already delivers the RAG system.
- **Then**: Phase 4 (assistant), Phase 5 (history), Phase 6 (voice), then the quality run (Phase 7) and verification.
