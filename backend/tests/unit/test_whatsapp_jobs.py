"""WhatsApp housekeeping: records are kept 90 days, expired lists are removed."""
from datetime import timedelta

from helpers_whatsapp import linked
from sqlalchemy import select

from mrcourt.db.base import utcnow
from mrcourt.models import ConversationState, InboundMessage, Message
from mrcourt.services.whatsapp import jobs


def test_old_delivery_records_incoming_rows_and_expired_lists_are_deleted(db) -> None:
    user = linked(db, "rohan.sharma@example.com")
    now = utcnow()
    for age, label in ((89, "keep"), (91, "drop")):
        db.add(Message(user_id=user.id, kind="reminder", channel="whatsapp", status="read", provider_message_id=label, created_at=now - timedelta(days=age)))
        db.add(InboundMessage(provider="development", provider_message_id=label, sender_hash="h", created_at=now - timedelta(days=age)))
    db.add(ConversationState(user_id=user.id, awaiting="case_choice", options=[], expires_at=now - timedelta(minutes=1)))
    db.commit()
    assert jobs.purge(db, now) == {"messages": 1, "inbound": 1, "state": 1}
    db.commit()
    assert [m.provider_message_id for m in db.scalars(select(Message))] == ["keep"]
    assert [m.provider_message_id for m in db.scalars(select(InboundMessage))] == ["keep"]
    assert db.scalars(select(ConversationState)).all() == []


def test_a_list_that_has_not_expired_is_kept(db) -> None:
    user = linked(db, "rohan.sharma@example.com")
    db.add(ConversationState(user_id=user.id, awaiting="case_choice", options=[], expires_at=utcnow() + timedelta(minutes=3)))
    db.commit()
    assert jobs.purge(db)["state"] == 0
