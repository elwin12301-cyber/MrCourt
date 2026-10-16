# MrCourt

Legal guidance grounded in Indian law, for Advocates and Petitioners. Answers cite the Act and
section they come from, or say plainly that no reliable source was found. Everything MrCourt
produces is informational, not legal advice.

- **Frontend**: React 18, TypeScript, Vite (`frontend/`)
- **Backend**: Python 3.12+, FastAPI, SQLAlchemy, Alembic (`backend/`)
- **Database**: PostgreSQL 16 with `pgvector` (target). SQLite works for local development and tests.
- **Design source of truth**: `design/MrCourt Web Prototype.html`
- **Specification and plan**: `specs/001-mrcourt-legal-app/` (Spec Kit), project principles in
  `.specify/memory/constitution.md`

## Run it locally

You need Python 3.12+ and Node 22+.

```bash
# 1. Backend
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"      # Windows. On macOS/Linux: .venv/bin/python
export DATABASE_URL=sqlite:///./dev.db COOKIE_SECURE=false   # PowerShell: $env:DATABASE_URL='sqlite:///./dev.db'
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m mrcourt.seed                 # fictional development data
.venv/Scripts/python -m mrcourt.corpus.ingest        # sample legal passages (UNVERIFIED, see below)
.venv/Scripts/python -m uvicorn mrcourt.main:app --port 8000

# 2. Frontend (another terminal)
cd frontend
npm install
npm run dev                                          # http://localhost:5173, proxies /api to :8000
```

**PostgreSQL (the database used in production, and now in development).** Start it with Docker:

```bash
docker compose up -d db                     # PostgreSQL 16 with pgvector on port 5432
MRCOURT_DB_PORT=5433 docker compose up -d db   # if another PostgreSQL already uses 5432 (PowerShell: $env:MRCOURT_DB_PORT=5433)
```

and put `DATABASE_URL=postgresql+psycopg://mrcourt:mrcourt@127.0.0.1:5433/mrcourt` (your port) in `backend/.env`.
Use `127.0.0.1`, not `localhost`: on Windows `localhost` can add a ten-second wait to every new connection.
Then run `alembic upgrade head`. To move an existing SQLite development database across:

```bash
python scripts/copy_sqlite_to_postgres.py --source sqlite:///./dev.db --target postgresql+psycopg://mrcourt:mrcourt@127.0.0.1:5433/mrcourt
```

The automated tests still use throw-away SQLite databases (fast and isolated); the Docker image has been run
against PostgreSQL 16 + pgvector, and the development app runs on it.

Development accounts (fictional, created by the seed command; password `password123`):

| Who | Email |
|-----|-------|
| Advocate (verified) | `rohan.sharma@example.com` |
| Client (invited to one case, has messages and updates) | `anita.sharma@example.com` |
| Second client on the same case (to see that clients are kept apart) | `ravi.mehta@example.com` |
| Administrator (sign in at `/login/admin`, linked at the bottom of the welcome screen) | `admin@example.com` |

The seed command refuses to run when `ENVIRONMENT=production`.

**Sign in.** Advocates, petitioners and administrators each have their own page: `/login/advocate`, `/login/petitioner` and `/login/admin` (and `/register/advocate`, `/register/petitioner`; administrators are never created through sign-up). The welcome screen's two buttons open them. An account only signs in on its own page; the other page explains which one to use and leaves no session behind.

## Tests

```bash
cd backend && .venv/Scripts/python -m pytest          # API, access control, answers, privacy
cd frontend && npm test                               # component and helper tests
cd frontend && npx playwright install chromium        # once
cd frontend && npm run test:e2e                       # browser tests (see below)
```

The browser tests start their **own** API on port 8001 with a fresh, seeded SQLite database, and
their own frontend on port 5174, so they never touch development data. They cover every screen,
keyboard-only use, WCAG 2.1 AA scans in light and dark themes at desktop and phone widths, and a
pixel comparison against the prototype.

## Configuration

Copy `.env.example` to `.env`. Names only are listed there; never commit values.

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Database connection |
| `SESSION_SECRET` | Signs session cookies. **Required** when `ENVIRONMENT=production` |
| `ALLOWED_ORIGINS` | Public address of the frontend (cross-origin write protection) |
| `COOKIE_SECURE` | `true` in production (HTTPS only cookies) |
| `ANTHROPIC_API_KEY` | Enables model-written answers and the assistant. Without it, answers quote the cited passages directly and the assistant is off |
| `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_FALLBACK_MODEL` | A free alternative for model-written **answers** (Ask MrCourt) when there is no Anthropic key (default `gemini-3.5-flash`, then `gemini-3.5-flash-lite` when busy). Same prompt, same citation check. The assistant (AI Assistant tab) still needs the Anthropic key. Free-tier limits change and apply per minute and per day; when Gemini is busy or out of quota (a slow reply counts as busy, then the lite model is tried) the cited passages are shown as they are, with a note, never a guess |
| `ASSISTANT_MODEL` | Model for the assistant (defaults to the answer model) |
| `VOYAGE_API_KEY` | Meaning-based search (embeddings and reranking, Voyage AI). Without it, search is by keywords only |
| `EMBEDDING_MODEL`, `RERANK_MODEL`, `MIN_RERANK_SCORE` | Voyage models and the score a meaning-only passage needs before it is cited (default 0.5, measured) |
| `MIN_RERANK_SCORE_KEYWORD` | The score a passage that only shares words with the question needs before it is cited, when the answer check ran (default 0.45, measured; 0 turns it off). Passages the answer check did not judge are not cited. |
| `SARVAM_API_KEY`, `STT_MODEL` | Speech to text for Indian languages (Sarvam AI). Without it, only browser voice works |
| `OCR_LANGUAGES` | Tesseract language packs for scans, joined with `+` (default `eng+tam`) |
| `KNOWLEDGE_DIR` | Where uploaded knowledge files are stored (default `knowledge/`, not committed) |
| `MAX_KNOWLEDGE_BYTES`, `ASSISTANT_MAX_STEPS` | Upload size limit (10 MB) and the most steps the assistant takes per request (6) |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_SMS_FROM` | Text messages (SMS) for codes and reminders, and the fallback when WhatsApp fails; empty means the development outbox |
| `WHATSAPP_PROVIDER` | The WhatsApp channel: `none` (default), `fast2sms`, `twilio` (free sandbox, with `TWILIO_WHATSAPP_FROM`) or `meta`. See "WhatsApp channel" below |
| `FAST2SMS_WHATSAPP_PHONE_NUMBER_ID`, `FAST2SMS_WHATSAPP_TEMPLATE_CODE`, `_REMINDER`, `_UPDATE`, `_ACTIVITY`, `FAST2SMS_WEBHOOK_SECRET` | WhatsApp through Fast2SMS (uses `FAST2SMS_API_KEY`): the connected number's id, the ids of the four approved templates, and the fixed secret its webhooks send |
| `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_APP_SECRET`, `WHATSAPP_VERIFY_TOKEN` | Meta's WhatsApp Business details: the number's id, the access token, the secret that signs its calls, and the token you type when setting up the webhook |
| `WHATSAPP_TEMPLATE_CODE`, `_REMINDER`, `_UPDATE`, `_ACTIVITY` | Names of the approved message templates (defaults `mrcourt_code`, `mrcourt_hearing_reminder`, `mrcourt_case_update`, `mrcourt_activity`) |
| `PUBLIC_APP_URL`, `WHATSAPP_WEBHOOK_URL`, `WHATSAPP_DAILY_SEND_CAP` | The site's public address (used in "read more" links), the exact address the provider calls (Twilio signs it; default is the public address plus `/api/v1/whatsapp/webhook`), and the most WhatsApp template messages sent per day (default 500) |

Send due reminders on a schedule with `python -m mrcourt.services.reminders`.

## The client experience

A client (petitioner) signs in to screens made for them, not a read-only copy of the advocate's:

- **Dashboard and My cases**: each case with a plain-language status (Notice stage, Hearing scheduled,
  Awaiting order or Closed), when it last changed, the next hearing, and their lawyer.
- **Case page**: the next hearing with a short general description of what usually happens at that kind
  of hearing, a timeline of what has happened, hearing history, documents the lawyer chose to share, who
  their lawyer is (only the contact details the lawyer filled in), who can see the case, and a box to
  ask the lawyer a question or request an update.
- **Updates**: a list with an unread count, refreshed every 30 seconds (set `VITE_UPDATES_POLL_MS` to
  change it; the browser tests use 3 seconds), plus the existing WhatsApp hearing reminders.
- **Ask MrCourt**: the same cited answers, with a notice and a link to the lawyer when the question is
  about the client's own case, and a standing reminder on every answer.

An advocate controls all of it from a **Client view** tab on each case: pick one of the four statuses,
write short updates, mark documents, hearing outcomes and notes as shared (**private by default**),
and answer client questions. Status changes and hearing dates are always visible to clients. Each
client's questions and replies are private to that client and the advocate.

**How privacy is enforced.** Clients can only call the `/client/*` endpoints, which build their view from
an explicit list of allowed fields. The advocate endpoints (`/cases`, `/dashboard`, `/drafts`, ...) refuse
clients entirely. Tests fetch every client endpoint for a case holding private notes, internal documents,
an unshared outcome and another client's question, and fail if any trace appears
(`backend/tests/integration/test_client_leaks.py`).

**Upgrading an existing database.** Run `python -m alembic upgrade head`. Revision `0002` adds the new
columns and tables and works on a database created before this feature as well as a fresh one.

**Content that needs a lawyer's review.** The hearing descriptions and the glossary
(`backend/src/mrcourt/corpus/data/hearing_descriptions.json` and `glossary.json`) are general wording
written for development and are marked `UNVERIFIED`. In production they are switched off until the marking
is removed after review, and clients then see just the date, time and court.

## The administrator console

An administrator signs in on their own page and gets a menu of their own: **Overview, Advocates, Clients,
Cases, Verifications, Audit log, Settings**. They see none of the advocate or client screens, and advocates
and clients cannot reach any admin screen or data (the server refuses them, not just the menu).

What an administrator **can** do:

- See every advocate, client and case, with search and filters. A person's page shows their details and how
  they are linked (an advocate's cases, a client's cases and lawyers).
- Open any case **in full**, read-only: private notes, internal documents, hearing outcomes not shared with
  the client, the whole timeline, and each client's questions and the lawyer's replies.
- Look after **accounts only**: correct a name, email, phone or Bar Council number; **suspend** (with a
  reason) and reactivate; **force a sign-out**; confirm or reject Bar Council numbers. Every change is saved
  at once, and a suspended or signed-out person is refused on their very next request.

What an administrator **cannot** do, because no such feature exists: edit, delete, reassign or close a case,
delete anything permanently, or reset a password.

**The audit log is the control for this broad access.** It records every account change, verification
decision, full case view and document download, with who, what and when. Lists and searches show overview
fields only and are not logged. Entries hold field names, reasons and statuses, never message text, passwords
or file contents, and cannot be edited or removed by anyone. Only administrators can read it.

**Creating an administrator.** Administrators are made by the people running the system, not through sign-up.
The seed command creates `admin@example.com` for development. In production, set a user's `role` to `admin`
directly in the database (and give them a strong password).

**Upgrading an existing database.** Run `python -m alembic upgrade head`. Revision `0003` adds the session
counter and the audit table, and works on a fresh database and on an older one. Everyone is signed out once
after upgrading, because sessions now carry a counter that lets an administrator end them.

## Knowledge Assistant (Ask MrCourt): answers, knowledge base, assistant, history and voice

The page is titled **Knowledge Assistant** (its menu entry is still "Ask MrCourt") and is the same for advocates,
clients and administrators: a "Secure retrieval active" badge and four tabs, **AI Assistant, Knowledge Base,
Text Assistant and History**. It follows the reference screen's layout and wording, in MrCourt's own colours.
Administrators get the page too: they can ask cited questions from the shared knowledge, manage shared sources,
use the Text Assistant (and add a conversation as a shared source) and see their own History; the agent mode stays
off for them. In History an administrator can also choose **Everyone's questions**: a list with who asked (no
answers, no conversation text), and each time it is shown an audit entry is written without the question text.

The page has four tabs.

- **AI Assistant.** *Answer* mode searches the knowledge base and cites every source; if nothing reliable is found
  it says so. *Assistant* mode (needs `ANTHROPIC_API_KEY`) works in steps for the signed-in person: it can
  look up their cases and hearings, search the knowledge base and propose a draft. It shows each step it
  took, uses only data that person may see (a client's assistant sees only what the lawyer shared), and
  never changes anything until the person presses Confirm. Administrators do not get Ask.
- **Knowledge Base.** Administrators add and remove shared sources (text, `.txt`, `.md` or text PDF, 10 MB at
  most). Advocates add private notes that only they can use or see. Clients can only read the list of shared
  sources. Removing a source deletes its text and file; old answers keep their citation label.
- **History.** Every question a person asked, searchable, with dropdowns for the assistant (Both, AI Assistant, Text
  Assistant), the outcome and Typed or Voice,
  with Open and Ask again. Only the asker sees it. It is in the data export and removed on deactivation.
  Administrators can list a person's questions from that person's page; each time is recorded in the audit
  log without the question text.

**Voice.** The microphone uses the browser's own speech recognition (best in Chrome and Edge). MrCourt
never receives or stores audio. A language list is offered; which languages work depends on the browser.

**Model service.** With a key set, questions, retrieved passages and (in Assistant mode) the case details a
tool returns are sent to the Claude API. Phone numbers and emails are left out of what the assistant reads.
Settings > Privacy says this, and a person should review it (see Known gaps).

**Measuring search quality.** `python backend/scripts/import_reference.py --questions <file>` loads readable
documents from a folder outside the repository into a throw-away database and reports how often retrieval
finds the right page and facts. Latest result: [quality-results.md](specs/004-ai-assistant-upgrade/quality-results.md).

**Upgrading.** `pip install -e backend` (new dependency `pypdf`), then `python -m alembic upgrade head`.
Revision `0004` gives each existing passage a shared document, and works on fresh and older databases.

## Complete RAG: meaning-based search, scans, Tamil and the Text Assistant

**Keys.** Put them in `backend/.env` (git-ignored), never in code or the repository:

```
VOYAGE_API_KEY=...
SARVAM_API_KEY=...
OCR_LANGUAGES=eng+tam
```

Tests and the end-to-end server blank these keys, so they never call the real services.

**Meaning-based search.** Every passage is embedded (Voyage AI, multilingual) after it is added, and every
question is embedded when asked. Keyword ranking and meaning ranking are merged, and a reranker then judges
the best candidates. A passage found only by meaning is cited only if the reranker scores it at least
`MIN_RERANK_SCORE`; if the reranker cannot run, only passages with keyword evidence are used. With no key the
app falls back to keywords and the Ask tab says so. To embed passages added before this feature (or after
a key was missing):

```bash
python -m mrcourt.services.embed_missing
```

Voyage accounts without a payment method are limited to a few requests a minute; each question uses two
requests (embed and rerank), so under that limit some questions fall back to keywords. Adding a payment method
on the Voyage account lifts the limit.

**Scans (OCR).** Scanned PDFs and PNG, JPEG or TIFF images are read with Tesseract in English and Tamil, and
pages read this way are marked, including in the cited source. Tesseract is a separate program that must be
installed on the server with the `eng` and `tam` language data; if it is missing, a scan fails with a reason
that says so. On Windows: install Tesseract (for example `choco install tesseract`) and add the Tamil data file
(`tam.traineddata`) to its `tessdata` folder. Quality on real Tamil scans has not been verified.

**Tamil and other languages.** Questions in Tamil are searched against English and Tamil passages by meaning,
and the answer says which language its sources are in. In keyword-only mode a Tamil question says that this
search needs meaning-based search.

**Text Assistant tab.** Speak or type a conversation (each spoken turn is sent to the speech service, Sarvam AI,
and the audio is not stored), edit lines, download a PDF, add it to the knowledge base (advocates, as a private
note), or delete it from the tab (its History entry stays). The PDF needs a font with Indic glyphs on the
server (Nirmala UI on Windows, Noto Sans Tamil elsewhere) to show Tamil; without one, Tamil letters become `?`.
Browser voice stays the default on the Ask tab; "Better for Tamil" uses the speech service.

**Reading a source.** Each citation has a Read source button that shows the passage, its document and page, and
whether it was read by OCR.

**Keys were shared in a chat.** The keys used while building this were pasted into a conversation, and one was
also found in a sample script in the earlier RAG project. Treat them as exposed and rotate them at Voyage and
Sarvam.

## Loading your own law PDFs

`backend/scripts/ingest_law_folder.py` adds a folder of law PDFs to the knowledge base as shared sources (the
originals stay outside the repository; the text goes into the database). It is safe to run again: sources already
present are skipped and identical files are added once.

```bash
cd backend
DATABASE_URL=sqlite:///./dev.db .venv/Scripts/python scripts/ingest_law_folder.py --folder C:\Users\Paul\Downloads
DATABASE_URL=sqlite:///./dev.db .venv/Scripts/python -m mrcourt.services.embed_missing --pace 60   # meaning-based search data
```

Answers come straight from the PDFs: ask "What is IPC for theft?" and the answer quotes the Indian Penal Code notes
(Chapter 11, Sn. 378, and the section text) with the page it came from. Keyword search works as soon as the files are
added; meaning-based search fills in as the second command runs (about 3 hours on a free Voyage account, because of its
per-minute limits; adding a payment method makes it much faster). The list of files is the `MANIFEST` at the top of the
script; edit it to add more. Files that are damaged or incomplete downloads are reported and skipped (three were
found: the Evidence Act, the Limitation Act and the Sale of Goods Act; download them again and rerun).

## Sign-up, forgot password and text-message reminders

- **Registration page** (`/register`): choose a role (Advocate or Petitioner; administrators cannot sign up), then give a
  username, full name, email, mobile number and password (advocates may add a Bar Council number). The username is unique,
  3 to 30 characters, and can be used to sign in. Demo usernames: `rohan` (advocate), `anita` (petitioner), `siteadmin`.
- **Sign-up** asks for a mobile number and texts a 6-digit code to it; the person enters the code (or chooses
  "Verify later" and does it in Settings). Changing the number makes it unverified again.
- **Forgot password** (link on each sign-in page): a code is texted to the **verified** phone on the account, the
  person chooses a new password, and every session of theirs ends. The reply is the same whether or not an account matches.
- **Hearing reminders**: the advocate who owns a case and each client who accepted the invitation are texted
  **5 days before, 1 day before and on the day** of each hearing, once each, if their phone is verified and "Text message
  reminders" is on in Settings. The text names the case and the time only. A hearing added at short notice sends one
  text. Run the job every hour: `python -m mrcourt.services.reminders` (Windows Task Scheduler or cron).
- **Without keys** nothing is really sent: messages go to a development outbox you can read at
  **http://localhost:5173/dev/messages** (this page does not exist in production or once real keys are set).

**Free sending with Twilio (SMS trial and WhatsApp sandbox).** Create a free Twilio account, then put these in
`backend/.env` (never commit it):

```
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_SMS_FROM=+1...                       # your Twilio trial phone number (leave empty to turn SMS off)
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886  # the sandbox number: used by the WhatsApp channel (see below)
```

- **WhatsApp sandbox:** see "WhatsApp channel" below. Each person who should receive messages sends the sandbox's
  "join ..." phrase from their own WhatsApp first.
- **SMS trial:** a trial account texts only numbers you have verified under Verified Caller IDs, and adds a trial note
  to each message.
- **Fast2SMS (India):** set `FAST2SMS_API_KEY` in `backend/.env`. Codes go by its OTP route and reminders by its Quick SMS
  route; the account needs wallet balance. Not tested against the live service. Twilio is used first if both are set.
- Text messages go out by the first SMS sender that is set up (Twilio, then Fast2SMS). WhatsApp is separate. These free
  accounts are for testing; sending to real clients at scale needs a paid, registered account (in India, sender and
  template registration applies).
- The Twilio and Fast2SMS senders have been tested only against stand-ins, not the live services.

## WhatsApp channel

A consent-based, two-way channel (feature 010). It is off until a provider is set up (`WHATSAPP_PROVIDER`); with `none`
everything stays on the development outbox and by SMS.

**What people get.** In **Settings -> WhatsApp** a person links their verified mobile number and switches on, one by one,
what they want: sign-in and verification codes, hearing reminders (5 days before, 1 day before, on the day), and for
clients a short note when their advocate posts an update (advocates can get a note when a client writes). **Everything is
off until switched on.** These messages name only the case and the time, or say there is news; the detail stays in the
app. If WhatsApp fails or the number is not on WhatsApp, the same short words go once by text message (when the person
keeps "text message reminders" on).

**What people can ask.** A linked person can message the MrCourt WhatsApp number:

- a legal question, answered like Ask MrCourt (cited, with the disclaimer, in short form with the sources named and a
  link to History). Only shared sources are used: an advocate's private documents are never quoted on WhatsApp;
- `next hearing`, `status`, `today`, `help` (also in Hindi and Tamil). A client sees only cases they were invited to and
  only what the advocate shared; an advocate sees their own cases;
- a voice note (understood in the language chosen in Settings, quoted back as "I heard: ...");
- `STOP` (also in Hindi and Tamil) to switch every kind off at once.

A message from a number that is not linked gets one fixed "how to link" reply (at most twice a day) and nothing about any
account. Messages per number are limited (`WHATSAPP_QUESTIONS_PER_MINUTE` 3, `_PER_DAY` 40).

**What is stored.** Delivery records (kind, status, time, person; never the words) for 90 days; the question text only in
the person's own History (marked "Asked on WhatsApp"); no audio. Administrators open **Messages** to see counts, failures
(who and why, never the words or the number) and whether the service works. Deactivating an account removes the link, the
choices and the records. The purge and retries run in the in-app loop (`REMINDER_INTERVAL_MINUTES` above 0) or with
`python -m mrcourt.services.whatsapp.jobs` every minute from a scheduler.

**Try it without any account:**

```
python backend/scripts/whatsapp_dev_send.py --from 9000000005 --text "What is Section 138 of the NI Act?"
```

(link the number in Settings first; the reply is printed from the development outbox).

**Free test with the Twilio sandbox.** Put `WHATSAPP_PROVIDER=twilio` and the Twilio keys above in `backend/.env`. Expose
the backend on a public HTTPS address (any tunnel tool) and set the sandbox's "When a message comes in" and "Status callback"
to `https://<address>/api/v1/whatsapp/webhook`, with `WHATSAPP_WEBHOOK_URL` set to exactly that address (Twilio signs it).
Each tester sends the sandbox's `join ...` phrase first (it lapses after a few days).

**Production with Fast2SMS (India).** Fast2SMS connects your WhatsApp Business number and sends and receives for you. In its
panel: connect the number and note its **phone number id**; create the four templates (texts in
`specs/010-whatsapp-channel/contracts/whatsapp-api.md`), wait for approval and note each **template id**. Put these in
`backend/.env` (or the host's secret store; never commit them):

```
WHATSAPP_PROVIDER=fast2sms
FAST2SMS_API_KEY=...                        # the key you already use for text messages
FAST2SMS_WHATSAPP_PHONE_NUMBER_ID=...      # optional for sending templates, needed for replies to questions
FAST2SMS_WHATSAPP_TEMPLATE_CODE=...         # one variable: the code
FAST2SMS_WHATSAPP_TEMPLATE_REMINDER=...     # two variables: the case, then when
FAST2SMS_WHATSAPP_TEMPLATE_UPDATE=...       # one variable: the case
FAST2SMS_WHATSAPP_TEMPLATE_ACTIVITY=...     # one variable: the case
FAST2SMS_WEBHOOK_SECRET=...                 # the 40-character secret from the panel's webhook settings
```

Then in Fast2SMS **Webhooks -> WhatsApp -> Add webhook** (twice, or once with the event "All"), method POST, URL
`https://<your site>/api/v1/whatsapp/webhook`, and turn on webhook signing so each call carries your secret. Payloads:

```
{"webhook_type":"incoming_message","from":"{{from}}","message_id":"{{message_id}}","message_type":"{{message_type}}","body":"{{body}}","media_url":"{{media_url}}","mime_type":"{{mime_type}}"}
{"webhook_type":"status_update","status":"{{status}}","message_id":"{{message_id}}","recipient_id":"{{recipient_id}}","error_message":"{{error_message}}"}
```

If the panel offers form encoding, prefer it (a message containing a double quote could otherwise break the JSON):
`webhook_type=incoming_message&from={{from}}&message_id={{message_id}}&message_type={{message_type}}&body={{body}}&media_url={{media_url}}&mime_type={{mime_type}}`.
**Their webhook secret is a fixed value, not a signature**: anyone who learns it can forge a call, so keep it out of logs and
chats and change it if it leaks. **Not yet tested against the live service**: the first live test must confirm that the
template ids and number id work, that status reports match our messages (the app falls back to matching by recipient when a
report's id differs), that text with quotes arrives intact, and whether voice-note media addresses are fetchable.

**Production with Meta's WhatsApp Business.** You need a verified business account, a registered number and four approved
message templates (names above; texts in `specs/010-whatsapp-channel/contracts/whatsapp-api.md`). Set `WHATSAPP_PROVIDER=meta`,
`WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_APP_SECRET` and `WHATSAPP_VERIFY_TOKEN`; in Meta's dashboard
set the webhook to `https://<your site>/api/v1/whatsapp/webhook` with that verify token. Keys go only in `backend/.env` or the
host's secret store. WhatsApp charges for template messages and its prices and free allowances change: check them first.
Test steps: `specs/010-whatsapp-channel/quickstart.md`. **Roll back** with `WHATSAPP_PROVIDER=none`.

## Deploying on Render

The repository has a `Dockerfile` (builds the website and serves it from the API, one address) and a
`render.yaml` Blueprint (that web service plus a PostgreSQL database).

1. Sign in at render.com with GitHub, then **New > Blueprint** and choose this repository.
2. Fill the secret values when asked: `ADMIN_EMAIL` and `ADMIN_PASSWORD` (the first administrator, password at
   least 12 characters), `FAST2SMS_API_KEY` (text messages), and optionally `VOYAGE_API_KEY`, `SARVAM_API_KEY`,
   `ANTHROPIC_API_KEY`. `SESSION_SECRET` is generated for you. Never put keys in the repository.
3. Apply. The first deploy takes several minutes. Sign in at `/login/admin` with the administrator email.

On every start the container runs the database migrations and creates the administrator if none exists. No demo
accounts or sample legal texts are created in production: add verified legal documents in the Knowledge base.

Limits of the free plans (check Render's current terms):
- The free web service sleeps when idle, so the first visit after a pause is slow, and the in-app hourly reminder
  run (`REMINDER_INTERVAL_MINUTES`) does not happen while it sleeps. For reliable reminders use a paid instance or
  an outside scheduler running `python -m mrcourt.services.reminders`.
- Uploaded files are stored on the container's disk, which is wiped on every deploy. Use a persistent disk (paid)
  for case documents.
- The free database is temporary; move to a paid database before real use.
- A public sign-up page with a text-message key lets anyone trigger paid texts. Watch your balance.

Tested locally: the Docker image with PostgreSQL 16 + pgvector (migrations, sign-up, sign-in by username, the
administrator, cases, questions). Not yet tested on Render itself.

## Document details (metadata)

Every knowledge document is mapped to standard details when it is added (feature 008): type (statute, judgment,
order, petition, deed, deposition, notice), court and bench, case numbers and CNR, case title and parties, judges, date,
Acts and sections referred to, outcome, language, and whether its text could be read at all.

- **Nothing is guessed.** A value is filled only from the document's text; each field says how sure MrCourt is
  ("Found in the text", "Likely – please check", "Not found", "Confirmed by a person").
- **Corrections stick.** In the Knowledge base, open **Details** on a document and **Correct details**. Corrections
  are kept when details are mapped again (**Map my documents again** / **Map shared details again**). Corrections to
  shared documents are recorded in the audit log.
- **Filters**: type, court, year, Act, section or article, case number, in the Knowledge base and under
  **Limit sources** when asking. Filter choices come only from documents you may see.
- **Citations** show the details in short ("Judgment · Madras High Court · 07 Apr 2025 · S.A. 1106/2019",
  "Statute · s. 21"), and the ranker (feature 009) uses court, date and type.
- **Unreadable text**: PDFs whose built-in text uses an old Tamil font encoding come out as gibberish. They are
  marked "Text could not be read: needs OCR" and left unmapped. Scanning them with OCR (Tesseract with the Tamil
  pack) is the fix.
- Map everything again from the command line: `python -m mrcourt.services.metadata --remap`. Check accuracy:
  `python scripts/check_metadata.py`.

## How answers are ranked

Sources for an answer are found by matching words and by matching meaning, then ordered by a weighted score
(feature 009):

- **Scores**: word match (`RANK_W_KEYWORD`), meaning match (`RANK_W_MEANING`) and the answer check, a second
  service that judges whether a passage answers the question (`RANK_W_RERANK`). Weights are shared out when
  the answer check is unavailable.
- **Named sections, articles and cases first**: "Section 138 NI Act", "Article 21", "W.P. 11944/2013". A passage
  that *is* that provision or case is pinned first; one that only mentions it is raised (`RANK_BOOST_SECTION`).
  A named section that no source contains is reported ("Not found in the sources: ...") and never replaced by
  another section. Old and new criminal codes (IPC/BNS, CrPC/BNSS) are never treated as the same.
- **Kind of question**: law and punishment questions prefer statutes, "how have courts decided" prefers
  judgments (newer first, when the date is known), and an advocate asking about "my case" gets their own case
  documents first (`RANK_BOOST_TYPE`, `RANK_BOOST_OWN_CASE`, `RANK_RECENCY_MAX`, `RANK_BOOST_COURT`).
- **Variety**: at most `RANK_PER_DOCUMENT` (2) passages from one document, unless nothing else qualifies.
- **Safety is unchanged**: only passages the person may see; a passage without word evidence needs the answer
  check's approval; every citation is checked; "no reliable source" when nothing qualifies.
- Administrators can open **Why these sources?** under an answer (and in everyone's questions) to see the scores
  and signals; other users' private documents appear only as hidden rows. Viewing it is recorded in the audit log.
- `RANKING_MODE=rrf` switches back to the earlier ranker (rollback).

Measure ranking changes with the evaluation set (shared law corpus only):

```bash
cd backend
python scripts/evaluate_ranking.py --questions tests/data/ranking_eval_shared.json --mode both     --baseline ../specs/009-hybrid-ranking/eval-baseline.json --grid
```

## How answers stay honest

1. The question is matched against the indexed legal passages.
2. Only those passages are given to the answer writer.
3. A verifier rejects any paragraph without a retrieved citation, and any section number the cited
   passage does not contain. If anything fails, or nothing matches, the user sees "could not find a
   reliable source" instead of a guess.

## Known gaps (read before relying on this)

- **Automated tests run on SQLite only.** The development app now runs on PostgreSQL 16 + pgvector (all
  migrations, the copied development data, sign-in, cases and cited answers checked by hand), and the Docker
  image was checked against it, but the test suites have not been run against PostgreSQL.
- **The legal corpus is a five-passage development sample, paraphrased from memory.** It is marked
  `UNVERIFIED` and the ingest command refuses to load it in production. Every passage must be checked
  against the official text, and a real corpus (BNS, BNSS, BSA, the Constitution, more of the NI Act,
  judgments) must be sourced and licensed before real use.
- **Meaning-based search needs a Voyage key and is rate limited on free accounts.** See the section above and
  [quality-results.md](specs/005-complete-rag/quality-results.md) for what it achieved on the reference questions.
- **The model-written answer path (`ANTHROPIC_API_KEY`) is untested against the live API.** The
  verifier that guards it is tested with fake generators.
- **The WhatsApp channel is untested against the live services.** The Meta and Twilio adapters, their signature checks and
  the sending are tested with sample payloads and a fake HTTP transport only; WhatsApp delivers only approved templates
  outside the 24-hour window, so it needs registered templates before it delivers reminders. A real WhatsApp voice note
  (OGG) has not been sent through the speech service yet.
- **A login code that WhatsApp reports as failed later is not re-sent by text** (the code is not kept); only an immediate
  refusal falls back to SMS. The person asks for a new code.
- **Text messages are untested against a real account.** Codes and reminders go to a development outbox until Twilio or
  Fast2SMS keys are set; those senders are tested only against stand-ins. Email is not used to deliver codes.
- **Hearing descriptions and the glossary have not been reviewed by a lawyer** (task T070 for feature 002).
  Until they are, they are off in production.
- **The "is this about my own case?" check is keyword-based.** Unusual wording can slip past it, which is
  why every client answer also carries a reminder to ask the lawyer. It is not a substitute for review.
- **Client updates appear inside MrCourt first.** A client who has not linked WhatsApp and switched on case updates sees
  nothing outside the app except the hearing reminders; the WhatsApp note says only that there is news.
- **Administrators have full access to private case content**, including advocates' private knowledge-base documents:
  they can see them with their owner's name, search them in their own questions, correct their mapped details (parties,
  judges, case numbers), map them again and **remove them for good**. Every such action is recorded (`knowledge.private.*`
  audit entries: who and which document, never the title or content). That is a deliberate choice, protected only by the audit
  log. Review it against the DPDP Act and your organisation's policy before launch (task T032 for feature 003),
  and have someone read the audit log regularly.
- **Question text, passage text and (with the speech option) voice go to Voyage AI and Sarvam AI.** Include these in
  the privacy review (task T036 for feature 005).
- **Questions and passages go to Google when `GEMINI_API_KEY` is set.** On Google's free tier, prompts may be used to
  improve Google's products. Do not use the free tier with real client papers; use a paid key (not used for
  training) or keep the key unset.
- **Questions and case details go to a third-party AI service** when `ANTHROPIC_API_KEY` is set. Check this,
  the retention of question history, and administrator access to it against the DPDP Act and your policy
  before launch (task T052 for feature 004). Without a key nothing leaves the app.
- **OCR has not been run for real.** No Tesseract was installed where this was built, so OCR is tested with a
  stand-in. Install Tesseract with English and Tamil data and try your own scans before relying on it. Scans
  that already contain a poor hidden text layer (some of the Tamil sample PDFs) are read as text, not re-scanned.
- **The assistant has not been run against the live model.** Its loop, tools, confirmation and privacy rules
  are tested with a scripted stand-in.
- **Retention after deactivation** (case records are kept) needs legal review against the DPDP Act
  before launch (task T101).
- **Screens with live data** (dashboard, cases, ask, drafts, settings) are checked for accessibility
  and behaviour but not pixel-compared with the prototype; the welcome, sign-in brand panel and
  navigation are pixel-identical.

## Deliberate differences from the prototype

- Sign-in form and registration form are spaced like the Welcome panel. The prototype's CSS rule
  never applied to its `<form>`, leaving the fields cramped.
- Two light-theme colours are slightly darker for WCAG AA contrast: `--muted` `#6B7280` to `#636978`
  and `--gold-ink` `#8A6A33` to `#82622D` (noted at the top of `frontend/src/styles/tokens.css`).
- The prototype's pre-filled credentials and hard-coded answers are gone; data comes from the API.
