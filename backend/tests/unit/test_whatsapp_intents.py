"""Which short messages are requests ("next hearing", "status", "today", "help") and which are questions."""
import pytest

from mrcourt.services.whatsapp.intents import parse


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("next hearing", "next_hearing"),
        ("Next hearing please", "next_hearing"),
        ("When is my hearing?", "next_hearing"),
        ("hearing", "next_hearing"),
        ("status", "status"),
        ("What is the status", "status"),
        ("Case status!", "status"),
        ("today", "today"),
        ("hearing today", "today"),
        ("help", "help"),
        ("Hi", "help"),
        ("अगली सुनवाई", "next_hearing"),
        ("स्थिति", "status"),
        ("आज", "today"),
        ("அடுத்த விசாரணை", "next_hearing"),
        ("நிலை", "status"),
        ("இன்று", "today"),
    ],
)
def test_short_requests_are_recognised_in_three_languages(text, intent) -> None:
    assert parse(text) == intent


@pytest.mark.parametrize(
    "text",
    [
        "What is the status of an appeal under Section 100 of the CPC?",
        "Status of FIR",
        "What does Section 138 of the NI Act say about cheque dishonour?",
        "hearing adjournment rules",
        "when is the next hearing in State v. Imran Khan",
        "",
        "12",
    ],
)
def test_real_questions_are_not_mistaken_for_requests(text) -> None:
    assert parse(text) is None
