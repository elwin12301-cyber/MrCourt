import pytest

from mrcourt.config import get_settings
from mrcourt.corpus.ingest import load_sample_corpus

API = "/api/v1/history"
QUESTION = "What is the punishment for cheque bounce under Section 138 of the NI Act?"


@pytest.fixture(autouse=True)
def _setup(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "")
    load_sample_corpus(db)
    db.commit()


def _seed(client):
    client.post("/api/v1/questions", json={"text": QUESTION})
    client.post("/api/v1/questions", json={"text": "How do I register a trademark in India?"})
    c = client.post("/api/v1/text/conversations", json={}).json()
    client.post(f"/api/v1/text/conversations/{c['id']}/lines", json={"text": "Spoken note about the hearing", "source": "voice"})
    return c


def _texts(client, **params):
    return [i["text"] for i in client.get(API, params=params).json()["items"]]


def test_the_source_filter_separates_ask_from_the_text_assistant(advocate_client):
    _seed(advocate_client)
    assert _texts(advocate_client, source="text") == ["Spoken note about the hearing"]
    assert sorted(_texts(advocate_client, source="ask")) == sorted([QUESTION, "How do I register a trademark in India?"])
    assert len(_texts(advocate_client, source="all")) == 3 == len(_texts(advocate_client))


def test_the_source_filter_combines_with_search_input_and_outcome(advocate_client):
    _seed(advocate_client)
    assert _texts(advocate_client, source="text", q="hearing") == ["Spoken note about the hearing"]
    assert _texts(advocate_client, source="text", q="cheque") == []
    assert _texts(advocate_client, source="text", input="voice") == ["Spoken note about the hearing"]
    assert _texts(advocate_client, source="text", input="typed") == []
    # Saved conversations have no outcome, so outcome filters leave them out.
    assert "Spoken note about the hearing" not in _texts(advocate_client, outcome="answered")
    assert "Spoken note about the hearing" not in _texts(advocate_client, outcome="none")


def test_text_entries_are_in_the_default_list_with_their_label(advocate_client):
    _seed(advocate_client)
    labels = {i["text"]: i["outcome_label"] for i in advocate_client.get(API).json()["items"]}
    assert labels["Spoken note about the hearing"] == "Saved" and labels[QUESTION] == "Answered"


def test_opening_a_live_conversation_entry_shows_it_is_not_deleted(advocate_client):
    c = _seed(advocate_client)
    item = advocate_client.get(API, params={"source": "text"}).json()["items"][0]
    detail = advocate_client.get(f"{API}/{item['id']}").json()
    assert detail["conversation_id"] == c["id"] and detail["conversation_deleted"] is False
    assert detail["lines"][0]["source"] == "voice"
