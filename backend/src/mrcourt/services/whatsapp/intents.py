"""Short requests answered without AI: "next hearing", "status", "today", "help" (feature 010).

Words are matched exactly after small filler words are dropped, in English, Hindi and Tamil, so a real question
that happens to contain "status" still goes to the legal answer. A client sees only the cases they were invited
to and only what the advocate shares (the client-facing status, the next hearing's date, time and court); an
advocate sees their own cases. A client with several cases picks one from a short numbered list.
"""

import unicodedata
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from mrcourt.db.base import utcnow
from mrcourt.models import Case, ConversationState, User
from mrcourt.services.access import visible_cases
from mrcourt.services.cases import aware, next_hearing
from mrcourt.services.client_status import STATUS_LABELS
from mrcourt.services.reminders import IST

CHOICE_MINUTES = 5  # how long a "choose a case" list waits for the answer

FILLER = frozenset({"please", "my", "the", "what", "is", "when", "tell", "me", "show", "give", "a", "of", "do", "i", "have"})

PHRASES = {
    "next_hearing": {"next hearing", "hearing", "next date", "next hearing date", "अगली सुनवाई", "सुनवाई", "अगलीसुनवाई", "அடுத்த விசாரணை", "விசாரணை"},
    "status": {"status", "case status", "स्थिति", "केस स्थिति", "நிலை", "வழக்கு நிலை"},
    "today": {"today", "todays hearings", "hearing today", "hearings today", "आज", "आज की सुनवाई", "இன்று", "இன்றைய விசாரணை"},
    "help": {"help", "menu", "hi", "hello", "hey", "मदद", "உதவி"},
}

HELP = (
    "You can ask me a legal question in your own words, for example: What is Section 138 of the NI Act?\n\n"
    "Or send one of these:\n- next hearing\n- status\n- today\n- STOP to stop WhatsApp messages from MrCourt."
)


def _words(text: str) -> str:
    """Lower case, punctuation removed (letters, marks and digits kept), filler words dropped."""
    cleaned = "".join(ch if unicodedata.category(ch)[0] in "LMN" else " " for ch in (text or "").lower())
    return " ".join(w for w in cleaned.split() if w not in FILLER)


def parse(text: str) -> str | None:
    """The short request this message is, or None when it is a question."""
    words = _words(text)
    for intent, phrases in PHRASES.items():
        if words in phrases:
            return intent
    return None


def _when(moment: datetime) -> str:
    return f"{aware(moment).astimezone(IST):%d %b %Y, %I:%M %p}"


def _cases(db: Session, user: User) -> list[Case]:
    query = visible_cases(user).options(selectinload(Case.hearings)).order_by(Case.title)
    return list(db.scalars(query))


def _next_hearing_line(case: Case, now: datetime) -> str:
    hearing = next_hearing(case, now)
    if hearing is None:
        return f"No hearing is scheduled for {case.title}."
    room = f", room {hearing.court_room}" if hearing.court_room else ""
    return f"Next hearing in {case.title}: {_when(hearing.scheduled_at)} at {case.court}{room}."


def _status_line(case: Case, now: datetime) -> str:
    label = STATUS_LABELS.get(case.client_status or "")
    head = (
        f"Status of {case.title}: {label}."
        if label
        else f"Your advocate has not shared a status for {case.title} yet."
    )
    return f"{head}\n{_next_hearing_line(case, now)}"


def _for_client(db: Session, user: User, intent: str, now: datetime) -> str:
    cases = _cases(db, user)
    if not cases:
        return "You have no cases shared with you on MrCourt yet. Ask your advocate to invite you."
    if intent == "today":
        today = [
            f"- {c.title}: {aware(h.scheduled_at).astimezone(IST):%I:%M %p}"
            for c in cases
            for h in c.hearings
            if aware(h.scheduled_at).astimezone(IST).date() == now.astimezone(IST).date()
        ]
        return "Your hearings today:\n" + "\n".join(today) if today else "You have no hearings today."
    if len(cases) == 1:
        return _status_line(cases[0], now) if intent == "status" else _next_hearing_line(cases[0], now)
    state = db.get(ConversationState, user.id)
    options = [str(c.id) for c in cases[:9]]
    if state is None:
        state = ConversationState(user_id=user.id, awaiting="case_choice", options=options, intent=intent, expires_at=now)
        db.add(state)
    state.awaiting, state.options, state.intent = "case_choice", options, intent
    state.expires_at = now + timedelta(minutes=CHOICE_MINUTES)
    lines = [f"{n}. {c.title}" for n, c in enumerate(cases[:9], start=1)]
    return "Which case? Reply with its number.\n" + "\n".join(lines)


def _for_advocate(db: Session, user: User, intent: str, now: datetime) -> str:
    cases = [c for c in _cases(db, user) if c.status != "closed"]
    if not cases:
        return "You have no open cases on MrCourt."
    upcoming = sorted(
        ((aware(h.scheduled_at), c) for c in cases for h in c.hearings if aware(h.scheduled_at) >= now),
        key=lambda pair: pair[0],
    )
    if intent == "today":
        today = [f"- {c.title}: {when.astimezone(IST):%I:%M %p}" for when, c in upcoming if when.astimezone(IST).date() == now.astimezone(IST).date()]
        return "Your hearings today:\n" + "\n".join(today) if today else "You have no hearings today."
    if not upcoming:
        return f"You have {len(cases)} open case(s) and no upcoming hearings."
    lines = [f"{n}. {c.title}: {_when(when)}" for n, (when, c) in enumerate(upcoming[:3], start=1)]
    head = "Your next hearings:" if intent == "next_hearing" else f"You have {len(cases)} open case(s). Your next hearings:"
    return head + "\n" + "\n".join(lines)


def _choice(db: Session, user: User, text: str, now: datetime) -> str | None:
    """The answer for a number sent while a case list is open, or None when no list is waiting."""
    state = db.get(ConversationState, user.id)
    if state is None:
        return None
    if aware(state.expires_at) < now:
        db.delete(state)
        return None
    if not text.strip().isdigit():
        return None
    number = int(text.strip())
    if not 1 <= number <= len(state.options):
        return f"Please reply with a number from 1 to {len(state.options)}."
    case = db.get(Case, uuid.UUID(state.options[number - 1]))
    intent = state.intent
    db.delete(state)
    visible = {c.id for c in _cases(db, user)}
    if case is None or case.id not in visible:
        return "I could not find that case."  # the same reply for a case that is gone or is not theirs
    return _status_line(case, now) if intent == "status" else _next_hearing_line(case, now)


def reply_for(db: Session, user: User, text: str, now: datetime | None = None) -> str | None:
    """The answer to a short request, or None when the message is not one (it is a question)."""
    now = now or utcnow()
    chosen = _choice(db, user, text, now)
    if chosen is not None:
        return chosen
    intent = parse(text)
    if intent is None:
        return None
    if intent == "help":
        return HELP
    if user.role == "petitioner":
        return _for_client(db, user, intent, now)
    if user.role == "advocate":
        return _for_advocate(db, user, intent, now)
    return HELP
