from fastapi.testclient import TestClient


def sign_in(client: TestClient, email: str, password: str = "password123") -> None:
    response = client.post("/api/v1/auth/login", json={"identifier": email, "password": password})
    assert response.status_code == 200, response.text


def make_document(db, *, title, citation, passages, owner=None, kind="judgment", status="ready"):
    """Create a knowledge document with ready passages (one string per passage) and return it."""
    from mrcourt.models import KnowledgeDocument, LegalSource

    doc = KnowledgeDocument(
        title=title,
        citation=citation,
        kind=kind,
        owner_id=owner.id if owner else None,
        status=status,
        passage_count=len(passages),
        created_by=owner.id if owner else None,
    )
    db.add(doc)
    db.flush()
    for number, text in enumerate(passages, start=1):
        db.add(
            LegalSource(
                kind=kind,
                instrument=title,
                citation_label=f"{citation}, page {number}",
                text=text,
                document_id=doc.id,
                owner_id=owner.id if owner else None,
                page=number,
            )
        )
    db.flush()
    return doc


class ScriptedModel:
    """Stands in for the model service: replays prepared replies and records what it was asked."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if not self.replies:
            raise AssertionError("The scripted model ran out of replies")
        return self.replies.pop(0)
