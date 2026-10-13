"""Document details (feature 008): view, correct, and map again."""
import json
from pathlib import Path

from helpers import make_document, sign_in
from sqlalchemy import select

from mrcourt.models import AuditEntry, KnowledgeDocument, LegalSource, User
from mrcourt.services import metadata

API = "/api/v1/knowledge"
SAMPLES = {d["id"]: d for d in json.loads(
    (Path(__file__).resolve().parents[1] / "data" / "metadata" / "samples.json").read_text(encoding="utf-8"))["documents"]}


def _user(db, email):
    return db.scalar(select(User).where(User.email == email))


def _private_judgment(db, owner_email="rohan.sharma@example.com"):
    sample = SAMPLES["hc_second_appeal"]
    doc = make_document(db, title=sample["title"], citation="Second appeal", kind="note",
                        owner=_user(db, owner_email), passages=sample["pages"])
    metadata.map_document(db, doc)
    db.commit()
    return doc


def _shared_order(db):
    sample = SAMPLES["writ_order"]
    doc = make_document(db, title=sample["title"], citation="Writ order", kind="judgment", passages=sample["pages"])
    metadata.map_document(db, doc)
    db.commit()
    return doc


def test_the_owner_sees_every_field_with_its_confidence(advocate_client, db):
    doc = _private_judgment(db)
    body = advocate_client.get(f"{API}/documents/{doc.id}/details").json()
    assert body["can_edit"] is True and body["text_quality"] == "readable"
    assert body["fields"]["court"] == {"value": "Madras High Court", "confidence": "found", "source": "text"}
    assert body["fields"]["outcome"]["value"] == "dismissed"
    row = next(d for d in advocate_client.get(f"{API}/documents").json() if d["id"] == str(doc.id))
    assert row["details"]["short"] == "Judgment · Madras High Court · 19 Mar 2024 · S.A. 2207/2018"


def test_clients_and_other_advocates_never_see_private_details(advocate_client, second_client, db):
    doc = _private_judgment(db)
    sign_in(second_client, "anita.sharma@example.com")
    assert second_client.get(f"{API}/documents/{doc.id}/details").status_code == 404
    assert all(d["id"] != str(doc.id) for d in second_client.get(f"{API}/documents").json())
    other = User(role="advocate", full_name="Other Advocate", email="other.advocate@example.com", username="otheradv",
                 password_hash="x")
    db.add(other)
    db.commit()
    theirs = _private_judgment(db, owner_email="other.advocate@example.com")
    assert advocate_client.get(f"{API}/documents/{theirs.id}/details").status_code == 404
    assert all(d["id"] != str(theirs.id) for d in advocate_client.get(f"{API}/documents").json())


def test_administrators_see_private_documents_and_every_view_is_audited(admin_client, db):
    doc = _private_judgment(db)
    row = next(d for d in admin_client.get(f"{API}/documents").json() if d["id"] == str(doc.id))
    assert row["scope"] == "private" and row["owner"] == "rohan" and row["can_remove"] is False
    body = admin_client.get(f"{API}/documents/{doc.id}/details").json()
    assert body["fields"]["court"]["value"] == "Madras High Court"
    assert body["can_edit"] is False  # seeing is not correcting: only the owner corrects
    assert admin_client.patch(f"{API}/documents/{doc.id}/details", json={"fields": {"court": "X"}}).status_code == 403
    passage = db.scalar(select(LegalSource).where(LegalSource.document_id == doc.id))
    read = admin_client.get(f"{API}/passages/{passage.id}")
    assert read.status_code == 200 and read.json()["scope"] == "private"
    actions = [e.action for e in db.scalars(select(AuditEntry))]
    assert {"knowledge.private.list", "knowledge.private.details", "knowledge.private.passage"} <= set(actions)
    entries = db.scalars(select(AuditEntry).where(AuditEntry.action.like("knowledge.private.%"))).all()
    assert "Velan" not in json.dumps([e.detail for e in entries])  # who and which, never content


def test_a_correction_is_kept_when_mapped_again(advocate_client, db):
    doc = _private_judgment(db)
    response = advocate_client.patch(f"{API}/documents/{doc.id}/details",
                                     json={"fields": {"court": "High Court of Madras (Madurai Bench)", "outcome": None}})
    assert response.status_code == 200
    fields = response.json()["fields"]
    assert fields["court"]["confidence"] == "confirmed" and fields["court"]["source"] == "person"
    assert fields["outcome"] == {**fields["outcome"], "value": None, "confidence": "confirmed"}
    assert advocate_client.post(f"{API}/documents/remap").status_code == 200
    db.expire_all()
    again = db.get(KnowledgeDocument, doc.id)
    assert again.details["court"]["value"] == "High Court of Madras (Madurai Bench)"
    assert again.court == "High Court of Madras (Madurai Bench)"
    assert again.details["outcome"]["value"] is None


def test_corrections_are_checked(advocate_client, db):
    doc = _private_judgment(db)
    for bad in ({"decided_on": "19/03/2024"}, {"doc_type": "poem"}, {"judges": "one name"}, {"nonsense": "x"},
                {"text_quality": "readable"}):
        assert advocate_client.patch(f"{API}/documents/{doc.id}/details", json={"fields": bad}).status_code == 422, bad


def test_only_administrators_correct_shared_documents_and_it_is_audited(advocate_client, admin_client, db):
    doc = _shared_order(db)
    assert advocate_client.patch(f"{API}/documents/{doc.id}/details", json={"fields": {"outcome": "dismissed"}}).status_code == 403
    assert admin_client.patch(f"{API}/documents/{doc.id}/details", json={"fields": {"outcome": "dismissed"}}).status_code == 200
    entry = db.scalars(select(AuditEntry).where(AuditEntry.action == "knowledge.details.edit")).first()
    assert entry is not None and entry.detail["fields"] == ["outcome"]


def test_remap_scope(advocate_client, admin_client, db):
    private = _private_judgment(db)
    _shared_order(db)
    private.details = None
    db.commit()
    summary = admin_client.post(f"{API}/documents/remap").json()
    assert summary["documents"] >= 1
    db.expire_all()
    assert db.get(KnowledgeDocument, private.id).details is None  # the administrator never maps private documents
    assert advocate_client.post(f"{API}/documents/remap").json()["fields_found"]["court"] == 1
    sign_in(advocate_client, "anita.sharma@example.com")  # now the client, in the same browser
    assert advocate_client.post(f"{API}/documents/remap").status_code == 403


def test_details_appear_on_a_passage(advocate_client, db):
    doc = _private_judgment(db)
    passage = advocate_client.get(f"{API}/documents").json()
    from mrcourt.models import LegalSource

    first = db.scalars(select(LegalSource).where(LegalSource.document_id == doc.id).order_by(LegalSource.page)).first()
    body = advocate_client.get(f"{API}/passages/{first.id}").json()
    assert body["details"]["court"] == "Madras High Court"
    assert body["details_label"].startswith("Judgment · Madras High Court")
    assert passage
