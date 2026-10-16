"""Voice notes over WhatsApp: quoted back, then answered like typed text; never kept as audio."""
import builtins

import pytest
from helpers import make_document
from helpers_whatsapp import NUMBER, linked, send
from sqlalchemy import select

from mrcourt.config import get_settings
from mrcourt.models import InboundMessage, LegalSource, Question
from mrcourt.services.speech import FakeSpeech, SpeechUnavailable, set_speech
from mrcourt.services.whatsapp import inbound, voice

ROHAN = "rohan.sharma@example.com"
ASK = "What does Section 138 NI Act say about cheque dishonour?"


@pytest.fixture(autouse=True)
def _setup(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "whatsapp_questions_per_minute", 100)
    exact = make_document(db, title="Negotiable Instruments Act, 1881", citation="NI Act s.138", kind="act_section",
                          passages=["Dishonour of cheque for insufficiency of funds in the account."])
    db.flush()
    db.scalars(select(LegalSource).where(LegalSource.document_id == exact.id)).first().section = "138"
    db.commit()
    yield
    set_speech(None)


def reply_to(fake):
    return fake.texts_to(NUMBER)


def test_a_voice_question_is_quoted_back_and_answered(client, db, fake_channel) -> None:
    speech = FakeSpeech([ASK])
    set_speech(speech)
    linked(db, ROHAN)
    send(client, kind="audio", text="", media="MEDIA1")
    (text,) = reply_to(fake_channel)
    assert text.startswith(f"I heard: “{ASK}”\n\n") and "Sources:" in text and "NI Act s.138" in text
    assert fake_channel.fetched == ["MEDIA1"]
    assert speech.codecs == ["ogg"] and speech.calls == [(len(b"fake-ogg"), "en-IN")]
    db.expire_all()
    (question,) = db.scalars(select(Question))
    assert (question.text, question.input_method, question.channel) == (ASK, "voice", "whatsapp")
    (row,) = db.scalars(select(InboundMessage))
    assert (row.kind, row.payload) == ("voice", None)


def test_a_spoken_short_request_is_quoted_and_answered_without_a_question(client, db, fake_channel) -> None:
    set_speech(FakeSpeech(["next hearing"]))
    linked(db, ROHAN)
    send(client, kind="audio", text="", media="MEDIA1")
    (text,) = reply_to(fake_channel)
    assert text.startswith("I heard: “next hearing”") and "Your next hearings:" in text
    assert db.scalars(select(Question)).all() == []


def test_a_voice_note_that_cannot_be_understood_is_not_answered(client, db, fake_channel) -> None:
    set_speech(FakeSpeech([""]))
    linked(db, ROHAN)
    send(client, kind="audio", text="", media="MEDIA1")
    assert reply_to(fake_channel) == [inbound.REPLIES["voice_failed"]]
    assert db.scalars(select(Question)).all() == []


def test_when_the_speech_service_fails_the_person_is_asked_to_try_again(client, db, fake_channel) -> None:
    class Failing:
        def transcribe(self, audio, language, codec="wav"):
            raise SpeechUnavailable("down")

    set_speech(Failing())
    linked(db, ROHAN)
    send(client, kind="audio", text="", media="MEDIA1")
    assert reply_to(fake_channel) == [inbound.REPLIES["voice_failed"]]


def test_without_a_speech_service_voice_notes_are_politely_declined(client, db, fake_channel) -> None:
    set_speech(None, disabled=True)
    linked(db, ROHAN)
    send(client, kind="audio", text="", media="MEDIA1")
    assert reply_to(fake_channel) == [inbound.REPLIES["voice_off"]]
    assert fake_channel.fetched == []  # the audio is not even downloaded


def test_audio_that_cannot_be_fetched_or_is_too_long_gets_its_own_reply(client, db, fake_channel) -> None:
    set_speech(FakeSpeech([ASK]))
    linked(db, ROHAN)
    fake_channel.audio = None
    send(client, kind="audio", text="", media="M1", id="a")
    fake_channel.audio = b"x" * (voice.MAX_BYTES + 1)
    send(client, kind="audio", text="", media="M2", id="b")
    assert reply_to(fake_channel) == [inbound.REPLIES["voice_failed"], inbound.REPLIES["voice_long"]]


def test_the_language_chosen_in_settings_is_used(client, db, fake_channel) -> None:
    speech = FakeSpeech([ASK])
    set_speech(speech)
    user = linked(db, ROHAN)
    user.settings.language = "ta"
    db.commit()
    send(client, kind="audio", text="", media="MEDIA1")
    assert speech.calls[0][1] == "ta-IN"


def test_a_voice_note_from_a_number_that_is_not_linked_is_never_downloaded(client, db, fake_channel) -> None:
    speech = FakeSpeech([ASK])
    set_speech(speech)
    send(client, sender="919123456780", kind="audio", text="", media="MEDIA1")
    assert fake_channel.fetched == [] and speech.calls == []
    assert fake_channel.texts_to("919123456780") == [inbound.REPLIES["unknown"]]


def test_the_audio_is_never_written_to_disk(client, db, fake_channel, monkeypatch) -> None:
    set_speech(FakeSpeech([ASK]))
    linked(db, ROHAN)
    writes = []
    real_open = builtins.open

    def spying(file, mode="r", *args, **kwargs):
        if any(flag in mode for flag in "wax+"):
            writes.append(str(file))
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", spying)
    send(client, kind="audio", text="", media="MEDIA1")
    assert writes == []


def test_the_codec_follows_the_audio_type() -> None:
    assert voice.codec_for("audio/ogg; codecs=opus") == "ogg"
    assert voice.codec_for("audio/mpeg") == "mp3"
    assert voice.codec_for(None) == "ogg"
