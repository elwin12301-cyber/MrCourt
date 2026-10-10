import io
import wave
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from mrcourt.api.deps import CurrentUser
from mrcourt.services import ratelimit
from mrcourt.services.speech import LANGUAGES, MAX_SECONDS, SpeechUnavailable, get_speech

router = APIRouter(prefix="/speech", tags=["speech"])

MAX_BYTES = 2 * 1024 * 1024


class Transcript(BaseModel):
    text: str


def _wav_seconds(data: bytes) -> float:
    try:
        with wave.open(io.BytesIO(data)) as w:
            return w.getnframes() / float(w.getframerate() or 1)
    except (wave.Error, EOFError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "That is not a WAV recording") from exc


@router.post("/transcribe", response_model=Transcript)
async def transcribe(
    user: CurrentUser,
    audio: Annotated[UploadFile, File()],
    language: Annotated[str, Form()] = "en-IN",
) -> Transcript:
    """Turns one short spoken turn into text. The audio is read into memory, passed to the speech
    service and forgotten; nothing is stored."""
    speech = get_speech()
    if speech is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "speech_unavailable")
    if language not in LANGUAGES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Choose one of the offered languages")
    ratelimit.hit(f"speech:{user.id}", limit=20, window_seconds=60)

    data = await audio.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "That recording is too long. Keep each turn short.")
    if _wav_seconds(data) > MAX_SECONDS + 1:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "That recording is too long. Keep each turn under 28 seconds.")
    try:
        text = await run_in_threadpool(speech.transcribe, data, language)
    except SpeechUnavailable as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return Transcript(text=text)
