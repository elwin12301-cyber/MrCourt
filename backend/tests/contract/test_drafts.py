"""Contract tests for /drafts."""

import io
import zipfile

import pytest

API = "/api/v1"


@pytest.fixture
def case_id(advocate_client):
    cases = advocate_client.get(f"{API}/cases").json()
    return next(c["id"] for c in cases if c["title"] == "Sharma v. Verma Traders")


def create(client, template="notice", case_id=None):
    payload = {"template": template}
    if case_id:
        payload["case_id"] = case_id
    return client.post(f"{API}/drafts", json=payload)


def test_requires_sign_in(client):
    assert client.get(f"{API}/drafts").status_code == 401


@pytest.mark.parametrize("template", ["notice", "bail", "reply", "affidavit"])
def test_generate_each_template(advocate_client, case_id, template):
    response = create(advocate_client, template, case_id)
    assert response.status_code == 201
    draft = response.json()
    assert draft["template"] == template
    assert draft["version"] == 1
    assert draft["ai_generated"] is True
    assert draft["title"] and draft["body"] and draft["subtitle"]


def test_notice_uses_case_data_and_keeps_placeholders_for_unknown_facts(advocate_client, case_id):
    body = create(advocate_client, "notice", case_id).json()["body"]
    assert "Anita Sharma" in body and "Verma Traders Pvt. Ltd." in body
    assert "Section 138" in body
    assert "[amount]" in body, "facts we do not hold stay as placeholders, never invented"


def test_draft_without_a_case_is_allowed(advocate_client):
    assert create(advocate_client, "affidavit").status_code == 201


def test_list_and_get(advocate_client, case_id):
    created = create(advocate_client, "bail", case_id).json()
    listed = advocate_client.get(f"{API}/drafts", params={"case_id": case_id}).json()
    assert created["id"] in {d["id"] for d in listed}
    assert advocate_client.get(f"{API}/drafts/{created['id']}").json()["id"] == created["id"]


def test_save_edits_increments_version_and_marks_reviewed(advocate_client, case_id):
    draft = create(advocate_client, "notice", case_id).json()
    saved = advocate_client.put(f"{API}/drafts/{draft['id']}", json={"body": "Edited by the advocate."})
    assert saved.status_code == 200
    body = saved.json()
    assert body["version"] == 2 and body["body"] == "Edited by the advocate."
    assert body["reviewed"] is True
    assert body["ai_generated"] is True, "the review flag stays: the text began as generated"


def test_export_docx_and_pdf(advocate_client, case_id):
    draft = create(advocate_client, "notice", case_id).json()
    docx = advocate_client.post(f"{API}/drafts/{draft['id']}/export", json={"format": "docx"})
    assert docx.status_code == 200
    assert "wordprocessingml" in docx.headers["content-type"]
    with zipfile.ZipFile(io.BytesIO(docx.content)) as z:
        assert b"Section 138" in z.read("word/document.xml")

    pdf = advocate_client.post(f"{API}/drafts/{draft['id']}/export", json={"format": "pdf"})
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")


def test_export_rejects_unknown_format(advocate_client, case_id):
    draft = create(advocate_client, "notice", case_id).json()
    assert advocate_client.post(f"{API}/drafts/{draft['id']}/export", json={"format": "exe"}).status_code == 422


def test_unknown_template_is_rejected(advocate_client):
    assert create(advocate_client, "poem").status_code == 422
