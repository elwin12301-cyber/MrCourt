"""The public webhook the WhatsApp provider calls (feature 010). Protected by the provider's signature."""

import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse

from mrcourt.api.deps import DbSession
from mrcourt.config import get_settings
from mrcourt.db.base import get_db
from mrcourt.services.whatsapp import inbound, outbox
from mrcourt.services.whatsapp.channel import SignatureError, get_channel, provider_name

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])
logger = logging.getLogger(__name__)

MAX_BODY_BYTES = 1024 * 1024


def webhook_url() -> str:
    """The exact public address the provider calls (Twilio signs it)."""
    settings = get_settings()
    return settings.whatsapp_webhook_url or settings.public_app_url.rstrip("/") + "/api/v1/whatsapp/webhook"


def _channel_is_off() -> bool:
    return provider_name() == "none" and get_settings().environment == "production"


def _handle_later(app, row_id) -> None:  # type: ignore[no-untyped-def]
    """Handles one stored message after the webhook has answered. Uses the application's database provider (so
    tests that replace it see the same data) with the usual commit-on-success, rollback-on-error."""
    provider = app.dependency_overrides.get(get_db, get_db)
    generator = provider()
    db = next(generator)
    try:
        inbound.process(db, row_id)
    except Exception as error:  # noqa: BLE001 - the stored row is retried by the hourly job
        logger.warning("A WhatsApp message could not be handled (%s)", type(error).__name__)
        try:
            generator.throw(error)
        except Exception:  # noqa: BLE001, S110 - the generator re-raises after rolling back
            pass
    else:
        next(generator, None)


@router.get("/webhook")
def verify(
    mode: Annotated[str | None, Query(alias="hub.mode")] = None,
    token: Annotated[str | None, Query(alias="hub.verify_token")] = None,
    challenge: Annotated[str | None, Query(alias="hub.challenge")] = None,
) -> PlainTextResponse:
    """Meta's one-time setup call: answered only when the token matches the one we hold."""
    from mrcourt.services.whatsapp.meta import verify_challenge

    if not verify_challenge(mode, token) or challenge is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed")
    return PlainTextResponse(challenge)


@router.post("/webhook")
async def receive(request: Request, background: BackgroundTasks, db: DbSession) -> dict[str, str]:
    if _channel_is_off():
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed")
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        raise HTTPException(413, "Too large")
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise HTTPException(413, "Too large")
    try:
        parsed = get_channel().verify_and_parse(request.headers, body, webhook_url())
    except SignatureError:
        # Nothing is read or stored; the body is never logged.
        logger.warning("WhatsApp webhook call refused: signature check failed")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed") from None
    for report in parsed.reports:
        outbox.apply_report(db, report)  # delivery news for a message we sent
    new_ids = inbound.accept(db, parsed)
    db.commit()
    for row_id in new_ids:
        background.add_task(_handle_later, request.app, row_id)
    return {}
