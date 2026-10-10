# Retrieval quality on the reference question set

Measured 2026-10-08 with `backend/scripts/import_reference.py` (no model, no network).

**Data**: the two readable English court documents and four scanned Tamil documents from the earlier RAG project were offered. Only text with a readable layer was loaded (the script reports what it skipped). Questions: the English lawyer question file for S.A. No. 1106 of 2019 (39 questions with expected page and answer).

**Method**: for each question, take the top 5 passages. It counts as found when one is on an expected page and together they contain at least half of the significant words of the expected answer.

| Measure | Result |
|---------|--------|
| Right page found | 30 of 39 (77%) |
| Answer facts found | 30 of 39 (77%) |
| Found (page and facts) | 28 of 39 (**72%**) |

**Target (SC-001): 90%. Not met by retrieval alone.**

## What helped

- Ranking with BM25 and measuring how rare a word is across everything the person may use (first run: 59%).
- Letting a one-word question match on that word, instead of demanding two (59% to 72% together with the change above).

## What is still missed, and why

The misses are mostly questions whose words do not appear in the answer passage:

- "Who appeared for the parties?" (the judgment says "For Appellant", not "appeared").
- "What was the final result?" (the judgment says "dismissed").
- "How did the plaintiff acquire his land?" (the judgment says "allotted ... in a family partition").
- Page 1 header questions ("Which court decided this case?"), where common words like "court" match many pages.

Plain keyword search cannot bridge these. The Tamil question file was not scored: retrieval here reads English only.

## Recommended next step

Add meaning-based search (embeddings fused with the keyword ranking), as planned in [research.md](research.md) R2. The interface already exists (`services/embeddings.py`) and retrieval already fuses vectors when they are present. It needs a provider and key, which is a decision for the owner (the earlier RAG project used Voyage). A cheaper step that uses only the Claude key is to let the model rewrite each question with the words a judgment would use before searching; it would be tested against this same script.

Until then, answers stay safe (they cite or say "no reliable source"), but recall on loosely worded questions is about 72%, not 90%.
