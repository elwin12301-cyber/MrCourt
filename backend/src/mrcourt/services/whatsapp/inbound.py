"""Incoming WhatsApp messages: keep one row per message (a repeat is ignored), then handle it in the background.

A stranger's number is never stored: only a keyed hash, so repeated senders can be limited. The text (or voice
note reference) of a message waiting to be handled sits in `payload` and is cleared when it has been handled.
"""

import hashlib
import hmac
import logging
import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mrcourt.config import get_settings
from mrcourt.db.base import utcnow
from mrcourt.models import InboundMessage as InboundRow
from mrcourt.models import User
from mrcourt.services import ask
from mrcourt.services.whatsapp import consent, format, intents, voice
from mrcourt.services.whatsapp.channel import InboundMessage, ParsedRequest, get_channel

logger = logging.getLogger(__name__)

QUESTION_MAX_CHARS = 2000  # the same limit as the website
UNKNOWN_REPLIES_PER_DAY = 2  # a stranger gets the "how to link" reply this many times a day, then silence


def _secret() -> bytes:
    secret = get_settings().session_secret or "dev-only-insecure-secret"
    return secret.encode()


def sender_hash(number: str) -> str:
    """A keyed hash of the number: enough to count messages per sender, useless for finding the number."""
    digits = "".join(c for c in number if c.isdigit())
    return hmac.new(_secret(), f"wa:{digits}".encode(), hashlib.sha256).hexdigest()


def store(db: Session, message: InboundMessage) -> InboundRow | None:
    """Keeps the message; returns None when the provider already delivered this one (a repeat)."""
    existing = db.scalar(
        select(InboundRow.id).where(
            InboundRow.provider == message.provider, InboundRow.provider_message_id == message.provider_message_id
        )
    )
    if existing is not None:
        return None
    row = InboundRow(
        provider=message.provider,
        provider_message_id=message.provider_message_id,
        sender_hash=sender_hash(message.sender),
        kind=message.kind,
        payload={
            "sender": message.sender,
            "text": message.text,
            "media_ref": message.media_ref or "",
            "media_type": message.media_type or "",
        },
    )
    try:
        with db.begin_nested():
            db.add(row)
    except IntegrityError:  # the same message arrived twice at once
        return None
    return row


def accept(db: Session, parsed: ParsedRequest) -> list[uuid.UUID]:
    """Stores the new messages of a verified webhook call. Returns the ids to handle in the background."""
    new: list[uuid.UUID] = []
    for message in parsed.messages:
        row = store(db, message)
        if row is not None:
            new.append(row.id)
    return new


# Fixed replies. None of them depends on whether an account exists for the number.
REPLIES = {
    "unknown": "This number is not linked to a MrCourt account. Open MrCourt, go to Settings and choose Link WhatsApp.",
    "limit": "You have sent a lot of messages. Please try again in a few minutes.",
    "busy": "I could not answer just now. Please try again in a minute.",
    "stop": "You will not get WhatsApp messages from MrCourt. You can switch them on again in Settings.",
    "unsupported": "I can read text and voice notes. Open MrCourt to add documents.",
    "voice_off": "Voice notes are not available right now. Please type your question.",
    "voice_failed": "I could not understand that voice note. Please try again, or type your question.",
    "voice_long": "That voice note is too long. Please keep it under 30 seconds, or type your question.",
}


def reply(number: str, text: str) -> None:
    """A free-text reply to a person's own message (inside the provider's 24-hour window). Never raises."""
    try:
        get_channel().send_text(number, text)
    except Exception as error:  # noqa: BLE001 - a reply that cannot be sent is not worth failing the whole step for
        logger.warning("A WhatsApp reply could not be sent (%s)", type(error).__name__)


def _finish(row: InboundRow, status: str = "processed") -> None:
    row.status = status
    row.payload = None  # the text is kept only while the message waits to be handled


def _count_since(db: Session, row: InboundRow, delta: timedelta, kind: str | None = None) -> int:
    query = select(func.count()).select_from(InboundRow).where(
        InboundRow.sender_hash == row.sender_hash, InboundRow.created_at >= utcnow() - delta
    )
    if kind is not None:
        query = query.where(InboundRow.kind == kind)
    return db.scalar(query) or 0


def _stranger(db: Session, row: InboundRow, sender: str, text: str) -> None:
    """A number that is not linked: one fixed reply (a couple of times a day), nothing about any account."""
    if row.kind == "text" and consent.is_stop(text):
        _finish(row)  # a stranger's STOP changes nothing and gets no answer
        return
    row.kind = "unknown_sender"
    db.flush()
    if _count_since(db, row, timedelta(days=1), "unknown_sender") <= UNKNOWN_REPLIES_PER_DAY:
        reply(sender, REPLIES["unknown"])
    _finish(row)


def _over_limit(db: Session, row: InboundRow, sender: str) -> bool:
    """Too many messages from one number. The first message over the limit gets one polite reply."""
    settings = get_settings()
    db.flush()
    per_minute, per_day = settings.whatsapp_questions_per_minute, settings.whatsapp_questions_per_day
    in_minute, in_day = _count_since(db, row, timedelta(minutes=1)), _count_since(db, row, timedelta(days=1))
    if in_minute <= per_minute and in_day <= per_day:
        return False
    if in_minute == per_minute + 1 or in_day == per_day + 1:
        reply(sender, REPLIES["limit"])
    return True


def _question(
    db: Session, row: InboundRow, user: User, sender: str, text: str, input_method: str = "typed", prefix: str = ""
) -> None:
    """A legal question: the same answer as the website (shared sources only), in short form."""
    asked = ask.ask(
        db, user, text[:QUESTION_MAX_CHARS], channel="whatsapp", input_method=input_method, shared_sources_only=True
    )
    row.kind = "question" if input_method == "typed" else "voice"
    row.question_id = asked.question.id
    reply(
        sender,
        prefix
        + format.answer_text(asked.result, case_specific_notice=asked.case_specific_notice, lawyer_reminder=asked.lawyer_reminder),
    )


def _typed_or_spoken(db: Session, row: InboundRow, user: User, sender: str, text: str, spoken: bool) -> None:
    """A short request ("next hearing", "status", ...) or a question; a spoken one starts with what was heard."""
    prefix = f"I heard: “{text}”\n\n" if spoken else ""
    answer = intents.reply_for(db, user, text)
    if answer is not None:  # "next hearing", "status", "today", "help", or a number choosing a case
        row.kind = "status"
        reply(sender, prefix + answer)
    else:
        _question(db, row, user, sender, text, "voice" if spoken else "typed", prefix)


def process(db: Session, row_id: uuid.UUID) -> None:
    """Handles one stored message."""
    row = db.get(InboundRow, row_id)
    if row is None or row.status != "received":
        return
    payload = row.payload or {}
    sender, text = payload.get("sender", ""), payload.get("text", "")
    row.attempts += 1
    user = consent.user_for_number(db, sender)
    if user is None:
        _stranger(db, row, sender, text)
        return
    row.user_id = user.id
    link = consent.get_link(db, user.id)
    if link is not None:
        link.last_inbound_at = utcnow()  # opens the 24-hour window for free-text replies
    if row.kind == "text" and consent.is_stop(text):
        row.kind = "stop"
        consent.stop_all(db, user)
        reply(sender, REPLIES["stop"])
        _finish(row)
        return
    if _over_limit(db, row, sender):
        _finish(row)
        return
    try:
        with db.begin_nested():  # a failure part-way leaves nothing half done
            if row.kind == "text":
                if text.strip():
                    _typed_or_spoken(db, row, user, sender, text.strip(), spoken=False)
            elif row.kind == "audio":
                try:
                    words = voice.transcribe(payload.get("media_ref", ""), payload.get("media_type"), user)
                except voice.VoiceError as error:
                    reply(sender, REPLIES[f"voice_{error.reason}"])
                else:
                    _typed_or_spoken(db, row, user, sender, words, spoken=True)
            else:
                reply(sender, REPLIES["unsupported"])
    except Exception as error:  # noqa: BLE001 - the person gets a short "try again" and no wrong answer
        logger.warning("A WhatsApp message could not be answered (%s)", type(error).__name__)
        reply(sender, REPLIES["busy"])
        _finish(row, "failed")
        return
    _finish(row)
