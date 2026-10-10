from sqlalchemy import select

from mrcourt.models import Case, User
from mrcourt.services.access import visible_cases
from mrcourt.services.session import (
    hash_password,
    issue_session,
    read_session,
    verify_password,
)


def test_password_round_trip():
    hashed = hash_password("a-long-password")
    assert verify_password(hashed, "a-long-password")
    assert not verify_password(hashed, "wrong")
    assert not verify_password(None, "anything")


def test_session_round_trip_and_tamper(db):
    user = db.scalars(select(User)).first()
    token = issue_session(user.id)
    assert read_session(token) == user.id
    assert read_session(token + "x") is None
    assert read_session(None) is None


def test_advocate_sees_own_cases_petitioner_sees_only_invited(db):
    advocate = db.scalars(select(User).where(User.email == "rohan.sharma@example.com")).one()
    petitioner = db.scalars(select(User).where(User.email == "anita.sharma@example.com")).one()
    assert len(db.scalars(visible_cases(advocate)).all()) == 5
    seen = db.scalars(visible_cases(petitioner)).all()
    assert [c.title for c in seen] == ["Sharma v. Verma Traders"]
    assert all(isinstance(c, Case) for c in seen)


def test_health(client):
    assert client.get("/api/v1/health").json() == {"status": "ok"}
