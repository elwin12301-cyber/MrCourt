"""Starts an isolated API for end-to-end tests: fresh SQLite database, seeded, on port 8001.

Run from the backend folder:  python scripts/e2e_server.py
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "e2e.db"

os.environ["DATABASE_URL"] = f"sqlite:///{DB.as_posix()}"
os.environ["COOKIE_SECURE"] = "false"
os.environ["ENVIRONMENT"] = "test"
# Browser tests never call the real services, even when backend/.env holds keys.
for _key in ("VOYAGE_API_KEY", "SARVAM_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "WHATSAPP_PROVIDER", "WHATSAPP_ACCESS_TOKEN", "WHATSAPP_APP_SECRET", "WHATSAPP_VERIFY_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_SMS_FROM", "TWILIO_WHATSAPP_FROM", "TWILIO_API_KEY_SID", "TWILIO_API_KEY_SECRET", "FAST2SMS_API_KEY", "FAST2SMS_WHATSAPP_PHONE_NUMBER_ID", "FAST2SMS_WEBHOOK_SECRET"):
    os.environ[_key] = ""
os.environ["ALLOWED_ORIGINS"] = "http://localhost:5174"
os.environ["LOGIN_ATTEMPTS_PER_WINDOW"] = "100000"
os.environ["UPLOAD_DIR"] = str(ROOT / "e2e-uploads")
sys.path.insert(0, str(ROOT / "src"))

if DB.exists():
    DB.unlink()

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

config = Config(str(ROOT / "alembic.ini"))
config.set_main_option("script_location", str(ROOT / "alembic"))
command.upgrade(config, "head")

from mrcourt.corpus.ingest import load_sample_corpus  # noqa: E402
from mrcourt.db.base import get_sessionmaker  # noqa: E402
from mrcourt.seed import seed  # noqa: E402

with get_sessionmaker()() as session:
    seed(session)
    load_sample_corpus(session)
    session.commit()

import json  # noqa: E402

from mrcourt.services import assistant  # noqa: E402


def scripted_assistant(*, system, messages, tools):  # type: ignore[no-untyped-def]
    """A stand-in for the model service so browser tests need no key and no network.

    It decides what to look up from the request, then summarises what the tools returned.
    """
    ask = messages[0]["content"].lower()
    results = [
        block
        for m in messages
        if m["role"] == "user" and isinstance(m["content"], list)
        for block in m["content"]
    ]
    names = {t["name"] for t in tools}

    def data(i: int):  # type: ignore[no-untyped-def]
        return json.loads(results[i]["content"].split(": ", 1)[1])

    def call(name: str, **args):  # type: ignore[no-untyped-def]
        return assistant.ModelReply(tool_calls=[assistant.ToolCall(f"t{len(results)}", name, args)])

    def say(text: str):  # type: ignore[no-untyped-def]
        return assistant.ModelReply(text=json.dumps({"paragraphs": [{"kind": "case", "text": text}]}))

    if "notice" in ask or "draft" in ask:
        if "propose_draft" not in names:
            return say("I cannot create drafts. Please ask your lawyer.")
        if not results:
            return call("list_cases")
        cases = data(0)
        if len(results) == 1 and cases:
            return call("propose_draft", template="notice", case_id=cases[0]["id"])
        return say("I have prepared a legal notice draft. It needs your confirmation.")
    if "hearing" in ask:
        if not results:
            if "list_hearings" in names:
                return call("list_hearings", from_date="2000-01-01", to_date="2100-01-01")
            return call("list_my_hearings")
        return say(f"You have {len(data(0))} upcoming hearings.")
    if not results:
        return call("list_cases" if "list_cases" in names else "list_my_cases")
    return say(f"You have {len(data(0))} cases.")


if os.environ.get("E2E_FAKE_ASSISTANT", "1") == "1":
    assistant.set_model(scripted_assistant)


# Stand-ins for the speech service and OCR, so browser tests need no key, no network and no OCR engine.
from mrcourt.services import ocr, speech  # noqa: E402


class _Speech:
    def transcribe(self, wav, language):  # type: ignore[no-untyped-def]
        return "வணக்கம் from the speech service" if language == "ta-IN" else "Spoken line from the speech service"


class _Ocr:
    def check(self) -> None:
        return None

    def read(self, image):  # type: ignore[no-untyped-def]
        return ocr.OcrPage("The zorvex scanned notice requires eleven days to reply.", 91.0)


if os.environ.get("E2E_FAKE_SPEECH", "1") == "1":
    speech.set_speech(_Speech())
if os.environ.get("E2E_FAKE_OCR", "1") == "1":
    ocr.set_ocr_engine(_Ocr())

import uvicorn  # noqa: E402

uvicorn.run("mrcourt.main:app", host="127.0.0.1", port=8001, log_level="warning")
