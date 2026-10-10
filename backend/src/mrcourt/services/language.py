"""Which language a text is written in, judged by its script, so an answer can say what language
its sources are in. Citations are never translated or changed."""

# (first code point, last code point, language name)
_SCRIPTS = [
    (0x0B80, 0x0BFF, "Tamil"),
    (0x0900, 0x097F, "Hindi"),  # Devanagari: Hindi and Marathi share it
    (0x0C00, 0x0C7F, "Telugu"),
    (0x0C80, 0x0CFF, "Kannada"),
    (0x0D00, 0x0D7F, "Malayalam"),
    (0x0980, 0x09FF, "Bengali"),
    (0x0A80, 0x0AFF, "Gujarati"),
]


def detect(text: str) -> str:
    """The language name for the dominant script in `text`; English when it is mostly Latin."""
    counts: dict[str, int] = {}
    for ch in text:
        code = ord(ch)
        for low, high, name in _SCRIPTS:
            if low <= code <= high:
                counts[name] = counts.get(name, 0) + 1
                break
    if not counts:
        return "English"
    name, count = max(counts.items(), key=lambda kv: kv[1])
    letters = sum(1 for ch in text if ch.isalpha())
    return name if count * 3 >= letters else "English"


def source_language_note(question: str, source_texts: list[str]) -> str | None:
    """Says which language the sources are in when that differs from the question's language."""
    asked = detect(question)
    found = sorted({detect(t) for t in source_texts})
    if not found or found == [asked]:
        return None
    return f"The sources are in {' and '.join(found)}."


def keyword_only_notice(question: str) -> str | None:
    """Honest message for a non-English question when only keyword search is available."""
    asked = detect(question)
    if asked == "English":
        return None
    return (
        f"Searching in {asked} needs meaning-based search, which is not available right now. "
        "Try asking in English."
    )
