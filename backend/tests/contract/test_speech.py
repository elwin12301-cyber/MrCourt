import io
import wave

import pytest

from mrcourt.services.speech import FakeSpeech, set_speech

API = "/api/v1/speech/transcribe"


def _wav(seconds: float = 1.0, rate: int = 16000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(seconds * rate))
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def _reset():
    yield
    set_speech(None)


def _post(client, data=None, language="ta-IN"):
    return client.post(API, data={"language": language}, files={"audio": ("turn.wav", data or _wav(), "audio/wav")})


def test_a_short_turn_is_transcribed_and_nothing_is_kept(advocate_client, tmp_path, monkeypatch):
    speech = FakeSpeech(["வணக்கம்"])
    set_speech(speech)
    response = _post(advocate_client)
    assert response.status_code == 200 and response.json() == {"text": "வணக்கம்"}
    assert speech.calls[0][1] == "ta-IN"
    assert not list(tmp_path.iterdir())  # nothing written next to the tests either


def test_without_a_speech_service_it_says_so(advocate_client):
    set_speech(None, disabled=True)
    response = _post(advocate_client)
    assert response.status_code == 409 and response.json()["detail"] == "speech_unavailable"


def test_every_role_may_use_it(client, second_client):
    from helpers import sign_in

    set_speech(FakeSpeech(["hello", "hello again"]))
    sign_in(client, "anita.sharma@example.com")
    sign_in(second_client, "admin@example.com")
    assert _post(client, language="en-IN").status_code == 200
    assert _post(second_client).status_code == 200


def test_bad_input_is_refused(advocate_client):
    set_speech(FakeSpeech(["x"]))
    assert _post(advocate_client, data=b"not a wav").status_code == 422
    assert _post(advocate_client, language="xx-XX").status_code == 422
    assert _post(advocate_client, data=_wav(40, 8000)).status_code == 413  # too long a turn
    assert _post(advocate_client, data=b"RIFF" + b"\x00" * (2 * 1024 * 1024 + 10)).status_code == 413


def test_a_failing_service_gives_a_calm_message(advocate_client):
    from mrcourt.services.speech import SpeechUnavailable

    class Broken:
        def transcribe(self, wav, language):
            raise SpeechUnavailable("Voice transcription is unavailable right now. Please type instead.")

    set_speech(Broken())
    response = _post(advocate_client)
    assert response.status_code == 502 and "type instead" in response.json()["detail"]


def test_it_is_rate_limited(advocate_client):
    set_speech(FakeSpeech(["x"] * 30))
    codes = [_post(advocate_client).status_code for _ in range(22)]
    assert codes.count(200) == 20 and codes[-1] == 429


def test_it_needs_sign_in(client):
    set_speech(FakeSpeech(["x"]))
    assert _post(client).status_code == 401
