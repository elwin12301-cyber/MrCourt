"""Exact legal references in a question ("Section 379 IPC", "Article 21", "W.P. 11944/2013") and whether a
passage is that provision or case (feature 009).

A passage *is* a section when its recorded section number matches; it *mentions* it when its text names it
("Section 299", "Sec. 299") or carries its heading ("21. Protection of life ..."). Old and new criminal codes are
different Acts: section 379 of the IPC is never treated as section 303 of the BNS.
"""

import re
from dataclasses import dataclass

# Act keys, the words people type for them, and words found in the matching instrument names.
ACTS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "IPC": (("ipc", "indian penal code", "penal code"), ("indian penal code",)),
    "BNS": (("bns", "bharatiya nyaya sanhita"), ("bharatiya nyaya sanhita",)),
    "BNSS": (("bnss", "bharatiya nagarik suraksha sanhita"), ("bharatiya nagarik suraksha sanhita",)),
    "BSA": (("bsa", "bharatiya sakshya adhiniyam"), ("bharatiya sakshya adhiniyam",)),
    "CRPC": (("crpc", "cr.p.c", "code of criminal procedure"), ("code of criminal procedure",)),
    "CPC": (("cpc", "c.p.c", "code of civil procedure"), ("code of civil procedure",)),
    "NI": (("ni act", "negotiable instruments"), ("negotiable instruments",)),
    "CONSTITUTION": (("constitution",), ("constitution of india",)),
    "CONTRACT": (("contract act", "indian contract"), ("contract act",)),
    "TPA": (("tpa", "transfer of property"), ("transfer of property",)),
    "EVIDENCE": (("evidence act",), ("evidence act",)),
}

SECTION_RE = re.compile(r"(?<![a-z]\.)\b(?:section|sec\.?|s\.|u/s\.?|under\s+section)\s*(\d{1,4}[a-z]?)\b", re.IGNORECASE)
ARTICLE_RE = re.compile(r"\b(?:article|art\.)\s*(\d{1,3}[a-z]?)\b", re.IGNORECASE)
# "379 IPC", "138 of the NI Act"
NUMBER_ACT_RE = re.compile(
    r"\b(\d{1,4}[a-z]?)\s+(?:of\s+(?:the\s+)?)?(ipc|bns|bnss|bsa|crpc|cpc|ni\s+act)\b", re.IGNORECASE
)
CASE_RE = re.compile(
    r"\b(w\.?\s?p|o\.?\s?s|crl\.?\s?a|crl\.?\s?o\.?\s?p|s\.?\s?a|a\.?\s?s|c\.?\s?r\.?\s?p|o\.?\s?a|c\.?\s?a|c\.?\s?m\.?\s?a)"
    r"\.?\s*(?:\(\w+\)\s*)?(?:no\.?\s*)?(\d{1,6})(?:\s*(?:/|of)\s*(\d{4}))?\b",
    re.IGNORECASE,
)
CNR_RE = re.compile(r"\b([A-Z]{4}\d{12})\b")


@dataclass(frozen=True)
class Reference:
    kind: str  # "section" | "article" | "case"
    number: str = ""  # section/article number, or case number
    act: str | None = None  # key of ACTS, when named
    case_type: str | None = None  # "WP", "OS", ...
    year: str | None = None
    cnr: str | None = None

    def label(self) -> str:
        if self.kind == "article":
            return f"Article {self.number} of the Constitution"
        if self.kind == "section":
            return f"Section {self.number}" + (f" {self.act}" if self.act else "")
        if self.cnr:
            return f"CNR {self.cnr}"
        return f"{self.case_type} {self.number}" + (f"/{self.year}" if self.year else "")


def _acts_named(text: str) -> list[str]:
    low = f" {text.lower()} "
    found = []
    for key, (words, _) in ACTS.items():
        if any(re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", low) for w in words):
            found.append(key)
    return found


def _case_type(raw: str) -> str:
    return re.sub(r"[^a-z]", "", raw.lower()).upper()


def parse_references(question: str) -> list[Reference]:
    refs: list[Reference] = []
    acts = _acts_named(question)
    act = acts[0] if len(acts) == 1 else None
    for match in NUMBER_ACT_RE.finditer(question):
        key = re.sub(r"\s+act$", "", match.group(2).lower()).upper().replace(" ", "")
        refs.append(Reference("section", match.group(1).upper(), "NI" if key == "NI" else key))
    for match in SECTION_RE.finditer(question):
        number = match.group(1).upper()
        if not any(r.kind == "section" and r.number == number for r in refs):
            refs.append(Reference("section", number, act))
    for match in ARTICLE_RE.finditer(question):
        refs.append(Reference("article", match.group(1).upper(), "CONSTITUTION"))
    for match in CNR_RE.finditer(question):
        refs.append(Reference("case", cnr=match.group(1)))
    for match in CASE_RE.finditer(question):
        refs.append(Reference("case", match.group(2), case_type=_case_type(match.group(1)), year=match.group(3)))
    return list(dict.fromkeys(refs))


def _instrument_is(act: str | None, instrument: str) -> bool:
    if act is None:
        return True
    return any(word in instrument.lower() for word in ACTS[act][1])


def match(
    ref: Reference,
    *,
    instrument: str,
    section: str | None,
    label: str,
    text: str,
    sections: list[str] | None = None,
    case_number: str | None = None,
) -> str | None:
    """'exact' when the passage is the referenced provision or case, 'mentions' when it names it, else None.
    `case_number` is the main case number mapped for the passage's document (feature 008)."""
    if ref.kind in ("section", "article"):
        if not _instrument_is(ref.act, instrument):
            return None
        if section and section.strip().upper() == ref.number:
            return "exact"
        if ref.number in [s.upper() for s in sections or []]:
            return "exact"
        word = r"(?:section|sec\.?|s\.)" if ref.kind == "section" else r"(?:article|art\.)"
        number = re.escape(ref.number)
        if re.search(rf"\b{word}\s*{number}\b", text, re.IGNORECASE) or re.search(
            rf"\b{word}\s*{number}\b", label, re.IGNORECASE
        ):
            return "mentions"
        # A heading such as "21. Protection of life and personal liberty" (not in a list of contents).
        headings = re.findall(rf"(?:^|\n|\|)\s*{number}\.\s+[A-Z][a-z]", text)
        if headings and len(re.findall(r"(?:^|\s)\d{1,3}[A-Z]?\.\s+[A-Z][a-z]", text)) <= 4:
            return "mentions"
        return None
    haystack = f"{case_number or ''}\n{label}\n{instrument}\n{text[:4000]}"
    if ref.cnr:
        return "exact" if ref.cnr in haystack.upper() else None
    for found in CASE_RE.finditer(haystack):
        if _case_type(found.group(1)) == ref.case_type and found.group(2) == ref.number:
            if ref.year is None or found.group(3) in (None, ref.year):
                return "exact"
    return None
