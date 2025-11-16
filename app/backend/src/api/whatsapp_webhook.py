"""WhatsApp webhook endpoints for receiving messages and events.

NOTE: This file has been simplified during Phase 2 refactoring.
The old question-based webhook handlers have been removed.
TODO: Reimplement webhook handlers using the new conversation-based system with:
  - ConversationMessage model
  - information_state/gathered_information fields
  - ConversationMemory service
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.rate_limit import limiter
from src.db.session import get_db_session

router = APIRouter(prefix="/api/webhooks/whatsapp", tags=["whatsapp-webhooks"])
logger = logging.getLogger(__name__)


class WebhookResponse(BaseModel):
    """Response model for webhook."""

    status: str


@router.get("", response_model=str)
async def verify_webhook(
    request: Request,
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
) -> str:
    """
    Verify WhatsApp webhook during setup.

    WhatsApp will send a GET request with:
    - hub.mode: should be 'subscribe'
    - hub.verify_token: your verify token
    - hub.challenge: random string to echo back

    Returns the challenge string if verification succeeds.
    """
    settings = get_settings()

    if not all([hub_mode, hub_verify_token, hub_challenge]):
        logger.warning("Webhook verification failed: missing parameters")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required parameters: hub.mode, hub.verify_token, hub.challenge",
        )

    if hub_mode != "subscribe":
        logger.warning(f"Webhook verification failed: invalid mode '{hub_mode}'")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid hub.mode, expected 'subscribe'"
        )

    expected_token = settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN
    if not expected_token or hub_verify_token != expected_token.get_secret_value():
        logger.warning("Webhook verification failed: invalid verify token")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid verify token")

    logger.info("Webhook verification successful")
    return hub_challenge


@router.post("", response_model=WebhookResponse)
@limiter.limit(get_settings().RATE_LIMIT_WEBHOOK)
async def receive_webhook(
    request: Request,
    payload: dict[str, Any],
    db_session: AsyncSession = Depends(get_db_session),
) -> WebhookResponse:
    """
    Receive WhatsApp webhook events (messages and status updates).

    TODO: Reimplement using conversation-based system.
    The old question-based handler has been removed during Phase 2 refactoring.
    """
    logger.warning(
        "WhatsApp webhook received but handler not yet reimplemented with conversation-based system"
    )
    # Always return 200 to avoid retries from WhatsApp
    return WebhookResponse(status="received")
