# Results: Complete RAG (005)

Run on 2026-10-08.

| Suite | Result |
|-------|--------|
| Backend (pytest) | 474 passed |
| Frontend unit (Vitest) | 15 passed |
| Type check and lint | clean |
| End-to-end, desktop and mobile (includes accessibility) | 384 passed in the last run; the run before had 383 passed and 1 flaky (passed on retry) |

Baseline before this feature: backend 412, unit 15, end-to-end 354.

## Live checks with the supplied keys

- **Voyage AI**: embedding and reranking work. On the dev server a loosely worded question ("What happens if a cheque is returned unpaid because of insufficient funds?") found Section 138 with search mode "meaning".
- **Sarvam AI**: speech to text works. A Tamil sample clip came back as correct Tamil text.
- **Search quality**: 67% (keywords only) to 87% found on the reference questions; 92% right page, 90% answer facts. Target was 90% combined, so it is just short. Details in [quality-results.md](quality-results.md).

## Not verified (needs a person or an install)

- **OCR was never run for real.** Tesseract is not installed on this machine, so OCR is tested with a stand-in. Install Tesseract with English and Tamil data and try real scans.
- **Tamil questions by meaning** are tested with a stand-in only; the reference question file is English.
- **Text Assistant microphone** is tested with a fake microphone and a stand-in speech service; live recording with a real microphone was not exercised in a browser.
- **PDF with Tamil text** needs an Indic-capable font on the server; the build was only tested without one.
- **The assistant and answer writing** still need an `ANTHROPIC_API_KEY` (not supplied).
- **T036**: legal and policy review of sending question text, passage text and voice to Voyage AI and Sarvam AI.
- **Rotate the keys**: they were pasted into a chat, and the speech key was also in a sample script.
- PostgreSQL has still never been run (the vector query path for it is untested).

## Notes

- Voyage accounts without a payment method are limited to a few requests a minute; each question needs two, so some will fall back to keyword search until a payment method is added.
- A sign-in request occasionally stalls under parallel browser load; one retry is allowed and a retried test is reported as flaky.
