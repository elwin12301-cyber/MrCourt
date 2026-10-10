"""The generator is untrusted: whatever it returns, unverified answers must never reach users."""

import pytest

from mrcourt.corpus.ingest import load_sample_corpus
from mrcourt.services import answering
from mrcourt.services.citations import GeneratedParagraph

QUESTION = "What is the punishment for cheque bounce under Section 138 of the NI Act?"


@pytest.fixture(autouse=True)
def _restore_generator():
    yield
    answering.set_generator(None)


@pytest.fixture
def loaded(db):
    load_sample_corpus(db)
    db.commit()
    return db


class Fixed:
    def __init__(self, result):
        self.result = result

    def generate(self, question, passages):
        return self.result(passages) if callable(self.result) else self.result


def test_default_generator_gives_a_cited_answer(loaded):
    result = answering.answer_question(loaded, QUESTION)
    assert result.outcome == "cited"
    assert [c.section for c in result.citations][0] == "138"


def test_uncited_paragraph_from_the_generator_is_discarded(loaded):
    answering.set_generator(Fixed([GeneratedParagraph("Two years in jail.", [])]))
    assert answering.answer_question(loaded, QUESTION).outcome == "no_reliable_source"


def test_invented_section_is_discarded(loaded):
    answering.set_generator(
        Fixed(lambda passages: [GeneratedParagraph("See Section 420 for fraud.", [passages[0].id])])
    )
    assert answering.answer_question(loaded, QUESTION).outcome == "no_reliable_source"


def test_generator_failure_fails_closed(loaded):
    answering.set_generator(Fixed(None))
    result = answering.answer_question(loaded, QUESTION)
    assert result.outcome == "no_reliable_source"
    assert result.message == answering.NO_SOURCE_MESSAGE


def test_repealed_provision_is_replaced_by_current_law(loaded):
    result = answering.answer_question(loaded, "When may bail be taken in a non-bailable offence under CrPC 437?")
    labels = [c.citation_label for c in result.citations]
    assert not any("Code of Criminal Procedure" in label for label in labels)
    assert any("Section 480" in label for label in labels)
