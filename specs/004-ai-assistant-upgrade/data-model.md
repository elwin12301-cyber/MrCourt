# Data Model: AI Assistant Upgrade

Migration `0004_ai_assistant` (idempotent, same style as 0002 and 0003).

## knowledge_documents (new)

| Field | Type | Notes |
|-------|------|-------|
| id | uuid | |
| title | string 300 | required |
| citation | string 400 | label used in answers, e.g. "S.A. No. 1106 of 2019, Madras High Court" |
| kind | string | `act_section`, `judgment`, `note` |
| owner_id | uuid, null | null = shared (administrator-managed); set = private to that advocate |
| status | string | `processing`, `ready`, `failed` |
| status_reason | string 300, null | plain reason shown when failed |
| file_name | string, null | original name |
| file_path | string, null | stored original; deleted on removal |
| page_count | int, null | |
| passage_count | int | |
| created_by | uuid | who added it |
| created_at, updated_at | datetime | |

Rules: only administrators create shared documents; only advocates create private notes (`kind = note`, `owner_id` = themselves); clients create none. Title plus owner is unique for non-failed documents (adding the same twice is refused).

States: `processing` becomes `ready` or `failed`. A document `processing` for over 10 minutes is shown as failed.

## legal_sources (passages; changed)

Adds `document_id` (uuid, null for legacy rows until backfill), `owner_id` (uuid, null = shared, copied from the document), `page` (int, null). Search only ever reads rows where `owner_id IS NULL OR owner_id = :user` and the document is `ready`.

Backfill: each existing row gets a document (title = citation label, kind from its `kind`, shared, ready, passage_count 1).

## questions (changed)

Adds `input_method` (`typed` | `voice`, default `typed`) and `mode` (`answer` | `assistant`, default `answer`).

## answers (changed)

Adds `answer_mode` (`full` | `passages`, default `passages` for old rows) and `steps` (JSON list, null for plain answers). `outcome` gains `answered` (assistant reply built from the person's own data, no legal citation). History maps `cited` and `answered` to "Answered", and `no_reliable_source` and `failed` to "No information found".

Paragraphs gain `kind` (`law` | `case`); old rows read as `law`.

## answer_citations (changed)

Adds `label` (snapshot of the citation label); `source_id` nullable, set null when the passage is removed.

## proposed_actions (new)

| Field | Type | Notes |
|-------|------|-------|
| id | uuid | the confirmation handle, unguessable |
| user_id | uuid | only this person can confirm |
| question_id | uuid | the request that produced it |
| kind | string | `create_draft` (only value for now) |
| params | JSON | template, case_id; validated when proposed and again on confirm |
| summary | string 300 | what the person is shown |
| status | string | `pending`, `done`, `declined`, `expired` |
| result_id | uuid, null | the draft created |
| expires_at | datetime | 10 minutes after proposal |
| created_at | datetime | |

Single use: confirming changes `pending` to `done` in the same transaction as the draft; any other state is refused.

## Step record (inside answers.steps)

`{ "tool": "list_cases", "label": "Looked up your cases", "status": "ok" | "refused" | "failed", "detail": "3 cases" }`. Details never contain contact information or private text beyond what the step label needs.

## Audit actions (feature 003 log)

`knowledge.add`, `knowledge.remove` (title and citation only), `history.view` (target = the person, no text).

## Privacy and retention

Questions, answers, steps and proposed actions are the asker's personal data: included in the data export, deleted when the account is deactivated (existing rule). Private documents and their files are deleted with the owner's account too. Shared documents stay.
