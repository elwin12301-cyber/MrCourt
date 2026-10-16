"""The administrator's Messages view: counts, failures, health and resend, without any message text."""
import json
from datetime import timedelta

import pytest
from helpers_whatsapp import NUMBER, linked
from sqlalchemy import select

from mrcourt.db.base import utcnow
from mrcourt.models import AuditEntry, Case, Message, User
from mrcourt.services.whatsapp.channel import set_channel

API = "/api/v1/admin/messages"
ANITA = "anita.sharma@example.com"
FIRST = "Sharma v. Verma Traders"


@pytest.fixture
def anita(db):
    return linked(db, ANITA, "reminders", "updates")


@pytest.fixture
def case(db):
    return db.scalars(select(Case).where(Case.title == FIRST)).one()


def upcoming(case):
    from mrcourt.services.cases import aware

    return next(h for h in case.hearings if aware(h.scheduled_at) > utcnow())


def add(db, user, *, kind="reminder", channel="whatsapp", status="sent", reason=None, case=None, hearing=None, fallback_of=None, age=0, pid=None):
    row = Message(
        user_id=user.id, kind=kind, channel=channel, status=status, failure_reason=reason, case_id=case.id if case else None,
        hearing_id=hearing.id if hearing else None, fallback_of=fallback_of, provider="fake", provider_message_id=pid,
        created_at=utcnow() - timedelta(days=age, minutes=age),
    )
    db.add(row)
    db.commit()
    return row


def test_only_administrators_can_open_the_view(advocate_client, client, db) -> None:
    assert client.get(f"{API}/summary").status_code in (401, 403)
    assert advocate_client.get(f"{API}/summary").status_code == 403
    assert advocate_client.get(f"{API}/failures").status_code == 403


def test_the_counts_are_per_kind_channel_and_status_for_the_period(admin_client, db, anita) -> None:
    for status in ("delivered", "delivered", "read", "failed"):
        add(db, anita, status=status, reason="not_on_whatsapp" if status == "failed" else None)
    add(db, anita, channel="sms", status="sent")
    add(db, anita, kind="update", status="queued")
    add(db, anita, status="delivered", age=30)  # outside the 7 days
    body = admin_client.get(f"{API}/summary", params={"days": 7}).json()
    totals = {(t["kind"], t["channel"]): t for t in body["totals"]}
    assert totals[("reminder", "whatsapp")] == {"kind": "reminder", "channel": "whatsapp", "queued": 0, "sent": 0, "delivered": 2, "read": 1, "failed": 1}
    assert totals[("reminder", "sms")]["sent"] == 1 and totals[("update", "whatsapp")]["queued"] == 1
    assert sum(t["delivered"] for t in body["totals"]) == 2
    assert sum(t["delivered"] for t in admin_client.get(f"{API}/summary", params={"days": 90}).json()["totals"]) == 3


def test_the_service_health_follows_recent_provider_failures(admin_client, db, anita, fake_channel) -> None:
    assert admin_client.get(f"{API}/summary").json()["service"]["healthy"] is True  # configured, nothing wrong yet
    for _ in range(3):
        add(db, anita, status="failed", reason="provider_down")
    service = admin_client.get(f"{API}/summary").json()["service"]
    assert service["configured"] is True and service["healthy"] is False
    add(db, anita, status="sent")
    assert admin_client.get(f"{API}/summary").json()["service"]["healthy"] is True


def test_with_no_provider_the_service_is_reported_as_not_connected(admin_client, db) -> None:
    set_channel(None)
    service = admin_client.get(f"{API}/summary").json()["service"]
    assert (service["configured"], service["healthy"], service["provider"]) == (False, None, "none")


def test_failures_show_the_person_and_the_reason_but_never_the_words_or_the_number(admin_client, db, anita, case) -> None:
    failed = add(db, anita, status="failed", reason="not_on_whatsapp", case=case)
    add(db, anita, channel="sms", status="sent", fallback_of=failed.id, case=case)
    add(db, anita, status="delivered", case=case)  # not a failure
    add(db, anita, channel="sms", status="failed", reason="provider_error")  # an SMS failure is not listed here
    response = admin_client.get(f"{API}/failures")
    (item,) = response.json()["items"]
    assert (item["person"], item["reason"], item["kind"], item["fell_back_to_sms"]) == ("Anita Sharma", "not_on_whatsapp", "reminder", True)
    text = json.dumps(response.json())
    assert NUMBER not in text and "9000000001" not in text and FIRST not in text and "Announcement" not in text and "MrCourt:" not in text


def test_failures_are_paged_newest_first(admin_client, db, anita) -> None:
    for age in range(5):
        add(db, anita, status="failed", reason="provider_down", age=age)
    first = admin_client.get(f"{API}/failures", params={"limit": 2}).json()
    assert len(first["items"]) == 2 and first["next_before"]
    second = admin_client.get(f"{API}/failures", params={"limit": 2, "before": first["next_before"]}).json()
    seen = [i["id"] for i in first["items"] + second["items"]]
    assert len(set(seen)) == 4
    last = admin_client.get(f"{API}/failures", params={"limit": 2, "before": second["next_before"]}).json()
    assert len(last["items"]) == 1 and last["next_before"] is None


def test_opening_the_failure_list_is_audited_as_a_count_only(admin_client, db, anita) -> None:
    add(db, anita, status="failed", reason="provider_down")
    admin_client.get(f"{API}/failures")
    db.expire_all()
    (entry,) = db.scalars(select(AuditEntry).where(AuditEntry.action == "whatsapp.admin.failures.view"))
    assert entry.detail == {"shown": 1}


def test_a_failed_reminder_can_be_sent_again_and_it_is_audited_without_the_words(admin_client, db, anita, case, fake_channel) -> None:
    failed = add(db, anita, status="failed", reason="provider_down", case=case, hearing=upcoming(case))
    listed = admin_client.get(f"{API}/failures").json()["items"][0]
    assert listed["can_resend"] is True
    response = admin_client.post(f"{API}/{failed.id}/resend")
    assert response.status_code == 202 and response.json() == {"status": "sent"}
    assert len(fake_channel.templates_to(NUMBER)) == 1 and fake_channel.templates_to(NUMBER)[0][0] == "reminder"
    db.expire_all()
    (entry,) = db.scalars(select(AuditEntry).where(AuditEntry.action == "whatsapp.admin.resend"))
    assert entry.detail == {"kind": "reminder", "result": "sent"}
    # once the person has been reached, a second resend is refused
    assert admin_client.post(f"{API}/{failed.id}/resend").status_code == 409


def test_a_login_code_a_delivered_message_or_an_opted_out_person_cannot_be_resent(admin_client, db, anita, case, fake_channel) -> None:
    code = add(db, anita, kind="code", status="failed", reason="provider_down")
    delivered = add(db, anita, status="delivered", case=case, hearing=upcoming(case))
    assert admin_client.post(f"{API}/{code.id}/resend").status_code == 409
    assert admin_client.post(f"{API}/{delivered.id}/resend").status_code == 409
    failed = add(db, anita, status="failed", reason="provider_down", case=case, hearing=upcoming(case), age=1)
    from mrcourt.services.whatsapp import consent

    consent.set_consent(db, db.get(User, anita.id), "reminders", False)
    db.commit()
    assert admin_client.post(f"{API}/{failed.id}/resend").status_code == 409
    assert fake_channel.sent == []


def test_resend_is_for_administrators_only(advocate_client, db, anita, case) -> None:
    failed = add(db, anita, status="failed", reason="provider_down", case=case, hearing=upcoming(case))
    assert advocate_client.post(f"{API}/{failed.id}/resend").status_code == 403
