"""Ask MrCourt for clients: same cited answers, never advice about their own case (FR-013, SC-007)."""

import pytest
from sqlalchemy import select

from mrcourt.corpus.ingest import load_sample_corpus
from mrcourt.models import Case

API = "/api/v1"
GENERAL = "What is the punishment for cheque bounce under Section 138 of the NI Act?"
PERSONAL = "Should I accept the settlement offer in my case about the Section 138 cheque bounce?"
DISCLAIMER = "Informational only, not legal advice."


@pytest.fixture
def corpus(db):
    load_sample_corpus(db)
    db.commit()


def ask(client, text, **extra):
    return client.post(f"{API}/questions", json={"text": text, **extra}).json()


def test_a_general_question_gets_a_cited_answer_and_the_standing_reminder(petitioner_client, corpus):
    body = ask(petitioner_client, GENERAL)
    assert body["outcome"] == "cited" and body["citations"]
    assert body["disclaimer"] == DISCLAIMER
    assert body["case_specific_notice"] is None
    assert "your lawyer" in body["lawyer_reminder"].lower()


def test_a_question_about_their_own_case_gets_the_ask_your_lawyer_notice(petitioner_client, corpus):
    body = ask(petitioner_client, PERSONAL)
    assert body["disclaimer"] == DISCLAIMER
    assert "cannot advise" in body["case_specific_notice"].lower()
    assert "your lawyer" in body["case_specific_notice"].lower()
    assert body["lawyer_reminder"]
    # General information may still be given, and it is still cited.
    if body["outcome"] == "cited":
        assert body["citations"]


def test_a_personal_question_with_no_general_source_still_gets_the_notice(petitioner_client, corpus):
    body = ask(petitioner_client, "Will I win my case against my landlord?")
    assert body["outcome"] == "no_reliable_source"
    assert body["case_specific_notice"]
    assert body["disclaimer"] == DISCLAIMER


def test_every_client_answer_carries_the_disclaimer_and_reminder(petitioner_client, corpus):
    for question in (GENERAL, PERSONAL, "How do I register a trademark?", "What is the capital of France?"):
        body = ask(petitioner_client, question)
        assert body["disclaimer"] == DISCLAIMER, question
        assert body["lawyer_reminder"], question


def test_asking_from_within_a_case_does_not_change_the_answer(petitioner_client, db, corpus):
    case = db.scalars(select(Case).where(Case.title == "Sharma v. Verma Traders")).one()
    plain = ask(petitioner_client, GENERAL)
    within = ask(petitioner_client, GENERAL, case_id=str(case.id))
    assert plain["paragraphs"] == within["paragraphs"]
    assert plain["citations"] == within["citations"]
    assert "Sharma v. Verma Traders" not in str(within)  # nothing about the case is used or echoed


def test_advocates_do_not_get_the_client_fields(advocate_client, corpus):
    body = ask(advocate_client, PERSONAL)
    assert body["case_specific_notice"] is None and body["lawyer_reminder"] is None


def test_clients_cannot_use_another_clients_case_id(petitioner_client, db, corpus):
    other = db.scalars(select(Case).where(Case.title == "State v. Imran Khan")).one()
    response = petitioner_client.post(f"{API}/questions", json={"text": GENERAL, "case_id": str(other.id)})
    assert response.status_code == 404
