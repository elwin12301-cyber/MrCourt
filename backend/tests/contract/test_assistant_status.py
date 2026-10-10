from mrcourt.config import get_settings


def test_status_without_a_key_is_passages_only(advocate_client, monkeypatch):
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "")
    body = advocate_client.get("/api/v1/assistant/status").json()
    assert body["answers"] == "passages"
    assert body["assistant"] is False
    assert "cited passages only" in body["notice"]


def test_status_with_a_key_turns_the_assistant_on_for_advocates_and_clients(client, monkeypatch):
    from helpers import sign_in

    monkeypatch.setattr(get_settings(), "anthropic_api_key", "test-key")
    for email in ("rohan.sharma@example.com", "anita.sharma@example.com"):
        sign_in(client, email)
        body = client.get("/api/v1/assistant/status").json()
        assert (body["answers"], body["assistant"], body["notice"]) == ("full", True, None)
        assert body["search"] == "keywords" and body["speech"] is False and "ocr" in body


def test_the_assistant_is_never_offered_to_administrators(admin_client, monkeypatch):
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "test-key")
    assert admin_client.get("/api/v1/assistant/status").json()["assistant"] is False


def test_status_needs_sign_in(client):
    assert client.get("/api/v1/assistant/status").status_code == 401
