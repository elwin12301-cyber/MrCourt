import pytest
from fpdf import FPDF
from helpers import sign_in
from sqlalchemy import select

from mrcourt.config import get_settings
from mrcourt.models import AuditEntry, LegalSource

API = "/api/v1/knowledge/documents"
PHRASE = "The zanzibar covenant requires eleven months of notice before termination."


@pytest.fixture(autouse=True)
def _knowledge_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "knowledge_dir", str(tmp_path / "knowledge"))


def _pdf(pages: list[str]) -> bytes:
    pdf = FPDF()
    for text in pages:
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.multi_cell(0, 8, text)
    return bytes(pdf.output())


def _add(client, title="Zanzibar note", citation="Zanzibar v. State", files=None, **extra):
    return client.post(API, data={"title": title, "citation": citation, **extra}, files=files)


def test_an_administrator_adds_shared_text_that_is_ready_at_once(admin_client):
    response = _add(admin_client, kind="judgment", text=PHRASE)
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["scope"], body["status"], body["kind"], body["can_remove"]) == ("shared", "ready", "judgment", True)
    assert body["passage_count"] == 1


def test_an_uploaded_pdf_becomes_ready_with_page_numbers(admin_client, db):
    long_page = " ".join([PHRASE] * 3)
    pdf = _pdf([long_page, "The second page talks about the quokka reserve and its rules. " * 3])
    response = _add(admin_client, title="Two pages", citation="Two v. Pages", files={"file": ("two.pdf", pdf, "application/pdf")})
    assert response.status_code == 201
    row = next(d for d in admin_client.get(API).json() if d["title"] == "Two pages")
    assert row["status"] == "ready" and row["page_count"] == 2
    labels = sorted(s.citation_label for s in db.scalars(select(LegalSource).where(LegalSource.instrument == "Two pages")))
    assert labels == ["Two v. Pages, page 1", "Two v. Pages, page 2"]


@pytest.mark.parametrize(
    ("name", "content", "reason"),
    [
        ("empty.txt", b"   \n  ", "No readable text"),
        ("scan.pdf", _pdf(["x"]), "needs OCR"),
        ("broken.pdf", b"%PDF-1.4 not really", "not a readable PDF"),
    ],
)
def test_unreadable_files_end_failed_with_a_plain_reason(admin_client, name, content, reason):
    response = _add(admin_client, title=name, citation=name, files={"file": (name, content, "application/octet-stream")})
    assert response.status_code == 201
    row = next(d for d in admin_client.get(API).json() if d["title"] == name)
    assert row["status"] == "failed" and reason in row["status_reason"]


def test_unsupported_and_oversized_files_are_refused(admin_client, monkeypatch):
    assert _add(admin_client, files={"file": ("a.exe", b"MZ", "application/octet-stream")}).status_code == 422
    monkeypatch.setattr(get_settings(), "max_knowledge_bytes", 10)
    assert _add(admin_client, files={"file": ("a.txt", b"x" * 50, "text/plain")}).status_code == 413


def test_text_and_file_are_not_both_or_neither(admin_client):
    assert _add(admin_client).status_code == 422
    assert _add(admin_client, text="hello world", files={"file": ("a.txt", b"hello", "text/plain")}).status_code == 422


def test_the_same_title_twice_is_refused(admin_client):
    assert _add(admin_client, text=PHRASE).status_code == 201
    assert _add(admin_client, text=PHRASE).status_code == 409


def test_advocates_add_private_notes_only_they_can_see_or_use(client, second_client):
    sign_in(client, "rohan.sharma@example.com")
    sign_in(second_client, "admin@example.com")
    body = _add(client, title="My note", citation="My note", kind="judgment", text=PHRASE).json()
    assert (body["scope"], body["kind"]) == ("private", "note")
    assert [d["title"] for d in client.get(API).json() if d["scope"] == "private"] == ["My note"]
    # The administrator sees it, with its owner, and may remove it (recorded in the audit log).
    admin_row = next(d for d in second_client.get(API).json() if d["title"] == "My note")
    assert admin_row["owner"] == "rohan" and admin_row["can_remove"] is True
    assert second_client.delete(f"{API}/{body['id']}").status_code == 204


def test_clients_can_read_shared_titles_but_not_add_or_remove(client, second_client):
    sign_in(second_client, "admin@example.com")
    shared = _add(second_client, text=PHRASE).json()
    sign_in(client, "anita.sharma@example.com")
    rows = client.get(API).json()
    assert [r["title"] for r in rows] == ["Zanzibar note"]
    assert rows[0]["passage_count"] is None and rows[0]["can_remove"] is False
    assert _add(client, title="Mine", citation="Mine", text="hello world").status_code == 403
    assert client.delete(f"{API}/{shared['id']}").status_code == 403


def test_advocates_cannot_remove_shared_sources(client, second_client):
    sign_in(second_client, "admin@example.com")
    shared = _add(second_client, text=PHRASE).json()
    sign_in(client, "rohan.sharma@example.com")
    assert client.delete(f"{API}/{shared['id']}").status_code == 403


def test_search_and_filters(admin_client):
    _add(admin_client, title="Alpha act", citation="Alpha Act", kind="act_section", text="alpha alpha text here")
    _add(admin_client, title="Beta case", citation="Beta v. State", kind="judgment", text="beta beta text here")

    def titles(**params):
        return sorted(d["title"] for d in admin_client.get(API, params=params).json())

    assert titles(q="alpha") == ["Alpha act"]
    assert titles(kind="judgment", q="beta") == ["Beta case"]
    assert titles(status="failed") == []


def test_shared_adds_and_removes_are_audited_without_content(admin_client, db):
    body = _add(admin_client, text=PHRASE).json()
    assert admin_client.delete(f"{API}/{body['id']}").status_code == 204
    entries = db.scalars(select(AuditEntry).where(AuditEntry.action.like("knowledge.%")).order_by(AuditEntry.created_at)).all()
    assert [e.action for e in entries] == ["knowledge.add", "knowledge.remove"]
    assert all(set(e.detail) == {"title", "citation"} for e in entries)
    assert all(PHRASE not in str(e.detail) for e in entries)


def test_private_adds_are_not_audited(client, db):
    sign_in(client, "rohan.sharma@example.com")
    _add(client, text=PHRASE)
    assert db.scalars(select(AuditEntry).where(AuditEntry.action.like("knowledge.%"))).first() is None


def test_a_new_source_is_used_for_answers_and_a_removed_one_is_not(admin_client, second_client):
    sign_in(second_client, "rohan.sharma@example.com")

    def ask():
        return second_client.post("/api/v1/questions", json={"text": "How many months of notice does the zanzibar covenant require?"}).json()

    assert ask()["outcome"] == "no_reliable_source"
    doc = _add(admin_client, citation="Zanzibar v. State", text=PHRASE).json()
    first = ask()
    assert first["outcome"] == "cited" and first["citations"][0]["label"].startswith("Zanzibar v. State")
    admin_client.delete(f"{API}/{doc['id']}")
    assert ask()["outcome"] == "no_reliable_source"


def test_unauthenticated_requests_are_refused(client):
    assert client.get(API).status_code == 401
