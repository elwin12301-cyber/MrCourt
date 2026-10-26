"""The four voice audit actions have plain labels and may not carry any phrase."""
import pytest

from mrcourt.services import audit

ACTIONS = ("voice.consent.on", "voice.consent.off", "voice.cloud.on", "voice.cloud.off")


@pytest.mark.parametrize("action", ACTIONS)
def test_each_voice_action_has_a_plain_label(action) -> None:
    label = audit.ACTION_LABELS[action]
    assert label and "voice" in label.lower()


def test_a_phrase_or_audio_can_never_be_written_to_the_log(db) -> None:
    from mrcourt.models import User
    from sqlalchemy import select

    user = db.scalars(select(User)).first()
    for key in ("text", "body", "content"):
        with pytest.raises(ValueError):
            audit.record(db, user, "voice.consent.on", "user", user.id, **{key: "go to dashboard"})
