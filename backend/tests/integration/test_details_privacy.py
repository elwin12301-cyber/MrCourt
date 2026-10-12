"""Filters by document details (feature 008), and that private details never reach anyone else."""
import json
from pathlib import Path

from helpers import make_document, sign_in
from sqlalchemy import select

from mrcourt.models import User
from mrcourt.services import metadata

API = "/api/v1"
SAMPLES = {d["id"]: d for d in json.loads(
    (Path(__file__).resolve().parents[1] / "data" / "metadata" / "samples.json").read_text(encoding="utf-8"))["documents"]}


def _add(db, sample_id, owner=None, kind=None):
    s = SAMPLES[sample_id]
    doc = make_document(db, title=s["title"], citation=s["title"], kind=kind or ("note" if owner else "judgment"),
                        owner=owner, passages=s["pages"])
    metadata.map_document(db, doc)
    return doc


def _setup(db):
    rohan = db.scalar(select(User).where(User.email == "rohan.sharma@example.com"))
    private = _add(db, "hc_second_appeal", owner=rohan)
    shared_order = _add(db, "writ_order")
    shared_suit = _add(db, "district_suit")
    constitution = _add(db, "statute_page", kind="act_section")
    db.commit()
    return private, shared_order, shared_suit, constitution


def _ids(client, **params):
    return {d["title"] for d in client.get(f"{API}/knowledge/documents", params=params).json()}


def test_list_filters_alone_and_together(advocate_client, db):
    _setup(db)
    assert _ids(advocate_client, type="order") == {"Writ order"}
    assert _ids(advocate_client, court="Madras High Court") == {"Second appeal judgment", "Writ order"}
    assert _ids(advocate_client, type="judgment", year=2024) == {"Second appeal judgment"}
    assert _ids(advocate_client, act="CONSTITUTION", section="226") == {"Writ order"}
    assert _ids(advocate_client, act="CONSTITUTION", section="21") == {"Constitution of India"}
    assert _ids(advocate_client, case="312") == {"Suit judgment"}
    assert _ids(advocate_client, type="deed") == set()


def test_a_client_never_sees_private_values_in_lists_or_filter_options(advocate_client, second_client, db):
    _setup(db)
    sign_in(second_client, "anita.sharma@example.com")
    petitioner_client = second_client
    assert "Second appeal judgment" not in _ids(petitioner_client, court="Madras High Court")
    options = petitioner_client.get(f"{API}/knowledge/documents/filters").json()
    assert 2024 not in options["years"]  # only the private judgment is from 2024
    mine = advocate_client.get(f"{API}/knowledge/documents/filters").json()
    assert 2024 in mine["years"] and "Madras High Court" in mine["courts"]


def test_question_filters_limit_the_sources(advocate_client, db):
    _setup(db)
    body = advocate_client.post(f"{API}/questions", json={
        "text": "What does Article 21 protect about life and personal liberty?",
        "filters": {"act": "CONSTITUTION", "section": "21"},
    }).json()
    assert body["outcome"] == "cited"
    assert {c["label"].split(",")[0] for c in body["citations"]} == {"Constitution of India"}
    assert body["citations"][0]["details"].startswith("Statute · s. 21")


def test_a_filter_that_matches_nothing_says_so(advocate_client, db):
    _setup(db)
    body = advocate_client.post(f"{API}/questions", json={
        "text": "What does Article 21 protect about life and personal liberty?", "filters": {"type": "deed"},
    }).json()
    assert body["outcome"] == "no_reliable_source" and body["citations"] == []
    assert body["message"].startswith("No source matches the filters you chose.")


def test_question_filters_never_open_a_private_document_to_a_client(petitioner_client, db):
    _setup(db)
    body = petitioner_client.post(f"{API}/questions", json={
        "text": "Who was the appellant in the second appeal about the sale deed?",
        "filters": {"court": "Madras High Court"},
    }).json()
    assert all("Second appeal" not in c["label"] for c in body["citations"])
