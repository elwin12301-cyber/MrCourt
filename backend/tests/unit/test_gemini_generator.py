import json
import uuid
from types import SimpleNamespace

import httpx

from mrcourt.config import get_settings
from mrcourt.services.answering import ExtractiveGenerator, GeminiGenerator, get_generator


def passages():
    return [SimpleNamespace(id=uuid.uuid4(), citation_label=f"Act {n}", text=f"Text {n}") for n in (1, 2)]


def generator(handler):
    return GeminiGenerator(client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda _: None)


def reply(text, **extra):
    return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": text}, *extra.get("more", [])]}}]})


def test_the_reply_is_turned_into_cited_paragraphs_and_invented_labels_are_dropped(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "gemini_api_key", "test-key")
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["key"] = request.headers["x-goog-api-key"]
        seen["body"] = json.loads(request.content)
        return reply(json.dumps({"paragraphs": [{"text": "A.", "sources": ["S1", "S9"]}, {"text": "B.", "sources": ["S2"]}]}))

    p = passages()
    out = generator(handler).generate("What?", p)
    assert [(x.text, x.source_ids) for x in out] == [("A.", [p[0].id]), ("B.", [p[1].id])]
    assert seen["key"] == "test-key"
    assert "[S1] Act 1" in seen["body"]["contents"][0]["parts"][0]["text"]
    assert seen["body"]["generationConfig"]["responseMimeType"] == "application/json"


def test_thinking_parts_are_ignored_and_a_slow_down_reply_is_retried(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "gemini_api_key", "test-key")
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, json={"error": {"status": "RESOURCE_EXHAUSTED"}})
        return reply('{"paragraphs": []}', more=[{"text": "I am thinking", "thought": True}])

    assert generator(handler).generate("What?", passages()) == []
    assert len(calls) == 2


def test_a_busy_main_model_falls_back_to_the_lite_model(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(settings, "gemini_model", "main-model")
    monkeypatch.setattr(settings, "gemini_fallback_model", "lite-model")
    tried = []

    def handler(request: httpx.Request) -> httpx.Response:
        tried.append(request.url.path.split("/")[-1].split(":")[0])
        return httpx.Response(503) if tried[-1] == "main-model" else reply('{"paragraphs": []}')

    assert generator(handler).generate("What?", passages()) == []
    assert tried == ["main-model"] * 2 + ["lite-model"]


def test_a_model_that_does_not_answer_in_time_is_treated_as_busy(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(settings, "gemini_model", "main-model")
    monkeypatch.setattr(settings, "gemini_fallback_model", "lite-model")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("main-model:generateContent"):
            raise httpx.ReadTimeout("too slow", request=request)
        return reply('{"paragraphs": []}')

    assert generator(handler).generate("What?", passages()) == []


def test_any_failure_means_no_answer_not_a_guess(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "gemini_api_key", "test-key")
    assert generator(lambda r: httpx.Response(403, json={"error": {}})).generate("What?", passages()) is None
    assert generator(lambda r: reply("not json at all")).generate("What?", passages()) is None
    assert generator(lambda r: httpx.Response(200, json={"candidates": []})).generate("What?", passages()) is None


def test_the_writer_is_chosen_by_which_key_is_set(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    monkeypatch.setattr(settings, "gemini_api_key", "")
    assert isinstance(get_generator(), ExtractiveGenerator)
    monkeypatch.setattr(settings, "gemini_api_key", "k")
    assert isinstance(get_generator(), GeminiGenerator)


def _corpus(db):
    from helpers import make_document

    make_document(db, title="Quokka", citation="Quokka Act", passages=["Quokka rule: quokka habitats are protected by law."])
    db.commit()


def test_when_gemini_fails_the_cited_passages_are_shown_as_they_are(db, monkeypatch) -> None:
    from mrcourt.services.answering import WRITER_BUSY_NOTE, answer_question, set_generator

    _corpus(db)
    set_generator(generator(lambda r: httpx.Response(503)))
    try:
        result = answer_question(db, "Are quokka habitats protected?", None)
    finally:
        set_generator(None)
    assert result.outcome == "cited" and result.answer_mode == "passages"
    assert result.paragraphs and "quokka habitats are protected" in result.paragraphs[0].text
    assert result.message and WRITER_BUSY_NOTE in result.message


def test_when_gemini_says_the_passages_do_not_answer_there_is_no_source(db) -> None:
    from mrcourt.services.answering import answer_question, set_generator

    _corpus(db)
    set_generator(generator(lambda r: reply('{"paragraphs": []}')))
    try:
        result = answer_question(db, "Are quokka habitats protected?", None)
    finally:
        set_generator(None)
    assert result.outcome == "no_reliable_source" and result.answer_mode == "full"
