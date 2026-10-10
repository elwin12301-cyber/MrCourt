# Data Model: MrCourt Legal Assistance App

All tables use UUID primary keys and `created_at` / `updated_at` timestamps unless noted.
Personal profile data (`users`, `user_settings`, `questions`) is kept separate from case records
(`cases` and children) so deactivation can remove the former and keep the latter (FR-015).

## users
| Field | Notes |
|-------|-------|
| id | primary key |
| role | `advocate` or `petitioner` (FR-019) |
| full_name | required |
| email, phone | at least one required, each unique when present |
| password_hash | argon2id; null until a password is set |
| bar_registration_number | advocates only, e.g. `D/1234/2015` |
| verification_status | `none`, `pending`, `verified` (FR-021); `verified_by`, `verified_at` set by an administrator |
| is_admin | boolean, administrators confirm verification |
| status | `active` or `deactivated`; `deactivated_at` |

Rules: deactivated users cannot sign in; on deactivation `email`, `phone`, `full_name` are replaced by a
non-identifying placeholder and `password_hash` is cleared.

## user_settings (1:1 with users)
`language` (default `en`), `whatsapp_reminders` (bool, default true), `hearing_alert_days` (default 1),
`theme` (`system`, `light`, `dark`).

## otp_challenges
`user_id` or contact, `code_hash`, `expires_at`, `attempts`, `consumed_at`. Expire in 5 minutes, max 5 attempts.

## cases
| Field | Notes |
|-------|-------|
| id | primary key |
| owner_id | advocate user, required |
| title | e.g. "Sharma v. Verma Traders" |
| cnr_number | unique per owner |
| court | free text, e.g. "Saket District Court" |
| status | `active`, `hearing_soon`, `closed`; `hearing_soon` is derived when the next hearing is within 7 days, unless closed |
| stage | optional, e.g. "Evidence" |
| room | optional, e.g. "Court Room 12" |
| notes | text for the Notes tab |

## parties
`case_id`, `side` (`petitioner` or `respondent`), `name`, `is_client` (bool).

## hearings
`case_id`, `scheduled_at` (timestamp with time zone), `court_room`, `purpose`, `outcome`.
State: upcoming until `scheduled_at` passes; the earliest upcoming hearing is the case's next hearing
(none shows "No hearing scheduled").

## documents
`case_id`, `file_name`, `size_bytes`, `content_type`, `storage_key`, `uploaded_by`.

## case_invitations
`case_id`, `invitee_user_id` or `invitee_contact`, `status` (`pending`, `accepted`, `removed`), `invited_by`.
A petitioner can read a case only when an `accepted` invitation exists (FR-019). Accepting writes an
activity event for the owner (FR-020).

## drafts
`case_id`, `author_id` (advocate), `template` (`notice`, `bail`, `reply`, `affidavit`), `title`,
`body` (text), `version` (integer, starts at 1, incremented on each save), `last_edited_at`,
`ai_generated` (always true for generated drafts; the review flag is shown while true).

## draft_exports
`draft_id`, `format` (`docx` or `pdf`), `requested_by`, `created_at`. Audit record of explicit exports.

## legal_sources
| Field | Notes |
|-------|-------|
| id | primary key |
| kind | `act_section`, `constitution_article`, `judgment_passage` |
| instrument | e.g. "Negotiable Instruments Act, 1881" |
| section | e.g. "138"; null for judgments |
| citation_label | exact chip text, e.g. "Negotiable Instruments Act, 1881 · Section 138" |
| text | passage text |
| source_url | provenance |
| effective_status | `in_force`, `repealed`; `replaced_by_id` points at the successor |
| search_vector | full-text search column |
| embedding | pgvector column |

## questions
`user_id`, `case_id` (optional), `text`, `created_at`. Deleted on deactivation.

## answers
`question_id`, `outcome` (`cited` or `no_reliable_source`), `paragraphs` (JSON, each with the ids of its
supporting sources), `disclaimer` (always populated). Linked citations are stored in `answer_citations`
(`answer_id`, `source_id`, `position`).

## activity_events
`user_id` (recipient), `case_id` (optional), `kind` (`notice_served`, `order_uploaded`, `invite_accepted`, ...),
`message`, `created_at`. Feeds the dashboard's recent activity.

## Relationships
users 1—n cases (owner) · cases 1—n parties, hearings, documents, drafts, case_invitations ·
users 1—n case_invitations (invitee) · users 1—1 user_settings · users 1—n questions 1—1 answers 1—n answer_citations n—1 legal_sources.

## Derived dashboard values
- Active cases: owner's cases with status not `closed`.
- Hearings this week: upcoming hearings in the next 7 days.
- Drafts to review: drafts with `ai_generated` true and no save since generation.
