from types import SimpleNamespace

from mrcourt.services.question_type import classify

ADVOCATE = SimpleNamespace(role="advocate")
CLIENT = SimpleNamespace(role="petitioner")
ADMIN = SimpleNamespace(role="admin")


def test_law_questions() -> None:
    for q in ("What is the punishment for theft?", "Define cheating", "What does Section 138 say?",
              "ingredients of criminal breach of trust", "Is it bailable?", "திருட்டுக்கு தண்டனை என்ன?"):
        assert classify(q, ADVOCATE) == "law", q


def test_how_courts_decided() -> None:
    for q in ("How have courts decided bail in cheque cases?", "What has the Supreme Court held on res judicata?",
              "precedents on specific performance", "இந்த விஷயத்தில் தீர்ப்பு என்ன?"):
        assert classify(q, ADVOCATE) == "courts", q


def test_my_case_only_for_advocates() -> None:
    q = "What did the witness admit in my case?"
    assert classify(q, ADVOCATE) == "my_case"
    assert classify(q, CLIENT) != "my_case"
    assert classify(q, ADMIN) != "my_case"
    assert classify(q, None) != "my_case"


def test_other() -> None:
    assert classify("Tell me about easements", ADVOCATE) == "other"
