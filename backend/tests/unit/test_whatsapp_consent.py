"""Linking a verified number and choosing what is sent: off by default, one number per account, STOP."""
import pytest
from fastapi import HTTPException
from helpers_whatsapp import NUMBER, linked, verified
from sqlalchemy import select

from mrcourt.db.base import utcnow
from mrcourt.models import MessageConsent, User, WhatsAppLink
from mrcourt.services.whatsapp import consent

RAHUL = "rohan.sharma@example.com"
ANITA = "anita.sharma@example.com"
RAVI = "ravi.mehta@example.com"


def _code(error: pytest.ExceptionInfo) -> str:
    return str(error.value.detail)


def test_linking_needs_a_verified_phone(db) -> None:
    user = db.scalar(select(User).where(User.email == RAHUL))
    with pytest.raises(HTTPException) as error:
        consent.link(db, user)
    assert _code(error) == "phone_not_verified"
    user.phone = "9000000001"  # a number, but not checked with a code
    with pytest.raises(HTTPException) as error:
        consent.link(db, user)
    assert _code(error) == "phone_not_verified"


def test_after_linking_every_kind_is_still_off(db) -> None:
    user = linked(db, RAHUL)
    assert consent.get_link(db, user.id).msisdn == NUMBER
    assert [(k["kind"], k["enabled"]) for k in consent.view(db, user)["kinds"]] == [
        ("codes", False), ("reminders", False), ("activity", False),
    ]
    assert not any(consent.is_enabled(db, user.id, kind) for kind in consent.kinds_for("advocate"))


def test_a_number_belongs_to_one_account_and_the_error_does_not_say_whose(db) -> None:
    linked(db, RAHUL)
    other = verified(db, ANITA, "+919000000001")  # the same number written another way
    with pytest.raises(HTTPException) as error:
        consent.link(db, other)
    assert _code(error) == "number_in_use"
    assert "Rohan" not in str(error.value.detail) and "rohan" not in str(error.value.detail)


def test_a_number_given_up_can_be_linked_by_someone_else(db) -> None:
    first = linked(db, RAHUL)
    consent.unlink(db, first)
    first.phone = None
    db.commit()
    second = verified(db, ANITA, "9000000001")
    consent.link(db, second)
    assert consent.get_link(db, second.id).msisdn == NUMBER
    assert consent.get_link(db, first.id) is None


def test_each_role_has_its_own_kinds(db) -> None:
    assert consent.kinds_for("petitioner") == ("codes", "reminders", "updates")
    assert consent.kinds_for("advocate") == ("codes", "reminders", "activity")
    advocate = linked(db, RAHUL)
    with pytest.raises(HTTPException) as error:
        consent.set_consent(db, advocate, "updates", True)
    assert error.value.status_code == 404


def test_a_kind_can_be_switched_only_after_linking(db) -> None:
    user = verified(db, RAHUL)
    with pytest.raises(HTTPException) as error:
        consent.set_consent(db, user, "reminders", True)
    assert _code(error) == "not_linked"
    consent.link(db, user)
    consent.set_consent(db, user, "reminders", True)
    row = db.get(MessageConsent, (user.id, "reminders"))
    assert row.enabled and row.changed_by == "person" and row.changed_at is not None
    assert consent.is_enabled(db, user.id, "reminders") and not consent.is_enabled(db, user.id, "codes")


def test_unlinking_switches_everything_off_and_stops_the_channel(db) -> None:
    user = linked(db, RAHUL, "codes", "reminders")
    consent.unlink(db, user)
    assert consent.get_link(db, user.id) is None
    assert not any(consent.is_enabled(db, user.id, k) for k in consent.kinds_for("advocate"))
    assert all(not c.enabled for c in db.scalars(select(MessageConsent)))
    assert consent.user_for_number(db, NUMBER) is None


@pytest.mark.parametrize("word", ["STOP", " stop ", "Stop!", "unsubscribe", "रोकें", "நிறுத்து", "stop all"])
def test_stop_words_are_recognised_in_three_languages(word) -> None:
    assert consent.is_stop(word)


@pytest.mark.parametrize("word", ["START", "stop the hearing reminders for my case please", "hello", "", "next hearing"])
def test_other_words_are_not_stop(word) -> None:
    assert not consent.is_stop(word)


def test_stop_switches_everything_off_and_start_turns_nothing_on(db) -> None:
    user = linked(db, ANITA, "reminders", "updates")
    consent.stop_all(db, user)
    rows = {c.kind: c for c in db.scalars(select(MessageConsent).where(MessageConsent.user_id == user.id))}
    assert all(not c.enabled and c.changed_by == "stop" for c in rows.values())
    assert consent.get_link(db, user.id) is not None  # still linked: the person can switch back on in Settings
    from mrcourt.services.whatsapp import inbound
    from mrcourt.services.whatsapp.channel import InboundMessage

    row = inbound.store(db, InboundMessage("development", "m-start", NUMBER, "text", "START"))
    inbound.process(db, row.id)
    assert not any(consent.is_enabled(db, user.id, k) for k in consent.kinds_for("petitioner"))


def test_only_the_verified_linked_owner_of_a_number_is_found(db) -> None:
    user = linked(db, RAVI)
    assert consent.user_for_number(db, NUMBER).id == user.id
    assert consent.user_for_number(db, "919000000099") is None
    user.phone_verified_at = None  # the number is no longer verified
    db.commit()
    assert consent.user_for_number(db, NUMBER) is None


def test_the_number_is_masked_for_display(db) -> None:
    assert consent.mask("919000000172") == "+91 ••••• ••172"
    assert consent.mask(None) is None
