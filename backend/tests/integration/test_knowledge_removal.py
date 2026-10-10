from datetime import timedelta
from pathlib import Path

import pytest
from helpers import sign_in
from sqlalchemy import select

from mrcourt.config import get_settings
from mrcourt.db.base import utcnow
from mrcourt.models import AnswerCitation, KnowledgeDocument, LegalSource, User

API = "/api/v1/knowledge/documents"
PHRASE = "The zanzibar covenant requires eleven months of notice before termination."
QUESTION = {"text": "How many months of notice does the zanzibar covenant require?"}


@pytest.fixture(autouse=True)
def _knowledge_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "knowledge_dir", str(tmp_path / "knowledge"))


def test_removing_a_private_note_erases_its_text_and_file_but_old_answers_keep_their_label(client, db):
    sign_in(client, "rohan.sharma@example.com")
    doc = client.post(
        API,
        data={"title": "Note", "citation": "Rohan private note"},
        files={"file": ("n.txt", PHRASE.encode(), "text/plain")},
    ).json()
    assert client.post("/api/v1/questions", json=QUESTION).json()["outcome"] == "cited"
    stored = Path(db.scalar(select(KnowledgeDocument.file_path)))
    assert stored.exists()

    assert client.delete(f"{API}/{doc['id']}").status_code == 204

    assert db.scalars(select(LegalSource).where(LegalSource.text.contains("zanzibar"))).first() is None
    assert db.scalars(select(KnowledgeDocument)).all() == []
    assert not stored.exists()
    citation = db.scalars(select(AnswerCitation)).one()
    assert citation.source_id is None and citation.label == "Rohan private note"
    assert client.post("/api/v1/questions", json=QUESTION).json()["outcome"] == "no_reliable_source"


def test_the_sample_corpus_shows_up_as_shared_documents(admin_client, db):
    from mrcourt.corpus.ingest import load_sample_corpus

    load_sample_corpus(db)
    db.commit()
    rows = admin_client.get(API).json()
    assert len(rows) >= 5 and all(r["scope"] == "shared" and r["status"] == "ready" for r in rows)


def test_a_document_stuck_processing_is_shown_as_failed(admin_client, db):
    admin = db.scalar(select(User).where(User.email == "admin@example.com"))
    stuck = KnowledgeDocument(
        title="Stuck",
        citation="Stuck",
        kind="judgment",
        status="processing",
        created_by=admin.id,
        updated_at=utcnow() - timedelta(minutes=30),
    )
    db.add(stuck)
    db.commit()
    row = next(d for d in admin_client.get(API).json() if d["title"] == "Stuck")
    assert row["status"] == "failed" and "did not finish" in row["status_reason"]
    assert admin_client.delete(f"{API}/{row['id']}").status_code == 204
