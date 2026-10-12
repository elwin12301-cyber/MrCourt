"""Metadata mapping on FICTIONAL sample documents (tests/data/metadata/samples.json)."""
import json
from pathlib import Path

import pytest

from mrcourt.services.metadata import extract, statute_sections, text_quality

SAMPLES = json.loads((Path(__file__).resolve().parents[1] / "data" / "metadata" / "samples.json").read_text(encoding="utf-8"))
DOCS = {d["id"]: d for d in SAMPLES["documents"]}

CASES = [
    (doc_id, name, expected)
    for doc_id, doc in DOCS.items()
    for name, expected in doc["expected"].items()
    if name != "page_sections"
]


def _value(fields, name):
    if name == "case_number":
        values = fields["case_numbers"]["value"]
        return (values[0] if values else None), fields["case_numbers"]["confidence"]
    return fields[name]["value"], fields[name]["confidence"]


@pytest.mark.parametrize(("doc_id", "name", "expected"), CASES, ids=[f"{c[0]}-{c[1]}" for c in CASES])
def test_each_field_as_expected(doc_id, name, expected):
    doc = DOCS[doc_id]
    fields = extract(doc["title"], doc["pages"], doc["kind"])
    value, confidence = _value(fields, name)
    want_value, want_confidence = expected
    assert confidence == want_confidence, (value, confidence)
    if name == "acts":
        assert value == want_value
    else:
        assert value == want_value


def test_no_value_is_invented_from_an_empty_document():
    fields = extract("Untitled", [""], "note")
    assert all(f["value"] in (None, [], {}) for n, f in fields.items() if n != "text_quality")
    assert fields["text_quality"]["value"] == "unreadable"


def test_every_value_found_in_the_text_appears_in_it():
    for doc in DOCS.values():
        text = "\n".join(doc["pages"]).lower().replace(" ", "")
        fields = extract(doc["title"], doc["pages"], doc["kind"])
        for name in ("judges",):
            for judge in fields[name]["value"] or []:
                assert judge.lower().replace(" ", "") in text


def test_statute_headings_give_sections_and_contents_pages_give_none():
    pages = DOCS["statute_page"]["pages"]
    assert statute_sections(pages[0])[0] == ["21", "21A"]
    assert statute_sections(pages[1])[0] == []
    assert statute_sections("CHAPTER-6\nSection 299 deals with culpable homicide.")[0] == ["299"]
    assert statute_sections("CHAPTER XVII\nOf offences against property")[1] == "CHAPTER XVII"


def test_text_quality():
    assert text_quality("The appeal is dismissed and the decree of the court is confirmed.") == "readable"
    assert text_quality("GlLnurfllgGzuog6ur ucirefl soh GlLor--rfl gGzuognn Gioeir$lmouu ueir6rfls6h") == "unreadable"
    assert text_quality("வழக்கு தள்ளுபடி செய்யப்படுகிறது") == "readable"


def test_a_judge_name_survives_a_garbled_title():
    from mrcourt.services.metadata import judges

    assert judges("CORAM\nTHE HONOURABLE \TRS, JUSTICE R.HEMALATHA\nS.A.No.1 of 2019") == ["R.Hemalatha"]
    assert judges("No judge named here") == []
