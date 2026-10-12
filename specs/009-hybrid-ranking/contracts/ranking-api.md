# Contract: ranking explanation and evaluation

## GET /api/v1/admin/questions/{question_id}/ranking

Administrators only (403 for everyone else; 404 if the question or its answer does not exist; a question has exactly one answer, and the browser knows question ids).

**200**

```json
{
  "question_id": "uuid",
  "recorded": true,
  "mode": "hybrid",
  "question_type": "law",
  "references": [{"kind": "section", "act": "Indian Penal Code", "section": "379"}],
  "passages": [
    {
      "position": 1,
      "hidden": false,
      "label": "Indian Penal Code, s. 379",
      "pinned": true,
      "scores": {"keyword": 0.92, "meaning": 0.61, "rerank": 0.88, "combined": 0.84},
      "signals": [{"name": "exact_section", "label": "Named in the question", "value": "pinned"}]
    },
    {
      "position": 2,
      "hidden": true,
      "label": null,
      "pinned": false,
      "scores": {"keyword": 0.40, "meaning": 0.55, "rerank": 0.71, "combined": 0.58},
      "signals": []
    }
  ]
}
```

- `hidden: true` when the passage belongs to another user's private document: no label, no text, no signal
  that names a case or person.
- `recorded: false` with an empty `passages` list for answers made before this feature.
- Viewing is recorded in the administrator audit log (`answer.ranking.view`).

## Answers (unchanged shape)

`POST /api/v1/questions` and the assistant keep their response shapes. Citation order may change; at most two
citations come from one document unless no other source qualifies.

## Evaluation CLI

```text
python scripts/evaluate_ranking.py --questions FILE [--questions FILE ...]
       [--mode rrf|hybrid|both] [--grid] [--baseline specs/009-hybrid-ranking/eval-baseline.json]
       [--save-baseline]
```

Prints per mode: hit@1, hit@3, hit@5, MRR, counts per question type, and with a baseline the per-question
changes (better / worse / same). `--grid` searches weights and boosts over a small grid using cached scores and
prints the best settings. Exit code 1 if `hybrid` is worse than the baseline on hit@1 or MRR.
