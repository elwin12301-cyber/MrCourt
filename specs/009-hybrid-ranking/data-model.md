# Data model: Hybrid ranking

## Ranking settings (configuration, not a table)

| Setting | Default | Notes |
|---|---|---|
| `RANKING_MODE` | `hybrid` | `rrf` = current ranker, kept as baseline and rollback |
| `RANK_W_KEYWORD` | 0.35 | weights are normalised to sum to 1 |
| `RANK_W_MEANING` | 0.15 | |
| `RANK_W_RERANK` | 0.50 | |
| `RANK_BOOST_TYPE` | 0.10 | document type suits the question type |
| `RANK_BOOST_COURT` | 0.08 | court named in the question |
| `RANK_BOOST_OWN_CASE` | 0.15 | advocate's own case document, my-case questions only |
| `RANK_RECENCY_MAX` | 0.05 | judgments, scaled by age (newest 0.05, 20+ years 0) |
| `RANK_PER_DOCUMENT` | 2 | diversity cap (FR-004) |
| `RERANK_CANDIDATES` | 20 | was 10; still one reranker call |

The evaluation script prints the chosen values with their scores; the accepted set is recorded in
`specs/009-hybrid-ranking/eval-results.md`.

## Answer.ranking (new nullable JSON column on `answers`)

```json
{
  "mode": "hybrid",
  "question_type": "law",
  "references": [{"kind": "section", "act": "Indian Penal Code", "section": "379"}],
  "passages": [
    {
      "source_id": "uuid",
      "position": 1,
      "pinned": true,
      "scores": {"keyword": 0.92, "meaning": 0.61, "rerank": 0.88, "combined": 0.84},
      "signals": [{"name": "exact_section", "value": "pinned"}, {"name": "type_statute", "value": 0.10}]
    }
  ]
}
```

- Written once when the answer is made; older answers have `null` (panel says "not recorded").
- Contains ids and numbers only, never passage text or personal names.
- Migration `0008_answer_ranking`: add the column, idempotent like earlier revisions.

## Reference (in memory)

`{kind: "section" | "case", act?: str, section?: str, case_number?: str, cnr?: str}`, parsed from the question.

## Evaluation question (file)

```json
{"id": "q017", "question": "...", "type": "law | courts | my_case | other",
 "expected": [{"instrument": "Indian Penal Code", "section": "379"}] ,
 "exact_reference": true, "language": "en"}
```

`expected` may instead name a document title and page for judgments. Shared-corpus questions only in the repository.
