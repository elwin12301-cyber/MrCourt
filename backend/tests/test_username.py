"""Usernames: chosen at sign-up, unique, and usable to sign in."""
from fastapi.testclient import TestClient

PASSWORD = "a-strong-password"


def _register(client: TestClient, **over):
    body = {"role": "petitioner", "full_name": "Nina Rao", "username": "nina.rao", "email": "nina@example.com",
            "phone": "+919800000001", "password": PASSWORD}
    body.update(over)
    return client.post("/api/v1/auth/register", json=body)


def test_sign_up_stores_the_username_and_returns_it(client: TestClient) -> None:
    response = _register(client)
    assert response.status_code == 201
    assert client.get("/api/v1/me").json()["username"] == "nina.rao"


def test_username_is_unique_ignoring_capitals(client: TestClient) -> None:
    assert _register(client).status_code == 201
    other = _register(client, username="NINA.RAO", email="other@example.com", phone="+919800000002")
    assert other.status_code == 409
    assert "username is taken" in other.json()["detail"]


def test_reserved_and_malformed_usernames_are_refused(client: TestClient) -> None:
    assert _register(client, username="admin").status_code == 409
    for bad in ["ab", "1starts-with-digit", "has space", "x" * 31, "semi;colon"]:
        assert _register(client, username=bad, email=f"{len(bad)}@example.com", phone=None).status_code == 422, bad


def test_signing_in_with_the_username_any_capitals(client: TestClient) -> None:
    _register(client)
    client.post("/api/v1/auth/logout")
    ok = client.post("/api/v1/auth/login", json={"identifier": "Nina.RAO", "password": PASSWORD})
    assert ok.status_code == 200
    assert client.get("/api/v1/me").json()["username"] == "nina.rao"
    bad = client.post("/api/v1/auth/login", json={"identifier": "nina.rao", "password": "wrong-password-1"})
    assert bad.status_code == 401


def test_admin_cannot_be_created_through_sign_up(client: TestClient) -> None:
    assert _register(client, role="admin").status_code == 422


def test_a_username_alone_does_not_match_someone_elses_phone_or_email(client: TestClient) -> None:
    _register(client)
    client.post("/api/v1/auth/logout")
    other = client.post("/api/v1/auth/login", json={"identifier": "nina", "password": PASSWORD})
    assert other.status_code == 401
