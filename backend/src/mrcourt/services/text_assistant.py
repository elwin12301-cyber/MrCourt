"""The Text Assistant: a person's private, editable conversation of spoken or typed lines.

Each conversation has a History entry (a Question row with mode "text") that is created with it and
kept when the conversation is deleted, so deleting only tidies the tab. Audio is never kept; only
the transcribed text is.
"""

import uuid
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from mrcourt.db.base import utcnow
from mrcourt.models import Question, TextConversation, TextLine, User

MAX_LINES = 200
MAX_LINE_CHARS = 2000
DEFAULT_TITLE = "New conversation"
SPEECH_LANGUAGES = ("en-IN", "hi-IN", "ta-IN", "te-IN", "kn-IN", "ml-IN", "mr-IN", "bn-IN", "gu-IN")


def _history_row(db: Session, conversation: TextConversation) -> Question | None:
    return db.scalar(select(Question).where(Question.conversation_id == conversation.id))


def create(db: Session, user: User, language: str = "en-IN") -> TextConversation:
    if language not in SPEECH_LANGUAGES:
        language = "en-IN"
    conversation = TextConversation(user_id=user.id, title=DEFAULT_TITLE, language=language)
    db.add(conversation)
    db.flush()
    db.add(
        Question(
            user_id=user.id,
            text=DEFAULT_TITLE,
            input_method="typed",
            mode="text",
            conversation_id=conversation.id,
        )
    )
    db.flush()
    return conversation


def get_own(db: Session, user: User, conversation_id: uuid.UUID, *, include_deleted: bool = False) -> TextConversation:
    conversation = db.get(TextConversation, conversation_id)
    if (
        conversation is None
        or conversation.user_id != user.id
        or (conversation.deleted_at is not None and not include_deleted)
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return conversation


def list_own(db: Session, user: User) -> list[TextConversation]:
    return list(
        db.scalars(
            select(TextConversation)
            .where(TextConversation.user_id == user.id, TextConversation.deleted_at.is_(None))
            .order_by(TextConversation.updated_at.desc())
        )
    )


def _sync_history(db: Session, conversation: TextConversation) -> None:
    row = _history_row(db, conversation)
    if row is None:
        return
    row.text = conversation.title
    row.input_method = "voice" if any(line.source == "voice" for line in conversation.lines) else "typed"


def rename(db: Session, conversation: TextConversation, title: str | None, language: str | None) -> None:
    if title is not None and title.strip():
        conversation.title = title.strip()[:200]
    if language in SPEECH_LANGUAGES:
        conversation.language = language  # type: ignore[assignment]
    conversation.updated_at = utcnow()
    _sync_history(db, conversation)
    db.flush()


def add_line(db: Session, conversation: TextConversation, text: str, source: str) -> TextLine:
    text = text.strip()
    if not text:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A line cannot be empty")
    if len(conversation.lines) >= MAX_LINES:
        raise HTTPException(status.HTTP_409_CONFLICT, f"A conversation can hold {MAX_LINES} lines. Start a new one.")
    line = TextLine(
        conversation_id=conversation.id,
        position=(conversation.lines[-1].position + 1) if conversation.lines else 1,
        text=text[:MAX_LINE_CHARS],
        source="voice" if source == "voice" else "typed",
        created_at=utcnow(),
    )
    db.add(line)
    conversation.lines.append(line)
    if conversation.title == DEFAULT_TITLE:
        conversation.title = text[:60]
    conversation.updated_at = utcnow()
    _sync_history(db, conversation)
    db.flush()
    return line


def _own_line(conversation: TextConversation, line_id: uuid.UUID) -> TextLine:
    line = next((line for line in conversation.lines if line.id == line_id), None)
    if line is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return line


def edit_line(db: Session, conversation: TextConversation, line_id: uuid.UUID, text: str) -> TextLine:
    line = _own_line(conversation, line_id)
    text = text.strip()
    if not text:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A line cannot be empty")
    line.text = text[:MAX_LINE_CHARS]
    conversation.updated_at = utcnow()
    db.flush()
    return line


def remove_line(db: Session, conversation: TextConversation, line_id: uuid.UUID) -> None:
    line = _own_line(conversation, line_id)
    conversation.lines.remove(line)
    db.delete(line)
    conversation.updated_at = utcnow()
    _sync_history(db, conversation)
    db.flush()


def delete(db: Session, conversation: TextConversation) -> None:
    """Hides it from the Text Assistant tab. Its History entry, and the text, stay."""
    conversation.deleted_at = utcnow()
    db.flush()


def as_text(conversation: TextConversation) -> str:
    return "\n".join(line.text for line in conversation.lines)


# ----- PDF --------------------------------------------------------------------------------------

_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\Nirmala.ttf",  # Tamil, Hindi and other Indian scripts on Windows
    "/usr/share/fonts/truetype/noto/NotoSansTamil-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _unicode_font() -> str | None:
    return next((f for f in _FONT_CANDIDATES if Path(f).exists()), None)


def to_pdf(conversation: TextConversation) -> bytes:
    """A simple PDF of the conversation. Indian scripts need a Unicode font on the server; without
    one, characters outside Latin-1 are replaced so the file still builds."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    font = _unicode_font()
    if font:
        pdf.add_font("body", "", font)
        pdf.set_font("body", size=12)

        def clean(s: str) -> str:
            return s
    else:
        pdf.set_font("Helvetica", size=12)

        def clean(s: str) -> str:
            return s.encode("latin-1", "replace").decode("latin-1")

    if font:
        try:
            pdf.set_text_shaping(True)  # joins Tamil and other Indic letters correctly; needs uharfbuzz
        except Exception:  # noqa: BLE001 - without it the text is still written, just unshaped
            pass
    pdf.multi_cell(0, 9, clean(conversation.title), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    for line in conversation.lines:
        pdf.multi_cell(0, 7, clean(line.text), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
    return bytes(pdf.output())
