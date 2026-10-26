"""Voice control settings: consent, the cloud option and the language. Audited without any phrase or audio."""
import json

from helpers import sign_in
from sqlalchemy import select

from mrcourt.models import AuditEntry

API = "/api/v1/me/settings"


def _voice(body: dict) -> dict:
    return {k: body[k] for k in ("voice_consent", "voice_cloud_opt_in", "voice_language")}


def _actions(db) -> list[str]:
    db.expire_all()
    return [e.action for e in db.scalars(select(AuditEntry).where(AuditEntry.action.like("voice.%")).order_by(AuditEntry.created_at))]


def test_voice_control_starts_off_for_everyone(advocate_client) -> None:
    settings = advocate_client.get("/api/v1/me").json()["settings"]
    assert _voice(settings) == {"voice_consent": False, "voice_cloud_opt_in": False, "voice_language": None}


def test_agreeing_is_kept_and_audited_once(advocate_client, db) -> None:
    body = advocate_client.patch(API, json={"voice_consent": True}).json()
    assert body["voice_consent"] is True
    advocate_client.patch(API, json={"voice_consent": True})  # nothing changed: nothing recorded
    assert advocate_client.get("/api/v1/me").json()["settings"]["voice_consent"] is True
    assert _actions(db) == ["voice.consent.on"]


def test_the_time_of_consent_is_not_returned(advocate_client) -> None:
    body = advocate_client.patch(API, json={"voice_consent": True}).json()
    assert "voice_consent_at" not in body and "voice_consent_at" not in json.dumps(body)


def test_the_cloud_option_needs_consent_first(advocate_client, db) -> None:
    response = advocate_client.patch(API, json={"voice_cloud_opt_in": True})
    assert response.status_code == 422 and "Agree to voice control first" in response.text
    assert _actions(db) == []
    advocate_client.patch(API, json={"voice_consent": True})
    assert advocate_client.patch(API, json={"voice_cloud_opt_in": True}).json()["voice_cloud_opt_in"] is True
    assert _actions(db) == ["voice.consent.on", "voice.cloud.on"]


def test_agreeing_and_choosing_the_cloud_in_one_request_works(advocate_client, db) -> None:
    body = advocate_client.patch(API, json={"voice_consent": True, "voice_cloud_opt_in": True}).json()
    assert (body["voice_consent"], body["voice_cloud_opt_in"]) == (True, True)
    assert _actions(db) == ["voice.consent.on", "voice.cloud.on"]


def test_withdrawing_consent_also_turns_the_cloud_option_off(advocate_client, db) -> None:
    advocate_client.patch(API, json={"voice_consent": True, "voice_cloud_opt_in": True})
    body = advocate_client.patch(API, json={"voice_consent": False}).json()
    assert (body["voice_consent"], body["voice_cloud_opt_in"]) == (False, False)
    assert _actions(db)[-2:] == ["voice.consent.off", "voice.cloud.off"]


def test_withdrawing_when_the_cloud_was_off_writes_one_entry(advocate_client, db) -> None:
    advocate_client.patch(API, json={"voice_consent": True})
    advocate_client.patch(API, json={"voice_consent": False})
    assert _actions(db) == ["voice.consent.on", "voice.consent.off"]


def test_asking_for_cloud_while_withdrawing_is_refused(advocate_client) -> None:
    advocate_client.patch(API, json={"voice_consent": True})
    response = advocate_client.patch(API, json={"voice_consent": False, "voice_cloud_opt_in": True})
    assert response.status_code == 422


def test_the_language_is_one_of_the_launch_languages_or_none(advocate_client) -> None:
    for code in ("en-IN", "hi-IN", "ta-IN"):
        assert advocate_client.patch(API, json={"voice_language": code}).json()["voice_language"] == code
    assert advocate_client.patch(API, json={"voice_language": None}).json()["voice_language"] is None
    for bad in ("fr-FR", "ta", "", "x" * 20):
        assert advocate_client.patch(API, json={"voice_language": bad}).status_code == 422


def test_the_language_choice_is_not_audited(advocate_client, db) -> None:
    advocate_client.patch(API, json={"voice_language": "ta-IN"})
    assert _actions(db) == []


def test_signed_out_people_cannot_change_it(client) -> None:
    assert client.patch(API, json={"voice_consent": True}).status_code == 401


def test_every_role_can_use_it(petitioner_client, admin_client) -> None:
    for who in (petitioner_client, admin_client):
        assert who.patch(API, json={"voice_consent": True}).json()["voice_consent"] is True


def test_audit_entries_hold_only_who_and_when(advocate_client, db) -> None:
    advocate_client.patch(API, json={"voice_consent": True, "voice_cloud_opt_in": True, "voice_language": "ta-IN"})
    advocate_client.patch(API, json={"voice_consent": False})
    db.expire_all()
    for entry in db.scalars(select(AuditEntry).where(AuditEntry.action.like("voice.%"))):
        assert not entry.detail
        assert "ta-IN" not in json.dumps(entry.detail) and entry.target_type == "user"
