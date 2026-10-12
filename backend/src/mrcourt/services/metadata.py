"""Document details (feature 008): map a document's text to standard fields, each with a confidence.

Rules only (no outside service): headers of Indian court papers are regular ("IN THE HIGH COURT OF JUDICATURE AT
MADRAS", "DELIVERED ON : 07.04.2025", "... Appellant", "Vs", "... Respondents"). A value is stored only when text
supports it; otherwise the field is empty and marked "not_found". Fields a person corrected are never changed by
mapping again. Text with a broken layer (legacy Tamil fonts) is marked unreadable and not mapped.

    python -m mrcourt.services.metadata --remap      # map every ready document again (keeps corrections)
"""

import argparse
import re
from collections import Counter
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from mrcourt.models import DocumentReference, KnowledgeDocument, LegalSource
from mrcourt.services.references import ACTS, CASE_RE, CNR_RE

FIELDS = (
    "doc_type", "court", "bench", "case_numbers", "cnr", "case_title", "parties", "judges", "decided_on", "acts",
    "outcome", "language", "text_quality",
)
DOC_TYPES = ("statute", "judgment", "order", "petition", "deed", "deposition", "notice", "other")
OUTCOMES = ("allowed", "dismissed", "partly allowed", "decreed", "disposed")
TYPE_LABELS = {
    "statute": "Statute", "judgment": "Judgment", "order": "Order", "petition": "Petition", "deed": "Deed",
    "deposition": "Deposition", "notice": "Notice", "other": "Document",
}
MONTHS = {m: i for i, m in enumerate(
    ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"),
    start=1,
)}
STOPWORDS = frozenset(
    "the of and in to is a that for by on court was with as be petitioner respondent appellant section under this "
    "which are not has suit plaintiff defendant order dated filed".split()
)


def field(value: object = None, confidence: str = "not_found", alternatives: list | None = None) -> dict[str, object]:  # type: ignore[type-arg]
    out: dict[str, object] = {"value": value, "confidence": confidence if value not in (None, [], {}) else "not_found", "source": "text"}
    if alternatives:
        out["alternatives"] = alternatives
    return out


# ----- reading the text -------------------------------------------------------------------------


def _tamil_share(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    return sum(1 for c in letters if "஀" <= c <= "௿") / len(letters) if letters else 0.0


def _english_share(text: str) -> float:
    words = re.findall(r"[A-Za-z]+", text)
    return sum(1 for w in words if w.lower() in STOPWORDS) / len(words) if words else 0.0


def text_quality(text: str) -> str:
    """'unreadable' for text with almost no English function words and almost no Tamil letters."""
    if not text.strip():
        return "unreadable"
    return "readable" if _tamil_share(text) >= 0.3 or _english_share(text) >= 0.08 else "unreadable"


def language(text: str) -> str | None:
    tamil, english = _tamil_share(text), _english_share(text)
    if tamil >= 0.3 and english >= 0.08:
        return "mixed"
    if tamil >= 0.3:
        return "ta"
    if english >= 0.08:
        return "en"
    return None


def _case_label(kind: str, number: str, year: str | None) -> str:
    letters = re.sub(r"[^A-Za-z]", "", kind).upper()
    known = {"CRLA": "Crl.A.", "CRLOP": "Crl.O.P.", "CRP": "C.R.P.", "CMA": "C.M.A."}
    prefix = known.get(letters, ".".join(letters) + ".")
    return f"{prefix} {number}" + (f"/{year}" if year else "")


def case_numbers(text: str) -> list[str]:
    found = [_case_label(m.group(1), m.group(2), m.group(3)) for m in CASE_RE.finditer(text)]
    return list(dict.fromkeys(found))


def _title(name: str) -> str:
    return re.sub(r"[A-Za-z]{2,}", lambda m: m.group(0).capitalize(), name.strip())


def court(header: str) -> str | None:
    up = re.sub(r"\s+", " ", header.upper())
    if m := re.search(r"HIGH COURT OF JUDICATURE AT ([A-Z]+)", up):
        return f"{m.group(1).title()} High Court"
    if "SUPREME COURT OF INDIA" in up:
        return "Supreme Court of India"
    if m := re.search(r"HIGH COURT OF ([A-Z]+(?: [A-Z]+)?)\b", up):
        return f"{m.group(1).title()} High Court"
    if m := re.search(r"DISTRICT MUNSIF,? (?:COURT,? )?(?:AT )?([A-Z]+)", up):
        return f"District Munsif Court, {m.group(1).title()}"
    if m := re.search(r"(?:SUBORDINATE JUDGE|SUB[- ]?COURT|SUB JUDGE),? (?:AT )?([A-Z]+)", up):
        return f"Sub Court, {m.group(1).title()}"
    if m := re.search(r"(?:PRINCIPAL |ADDITIONAL )?DISTRICT (?:JUDGE|COURT),? (?:AT )?([A-Z]+)", up):
        return f"District Court, {m.group(1).title()}"
    return None


def _date(day: str, month: str, year: str) -> date | None:
    try:
        number = int(month) if month.isdigit() else MONTHS.get(month.lower())
        return date(int(year), int(number), int(day)) if number else None  # type: ignore[arg-type]
    except ValueError:
        return None


NUMERIC_DATE = r"(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{4})"
WORD_DATE = r"(\d{1,2})(?:st|nd|rd|th)?\s+(?:day\s+of\s+)?([A-Za-z]+),?\s+(\d{4})"


def decided_on(pages: list[str]) -> dict[str, object]:
    text = "\n".join(pages)
    labelled = re.search(rf"(?:DELIVERED ON|PRONOUNCED ON|DECIDED ON|DATED|DATE OF (?:JUDGMENT|ORDER))\s*:?\s*{NUMERIC_DATE}", text, re.I)
    if labelled and (d := _date(*labelled.groups())):
        return field(d.isoformat(), "found")
    pronounced = re.search(rf"pronounced[^.]*?{WORD_DATE}", text, re.I)
    if pronounced and (d := _date(*pronounced.groups())):
        return field(d.isoformat(), "found")
    candidates = [d for m in re.finditer(NUMERIC_DATE, text) if (d := _date(*m.groups()))]
    candidates += [d for m in re.finditer(WORD_DATE, text) if (d := _date(*m.groups()))]
    if candidates:
        return field(candidates[0].isoformat(), "likely", [c.isoformat() for c in candidates[1:4]])
    return field()


def judges(header: str) -> list[str]:
    names = re.findall(
        # A few stray characters are allowed before JUSTICE: scans garble "MRS." into things like "\TRS,".
        r"(?:HON'?BLE|HONOURABLE)\s+[^\n]{0,8}?\s*JUSTICE\s+([A-Z][A-Z.\s]*?[A-Z])\s*(?:\n|$|,|\bAND\b)",
        header,
        re.I,
    )
    return list(dict.fromkeys(_title(re.sub(r"\s+", "", n) if "." in n else n) for n in names))


ROLE_P = r"\.{2,}\s*(?:Appellants?|Petitioners?|Plaintiffs?|Complainants?)\b"
ROLE_R = r"\.{2,}\s*(?:Respondents?|Defendants?|Accused)\b"
STOP = re.compile(r"JUSTICE|CORAM|\bof\s+\d{4}\b|JUDGMENT|\bON\s*:|DATED|Present|ORDER|^\s*$", re.I)


def _names(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        line = re.split(r"\.{2,}", line)[0]
        for part in re.split(r"\s(?=\d+\s*\.)", line):
            name = re.sub(r"^\s*\d+\s*\.\s*", "", part).strip(" ,.")
            name = re.sub(r"\s*\((?:died|deceased)\)?", "", name, flags=re.I).strip()
            if name and not re.fullmatch(r"vs?\.?", name, re.I) and len(name) <= 120:
                out.append(name)
    return out


def parties(header: str) -> dict[str, list[str]] | None:
    lines = header.splitlines()
    p_at = next((i for i, l in enumerate(lines) if re.search(ROLE_P, l, re.I)), None)
    if p_at is None:
        return None
    start = p_at
    while start > 0 and not STOP.search(lines[start - 1]) and not CASE_RE.search(lines[start - 1]):
        start -= 1
    petitioners = _names(lines[start : p_at + 1])
    r_at = next((i for i in range(p_at + 1, len(lines)) if re.search(ROLE_R, lines[i], re.I)), None)
    respondents: list[str] = []
    if r_at is not None:
        vs = next((i for i in range(p_at + 1, r_at + 1) if re.fullmatch(r"\s*(?:vs?\.?|versus)\s*", lines[i], re.I)), p_at)
        respondents = _names(lines[vs + 1 : r_at + 1])
    return {"petitioner": petitioners, "respondent": respondents} if petitioners else None


def _act_key(name: str) -> str | None:
    low = name.lower()
    for key, (words, instrument_words) in ACTS.items():
        if any(w in low for w in (*instrument_words, *words) if len(w) > 3):
            return key
    return None


def acts(text: str) -> list[dict[str, str | None]]:
    found: list[tuple[str, str | None]] = []
    for m in re.finditer(
        r"\b(?:Section|Sec\.?|S\.|u/s\.?)\s*(\d{1,4}[A-Z]?)\s+(?:of\s+(?:the\s+)?)?((?:[A-Z][A-Za-z]*\s+|of\s+|the\s+)*?"
        r"(?:Act|Code|Sanhita|Adhiniyam)\b(?:\s+of\s+(?:[A-Z][A-Za-z]+\s?)+)?|IPC|BNS|BNSS|BSA|CrPC|CPC)",
        text,
    ):
        if key := _act_key(m.group(2)) or {"IPC": "IPC", "BNS": "BNS", "BNSS": "BNSS", "BSA": "BSA", "CRPC": "CRPC", "CPC": "CPC"}.get(m.group(2).upper()):
            found.append((key, m.group(1).upper()))
    for m in re.finditer(r"\bArticles?\s+(\d{1,3}[A-Z]?)\s+of\s+the\s+Constitution", text, re.I):
        found.append(("CONSTITUTION", m.group(1).upper()))
    return [{"act": a, "section": s} for a, s in dict.fromkeys(found)]


def outcome(pages: list[str]) -> str | None:
    tail = re.sub(r"\s+", " ", " ".join(pages[-2:]).lower())
    if re.search(r"partly allowed|allowed in part", tail):
        return "partly allowed"
    m = re.search(r"\b(?:appeal|petition|suit|revision|application|case)s?\s+(?:is|are|stands?)\s+(?:hereby\s+)?(dismissed|allowed|decreed|disposed)", tail)
    if m:
        return m.group(1)
    m = re.search(r"\b(?:is|are)\s+(?:hereby\s+)?(dismissed|allowed|decreed)\b", tail)
    return m.group(1) if m else None


def doc_type(title: str, header: str, kind: str) -> dict[str, object]:
    if kind == "act_section":
        return field("statute", "found")
    up = header.upper()
    # Strong court markers first: a judgment may mention a sale deed or a witness without being one.
    rules = (
        ("judgment", r"(?m)^\s*(?:COMMON\s+)?JUDG(?:E)?MENT\s*$|DELIVERED ON|RESERVED ON|PRONOUNCED"),
        ("order", r"(?m)^\s*(?:COMMON\s+)?ORDER\s*$"),
        ("deed", r"(?m)^\s*(?:(?:SALE|GIFT|SETTLEMENT|MORTGAGE|PARTITION|RELEASE)\s+DEED|DEED OF (?:SALE|GIFT))\b"),
        ("deposition", r"(?m)^\s*(?:[DP]\.?\s?W\.?\s?-?\s?\d|.*\b(?:CROSS|CHIEF)[- ]?EXAMINATION)"),
        ("petition", r"PETITION(?:ER)?\b.*?\bPRAY|PRAYS?\b"),
        ("notice", r"LEGAL NOTICE|NOTICE UNDER"),
    )
    for name, pattern in rules:
        if re.search(pattern, up, re.S):
            return field(name, "found")
    hints = (("judgment", "judg"), ("order", "order"), ("deed", "deed"), ("deposition", "cross"), ("petition", "petition"))
    for name, word in hints:
        if word in title.lower():
            return field(name, "likely")
    return field()


def extract(title: str, pages: list[str], kind: str = "note") -> dict[str, dict[str, object]]:
    """Every field for one document, from its title and page texts."""
    text = "\n".join(pages)
    header = "\n".join(pages[:2])
    quality = text_quality(text)
    out: dict[str, dict[str, object]] = {name: field() for name in FIELDS}
    out["text_quality"] = field(quality, "found")
    out["doc_type"] = doc_type(title, header if quality == "readable" else "", kind)
    if quality == "unreadable":
        from_title = case_numbers(title) or [
            _case_label(m.group(1), m.group(2), None) for m in re.finditer(r"\b(W\.?P|O\.?S|S\.?A|A\.?S)\.?\s*(\d{1,6})\b", title, re.I)
        ]
        if from_title:
            out["case_numbers"] = field(from_title, "likely")
        return out
    out["language"] = field(language(text), "found")
    if kind == "act_section":
        out["acts"] = field(acts(text), "found")
        return out
    numbers = case_numbers(pages[0] if pages else "")
    if numbers:
        out["case_numbers"] = field(numbers, "found")
    elif later := case_numbers(text):
        out["case_numbers"] = field(later, "likely")
    if cnr := CNR_RE.search(text):
        out["cnr"] = field(cnr.group(1), "found")
    if name := court(header):
        out["court"] = field(name, "found")
    if names := judges(header):
        out["judges"] = field(names, "found")
    who = parties(header)
    if who:
        out["parties"] = field(who, "found")
        if who["petitioner"] and who["respondent"]:
            out["case_title"] = field(f"{who['petitioner'][0]} v. {who['respondent'][0]}", "found")
    out["decided_on"] = decided_on(pages)
    out["acts"] = field(acts(text), "found")
    if result := outcome(pages):
        out["outcome"] = field(result, "found")
    return out


def statute_sections(text: str) -> tuple[list[str], str | None]:
    """Section/article numbers a statute passage carries: headings like "21. Protection of life ...—", or
    "Section 299" when only a few are named. Lists of contents (headings without the dash) give nothing."""
    headings = re.findall(r"(?:^|\n)\s*(\d{1,3}[A-Z]{0,2})\.\s+[A-Z][^\n]{2,160}?\.\s*[—–-]", text)
    named = re.findall(r"\b(?:Section|Article)\s+(\d{1,3}[A-Z]?)\b", text)
    sections = list(dict.fromkeys([*headings, *(named if len(set(named)) <= 4 else [])]))
    chapter = re.search(r"\bCHAPTER\s*[-–]?\s*([IVXLC]+|\d+)\b", text)
    return sections, (f"CHAPTER {chapter.group(1)}" if chapter else None)


# ----- storing ----------------------------------------------------------------------------------


def _iso_date(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value)) if value else None
    except ValueError:
        return None


def mirror(doc: KnowledgeDocument) -> None:
    """Copy current field values into the indexed columns filters use."""
    details = doc.details or {}
    value = lambda name: (details.get(name) or {}).get("value")  # noqa: E731
    doc.doc_type = value("doc_type")
    doc.court = (value("court") or None) and str(value("court"))[:200]
    numbers = value("case_numbers") or []
    doc.case_number = str(numbers[0])[:60] if numbers else None
    doc.decided_on = _iso_date(value("decided_on"))
    doc.language = value("language")
    doc.text_quality = value("text_quality")


def apply(db: Session, doc: KnowledgeDocument, extracted: dict[str, dict[str, object]]) -> None:
    """Store mapped details, keeping every field a person corrected, and refresh references and statute sections."""
    current = dict(doc.details or {})
    for name, value in extracted.items():
        if (current.get(name) or {}).get("source") == "person":
            continue
        current[name] = value
    doc.details = current
    mirror(doc)
    db.execute(delete(DocumentReference).where(DocumentReference.document_id == doc.id))
    seen: set[tuple[str, str | None]] = set()
    for ref in (current.get("acts") or {}).get("value") or []:  # type: ignore[union-attr]
        key = (str(ref.get("act"))[:30], (str(ref["section"])[:20] if ref.get("section") else None))
        if key not in seen:
            seen.add(key)
            db.add(DocumentReference(document_id=doc.id, act=key[0], section=key[1]))
    if doc.doc_type == "statute":
        act = _act_key(doc.title)
        for passage in db.scalars(select(LegalSource).where(LegalSource.document_id == doc.id)):
            sections, chapter = statute_sections(passage.text or "")
            passage.sections = sections or None
            passage.chapter = chapter
            if passage.section is None and len(sections) == 1:
                passage.section = sections[0]
            for number in [*(sections or []), *([passage.section] if passage.section else [])]:
                key = (act or "", str(number)[:20])
                if act and key not in seen:
                    seen.add(key)
                    db.add(DocumentReference(document_id=doc.id, act=act, section=key[1]))
    db.flush()


def map_document(db: Session, doc: KnowledgeDocument) -> dict[str, dict[str, object]]:
    pages = [
        s.text or ""
        for s in db.scalars(select(LegalSource).where(LegalSource.document_id == doc.id).order_by(LegalSource.page))
    ]
    extracted = extract(doc.title, pages, doc.kind)
    apply(db, doc, extracted)
    return extracted


def remap(db: Session, documents: list[KnowledgeDocument]) -> dict[str, object]:
    found: Counter[str] = Counter()
    unreadable = 0
    for doc in documents:
        if doc.status != "ready":
            continue
        map_document(db, doc)
        for name, value in (doc.details or {}).items():
            if value.get("value") not in (None, [], {}) and name not in ("text_quality", "language"):  # type: ignore[union-attr]
                found[name] += 1
        unreadable += doc.text_quality == "unreadable"
    return {"documents": sum(1 for d in documents if d.status == "ready"), "fields_found": dict(found), "unreadable": unreadable}


def short_label(doc: KnowledgeDocument | None, passage: LegalSource | None = None) -> str | None:
    """'Judgment · Madras High Court · 07 Apr 2025 · S.A. 1106/2019', or 'Statute · s. 21' for statute passages."""
    if doc is None or not doc.details:
        return None
    parts = [TYPE_LABELS.get(doc.doc_type or "", "")] if doc.doc_type else []
    if doc.doc_type == "statute":
        sections = (passage.sections if passage is not None else None) or ([passage.section] if passage is not None and passage.section else [])
        if sections:
            parts.append("s. " + ", ".join(sections[:3]))
    else:
        parts += [doc.court or "", f"{doc.decided_on:%d %b %Y}" if doc.decided_on else "", doc.case_number or ""]
    if doc.text_quality == "unreadable":
        parts.append("text could not be read")
    label = " · ".join(p for p in parts if p)
    return label or None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--remap", action="store_true", help="map every ready document again (corrections kept)")
    args = parser.parse_args()
    if not args.remap:
        parser.print_help()
        return
    from mrcourt.db.base import get_sessionmaker

    with get_sessionmaker()() as db:
        summary = remap(db, list(db.scalars(select(KnowledgeDocument))))
        db.commit()
    print(summary)


if __name__ == "__main__":
    main()
