# Law documents loaded into the knowledge base

Loaded 2026-10-08 into the development database from `C:\Users\Paul\Downloads` with `backend/scripts/ingest_law_folder.py`.

**35 sources, about 4,950 passages** (class-room law notes by M. S. Rama Rao, plus the 2024 Constitution of India text and a reference catalog), including the Indian Penal Code (89 pages, 214 passages), the Code of Criminal Procedure, the Constitution of India (two versions), the Negotiable Instruments Act, the Code of Civil Procedure, the Contract Act, the Transfer of Property Act, Hindu and Mohammedan law, torts, company law and more.

**Not loaded (damaged or incomplete downloads):** `EVIDENCE_ACT.pdf` (606,208 bytes), `LIMITATION_ACT.pdf` (49,152 bytes), `SALE_OF_GOODS_ACT.pdf` (65,536 bytes). The files end without the part PDFs need to be opened, so they cannot be read; download them again and run the script again.

**Skipped as duplicates:** `INDIAN_PENAL_CODE (1).pdf` and `INDIAN_CONSTITUTIONAL_HISTORY (1).pdf` (identical to the copies without "(1)").

## "What is IPC for theft?"

Answered from the Indian Penal Code PDF, citing its pages: the Chapter 11 note on theft and Sn. 378 (page 38 of the PDF) and the statutory text of 378 to 380 (pages 75 and 76), with the other related pages after them. The question "What is the punishment for theft under IPC?" returns the same pages.

## Two bugs found and fixed while doing this

- The citation check did not recognise the word "sections" (plural) or article numbers like 243ZA, so any passage that mentioned "sections 299 and 300" made the whole answer fail with "no reliable source". Fixed, with tests.
- Embedding requests were sized for a free account's limit of about 10,000 tokens a minute; they now wait out the per-minute window and are batched by size.

## Caveats

- These are study notes, not the official text of the Acts, and the IPC has been replaced by the Bharatiya Nyaya Sanhita (BNS). The constitution asks for current statutes to be preferred: answers from the IPC notes should be treated as the older code. Adding the BNS, BNSS and BSA texts is the natural next step.
- Passages are fixed-size pieces of each page, so an answer may start or end in the middle of a sentence.
- A person should check the sources before anyone relies on them.
