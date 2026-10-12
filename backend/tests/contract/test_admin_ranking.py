"""GET /admin/questions/{id}/ranking: why each source ranked where it did (feature 009)."""
import uuid

from helpers import make_document
from sqlalchemy import select

from mrcourt.corpus.ingest import load_sample_corpus
from mrcourt.models import AuditEntry, User

API = "/api/v1"


def _ask(client, text):
    response = client.post(f"{API}/questions", json={"text": text})
    assert response.status_code == 200, response.text
    return response.json()["question_id"]


def test_admins_see_scores_and_signals(advocate_client, admin_client, db):
    load_sample_corpus(db)
    db.commit()
    qid = _ask(advocate_client, "What is the punishment for cheque bounce under Section 138 of the NI Act?")
    body = admin_client.get(f"{API}/admin/questions/{qid}/ranking").json()
    assert body["recorded"] is True and body["mode"] == "hybrid"
    assert body["question_type"] == "law"
    first = body["passages"][0]
    assert first["position"] == 1 and not first["hidden"] and first["label"]
    assert set(first["scores"]) == {"keyword", "meaning", "rerank", "combined"}
    assert db.scalars(select(AuditEntry).where(AuditEntry.action == "answer.ranking.view")).first() is not None


def test_only_administrators(advocate_client, petitioner_client):
    qid = _ask(advocate_client, "What is the punishment for dishonour of a cheque?")
    assert advocate_client.get(f"{API}/admin/questions/{qid}/ranking").status_code == 403


def test_unknown_question(admin_client):
    assert admin_client.get(f"{API}/admin/questions/{uuid.uuid4()}/ranking").status_code == 404


def test_another_users_private_document_is_hidden(advocate_client, admin_client, db):
    rohan = db.scalar(select(User).where(User.email == "rohan.sharma@example.com"))
    make_document(db, title="WP 11944-2013 Order", citation="WP 11944-2013 Order", kind="note", owner=rohan,
                  passages=["W.P.No.11944 of 2013. The writ petition is allowed; zanzibar order set aside."])
    db.commit()
    qid = _ask(advocate_client, "Summarise W.P. 11944/2013 zanzibar order")
    body = admin_client.get(f"{API}/admin/questions/{qid}/ranking").json()
    private = [p for p in body["passages"] if p["hidden"]]
    assert private and private[0]["label"] is None
    assert all(s["name"] != "exact_reference" for p in private for s in p["signals"])
    assert "11944" not in str(private)


def test_answers_from_before_this_feature_say_not_recorded(advocate_client, admin_client, db, monkeypatch):
    from mrcourt.config import get_settings

    monkeypatch.setattr(get_settings(), "ranking_mode", "rrf")  # the old ranker records nothing
    qid = _ask(advocate_client, "What is the punishment for dishonour of a cheque?")
    body = admin_client.get(f"{API}/admin/questions/{qid}/ranking").json()
    assert body == {"question_id": qid, "recorded": False, "mode": None, "question_type": None, "references": [], "passages": []}
