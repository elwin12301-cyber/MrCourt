# Implementation Plan: AI Assistant Upgrade

**Branch**: `004-ai-assistant-upgrade` | **Date**: 2026-10-08 | **Spec**: [spec.md](spec.md)

## Summary

Turn Ask MrCourt into three tabs (Ask, Knowledge Base, History) and add an assistant that works in steps. Knowledge becomes managed documents split into page-aware passages, searched with a stronger lexical ranking, and restricted by owner so private notes never reach anyone else. The assistant is a small tool-using loop around the Claude API whose tools are read-only, except one that only *proposes* a draft; nothing is created until the person confirms. History reuses the stored questions and answers. Voice stays browser-only and gets clear states, language choice and dictation tracking.

## Technical Context

Same stack as features 001 to 003 (FastAPI, SQLAlchemy, Alembic; React, TypeScript, TanStack Query; SQLite in tests, PostgreSQL target).

**New dependency**: `pypdf` (read text PDFs). Everything else already exists (`anthropic`, `python-docx`, `fpdf2`).

**Key design decisions** (reasons in [research.md](research.md))

- **Documents and passages.** New table `knowledge_documents` (title, citation, kind, owner, status). The existing `legal_sources` rows become the passages (chunks), gaining `document_id`, `owner_id` (null means shared) and `page`. Existing five passages are backfilled into one document each, owned by nobody (shared).
- **Owner filter inside the query.** Retrieval takes the asking user and only ever loads passages that are shared or owned by that user. There is no code path that loads private passages and filters afterwards.
- **Ranking.** Keep the current candidate step and minimum-evidence rule, replace the "share of terms" score by BM25-style scoring over the candidate passages, and keep neighbouring passages from the same page together. Embeddings are not added now; they are the fallback if the quality target in SC-001 is missed (see Key Risks).
- **Ingestion.** Upload saves the file, creates the document as `processing`, and a background task extracts text (plain text, text PDF), splits into ~1,000 character passages that never cross a page, and sets `ready` or `failed` with a plain reason. No scanning of images (out of scope).
- **Removal.** Removing a document deletes its file, its passages and the document row. Past answers keep their citation through a label snapshot added to `answer_citations`; the passage text is not kept, so removing a private note really removes it.
- **Assistant loop.** `services/assistant.py` runs at most 6 model turns. Tools are plain functions bound to the signed-in user:
  - advocate: `list_cases`, `get_case`, `list_hearings`, `search_knowledge`, `propose_draft`
  - client: `list_my_cases`, `get_my_case` (built on the existing client view), `list_my_hearings`, `search_knowledge`
  The user id is bound when tools are created; the model never supplies it. `propose_draft` only writes a `proposed_actions` row.
- **Answer shape.** The assistant's final reply is the same paragraph structure as an answer, each paragraph marked `law` (must cite passages found by `search_knowledge` in this run and passes the existing citation check) or `case` (from tool results, no citation needed). A `law` paragraph that fails verification is dropped; if none remain for a legal question the outcome is "no reliable source".
- **Confirmation.** `POST /assistant/actions/{id}/confirm` runs the existing `create_draft` as that user, once. Actions expire after 10 minutes, belong to one user, and decline or expiry changes nothing.
- **No key, no agent.** `/assistant/status` reports `{answers: "full"|"passages", assistant: true|false}`. Without `ANTHROPIC_API_KEY` the assistant is off and Ask uses the extractive generator, with a visible note.
- **History.** `questions` gains `input_method` and `mode`; `answers` gains `steps` (JSON) and `answer_mode`. `GET /history` lists the caller's own questions only. Admin view of someone else's history is `GET /admin/users/{id}/questions`, which writes a `history.view` audit entry that holds no question text.
- **Privacy of the model service.** Questions, passages and, in assistant mode, the case details a tool returns are sent to the Claude API. Tool results leave out phone, email and address. The Ask screen says so beside the Assistant toggle, and Settings > privacy gains a line.
- **Voice.** Keep browser recognition. `useSpeechInput` gains states (idle, listening, unsupported, denied, error), language choice, live interim text, a polite live-region announcement and a flag saying the question used dictation, sent as `input_method`.

**Source layout (new or changed)**

```text
backend/src/mrcourt/models/knowledge.py            # KnowledgeDocument, ProposedAction
backend/src/mrcourt/models/legal.py                # + document_id, owner_id, page; Question + input_method, mode; Answer + steps, answer_mode; AnswerCitation + label
backend/src/mrcourt/services/knowledge.py          # add, list, remove, status
backend/src/mrcourt/services/ingest.py             # extract, chunk, publish
backend/src/mrcourt/services/retrieval.py          # owner filter, BM25 scoring
backend/src/mrcourt/services/answering.py          # user-aware, answer_mode
backend/src/mrcourt/services/assistant.py          # loop, tools, steps, proposals
backend/src/mrcourt/services/history.py            # list, open
backend/src/mrcourt/api/knowledge.py               # /knowledge/*
backend/src/mrcourt/api/assistant.py               # /assistant/*
backend/src/mrcourt/api/history.py                 # /history/*
backend/src/mrcourt/api/admin.py                   # + /admin/users/{id}/questions
backend/src/mrcourt/schemas/{knowledge,assistant,history}.py
backend/alembic/versions/0004_ai_assistant.py
backend/scripts/import_reference.py                # import RAG docs, run the question-set evaluation
frontend/src/pages/Ask.tsx                         # becomes the tabbed shell
frontend/src/pages/ask/{AskTab,KnowledgeTab,HistoryTab}.tsx
frontend/src/components/{AssistantSteps,ProposedAction,VoiceButton}.tsx
frontend/src/hooks/useSpeechInput.ts               # states, language, interim text
frontend/src/services/{assistant,knowledge,history}.ts
frontend/src/pages/AdminKnowledge.tsx              # admin menu item "Knowledge base"
```

## Constitution Check

| Principle | Gate | Status |
|-----------|------|--------|
| I. Grounded, cited answers | Law paragraphs must cite passages and pass the existing verification; no passage means "no reliable source"; assistant `law` paragraphs obey the same rule | PASS |
| II. Not legal advice | Notice on every answer and assistant reply; client replies keep the lawyer prompt and the case-specific guard; drafts are created only after confirmation and stay editable and flagged | PASS |
| III. Privacy by design (DPDP) | Private notes filtered in the query; assistant limited to the person's own data; contact details left out of tool results; history exported and deleted with the account; admin history views audited without text; disclosure of the model service on screen | PASS WITH NOTE: sending case details to a third-party model service needs a legal and policy review before launch (task at the end) |
| IV. Accessible and responsive | Tabs pattern from case detail, labelled mic button with live announcements, axe scans for new screens in both themes | PASS |
| V. Design system | Existing tabs, cards, chips, table styles; no new colours | PASS |
| VI. Simplicity | Justified additions below | PASS |

Re-check after design: unchanged.

## Complexity Tracking

| Addition | Why needed | Simpler alternative rejected because |
|----------|-----------|--------------------------------------|
| `knowledge_documents` table beside passages | Users manage whole documents (title, status, remove), while search works on passages | Managing raw passages would show hundreds of rows per judgment |
| Tool loop for the assistant | The owner asked for multi-step actions with visible steps | A single prompt cannot look things up, and could not show its steps |
| `proposed_actions` table | Confirmation must be single-use, per person and expiring | A flag in the browser could be replayed or forged |
| `pypdf` | Judgments are PDFs | Asking users to paste text defeats uploading |

## Key Risks

- **Quality target (SC-001).** Lexical ranking may miss questions worded differently from the judgment. The evaluation script measures it on the reference question set; if the target is missed, add embeddings (an interface already exists in `services/embeddings.py`) before shipping.
- **Prompt injection.** Passages and case fields are passed as data in the user turn; the system prompt is constant; tool arguments are validated and ids come from the bound user, so injected text cannot widen access. Tests cover this.
- **Cost and abuse.** Per-user rate limits (answers 30/min as today, assistant 10/min, uploads 10/hour) and a hard cap of 6 model turns per assistant request.
- **Model service outages.** Every failure falls back to passages-only or a calm message; nothing is stored as an answer that was not produced.
- **Voice quality for Indian languages** varies by browser; the screen says so, and typing always works.
- **Real court data.** The reference documents are not copied into the repository; import runs from a local path.
