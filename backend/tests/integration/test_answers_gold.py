"""Reviewed gold set: questions with known expected outcomes.

Extend this list whenever the corpus grows. Each entry is reviewed by a person; the expected
outcome and the sections that must be cited are part of the review.
"""

import pytest

from mrcourt.corpus.ingest import load_sample_corpus

API = "/api/v1"

GOLD = [
    # (question, expected outcome, citation labels that must appear)
    (
        "What is the punishment for cheque bounce under Section 138 of the NI Act?",
        "cited",
        ["Negotiable Instruments Act, 1881 · Section 138"],
    ),
    (
        "Which court has jurisdiction for a cheque dishonour complaint under the NI Act?",
        "cited",
        ["Negotiable Instruments Act, 1881 · Section 142"],
    ),
    (
        "How does bail work for non-bailable offences under BNSS?",
        "cited",
        [
            "Bharatiya Nagarik Suraksha Sanhita, 2023 · Section 480",
            "Bharatiya Nagarik Suraksha Sanhita, 2023 · Section 483",
        ],
    ),
    ("How do I register a trademark in India?", "no_reliable_source", []),
    ("What is the capital of France?", "no_reliable_source", []),
    ("Can you recommend a good restaurant near Saket court?", "no_reliable_source", []),
]


@pytest.mark.parametrize(("question", "outcome", "labels"), GOLD)
def test_gold_question(advocate_client, db, question, outcome, labels):
    load_sample_corpus(db)
    db.commit()
    body = advocate_client.post(f"{API}/questions", json={"text": question}).json()
    assert body["outcome"] == outcome
    got = {c["label"] for c in body["citations"]}
    for label in labels:
        assert label in got
    if outcome == "no_reliable_source":
        assert body["citations"] == [] and body["paragraphs"] == []

