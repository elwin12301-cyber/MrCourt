"""Delivery status only moves forward; a failure is final unless the message was already delivered."""
import pytest
from helpers_whatsapp import linked
from sqlalchemy import select

from mrcourt.db.base import utcnow
from mrcourt.models import Message
from mrcourt.services.whatsapp import outbox
from mrcourt.services.whatsapp.channel import DeliveryReport


@pytest.fixture
def row(db):
    user = linked(db, "rohan.sharma@example.com", "codes")
    message = Message(
        user_id=user.id, kind="code", channel="whatsapp", provider="fake", provider_message_id="p1", status="sent", created_at=utcnow()
    )
    db.add(message)
    db.commit()
    return message


def report(status, reason=None, id="p1"):  # noqa: A002
    return DeliveryReport("fake", id, status, reason)


def test_sent_then_delivered_then_read(db, row) -> None:
    for status in ("delivered", "read"):
        outbox.apply_report(db, report(status))
        assert row.status == status


def test_an_older_status_arriving_late_changes_nothing(db, row) -> None:
    outbox.apply_report(db, report("read"))
    outbox.apply_report(db, report("delivered"))
    outbox.apply_report(db, report("sent"))
    assert row.status == "read"


def test_failed_is_final_and_a_later_delivery_does_not_undo_it(db, row) -> None:
    outbox.apply_report(db, report("failed", "not_on_whatsapp"))
    assert (row.status, row.failure_reason) == ("failed", "not_on_whatsapp")
    outbox.apply_report(db, report("delivered"))
    assert row.status == "failed"


def test_a_failure_reported_after_delivery_is_ignored(db, row) -> None:
    outbox.apply_report(db, report("delivered"))
    outbox.apply_report(db, report("failed", "provider_error"))
    assert (row.status, row.failure_reason) == ("delivered", None)


def test_a_report_for_a_message_we_do_not_know_is_ignored(db, row) -> None:
    outbox.apply_report(db, report("delivered", id="someone-elses"))
    assert [m.status for m in db.scalars(select(Message))] == ["sent"]


def test_the_delivery_record_has_no_column_for_the_words() -> None:
    names = {c.name for c in Message.__table__.columns}
    assert not names & {"text", "body", "message", "content", "words", "variables", "code"}
