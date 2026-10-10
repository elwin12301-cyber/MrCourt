"""Turns an uploaded file or pasted text into page-aware passages for search.

Plain text and PDFs with selectable text are supported. Passages are about 1,000 characters and
never cross a page, so every citation can name one page. Pages that are pictures (scans, images)
are read with OCR; if OCR is not available the document fails with a plain reason instead.
"""

import io
import re
from dataclasses import dataclass

TARGET_CHARS = 1000
MAX_CHARS = 1400
OVERLAP_CHARS = 150
MIN_CHARS_PER_PAGE = 40  # fewer than this on average means the pages are pictures


class IngestError(Exception):
    """The document cannot be used. The message is plain and safe to show."""


@dataclass(frozen=True)
class Passage:
    page: int
    text: str


_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return "\n".join(line.strip() for line in text.split("\n")).strip()


IMAGE_TYPES = (".png", ".jpg", ".jpeg", ".tif", ".tiff")
LOW_CONFIDENCE = 60.0  # OCR average below this is flagged for a person to check
OCR_DPI = 200


@dataclass(frozen=True)
class PageText:
    number: int
    text: str
    ocr: bool = False  # read by OCR from a picture of the page
    confidence: float | None = None


def _text_pages(data: bytes, name: str, max_pages: int) -> list[PageText]:
    if name.endswith(".pdf"):
        if not data.startswith(b"%PDF-"):
            raise IngestError("This file is not a readable PDF.")
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError

        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise IngestError("This PDF is password protected. Remove the password and try again.")
            if len(reader.pages) > max_pages:
                raise IngestError(f"This PDF has more than {max_pages} pages.")
            return [PageText(n, clean_text(page.extract_text() or "")) for n, page in enumerate(reader.pages, start=1)]
        except IngestError:
            raise
        except (PyPdfError, ValueError, KeyError, OSError) as exc:
            raise IngestError("This file is not a readable PDF.") from exc
    if b"\x00" in data[:1024]:
        raise IngestError("This file is not plain text.")
    try:
        body = data.decode("utf-8")
    except UnicodeDecodeError:
        body = data.decode("latin-1")
    return [PageText(1, clean_text(body))]


def _ocr_pdf_pages(data: bytes, numbers: list[int], engine) -> dict[int, PageText]:  # type: ignore[no-untyped-def]
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(data)
    out: dict[int, PageText] = {}
    for number in numbers:
        image = document[number - 1].render(scale=OCR_DPI / 72).to_pil().convert("RGB")
        result = engine.read(image)
        out[number] = PageText(number, clean_text(result.text), True, result.confidence)
    return out


def _image_pages(data: bytes, engine, max_pages: int) -> list[PageText]:  # type: ignore[no-untyped-def]
    from PIL import Image, ImageSequence, UnidentifiedImageError

    try:
        image = Image.open(io.BytesIO(data))
        frames = [frame.convert("RGB") for frame in ImageSequence.Iterator(image)]
    except (UnidentifiedImageError, OSError) as exc:
        raise IngestError("This file is not a readable image.") from exc
    if len(frames) > max_pages:
        raise IngestError(f"This image file has more than {max_pages} pages.")
    pages = []
    for number, frame in enumerate(frames, start=1):
        result = engine.read(frame)
        pages.append(PageText(number, clean_text(result.text), True, result.confidence))
    return pages


def read_document(data: bytes, file_name: str, *, max_pages: int, use_ocr: bool = True) -> list[PageText]:
    """Pages of a text file, a PDF or an image. Pages that are pictures are read with OCR."""
    from mrcourt.config import get_settings
    from mrcourt.services.ocr import OcrUnavailable, get_engine

    name = file_name.lower()
    ocr_limit = min(max_pages, get_settings().max_ocr_pages)

    if name.endswith(IMAGE_TYPES):
        if not use_ocr:
            raise IngestError("Images need OCR to be read.")
        try:
            engine = get_engine()
        except OcrUnavailable as exc:
            raise IngestError(str(exc)) from exc
        pages = _image_pages(data, engine, ocr_limit)
    elif name.endswith((".pdf", ".txt", ".md")):
        pages = _text_pages(data, name, max_pages)
        needs = [p.number for p in pages if len(p.text) < MIN_CHARS_PER_PAGE]
        if name.endswith(".pdf") and needs:
            scan_like = len(needs) * 2 > len(pages)
            if not use_ocr:
                if scan_like:
                    raise IngestError(
                        "This looks like a scan; the pages have no readable text. Scanned documents need OCR."
                    )
            else:
                try:
                    engine = get_engine()
                except OcrUnavailable as exc:
                    if scan_like:
                        raise IngestError(str(exc)) from exc
                    engine = None  # a few blank pages in a text document are simply skipped
                if engine is not None:
                    if len(needs) > ocr_limit:
                        raise IngestError(f"This document has more than {ocr_limit} scanned pages.")
                    read = _ocr_pdf_pages(data, needs, engine)
                    pages = [read.get(p.number, p) for p in pages]
    else:
        raise IngestError("Only text (.txt, .md), PDF and image (.png, .jpg, .tif) files are supported.")

    if sum(len(p.text) for p in pages) == 0:
        raise IngestError("No readable text was found in this file.")
    return pages


def read_pages(data: bytes, file_name: str, *, max_pages: int) -> list[tuple[int, str]]:
    """[(page number, text)] for a text or PDF file, without OCR."""
    return [(p.number, p.text) for p in read_document(data, file_name, max_pages=max_pages, use_ocr=False)]


def _pieces(text: str) -> list[str]:
    """Paragraph-sized pieces no longer than TARGET_CHARS."""
    out: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) <= TARGET_CHARS:
            out.append(paragraph)
            continue
        buffer = ""
        for sentence in _SENTENCE.split(paragraph):
            while len(sentence) > TARGET_CHARS:  # no punctuation: cut at a space
                cut = sentence.rfind(" ", 0, TARGET_CHARS)
                cut = cut if cut > 0 else TARGET_CHARS
                if buffer:
                    out.append(buffer)
                    buffer = ""
                out.append(sentence[:cut].strip())
                sentence = sentence[cut:].strip()
            if len(buffer) + len(sentence) + 1 > TARGET_CHARS and buffer:
                out.append(buffer)
                buffer = ""
            buffer = f"{buffer} {sentence}".strip()
        if buffer:
            out.append(buffer)
    return out


def _tail(text: str) -> str:
    if len(text) <= OVERLAP_CHARS:
        return text
    tail = text[-OVERLAP_CHARS:]
    space = tail.find(" ")
    return tail[space + 1 :] if 0 <= space < len(tail) - 1 else tail


def chunk_pages(pages: list[tuple[int, str]]) -> list[Passage]:
    passages: list[Passage] = []
    for number, text in pages:
        current = ""
        for piece in _pieces(text):
            if current and len(current) + len(piece) + 1 > MAX_CHARS:
                passages.append(Passage(number, current))
                current = f"{_tail(current)} {piece}".strip()
            else:
                current = f"{current} {piece}".strip()
            if len(current) >= TARGET_CHARS:
                passages.append(Passage(number, current))
                current = _tail(current)
        # The leftover is only the overlap when nothing new was added after the last cut.
        if current and (not passages or passages[-1].page != number or not passages[-1].text.endswith(current)):
            passages.append(Passage(number, current))
    return passages
