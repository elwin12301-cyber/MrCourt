"""Security hardening: headers, cross-origin writes, rate limits and upload checks."""

import io

import pytest

from mrcourt.services import documents

API = "/api/v1"


def test_security_headers_on_every_response(client):
    headers = client.get(f"{API}/health").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "frame-ancestors 'none'" in headers["content-security-policy"]
    assert "microphone=(self)" in headers["permissions-policy"]


def test_cross_origin_writes_are_rejected(advocate_client):
    evil = advocate_client.post(
        f"{API}/questions", json={"text": "What is Section 138?"}, headers={"Origin": "https://evil.example"}
    )
    assert evil.status_code == 403


def test_same_origin_and_non_browser_writes_are_allowed(advocate_client):
    same = advocate_client.post(
        f"{API}/questions", json={"text": "What is Section 138?"}, headers={"Origin": "http://testserver"}
    )
    assert same.status_code == 200
    assert advocate_client.post(f"{API}/questions", json={"text": "What is Section 138?"}).status_code == 200


def test_configured_origins_are_allowed(advocate_client, monkeypatch):
    from mrcourt.config import get_settings

    monkeypatch.setattr(get_settings(), "allowed_origins", "https://app.example.org, http://localhost:5173")
    ok = advocate_client.post(
        f"{API}/questions", json={"text": "What is Section 138?"}, headers={"Origin": "https://app.example.org"}
    )
    assert ok.status_code == 200
    bad = advocate_client.post(
        f"{API}/questions", json={"text": "What is Section 138?"}, headers={"Origin": "https://app.example.org.evil.io"}
    )
    assert bad.status_code == 403


def test_reads_are_not_origin_checked(advocate_client):
    assert advocate_client.get(f"{API}/me", headers={"Origin": "https://evil.example"}).status_code == 200


def test_questions_are_rate_limited_per_user(advocate_client):
    statuses = [
        advocate_client.post(f"{API}/questions", json={"text": f"Question number {i}?"}).status_code
        for i in range(33)
    ]
    assert statuses[:30] == [200] * 30
    assert 429 in statuses[30:]


@pytest.fixture
def case_id(advocate_client):
    return advocate_client.get(f"{API}/cases").json()[0]["id"]


def upload(client, case_id, name, content, content_type):
    return client.post(
        f"{API}/cases/{case_id}/documents", files={"file": (name, io.BytesIO(content), content_type)}
    )


def test_upload_content_must_match_its_declared_type(advocate_client, case_id):
    assert upload(advocate_client, case_id, "a.pdf", b"%PDF-1.7 ok", "application/pdf").status_code == 201
    assert upload(advocate_client, case_id, "fake.pdf", b"MZ\x90\x00 not a pdf", "application/pdf").status_code == 415
    assert upload(advocate_client, case_id, "fake.png", b"%PDF-1.7", "image/png").status_code == 415


def test_upload_scanner_can_reject_a_file(advocate_client, case_id, monkeypatch):
    def reject(data: bytes) -> None:
        raise documents.UnsafeUpload("flagged")

    monkeypatch.setattr(documents, "SCANNER", reject)
    response = upload(advocate_client, case_id, "a.pdf", b"%PDF-1.7 ok", "application/pdf")
    assert response.status_code == 422


def test_uploaded_file_names_cannot_escape_the_upload_folder(advocate_client, case_id):
    response = upload(advocate_client, case_id, "../../evil.pdf", b"%PDF-1.7 ok", "application/pdf")
    assert response.status_code == 201
    assert "/" not in response.json()["file_name"] and ".." not in response.json()["file_name"]
