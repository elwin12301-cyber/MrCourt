"""Shared fixtures. Tests run against in-memory SQLite; the models use portable column types."""

import os

# Settings are cached on first use, so set test environment before importing the app.
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("ENVIRONMENT", "test")
# Tests never call the real services, even when a local .env holds keys.
for _key in ("VOYAGE_API_KEY", "SARVAM_API_KEY", "ANTHROPIC_API_KEY", "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_SMS_FROM", "TWILIO_WHATSAPP_FROM", "TWILIO_API_KEY_SID", "TWILIO_API_KEY_SECRET", "FAST2SMS_API_KEY", "FAST2SMS_WHATSAPP_PHONE_NUMBER_ID"):
    os.environ[_key] = ""

from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import mrcourt.models  # noqa: E402,F401
from mrcourt.db.base import Base, get_db  # noqa: E402
from mrcourt.main import create_app  # noqa: E402
from mrcourt.seed import seed  # noqa: E402
from helpers import sign_in  # noqa: E402
from mrcourt.services import notify, ratelimit  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_in_memory_state() -> Iterator[None]:
    notify.OUTBOX.clear()
    notify.set_notifier(None)
    ratelimit.reset_all()
    yield
    notify.set_notifier(None)


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine) -> Iterator[Session]:
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    seed(session)
    session.commit()
    yield session
    session.close()


def _build_app(engine):
    app = create_app()
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db() -> Iterator[Session]:
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    return app


@pytest.fixture
def app(engine, db):
    return _build_app(engine)


@pytest.fixture
def client(app) -> Iterator[TestClient]:
    with TestClient(app, base_url="http://testserver") as test_client:
        yield test_client


@pytest.fixture
def second_client(app) -> Iterator[TestClient]:
    """A different browser: its own cookies, the same application and database."""
    with TestClient(app, base_url="http://testserver") as test_client:
        yield test_client


@pytest.fixture
def admin_client(second_client: TestClient) -> TestClient:
    sign_in(second_client, "admin@example.com")
    return second_client


@pytest.fixture
def advocate_client(client: TestClient) -> TestClient:
    sign_in(client, "rohan.sharma@example.com")
    return client


@pytest.fixture
def petitioner_client(client: TestClient) -> TestClient:
    sign_in(client, "anita.sharma@example.com")
    return client
