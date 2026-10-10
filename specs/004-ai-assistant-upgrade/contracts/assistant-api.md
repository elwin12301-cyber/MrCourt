# API contract: AI Assistant Upgrade

All paths are under `/api/v1`. Sessions are cookies as today. Errors use `{ "detail": "..." }`. Unless stated, advocates and clients may call an endpoint; administrators may call only `/knowledge/*`, `/admin/*` and `/me`.

## Status

`GET /assistant/status` returns `{ "answers": "full" | "passages", "assistant": boolean, "notice": string | null }`. `assistant` is true only for advocates and clients when a model key is configured. `notice` explains passages-only mode.

## Ask (changed)

`POST /questions` body `{ "text": string (1..1000), "case_id"?: uuid, "input_method"?: "typed" | "voice" }` returns the existing answer shape plus `question_id`, `answer_mode`, and each paragraph's `kind` (`law`). Retrieval uses only shared passages and the caller's private passages.

## Assistant

`POST /assistant/requests` body `{ "text": string (1..1000), "input_method"?: "typed" | "voice" }` (rate limit 10 per minute per person; 403 for administrators; 409 `assistant_unavailable` without a model key) returns:

```json
{
  "question_id": "uuid",
  "outcome": "cited | answered | no_reliable_source",
  "steps": [{ "tool": "list_cases", "label": "Looked up your cases", "status": "ok", "detail": "3 cases" }],
  "paragraphs": [{ "text": "...", "kind": "law | case", "citation_numbers": [1] }],
  "citations": [{ "number": 1, "label": "...", "source_url": null }],
  "proposed_action": { "id": "uuid", "kind": "create_draft", "summary": "Create a Legal notice draft for Sharma v. Verma Traders", "expires_at": "iso" } | null,
  "disclaimer": "...",
  "lawyer_reminder": "..." | null
}
```

`POST /assistant/actions/{id}/confirm` runs the proposed action as the caller and returns `{ "status": "done", "draft_id": "uuid" }`. `POST /assistant/actions/{id}/decline` returns `{ "status": "declined" }`. Another person's id, an unknown id, a used or expired action all return 404 (expired: 410 `expired`), and change nothing.

## Knowledge

- `GET /knowledge/documents?q=&kind=&status=` lists what the caller may see: shared documents plus their own private notes. Row: `{ id, title, citation, kind, scope: "shared" | "private", status, status_reason, passage_count, page_count, created_at, can_remove }`. Clients receive shared documents with title, citation and kind only.
- `POST /knowledge/documents` as multipart `{ title, citation, kind, file? , text? }` (one of `file` or `text`): administrators create shared documents, advocates create private notes (`kind` forced to `note`); clients get 403. Returns the row with status `processing` (or `ready` for pasted text). 409 for a duplicate, 413 over the size limit, 422 for unsupported type.
- `DELETE /knowledge/documents/{id}`: administrators remove shared documents; advocates remove their own notes; others 403, other people's private notes 404. Writes `knowledge.remove` for shared documents.
- Shared adds and removes by an administrator write `knowledge.add` / `knowledge.remove` to the audit log.

## History

- `GET /history?q=&outcome=answered|none&input=typed|voice&mode=answer|assistant&limit=&before=` returns only the caller's questions, newest first: `{ items: [{ id, text, created_at, input_method, mode, outcome_label: "Answered" | "No information found" }], next_before }`.
- `GET /history/{id}` returns the stored question and answer in the same shape as the ask response (steps and citations included; a removed passage shows its stored label). Another person's id returns 404.

## Admin

`GET /admin/users/{id}/questions?limit=&before=` (administrators only) lists a person's questions with the same row shape and writes a `history.view` audit entry (target = the person, no text). Opening a single question is not offered to administrators.

## Data export and deletion

`GET /me/export` gains `questions` fields `input_method`, `mode`, `steps`, and `private_documents` (titles and text of the caller's own notes). Deactivation removes questions, answers, steps, proposed actions and private documents with their files.
