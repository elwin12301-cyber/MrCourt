"""Speech to text for Indian languages, through Sarvam AI.

Audio is held in memory for the length of one call and handed to the service; MrCourt never writes
it to disk or a database. Turns are short (the service's direct limit is about 30 seconds).
"""

import io
import logging
from dataclasses import dataclass, field
from typing import Protocol

from mrcourt.config import get_settings

logger = logging.getLogger(__name__)

MAX_SECONDS = 28.0
LANGUAGES = ("en-IN", "hi-IN", "ta-IN", "te-IN", "kn-IN", "ml-IN", "mr-IN", "bn-IN", "gu-IN")


class SpeechUnavailable(Exception):
    """The speech service cannot be used. The message is safe to show."""


class SpeechToText(Protocol):
    def transcribe(self, wav: bytes, language: str, codec: str = "wav") -> str: ...


class SarvamSpeech:
    def __init__(self, api_key: str, model: str) -> None:
        from sarvamai import SarvamAI

        self._client = SarvamAI(api_subscription_key=api_key)
        self.model = model

    def transcribe(self, wav: bytes, language: str, codec: str = "wav") -> str:
        """`codec` names the audio format: "wav" from the website, "ogg" or "opus" for WhatsApp voice notes."""
        mime = {"wav": "audio/wav", "ogg": "audio/ogg", "opus": "audio/ogg", "mp3": "audio/mpeg"}.get(codec, "audio/ogg")
        try:
            response = self._client.speech_to_text.transcribe(
                file=(f"turn.{codec}", io.BytesIO(wav), mime),
                model=self.model,
                mode="transcribe",
                language_code=language,
                input_audio_codec=codec,  # type: ignore[arg-type]
            )
            return str(getattr(response, "transcript", "") or "").strip()
        except Exception as exc:  # noqa: BLE001 - the SDK raises many HTTP error types
            logger.warning("Speech service failed", exc_info=True)
            raise SpeechUnavailable("Voice transcription is unavailable right now. Please type instead.") from exc


@dataclass
class FakeSpeech:
    """Deterministic stand-in for tests: returns queued texts in order."""

    texts: list[str] = field(default_factory=list)
    calls: list[tuple[int, str]] = field(default_factory=list)  # (audio bytes, language)
    codecs: list[str] = field(default_factory=list)

    def transcribe(self, wav: bytes, language: str, codec: str = "wav") -> str:
        self.calls.append((len(wav), language))
        self.codecs.append(codec)
        return self.texts.pop(0) if self.texts else ""


_override: SpeechToText | None = None
_disabled = False


def set_speech(provider: SpeechToText | None, *, disabled: bool = False) -> None:
    """Test hook: replace the speech service. `disabled=True` imitates having no key."""
    global _override, _disabled
    _override, _disabled = provider, disabled


def get_speech() -> SpeechToText | None:
    if _override is not None:
        return _override
    if _disabled:
        return None
    settings = get_settings()
    return SarvamSpeech(settings.sarvam_api_key, settings.stt_model) if settings.sarvam_api_key else None


def available() -> bool:
    return get_speech() is not None
