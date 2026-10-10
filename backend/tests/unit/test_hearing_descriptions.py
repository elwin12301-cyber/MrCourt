"""Hearing descriptions must be general, safe to show clients, and absent when unsure (FR-021)."""

import json
import re

import pytest

from mrcourt.config import get_settings
from mrcourt.services import hearing_descriptions as hd

BANNED = [
    r"\byour\b", r"\byou\b", r"\bwill win\b", r"\bwill lose\b", r"\bshould\b", r"\badvise\b",
    r"\bguarantee", r"\blikely to\b", r"\bmust\b", r"\bwe recommend\b",
]


@pytest.mark.parametrize(
    ("purpose", "expected_word"),
    [
        ("Evidence", "witness"),
        ("Cross-examination of witness", "witness"),
        ("Final arguments", "arguments"),
        ("Pronouncement of order", "decision"),
        ("Judgment", "decision"),
        ("Bail hearing", "bail"),
        ("Notice and appearance", "papers"),
        ("First hearing", "papers"),
        ("Mediation", "agreement"),
    ],
)
def test_purpose_selects_a_description(purpose, expected_word):
    description = hd.describe(purpose, None)
    assert description is not None
    assert expected_word in description.text.lower()


def test_case_stage_is_used_when_the_purpose_is_missing_or_unclear():
    assert "witness" in hd.describe(None, "Evidence").text.lower()
    assert "witness" in hd.describe("Listed", "Evidence stage").text.lower()


def test_purpose_beats_stage():
    assert "arguments" in hd.describe("Arguments", "Evidence").text.lower()


@pytest.mark.parametrize("purpose", [None, "", "Listed", "Misc", "Renewed application for X"])
def test_nothing_is_returned_when_there_is_no_reliable_basis(purpose):
    assert hd.describe(purpose, None) is None
    assert hd.describe(purpose, "") is None


def test_every_description_is_general_and_safe():
    data = json.loads(hd.CONTENT_PATH.read_text(encoding="utf-8"))
    assert data["kinds"], "content file must not be empty"
    for kind in data["kinds"]:
        text = kind["text"].lower()
        for pattern in BANNED:
            assert not re.search(pattern, text), f"{kind['key']} contains {pattern!r}"
        assert not re.search(r"\d", text), f"{kind['key']} states a number or date"
        assert len(kind["text"]) < 400, f"{kind['key']} is too long to be read at a glance"


def test_descriptions_carry_the_label_and_disclaimer():
    description = hd.describe("Evidence", None)
    assert description.label == "General information"
    assert description.disclaimer == "Informational only, not legal advice."


def test_unreviewed_content_is_switched_off_in_production(monkeypatch):
    monkeypatch.setattr(get_settings(), "environment", "production")
    assert hd.describe("Evidence", None) is None  # clients see date, time and court only


def test_reviewed_content_is_used_in_production(monkeypatch, tmp_path):
    reviewed = json.loads(hd.CONTENT_PATH.read_text(encoding="utf-8"))
    reviewed["review_status"] = "Reviewed by Adv. Example on 2026-10-01"
    path = tmp_path / "reviewed.json"
    path.write_text(json.dumps(reviewed), encoding="utf-8")
    monkeypatch.setattr(hd, "CONTENT_PATH", path)
    hd.load_content.cache_clear()
    monkeypatch.setattr(get_settings(), "environment", "production")
    try:
        assert hd.describe("Evidence", None) is not None
    finally:
        hd.load_content.cache_clear()
