import io

import pytest
from PIL import Image, ImageDraw
from sqlalchemy import select

from mrcourt.config import get_settings
from mrcourt.models import LegalSource
from mrcourt.services.ocr import OcrPage, OcrUnavailable, set_ocr_engine

API = "/api/v1/knowledge/documents"
PHRASE = "The zorvex covenant requires eleven months of notice."


class Engine:
    def __init__(self, text=PHRASE, confidence=92.0):
        self.text, self.confidence = text, confidence

    def check(self):
        return None

    def read(self, image):
        return OcrPage(self.text, self.confidence)


class Missing:
    def check(self):
        raise OcrUnavailable("This document is a scan and needs OCR, but OCR is not set up on the server. Install Tesseract.")

    def read(self, image):  # pragma: no cover
        raise AssertionError


@pytest.fixture(autouse=True)
def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "knowledge_dir", str(tmp_path / "knowledge"))
    yield
    set_ocr_engine(None)


def _png() -> bytes:
    image = Image.new("RGB", (300, 200), "white")
    ImageDraw.Draw(image).text((20, 20), "scan", fill="black")
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def _add(client, name="notice.png", content=None, title="Scanned notice"):
    return client.post(
        API,
        data={"title": title, "citation": "Scanned Notice"},
        files={"file": (name, content if content is not None else _png(), "application/octet-stream")},
    )


def test_a_scanned_image_becomes_ready_and_its_passages_are_marked(admin_client, db):
    set_ocr_engine(Engine())
    assert _add(admin_client).status_code == 201
    row = next(d for d in admin_client.get(API).json() if d["title"] == "Scanned notice")
    assert row["status"] == "ready" and row["ocr_pages"] == 1 and row["status_reason"] is None
    passage = db.scalars(select(LegalSource).where(LegalSource.instrument == "Scanned notice")).one()
    assert passage.read_by_ocr and passage.ocr_confidence == 92.0 and passage.text == PHRASE


def test_poor_reading_is_flagged_but_kept(admin_client):
    set_ocr_engine(Engine(confidence=31.0))
    _add(admin_client)
    row = next(d for d in admin_client.get(API).json() if d["title"] == "Scanned notice")
    assert row["status"] == "ready" and "hard to read" in row["status_reason"]


def test_a_scanned_document_is_found_by_a_question_about_its_content(admin_client, advocate_client):
    set_ocr_engine(Engine())
    _add(admin_client)
    # the advocate asks (a second browser is the advocate fixture on the same app)
    body = advocate_client.post("/api/v1/questions", json={"text": "How many months of notice does the zorvex covenant require?"}).json()
    assert body["outcome"] == "cited" and body["citations"][0]["label"].startswith("Scanned Notice")


def test_without_ocr_the_scan_fails_and_nothing_is_used(admin_client, db):
    set_ocr_engine(Missing())
    _add(admin_client)
    row = next(d for d in admin_client.get(API).json() if d["title"] == "Scanned notice")
    assert row["status"] == "failed" and "Install Tesseract" in row["status_reason"]
    assert db.scalars(select(LegalSource).where(LegalSource.instrument == "Scanned notice")).first() is None


def test_a_file_that_is_not_an_image_is_refused(admin_client):
    set_ocr_engine(Engine())
    _add(admin_client, name="fake.png", content=b"not an image at all", title="Not an image")
    row = next(d for d in admin_client.get(API).json() if d["title"] == "Not an image")
    assert row["status"] == "failed" and "not a readable image" in row["status_reason"]
