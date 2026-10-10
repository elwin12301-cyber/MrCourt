# Data Model: Client Case Status

Extends the model from feature 001 (see `specs/001-mrcourt-legal-app/data-model.md`). All new tables use UUID keys and `created_at`. Introduced by Alembic revision `0002`.

## Changes to existing tables

### cases
| Field | Notes |
|-------|-------|
| client_status | `notice_stage`, `hearing_scheduled`, `awaiting_order`, `closed`, or null (not set) |
| client_status_changed_at | When the client status last changed; null if never set |
| client_status_changed_by | Advocate user id |

Rules: setting `closed` also sets `status = closed`. Reopening requires choosing another client status and sets `status = active`. `client_status` is independent of the derived `hearing_soon` value.

### documents
| Field | Notes |
|-------|-------|
| shared_with_client | boolean, default false |

### hearings
| Field | Notes |
|-------|-------|
| outcome_shared | boolean, default false. The existing `outcome` text is shown to clients only when true |

### case_invitations
| Field | Notes |
|-------|-------|
| accepted_at | Set when a client accepts; shown to the client as "can see this case since" |

### user_settings
| Field | Notes |
|-------|-------|
| client_contact | JSON `{phone?, email?, office?}`, empty by default. Advocates only. Shown to clients only for filled fields |

## New tables

### timeline_entries
| Field | Notes |
|-------|-------|
| id | primary key |
| case_id | required |
| kind | `status_change`, `hearing_scheduled`, `hearing_rescheduled`, `outcome`, `document_shared`, `update`, `note` |
| text | Plain-language description written for the client when shared |
| shared_with_client | See rule below |
| hearing_id, document_id | Optional links to the related record |
| occurred_at | Event time |
| created_by | Advocate user id |

Visibility rule: `status_change`, `hearing_scheduled` and `hearing_rescheduled` are always visible to clients (the flag is stored true). `update` is created with the flag true. `outcome`, `document_shared` and `note` are visible only while the flag is true; the default is false. Unsharing the linked item sets the flag false.

### client_updates
| Field | Notes |
|-------|-------|
| id | primary key |
| client_id | The petitioner who receives it |
| case_id | Required |
| timeline_entry_id | Optional |
| kind | Same set as timeline kinds, plus `question_reply` |
| message | Short text naming the case and the change (no private data) |
| read_at | Null while unread |

One row per accepted client per event. Deleted when the client is removed from the case or deactivates.

### client_questions
| Field | Notes |
|-------|-------|
| id | primary key |
| case_id, client_id | Required; the question belongs to this client only |
| kind | `question` or `update_request` |
| text | 1 to 2000 characters |
| reply_text, replied_at, replied_by | Null until answered; one reply per question |
| reply_read_at | Null until the client views the reply |

Visible only to its client and the case's advocate. Never returned to other clients.

## Static content (not database tables)

- `corpus/data/hearing_descriptions.json`: general descriptions keyed by hearing kind with the keywords that select them. Marked UNVERIFIED until a lawyer reviews it.
- `corpus/data/glossary.json`: plain-language term explanations.

## Relationships

cases 1—n timeline_entries · cases 1—n client_updates (per client) · cases 1—n client_questions (per client) · users (client) 1—n client_updates, client_questions · timeline_entries n—1 hearings/documents (optional).

## State transitions

- **Client status**: any of the four values can be chosen at any time; every change writes a `status_change` timeline entry and one update per client. Choosing the same value again does nothing.
- **Sharing**: item private → shared writes a timeline entry and updates; shared → private hides the entry and the item immediately and writes no notice.
- **Client question**: sent → replied → reply read. A reply creates a `question_reply` update for that client only.

## Derived values

- Unread count for a client: `client_updates` with `read_at` null.
- "Can see this case since": the client's `accepted_at`; "other people with access": count of other accepted invitations on the case (names are not shown).

## Deactivation (extends feature 001)

- A client's deactivation deletes their `client_questions`, `client_updates` and invitations. The advocate's timeline and case records remain.
- An advocate's deactivation keeps cases, timeline entries and clients' questions with the case; the advocate's personal data is removed as in 001, and clients are shown "Your lawyer is no longer available on MrCourt".
