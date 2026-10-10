"""The advice guard spots questions that are about the asker's own case (spec FR-013)."""

import pytest

from mrcourt.services.advice_guard import (
    CASE_SPECIFIC_NOTICE,
    LAWYER_REMINDER,
    looks_case_specific,
)


@pytest.mark.parametrize(
    "question",
    [
        "Should I accept the settlement offer in my case?",
        "Will I win my case?",
        "will i lose the case",
        "What are my chances?",
        "Can I get bail in my case?",
        "My lawyer says to settle. Is that right?",
        "Am I going to go to jail?",
        "What should I do about my notice from the landlord?",
        "Should we settle?",
        "In my case the cheque was returned twice, what happens now?",
        "Do I have a good case against my employer?",
    ],
)
def test_questions_about_the_askers_own_case_are_flagged(question):
    assert looks_case_specific(question)


@pytest.mark.parametrize(
    "question",
    [
        "What is the punishment for cheque bounce under Section 138 of the NI Act?",
        "How does bail work for non-bailable offences under BNSS?",
        "What is the limitation period for a consumer complaint?",
        "Who can file a complaint under Section 142?",
        "How long does a case usually take?",
        "What is an adjournment?",
        "Can a cheque bounce complaint be filed in another city?",
    ],
)
def test_general_questions_are_not_flagged(question):
    assert not looks_case_specific(question)


def test_the_wording_is_plain_and_points_to_the_lawyer():
    assert "cannot advise" in CASE_SPECIFIC_NOTICE.lower()
    assert "your lawyer" in CASE_SPECIFIC_NOTICE.lower()
    assert "your lawyer" in LAWYER_REMINDER.lower()
    assert "general information" in LAWYER_REMINDER.lower()
