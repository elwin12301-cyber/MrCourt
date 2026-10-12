# Feature Specification: Hybrid ranking for answers and knowledge search

**Feature Branch**: `009-hybrid-ranking`

**Created**: 2026-10-12

**Status**: Draft

**Depends on**: 008-metadata-mapping (for the metadata signals in User Story 2)

**Input**: User description: "Hybrid ranking for MrCourt answers and knowledge search. Today retrieval fuses keyword and meaning results with rank fusion, then a reranker decides which meaning-only passages may be cited, and up to 5 passages are used per answer. Improve this into a tunable hybrid ranking: adjustable weights, metadata signals, exact legal references first, diversity, existing safety rules kept, an evaluation set with hit rate and mean reciprocal rank against the current baseline (67% -> 87%, target 90%+), and an explanation of each passage's rank for administrators."

## Current behaviour (baseline)

Answers today draw on passages found two ways: by matching words, and by matching meaning. The two lists are merged by position only. A second check scores how well each meaning-only passage answers the question, and such a passage may be cited only if it scores at least 0.5. Up to five passages are used per answer. On the earlier evaluation, questions written in different words from the source were answered from the right source 87% of the time (67% before meaning search).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A named section or case comes first (Priority: P1)

An advocate asks "What does Section 379 IPC say?" or "Summarise W.P. 11944/2013". The exact section or case they named is the first source cited whenever it exists in what they may see, even if other passages use more of the same words.

**Why this priority**: Lawyers mostly ask about exact references; getting the wrong section first is the most damaging ranking error.

**Independent Test**: Ask 20 questions naming a section or case number that exists in the knowledge base; the named source is cited first every time.

**Acceptance Scenarios**:

1. **Given** a question naming "Section 379 IPC" and that section is in the knowledge base, **Then** its passage is the first citation.
2. **Given** a question naming a section that is not in the knowledge base, **Then** the answer says that section was not found and does not present another section as if it were it.
3. **Given** "Section 379" with no Act named and several Acts have a section 379, **Then** the answer names which Act each cited passage is from.
4. **Given** a case number of a private document, **Then** only its owner gets it first; others are told no matching source exists.

---

### User Story 2 - Ranking uses document details and the kind of question (Priority: P1)

For "what is the punishment for cheating?" statute passages rank above judgments; for "how have courts decided bail in cheque cases?" judgments rank higher, recent ones before old ones of equal relevance; when an advocate asks about "my case" the documents of that case come first. Matching court or Act in the question raises a passage.

**Why this priority**: Gives the right kind of source for the question, which the current position-only merge cannot.

**Independent Test**: For each question type in the evaluation set, check that the preferred document type appears in the top 3 when it exists.

**Acceptance Scenarios**:

1. **Given** a "what is the law / punishment" question, **Then** a matching statute passage ranks above a judgment that only mentions it.
2. **Given** a "how have courts decided" question, **Then** judgments rank above statutes, newer before older when equally relevant.
3. **Given** a question naming a court, **Then** passages from that court rank above equal passages from other courts.
4. **Given** an advocate asks about one of their cases, **Then** that case's private documents rank first among equally relevant passages.

---

### User Story 3 - Varied sources, same safety (Priority: P1)

An answer never cites five passages from one long judgment when other relevant sources exist; at most two passages per document unless nothing else is relevant. All current safety rules hold: only passages the person may see, every citation checked, and "no reliable source found" when nothing scores high enough.

**Independent Test**: Run the evaluation set and check the per-document limit, visibility and no-source behaviour on every answer.

**Acceptance Scenarios**:

1. **Given** one judgment with 30 relevant passages and other relevant sources, **Then** no more than 2 of the 5 cited passages come from that judgment.
2. **Given** a client asks a question, **Then** no advocate's private passage is used, whatever its score.
3. **Given** no passage scores above the reliability threshold, **Then** the answer says no reliable source was found.

---

### User Story 4 - Every change is measured (Priority: P2)

A maintainer runs the evaluation (real questions with their expected sources) and gets a report: hit rate at 1, 3 and 5, mean reciprocal rank, results per question type, and the difference from the saved baseline. A change that lowers the scores is visible before release.

**Independent Test**: Run the report on the current ranking (baseline) and on the new ranking; both reports are produced and compared.

**Acceptance Scenarios**:

1. **Given** the evaluation set, **When** the report runs, **Then** it shows hit@1, hit@3, hit@5 and mean reciprocal rank overall and per question type, next to the baseline.
2. **Given** ranking weights are changed, **Then** the report shows which questions got better or worse.

---

### User Story 5 - Administrators can see why a passage ranked where it did (Priority: P3)

For any answer, an administrator opens "Why these sources?" and sees, for each cited passage, its word-match, meaning-match and answer-check scores and the signals applied (exact reference, document type, court, recency, own case), plus the final order. Passages the administrator may not see are shown only as "a private document of another user", with no title or content.

**Acceptance Scenarios**:

1. **Given** an answer, **Then** the administrator sees each cited passage's scores and signals in plain words.
2. **Given** a passage from another user's private document, **Then** its title and text are hidden.

---

### Edge Cases

- No meaning-search data for a passage (not yet processed): it is ranked on the other signals and never dropped for that reason alone.
- The answer-check service is unavailable: the current rule applies (only passages with word evidence are cited).
- The question is in Tamil: ranking signals still apply; exact references in Tamil text are recognised where written in standard form.
- Old and new criminal law: a question about BNS section 303 does not get IPC section 379 ranked first as if it were the same, unless the source text links them.
- Metadata missing (feature 008 not run on a document): no metadata signal is applied to it; it is not penalised.
- Ties: the more recent and then the shared (verified) source wins.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Ranking MUST combine word-match, meaning-match and answer-check scores with adjustable weights; defaults MUST be the best-scoring setting on the evaluation set.
- **FR-002**: An exact section or case reference in the question MUST put the matching passage first when the person may see it.
- **FR-003**: Ranking MUST apply metadata signals: exact Act/section, court, document type suited to the question type, recency of judgments, and the advocate's own case documents.
- **FR-004**: At most 2 cited passages MAY come from one document unless no other passage passes the reliability threshold.
- **FR-005**: Existing rules MUST hold: visibility per person, citation checking, reliability threshold and "no reliable source" reply.
- **FR-006**: An evaluation report MUST give hit@1, hit@3, hit@5 and mean reciprocal rank, overall and per question type, compared with a saved baseline.
- **FR-007**: Administrators MUST be able to see the scores and signals behind each cited passage of any answer, with other users' private documents hidden.
- **FR-008**: Weights and signals MUST be changeable by configuration without changing the safety rules.
- **FR-009**: Ranking MUST NOT noticeably slow answers (see SC-004).

### Key Entities

- **Ranking settings**: the weights and signal strengths in use, with the date and the evaluation scores they produced.
- **Evaluation question**: a question, its type, the expected source(s), and whether it uses exact references.
- **Ranking explanation**: per answer and passage, the scores, signals applied and final position.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Questions worded differently from their source are answered from the right source at least 90% of the time (baseline 87%).
- **SC-002**: Questions naming an existing section or case cite it first 100% of the time.
- **SC-003**: Hit@1 and mean reciprocal rank are each higher than the baseline on the full evaluation set, and no question type gets worse by more than 2 points.
- **SC-004**: Answers take no more than 10% longer than today on the same questions.
- **SC-005**: In tests, no private passage of another user appears in any answer or explanation.

## Assumptions

- The evaluation set starts from the existing quality questions and is extended to at least 100 questions covering statutes, judgments, exact references, own-case questions, and Tamil.
- Question type (law/punishment, how courts decided, about my case, other) is recognised from the wording; when unsure, no type preference is applied.
- The reliability threshold for meaning-only passages stays at its measured value unless the evaluation shows a better one.
- The explanation view is for administrators only; advocates continue to see the existing "steps" of an answer.
