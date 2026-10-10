# Quickstart: AI Assistant Upgrade

Validation guide. Endpoints are in [contracts/assistant-api.md](contracts/assistant-api.md), tables in [data-model.md](data-model.md).

## Prerequisites

- Backend and frontend running as in the README. After pulling this feature, run `python -m alembic upgrade head`, then `python -m mrcourt.seed` and `python -m mrcourt.corpus.ingest`.
- Install the new dependency: `pip install pypdf` (or reinstall the backend package).
- Optional for full mode: set `ANTHROPIC_API_KEY` in `backend/.env` and restart the API. Never commit it.
- Dev accounts: advocate `rohan.sharma@example.com`, client `anita.sharma@example.com`, administrator `admin@example.com`, all with `password123`.

## 1. Passages-only mode (no key)

Sign in as the advocate, open Ask MrCourt. Expect three tabs and a note "Running with cited passages only". Ask about cheque dishonour: cited passages appear. Ask something unrelated: "no reliable source". The Assistant toggle is disabled with the same note.

## 2. Knowledge base

1. Administrator: Knowledge base menu, add a shared text source, watch it become Ready, then ask a matching question as the advocate and see it cited.
2. Advocate: add a private note with a distinctive phrase. Ask a question that matches it: cited. Sign in as the client or the second advocate: the same question does not cite it, and the Knowledge tab does not list it.
3. Remove both. New answers no longer cite them; History still shows the earlier answers with their citation labels.
4. Upload a scanned or empty PDF: status Failed with a plain reason.

## 3. Assistant (needs a key, or the test double)

Advocate: "What are my hearings next week?" shows steps and a list. "Prepare a legal notice draft for the Sharma case" shows a proposal with Confirm and Decline; nothing exists in Drafts until Confirm; after Confirm an editable draft flagged for review exists. Client: the same hearings question uses only the client view; asking to create a draft is declined.

## 4. History

Ask three questions (one by voice, one with no answer). History lists them with Typed/Voice and outcome; search and both filters narrow the list; Open shows the stored answer; Ask again adds a new entry. Export data and confirm the questions are included.

## 5. Voice

In Chrome or Edge press the microphone: "Listening" appears and words fill the box. In a browser without recognition or with permission denied, a clear message appears and typing works. Operate it by keyboard only.

## 6. Administrator

Open a person's page, choose "Show questions asked": the list appears and the Audit log gains a `history.view` entry with no question text. Add and remove a shared source: `knowledge.add` and `knowledge.remove` entries appear.

## 7. Quality measurement

`python backend/scripts/import_reference.py --source D:\ClaudeTraning\Domains\RAG\docs --questions D:\ClaudeTraning\Domains\RAG\SA_1106_2019_Lawyer_Questions.txt` prints the retrieval hit rate for the reference question set and lists misses. Target: at least 90%.

## Automated checks

Backend: `pytest`. Frontend: `npx vitest run`, `npx tsc --noEmit`, `npx eslint src`. End to end: `npx playwright test` (uses a scripted model, so no key and no network).
