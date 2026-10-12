"""What kind of question this is, from its wording (feature 009): it decides which kind of document to prefer.

- "law": what the law says or the punishment (prefer statutes)
- "courts": how courts have decided (prefer judgments, newer first)
- "my_case": an advocate asking about their own matter (prefer their private case documents)
- "other": no preference
"""

import re

from mrcourt.models import User

_LAW = (
    r"\bpunish\w*", r"\bpenalt\w*", r"\bwhat (?:is|does|are) (?:the )?(?:section|article|law|definition)",
    r"\bdefin\w+", r"\bingredients?\b", r"\bessentials?\b", r"\bwhat is\b", r"\bbailable\b",
    r"\bcognizable\b", r"\bsay about\b", r"\bprovision\w*",
    "தண்டனை", "சட்டம் என்ன",
)
_COURTS = (
    r"\bheld\b", r"\bdecided\b", r"\bprecedents?\b", r"\bcase law\b", r"\bjudgments? (?:on|about|in)\b",
    r"\bhow (?:have|do|did) (?:the )?courts?\b", r"\bsupreme court (?:said|held|ruled)", r"\bruled?\b", r"\bratio\b",
    "தீர்ப்பு",
)
_MY_CASE = (
    r"\bmy case\b", r"\bmy client\b", r"\bthis case\b", r"\bour (?:case|matter|client)\b", r"\bmy matter\b",
    r"\bin the (?:petition|deed|cross|judgment) (?:i|we) (?:uploaded|added)\b",
    "என் வழக்கு",
)


def _any(patterns: tuple[str, ...], text: str) -> bool:
    return any(re.search(p, text) for p in patterns)


def classify(question: str, user: User | None) -> str:
    text = question.lower()
    if user is not None and user.role == "advocate" and _any(_MY_CASE, text):
        return "my_case"
    if _any(_COURTS, text):
        return "courts"
    if _any(_LAW, text):
        return "law"
    return "other"
