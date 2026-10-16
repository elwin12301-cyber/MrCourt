"""The short WhatsApp form of an answer: cut to fit, but sources, disclaimer and the client reminder always stay."""
from types import SimpleNamespace

from mrcourt.services.advice_guard import CASE_SPECIFIC_NOTICE, LAWYER_REMINDER
from mrcourt.services.answering import DISCLAIMER, NO_SOURCE_MESSAGE, AnswerResult
from mrcourt.services.citations import VerifiedParagraph
from mrcourt.services.whatsapp.format import answer_text


def cited(text="Under Section 138 a dishonoured cheque is an offence.", n=1, labels=("NI Act, 1881 · Section 138",), message=None):
    return AnswerResult(
        outcome="cited",
        paragraphs=[VerifiedParagraph(text, list(range(1, n + 1)))],
        citations=[SimpleNamespace(citation_label=label) for label in labels],
        message=message,
    )


def test_a_cited_answer_has_the_answer_its_sources_the_disclaimer_and_a_link() -> None:
    text = answer_text(cited())
    assert "Under Section 138 a dishonoured cheque is an offence. [1]" in text
    assert "Sources:\n[1] NI Act, 1881 · Section 138" in text
    assert DISCLAIMER in text and "Read more: http" in text and text.rstrip().endswith("/ask/history")


def test_a_long_answer_is_cut_at_a_sentence_but_nothing_else_is_dropped() -> None:
    sentences = " ".join(f"Sentence number {i} says something useful about the law." for i in range(60))
    result = cited(sentences, labels=tuple(f"Source {i}" for i in range(7)))
    text = answer_text(result, case_specific_notice=CASE_SPECIFIC_NOTICE, lawyer_reminder=LAWYER_REMINDER)
    assert len(text) < 1800
    assert "Sentence number 59" not in text
    assert "… [1]" in text  # the cut answer still carries its citation mark
    assert "+3 more in MrCourt" in text and "[4] Source 3" in text and "[5] Source 4" not in text
    for must in (DISCLAIMER, LAWYER_REMINDER, CASE_SPECIFIC_NOTICE):
        assert must in text


def test_the_cut_never_ends_in_the_middle_of_a_sentence_when_a_full_stop_is_available() -> None:
    long = "First point is short. " + "word " * 300
    out = answer_text(cited(long))
    answer = out.split("\n\n")[0]
    assert answer.endswith("… [1]") and "First point is short." in answer


def test_no_reliable_source_says_so_with_the_disclaimer() -> None:
    result = AnswerResult(outcome="no_reliable_source", message=NO_SOURCE_MESSAGE)
    text = answer_text(result)
    assert NO_SOURCE_MESSAGE in text and DISCLAIMER in text and "Sources:" not in text


def test_a_missing_section_is_reported_before_the_related_answer() -> None:
    note = "Not found in the sources: Section 999 IPC. The sources below are related, not that provision."
    text = answer_text(cited(message=note))
    assert text.index(note) < text.index("Under Section 138")


def test_a_client_answer_carries_the_lawyer_reminder() -> None:
    text = answer_text(cited(), lawyer_reminder=LAWYER_REMINDER)
    assert LAWYER_REMINDER in text and LAWYER_REMINDER not in answer_text(cited())


def test_a_long_source_name_is_shortened() -> None:
    label = "Indian Penal Code (IPC) (class-room notes), page 76 " + "x" * 200
    assert max(len(line) for line in answer_text(cited(labels=(label,))).splitlines() if line.startswith("[1]")) <= 100
