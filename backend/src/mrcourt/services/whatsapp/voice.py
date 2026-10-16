"""Voice notes over WhatsApp (feature 010): fetched, turned into text in memory, then treated like a typed message.

The audio is held in memory only for this one call and is never written to disk or the database; only the words
are kept, as the person's question. The person is always shown what was understood ("I heard: ...") before the
answer. The language is the one chosen in Settings (English if none).
"""

import logging

from mrcourt.models import User
from mrcourt.services.speech import LANGUAGES, SpeechUnavailable, get_speech
from mrcourt.services.whatsapp.channel import SendError, get_channel

logger = logging.getLogger(__name__)

MAX_BYTES = 1024 * 1024  # a spoken turn under 30 seconds is a few hundred kilobytes in WhatsApp's format

LANGUAGE_FOR = {"en": "en-IN", "hi": "hi-IN", "ta": "ta-IN", "te": "te-IN", "kn": "kn-IN", "ml": "ml-IN", "mr": "mr-IN", "bn": "bn-IN", "gu": "gu-IN"}


class VoiceError(Exception):
    """The voice note could not be turned into words. `reason` picks the reply: off | long | failed."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def language_for(user: User) -> str:
    chosen = (user.settings.language if user.settings else "en") or "en"
    return chosen if chosen in LANGUAGES else LANGUAGE_FOR.get(chosen.split("-")[0].lower(), "en-IN")


def codec_for(mime: str | None) -> str:
    """The audio format name the speech service wants: WhatsApp voice notes are OGG with the Opus codec."""
    mime = (mime or "").lower()
    if "mpeg" in mime or "mp3" in mime:
        return "mp3"
    if "wav" in mime:
        return "wav"
    return "ogg"


def transcribe(media_ref: str, media_type: str | None, user: User) -> str:
    """The words of a voice note. Raises VoiceError."""
    speech = get_speech()
    if speech is None:
        raise VoiceError("off")
    try:
        audio, mime = get_channel().fetch_audio(media_ref)
    except SendError as error:
        raise VoiceError("long" if error.reason == "media_too_large" else "failed") from error
    if len(audio) > MAX_BYTES:
        raise VoiceError("long")
    try:
        text = speech.transcribe(audio, language_for(user), codec_for(media_type or mime))
    except SpeechUnavailable as error:
        raise VoiceError("failed") from error
    except Exception as error:  # noqa: BLE001 - whatever the speech service raises, the person is asked to try again
        logger.warning("A voice note could not be read (%s)", type(error).__name__)
        raise VoiceError("failed") from error
    text = (text or "").strip()
    if len(text) < 2:
        raise VoiceError("failed")
    return text
