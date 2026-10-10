# Implementation Plan: Complete RAG

**Branch**: `005-complete-rag` | **Date**: 2026-10-08 | **Spec**: [spec.md](spec.md)

## Summary

Add the missing halves of a RAG system to the feature 004 base: meaning-based search fused with the existing keyword ranking, OCR so scans are searchable, Tamil questions, a server-side speech option, a Text Assistant tab with private conversations, a History source filter, and openable citations. Everything degrades to the previous behaviour when a key or tool is missing.

## Technical Context

Same stack as features 001 to 004. New libraries (already installed in the backend venv): `voyageai` (embeddings), `sarvamai` (speech), `pytesseract`, `pypdfium2`, `pillow` (OCR). Settings read from the environment or the git-ignored `backend/.env`: `VOYAGE_API_KEY`, `SARVAM_API_KEY`, `OCR_LANGUAGES`, plus `EMBEDDING_MODEL` (default `voyage-3.5`), `STT_MODEL` (default `saaras:v4`), `MIN_VECTOR_SCORE`.

**Key design decisions**

- **Embeddings.** `services/embeddings.py` becomes a small provider layer: a Voyage provider (query and document input types, 1024 dimensions, batching, retry on rate limits) and a deterministic fake for tests (`set_embedder`). Passages store `embedding` and `embedding_model`. Embedding runs in the background after a document is Ready (including pasted text), so uploads never wait on the service. A repeatable command `python -m mrcourt.services.embed_missing` fills older passages.
- **Fusion.** `retrieve()` builds two ranked lists over passages the person may use: BM25 (as now, with its minimum-evidence rule) and cosine similarity (passages above `MIN_VECTOR_SCORE`). They are merged with reciprocal rank fusion. Owner filtering happens in the SQL that loads candidates for both lists. If the question cannot be embedded, only the keyword list is used, and the result says `search_mode = "keywords"`. Citation verification and the "no reliable source" path are untouched.
- **Threshold.** `MIN_VECTOR_SCORE` is set from measurement on the reference questions and off-topic questions (the evaluation script prints both score ranges), not guessed.
- **OCR.** `services/ocr.py` has a Tesseract engine behind a small interface (`set_ocr_engine` for tests). `ingest.read_document` returns pages with an `ocr` flag and confidence; pages of a PDF with no text layer are rendered (pypdfium2) and read; images (PNG, JPEG, TIFF, with all TIFF frames) are one or more pages. If Tesseract or a language pack is missing the document fails with a reason that names what to install. Passages carry `read_by_ocr`; a document whose OCR confidence is low is Ready with a note.
- **Languages.** Voyage's multilingual model embeds Tamil and English into one space, so no separate Tamil index. A small script detector (Tamil, Devanagari, other) tells the answer which language the sources are in; in keyword-only mode a non-English question gets the honest "needs meaning-based search" message.
- **Speech.** `providers/speech.py` has the Sarvam provider (short WAV turns, 28 s limit) and a fake. `POST /speech/transcribe` takes a WAV upload in memory, never writes it, rate limits per person, and returns text. The browser microphone stays default; "Better for Tamil" and the Text Assistant use the endpoint. The notice naming the service is shown before first use.
- **Text Assistant.** New `text_conversations` and `text_lines` tables, owner-only. Creating a conversation also creates a History row (`Question` with `mode = "text"`), so History keeps it after the conversation is soft-deleted. PDF output uses fpdf2 with a Unicode font when one is installed (Nirmala UI on Windows, Noto Sans Tamil elsewhere), else plain Latin text.
- **History.** `mode` gains `text`; the list accepts `source=all|ask|text`; outcome label for text entries is "Saved". Opening a text entry returns its stored lines.
- **Citations.** `GET /knowledge/passages/{id}` returns text, document title, page and OCR flag if the person may see that passage (shared, or their own note); removed passages return 404 and the UI shows the stored label.

**Source layout (new or changed)**

```text
backend/src/mrcourt/services/embeddings.py        # providers, embed, embed_missing
backend/src/mrcourt/services/embed_missing.py     # one-off command
backend/src/mrcourt/services/retrieval.py         # vector list + fusion + search_mode
backend/src/mrcourt/services/ocr.py               # Tesseract engine, interface
backend/src/mrcourt/services/ingest.py            # read_document with OCR pages
backend/src/mrcourt/services/language.py          # script detection, source-language note
backend/src/mrcourt/providers/speech.py           # Sarvam + fake
backend/src/mrcourt/models/text.py                # TextConversation, TextLine
backend/src/mrcourt/services/text_assistant.py    # conversations, lines, pdf, add to knowledge
backend/src/mrcourt/api/{speech,text,knowledge,history}.py
backend/alembic/versions/0005_complete_rag.py
frontend/src/pages/ask/TextAssistantTab.tsx, PassageDialog (components/PassageViewer.tsx)
frontend/src/hooks/useRecorder.ts, services/wav.ts, services/text.ts
```

**Data model changes** (migration `0005`, idempotent): `legal_sources` + `embedding_model`, `read_by_ocr`, `ocr_confidence`; `knowledge_documents` + `ocr_pages`; `questions` + `conversation_id`; new `text_conversations` (id, user_id, title, language, deleted_at, created_at, updated_at) and `text_lines` (id, conversation_id, position, text, source, created_at).

**Contract summary**

- `GET /assistant/status` adds `search: "meaning" | "keywords"`, `speech: boolean`, `ocr: boolean`.
- `POST /questions` and assistant replies add `search_mode` and `source_language_note`.
- `POST /speech/transcribe` (multipart `audio`, `language`) returns `{ "text": string }`; 409 `speech_unavailable`; 413 over 2 MB; 429 rate limited.
- `/text/conversations` (list, create), `/{id}` (get, patch, delete), `/{id}/lines` (add), `/{id}/lines/{lineId}` (patch, delete), `/{id}/pdf` (download), `/{id}/knowledge` (add to knowledge base).
- `GET /history?source=all|ask|text`; history items gain `mode: "text"` and outcome label `Saved`.
- `GET /knowledge/passages/{id}`.

## Constitution Check

| Principle | Gate | Status |
|-----------|------|--------|
| I. Grounded, cited answers | Fusion only changes which passages are offered; verification and "no reliable source" unchanged; vector hits need a similarity threshold, measured | PASS |
| II. Not legal advice | Unchanged notices; OCR pages marked so people know text may have errors | PASS |
| III. Privacy by design (DPDP) | Audio held in memory only and never stored; embeddings made from passage text sent to Voyage, questions sent to Voyage; both named in Settings and README; keys only in `.env`; conversations private and deleted with the account | PASS WITH NOTE: two more third-party services receive personal and case-related text or audio; needs the review already open as T052 |
| IV. Accessible and responsive | Labelled mic and status regions, keyboard-operable lists, axe scans for new screens | PASS |
| V. Design system | Existing tabs, cards, chips, tables | PASS |
| VI. Simplicity | Justified below | PASS |

## Complexity Tracking

| Addition | Why needed | Simpler alternative rejected because |
|----------|-----------|--------------------------------------|
| Two ranked lists plus fusion | Keyword search alone reached 72%; meaning-based alone misses exact numbers (section 138) | Either one alone is weaker on legal text |
| Background embedding | Rate-limited external service must not block uploads | Inline embedding made uploads slow or failing |
| Text conversation tables | Conversations are edited line by line and must outlive the History entry | Storing them as questions loses editing |
| Tesseract engine interface | OCR is not installed here and must be testable | Hard-wiring the engine cannot be tested |

## Key Risks

- **Voyage free-tier limits** (a few requests and about 10,000 tokens a minute) slow bulk embedding; the provider retries, and the evaluation script caches vectors on disk outside the repository.
- **OCR cannot be run here** (no Tesseract). Behaviour is tested with a stand-in; real accuracy on Tamil scans is unverified until installed.
- **Sarvam speech** is tested with a stand-in plus one live call on a sample file if the key works.
- **Threshold choice** may trade recall for false sources; both are measured and recorded.
- **Keys in chat.** They must be rotated by the owner.
