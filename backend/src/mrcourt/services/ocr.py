"""Reading scanned pages (OCR).

Tesseract does the reading, with the English and Tamil language packs by default. It is a separate
program that must be installed on the server; when it is missing, a document that needs it fails
with a plain reason that says what to install, instead of being used half-read.
"""

from dataclasses import dataclass
from typing import Any, Protocol

from mrcourt.config import get_settings

INSTALL_HINT = (
    "This document is a scan and needs OCR, but OCR is not set up on the server. "
    "Install Tesseract with the {languages} language data (see the README), then add the document again."
)


class OcrUnavailable(Exception):
    """OCR cannot be used. The message is plain and safe to show."""


@dataclass(frozen=True)
class OcrPage:
    text: str
    confidence: float | None  # 0 to 100, the engine's own average, when it reports one


class OcrEngine(Protocol):
    def check(self) -> None:
        """Raises OcrUnavailable when the engine cannot run."""

    def read(self, image: Any) -> OcrPage: ...


class TesseractEngine:
    def __init__(self, languages: str) -> None:
        self.languages = languages

    def check(self) -> None:
        try:
            import pytesseract

            pytesseract.get_tesseract_version()
        except Exception as exc:  # noqa: BLE001 - missing program, missing library, wrong path
            raise OcrUnavailable(INSTALL_HINT.format(languages=self.languages.replace("+", " and "))) from exc
        installed = set(pytesseract.get_languages(config=""))
        missing = [lang for lang in self.languages.split("+") if lang not in installed]
        if missing:
            raise OcrUnavailable(
                f"Tesseract is installed but is missing the language data for: {', '.join(missing)}. "
                "Install it (see the README), then add the document again."
            )

    def read(self, image: Any) -> OcrPage:
        import pytesseract

        data = pytesseract.image_to_data(image, lang=self.languages, output_type=pytesseract.Output.DICT)
        words, confidences = [], []
        for text, conf in zip(data["text"], data["conf"], strict=False):
            if str(text).strip():
                words.append(str(text))
                try:
                    value = float(conf)
                except (TypeError, ValueError):
                    continue
                if value >= 0:
                    confidences.append(value)
        average = sum(confidences) / len(confidences) if confidences else None
        return OcrPage(" ".join(words), average)


_override: OcrEngine | None = None


def set_ocr_engine(engine: OcrEngine | None) -> None:
    """Test hook: replace the OCR engine."""
    global _override
    _override = engine


def get_engine() -> OcrEngine:
    """The engine to use, checked and ready; raises OcrUnavailable if it cannot run."""
    engine = _override or TesseractEngine(get_settings().ocr_languages)
    engine.check()
    return engine


def available() -> bool:
    try:
        get_engine()
    except OcrUnavailable:
        return False
    return True
