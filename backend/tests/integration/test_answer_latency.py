"""Answer latency (SC-004: an answer within 10 seconds).

This measures our own pipeline (retrieval, verification, storage) with the model call replaced by
the built-in extractive generator, so it catches regressions in our code. It cannot measure the
time a live model takes; check that separately in a staging environment.
"""

import statistics
import time

import pytest

from mrcourt.corpus.ingest import load_sample_corpus
from mrcourt.services import ratelimit

API = "/api/v1"
QUESTIONS = [
    "What is the punishment for cheque bounce under Section 138 of the NI Act?",
    "Which court has jurisdiction for a cheque dishonour complaint?",
    "How does bail work for non-bailable offences under BNSS?",
    "How do I register a trademark in India?",
    "What is the capital of France?",
]


@pytest.mark.parametrize("runs", [60])
def test_pipeline_p95_is_well_inside_the_budget(advocate_client, db, runs):
    load_sample_corpus(db)
    db.commit()
    timings = []
    for i in range(runs):
        ratelimit.reset_all()  # the per-user limit is not what is being measured here
        start = time.perf_counter()
        response = advocate_client.post(f"{API}/questions", json={"text": QUESTIONS[i % len(QUESTIONS)]})
        timings.append(time.perf_counter() - start)
        assert response.status_code == 200
    p95 = statistics.quantiles(timings, n=20)[-1]
    # The product budget is 10 s end to end; our own pipeline should use a small part of it.
    assert p95 < 2.0, f"p95 was {p95:.2f}s"
