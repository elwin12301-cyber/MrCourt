"""Development only: read the messages that would have been sent by text or WhatsApp (codes, reminders, replies).

Not available in production, and not available once a real text-message service is set up.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from mrcourt.config import get_settings
from mrcourt.services import notify

router = APIRouter(prefix="/dev", tags=["development"])


class DevMessage(BaseModel):
    to: str
    kind: str
    channel: str = "sms"  # sms | whatsapp
    text: str
    at: str


@router.get("/messages", response_model=list[DevMessage])
def messages() -> list[DevMessage]:
    if get_settings().environment not in ("development", "test") or notify.delivers_for_real():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return [
        DevMessage(to=m.contact, kind=m.kind, channel=m.channel, text=m.text, at=m.created_at.isoformat())
        for m in reversed(notify.OUTBOX[-50:])
    ]
