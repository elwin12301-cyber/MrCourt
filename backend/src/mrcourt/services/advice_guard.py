"""Keeps Ask MrCourt to general information for clients (spec FR-013, constitution principle II).

The detector is deliberately simple: it looks for first-person case language ("my case", "should I
accept", "will I win"). It cannot catch every phrasing, so every client answer also carries a
standing reminder, and protection never depends on this check alone.
"""

import re

CASE_SPECIFIC_NOTICE = (
    "MrCourt cannot advise on your case. Please ask your lawyer. "
    "What follows is general information only."
)
LAWYER_REMINDER = (
    "This is general information only. For advice about your own case, please ask your lawyer."
)

_PATTERNS = [
    r"\bmy (case|matter|lawyer|advocate|hearing|petition|complaint|notice|cheque|landlord|employer|"
    r"husband|wife|divorce|property|bail|settlement|chances|situation|rights)\b",
    r"\b(our|in my|for my|about my) (case|matter|lawyer|situation)\b",
    r"\bshould (i|we)\b",
    r"\bwill (i|we) (win|lose|get|be|go|have)\b",
    r"\bcan (i|we) (win|get|claim|expect|sue|appeal|settle|avoid)\b",
    r"\bam i (going|likely|able|liable)\b",
    r"\bagainst me\b",
    r"\bdo (i|we) have a (good |strong |valid )?(case|claim)\b",
    r"\bwhat (should|can|do) (i|we) do\b",
]
_COMPILED = [re.compile(p) for p in _PATTERNS]


def looks_case_specific(question: str) -> bool:
    text = re.sub(r"\s+", " ", question.lower())
    return any(p.search(text) for p in _COMPILED)
