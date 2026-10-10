import io

import pytest
from fpdf import FPDF
from PIL import Image, ImageDraw

from mrcourt.config import get_settings
from mrcourt.services import ocr
from mrcourt.services.ingest import IngestError, read_document, read_pages
from mrcourt.services.ocr import OcrPage, OcrUnavailable, TesseractEngine, set_ocr_engine


class FakeEngine:
    def __init__(self, texts, confidence=90.0):
        self.texts = list(texts)
        self.confidence = confidence
        self.images = []

    def check(self):
        return None

    def read(self, image):
        self.images.append(image)
        return OcrPage(self.texts[len(self.images) - 1], self.confidence)


class Missing:
    def check(self):
        raise OcrUnavailable("OCR is not set up")

    def read(self, image):  # pragma: no cover - never reached
        raise AssertionError


@pytest.fixture(autouse=True)
def _reset():
    yield
    set_ocr_engine(None)


def _picture(label="page"):
    image = Image.new("RGB", (300, 200), "white")
    ImageDraw.Draw(image).text((20, 20), label, fill="black")
    return image


def _scanned_pdf(pages: int) -> bytes:
    images = [_picture(f"scan {n}") for n in range(pages)]
    buffer = io.BytesIO()
    images[0].save(buffer, "PDF", save_all=True, append_images=images[1:])
    return buffer.getvalue()


def _png() -> bytes:
    buffer = io.BytesIO()
    _picture().save(buffer, "PNG")
    return buffer.getvalue()


def _tiff(frames: int) -> bytes:
    images = [_picture(f"frame {n}") for n in range(frames)]
    buffer = io.BytesIO()
    images[0].save(buffer, "TIFF", save_all=True, append_images=images[1:])
    return buffer.getvalue()


def test_scanned_pdf_pages_are_read_by_ocr_and_marked():
    engine = FakeEngine(["Sale deed first page text.", "Second page text."])
    set_ocr_engine(engine)
    pages = read_document(_scanned_pdf(2), "scan.pdf", max_pages=50)
    assert [(p.number, p.text, p.ocr, p.confidence) for p in pages] == [
        (1, "Sale deed first page text.", True, 90.0),
        (2, "Second page text.", True, 90.0),
    ]
    assert len(engine.images) == 2 and engine.images[0].size[0] > 300  # rendered larger than the source picture


def test_a_text_pdf_is_not_sent_to_ocr():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 8, "This page has real text. " * 10)
    engine = FakeEngine([])
    set_ocr_engine(engine)
    pages = read_document(bytes(pdf.output()), "text.pdf", max_pages=50)
    assert not pages[0].ocr and engine.images == []


def test_png_and_multi_frame_tiff_are_read_page_by_page():
    set_ocr_engine(FakeEngine(["Photo of a notice."]))
    assert [(p.number, p.ocr) for p in read_document(_png(), "notice.PNG", max_pages=50)] == [(1, True)]
    set_ocr_engine(FakeEngine(["one text here", "two text here"]))
    assert [p.text for p in read_document(_tiff(2), "bundle.tif", max_pages=50)] == ["one text here", "two text here"]


def test_without_ocr_a_scan_fails_with_a_reason_that_says_what_to_install():
    set_ocr_engine(Missing())
    with pytest.raises(IngestError, match="OCR is not set up"):
        read_document(_scanned_pdf(1), "scan.pdf", max_pages=50)
    with pytest.raises(IngestError, match="OCR is not set up"):
        read_document(_png(), "scan.png", max_pages=50)


def test_the_real_engine_names_what_to_install(monkeypatch):
    import pytesseract

    def boom():
        raise OSError("tesseract is not installed")

    monkeypatch.setattr(pytesseract, "get_tesseract_version", boom)
    with pytest.raises(OcrUnavailable) as caught:
        TesseractEngine("eng+tam").check()
    assert "Install Tesseract" in str(caught.value) and "eng and tam" in str(caught.value)


def test_missing_language_data_is_named(monkeypatch):
    import pytesseract

    monkeypatch.setattr(pytesseract, "get_tesseract_version", lambda: "5.0")
    monkeypatch.setattr(pytesseract, "get_languages", lambda config="": ["eng"])
    with pytest.raises(OcrUnavailable, match="tam"):
        TesseractEngine("eng+tam").check()


def test_the_engine_reads_with_the_configured_languages(monkeypatch):
    import pytesseract

    seen = {}

    def fake_data(image, lang, output_type):
        seen["lang"] = lang
        return {"text": ["Hello", "", "world"], "conf": ["91", "-1", "83"]}

    monkeypatch.setattr(pytesseract, "image_to_data", fake_data)
    result = TesseractEngine("eng+tam").read(_picture())
    assert seen["lang"] == "eng+tam"
    assert result.text == "Hello world" and result.confidence == pytest.approx(87.0)


def test_a_few_blank_pages_in_a_text_pdf_are_skipped_not_failed():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 8, "Readable text on the first page. " * 10)
    pdf.add_page()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 8, "Readable text on the third page. " * 10)
    set_ocr_engine(Missing())
    pages = read_document(bytes(pdf.output()), "mixed.pdf", max_pages=50)
    assert [p.ocr for p in pages] == [False, False, False]


def test_too_many_scanned_pages_are_refused(monkeypatch):
    monkeypatch.setattr(get_settings(), "max_ocr_pages", 2)
    set_ocr_engine(FakeEngine(["x"] * 5))
    with pytest.raises(IngestError, match="more than 2 scanned pages"):
        read_document(_scanned_pdf(3), "big.pdf", max_pages=50)


def test_plain_text_reading_without_ocr_still_flags_scans():
    set_ocr_engine(FakeEngine(["never used"]))
    with pytest.raises(IngestError, match="Scanned documents need OCR"):
        read_pages(_scanned_pdf(1), "scan.pdf", max_pages=50)


def test_availability_follows_the_engine():
    set_ocr_engine(FakeEngine([]))
    assert ocr.available()
    set_ocr_engine(Missing())
    assert not ocr.available()
