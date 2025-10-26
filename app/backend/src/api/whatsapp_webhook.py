"""WhatsApp webhook endpoints for receiving messages and events."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel

from src.core.config import get_settings
from src.services.whatsapp.webhook_handler import WebhookHandler

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

    # Check all required parameters are present
    if not all([hub_mode, hub_verify_token, hub_challenge]):
        logger.warning("Webhook verification failed: missing parameters")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required parameters: hub.mode, hub.verify_token, hub.challenge",
        )

    # Verify mode is 'subscribe'
    if hub_mode != "subscribe":
        logger.warning(f"Webhook verification failed: invalid mode '{hub_mode}'")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid hub.mode, expected 'subscribe'"
        )

    # Verify token matches
    expected_token = settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN
    if not expected_token or hub_verify_token != expected_token.get_secret_value():
        logger.warning("Webhook verification failed: invalid verify token")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid verify token"
        )

    logger.info("Webhook verification successful")
    return hub_challenge


@router.post("", response_model=WebhookResponse)
async def receive_webhook(request: Request, payload: dict[str, Any]) -> WebhookResponse:
    """
    Receive WhatsApp webhook events (messages and status updates).

    WhatsApp sends POST requests with message events and status updates.
    Always returns 200 to avoid retries from WhatsApp.
    """
    try:
        # Parse webhook payload
        events = WebhookHandler.parse_webhook_payload(payload)

        if not events:
            logger.debug("No events found in webhook payload")
            return WebhookResponse(status="ok")

        logger.info(f"Received {len(events)} webhook event(s)")

        # Process each event
        for event in events:
            event_type = event.get("event_type")

            if event_type == "message":
                await _handle_incoming_message(event)
            elif event_type == "status_update":
                await _handle_status_update(event)
            else:
                logger.warning(f"Unknown event type: {event_type}")

    except Exception as e:
        # Log error but still return 200 to avoid WhatsApp retries
        logger.error(f"Error processing webhook: {str(e)}", exc_info=True)

    return WebhookResponse(status="ok")


async def _handle_incoming_message(event: dict[str, Any]) -> None:
    """
    Handle incoming message from WhatsApp.

    Args:
        event: Parsed message event
    """
    wa_message_id = event.get("wa_message_id")
    from_number = event.get("from")
    content = event.get("content", {})
    message_type = content.get("type")

    logger.info(
        f"Incoming message: wa_id={wa_message_id}, from={from_number}, type={message_type}"
    )

    # TODO: In next issues, this will:
    # 1. Find or create WhatsAppSession for this phone number
    # 2. Store message in WhatsAppMessage table
    # 3. Trigger briefing orchestration logic
    # For now, just log it


async def _handle_status_update(event: dict[str, Any]) -> None:
    """
    Handle message status update from WhatsApp.

    Args:
        event: Parsed status update event
    """
    wa_message_id = event.get("wa_message_id")
    new_status = event.get("status")

    logger.info(f"Status update: wa_id={wa_message_id}, status={new_status}")

    # TODO: In next issues, this will:
    # 1. Find WhatsAppMessage by wa_message_id
    # 2. Update status field
    # 3. Update error fields if failed
    # For now, just log it
