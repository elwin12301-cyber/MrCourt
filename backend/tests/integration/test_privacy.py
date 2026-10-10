"""Deactivation: personal data goes, case records stay, sign-in stops (FR-015, Clarification 5)."""

from datetime import timedelta

from sqlalchemy import select

from helpers import sign_in
from mrcourt.db.base import utcnow
from mrcourt.models import (
    ActivityEvent, Case, Draft, Hearing, OtpChallenge, Question, User, UserSettings,
)
from mrcourt.services import reminders
from mrcourt.services.notify import OUTBOX

API = "/api/v1"
EMAIL = "rohan.sharma@example.com"


def test_deactivation_removes_personal_data_but_keeps_case_records(advocate_client, db):
    advocate_client.post(f"{API}/questions", json={"text": "What is Section 138?"})
    advocate_client.post(f"{API}/auth/otp/request", json={"identifier": EMAIL})
    user = db.scalars(select(User).where(User.email == EMAIL)).one()
    user_id = user.id
    cases_before = len(db.scalars(select(Case).where(Case.owner_id == user_id)).all())
    drafts_before = len(db.scalars(select(Draft).where(Draft.author_id == user_id)).all())
    hearings_before = len(db.scalars(select(Hearing)).all())

    assert advocate_client.post(f"{API}/me/deactivate", json={"acknowledge_case_retention": True}).status_code == 204
    db.expire_all()

    user = db.get(User, user_id)
    assert user.status == "deactivated" and user.deactivated_at is not None
    assert user.email is None and user.phone is None and user.password_hash is None
    assert user.bar_registration_number is None
    assert user.full_name == "Deactivated user"

    # Personal data is gone...
    assert db.scalars(select(Question).where(Question.user_id == user_id)).all() == []
    assert db.scalars(select(UserSettings).where(UserSettings.user_id == user_id)).all() == []
    assert db.scalars(select(OtpChallenge).where(OtpChallenge.user_id == user_id)).all() == []
    assert db.scalars(select(ActivityEvent).where(ActivityEvent.user_id == user_id)).all() == []
    # ...case records are retained.
    assert len(db.scalars(select(Case).where(Case.owner_id == user_id)).all()) == cases_before
    assert len(db.scalars(select(Draft).where(Draft.author_id == user_id)).all()) == drafts_before
    assert len(db.scalars(select(Hearing)).all()) == hearings_before


def test_deactivated_user_cannot_sign_in_again(advocate_client):
    advocate_client.post(f"{API}/me/deactivate", json={"acknowledge_case_retention": True})
    response = advocate_client.post(f"{API}/auth/login", json={"identifier": EMAIL, "password": "password123"})
    assert response.status_code == 401  # the email no longer exists on the account


def test_deactivated_email_can_be_registered_again(advocate_client, client):
    advocate_client.post(f"{API}/me/deactivate", json={"acknowledge_case_retention": True})
    response = client.post(
        f"{API}/auth/register",
        json={"role": "advocate", "full_name": "Returning", "email": EMAIL, "password": "a-strong-password"},
    )
    assert response.status_code == 201


def test_petitioner_deactivation_ends_their_access_to_shared_cases(client, db):
    sign_in(client, "anita.sharma@example.com")
    client.post(f"{API}/me/deactivate", json={"acknowledge_case_retention": True})
    sign_in_response = client.post(
        f"{API}/auth/login", json={"identifier": "anita.sharma@example.com", "password": "password123"}
    )
    assert sign_in_response.status_code == 401
