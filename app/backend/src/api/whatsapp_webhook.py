"""WhatsApp webhook endpoints for receiving messages and events."""

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.rate_limit import limiter
from src.db.models.authorized_phone import AuthorizedPhone
from src.db.models.organization import Organization
from src.db.models.whatsapp_message import WhatsAppMessage
from src.db.session import get_db_session
from src.services.ai import get_ai_service
from src.services.briefing.answer_processor import AnswerProcessorService
from src.services.briefing.briefing_start_service import (
    BriefingStartService,
    ClientHasActiveBriefingError,
)
from src.services.briefing.extraction_service import ExtractionService
from src.services.briefing.orchestrator import BriefingOrchestrator
from src.services.briefing.phone_utils import normalize_phone
from src.services.template_service import TemplateService
from src.services.whatsapp.webhook_handler import WebhookHandler
from src.services.whatsapp.whatsapp_account_service import WhatsAppAccountService
from src.services.whatsapp.whatsapp_service import WhatsAppService

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

    WhatsApp sends POST requests with message events and status updates.
    Always returns 200 to avoid retries from WhatsApp.
    """
    try:
        events = WebhookHandler.parse_webhook_payload(payload)

        if not events:
            logger.debug("No events found in webhook payload")
            return WebhookResponse(status="ok")

        logger.info(f"Received {len(events)} webhook event(s)")

        for event in events:
            event_type = event.get("event_type")

            if event_type == "message":
                await _handle_incoming_message(event, db_session)
            elif event_type == "status_update":
                await _handle_status_update(event, db_session)
            else:
                logger.warning(f"Unknown event type: {event_type}")

    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}", exc_info=True)

    return WebhookResponse(status="ok")


async def _handle_incoming_message(event: dict[str, Any], db_session: AsyncSession) -> None:
    """
    Handle incoming message from WhatsApp.

    Detects two types of senders:
    1. Authorized phone (architect) → Start new briefing
    2. Client phone → Process answer to existing briefing

    Args:
        event: Parsed message event
        db_session: Database session for processing
    """
    wa_message_id = event.get("wa_message_id")
    from_number = event.get("from")
    content = event.get("content", {})
    message_type = content.get("type")
    phone_number_id = event.get("phone_number_id")

    logger.info(f"Incoming message: wa_id={wa_message_id}, from={from_number}, type={message_type}")

    if message_type != "text":
        logger.info(f"Skipping non-text message type: {message_type}")
        return

    text_body = content.get("text", {}).get("body")
    if not text_body:
        logger.warning("Text message without body")
        return

    result = await db_session.execute(
        select(AuthorizedPhone).where(
            AuthorizedPhone.phone_number == from_number,
            AuthorizedPhone.is_active,
        )
    )
    authorized_phone = result.scalar_one_or_none()

    if authorized_phone:
        logger.info(f"Message from authorized phone: {from_number}")
        await _handle_authorized_phone_message(
            from_number=from_number,
            text_body=text_body,
            authorized_phone=authorized_phone,
            phone_number_id=phone_number_id,
            db_session=db_session,
        )
    else:
        logger.info(f"Message from potential client: {from_number}")
        await _handle_client_answer(
            from_number=from_number,
            text_body=text_body,
            wa_message_id=wa_message_id,
            phone_number_id=phone_number_id,
            db_session=db_session,
        )


async def _handle_authorized_phone_message(
    from_number: str,
    text_body: str,
    authorized_phone: Any,
    phone_number_id: str,
    db_session: AsyncSession,
) -> None:
    """
    Handle message from authorized phone (architect initiating briefing).

    Args:
        from_number: Sender's phone number
        text_body: Message text
        authorized_phone: AuthorizedPhone record
        phone_number_id: WhatsApp Business phone number ID
        db_session: Database session
    """
    try:
        result = await db_session.execute(
            select(Organization).where(Organization.id == authorized_phone.organization_id)
        )
        organization = result.scalar_one()

        ai_service = get_ai_service("openai")
        extraction_service = ExtractionService(ai_service)
        extracted_info = await extraction_service.extract_client_info(
            message=text_body,
            architect_id=authorized_phone.added_by_architect_id,
            model="gpt-4o-mini",
        )

        logger.info(
            f"Extracted client info: confidence={extracted_info.confidence}, "
            f"name={extracted_info.name}, phone={extracted_info.phone}"
        )

        if extracted_info.confidence < 0.5 or not extracted_info.name or not extracted_info.phone:
            error_msg = (
                "❌ Não consegui extrair os dados do cliente da sua mensagem.\n\n"
                "Por favor, envie novamente incluindo:\n"
                "- Nome completo do cliente\n"
                "- Telefone do cliente\n"
                "- Tipo de projeto (residencial, comercial, reforma, etc.)\n\n"
                "Exemplo: 'Cliente João Silva, tel 11987654321, quer fazer reforma residencial'"
            )

            account_service = WhatsAppAccountService(db_session)
            config = await account_service.get_account_config(
                organization_id=organization.id,
                phone_number_id_override=phone_number_id,
            )

            if config:
                wa_service = WhatsAppService(
                    phone_number_id=config.phone_number_id,
                    access_token=config.access_token,
                )
                await wa_service.send_text_message(to=from_number, text=error_msg)

            logger.warning(f"Extraction failed for message from {from_number}")
            return

        client_phone = normalize_phone(extracted_info.phone)

        template_service = TemplateService(db_session)
        template_version = await template_service.select_template_version_for_project(
            architect_id=authorized_phone.added_by_architect_id,
            project_type_slug=extracted_info.project_type or "residencial",
        )

        briefing_service = BriefingStartService(db_session)
        briefing = await briefing_service.start_briefing(
            organization_id=organization.id,
            architect_id=authorized_phone.added_by_architect_id,
            client_name=extracted_info.name,
            client_phone=client_phone,
            template_version_id=template_version.id,
        )

        orchestrator = BriefingOrchestrator(db_session)
        first_question_data = await orchestrator.next_question(briefing.id)
        first_question = first_question_data["question"]

        account_service = WhatsAppAccountService(db_session)
        config = await account_service.get_account_config(
            organization_id=organization.id,
            phone_number_id_override=phone_number_id,
        )

        if config:
            wa_service = WhatsAppService(
                phone_number_id=config.phone_number_id,
                access_token=config.access_token,
            )
            await wa_service.send_text_message(to=client_phone, text=first_question)

        await db_session.commit()

        logger.info(
            f"Briefing started via WhatsApp: briefing_id={briefing.id}, "
            f"client_phone={client_phone}, initiated_by={from_number}"
        )

    except ClientHasActiveBriefingError as e:
        error_msg = f"⚠️ Este cliente já possui um briefing ativo.\n\n{str(e)}"

        account_service = WhatsAppAccountService(db_session)
        config = await account_service.get_account_config(
            organization_id=organization.id,
            phone_number_id_override=phone_number_id,
        )

        if config:
            wa_service = WhatsAppService(
                phone_number_id=config.phone_number_id,
                access_token=config.access_token,
            )
            await wa_service.send_text_message(to=from_number, text=error_msg)

        logger.warning(f"Cannot start briefing: {str(e)}")
        await db_session.rollback()

    except Exception as e:
        logger.error(f"Error starting briefing from authorized phone: {str(e)}", exc_info=True)
        await db_session.rollback()


async def _handle_client_answer(
    from_number: str,
    text_body: str,
    wa_message_id: str,
    phone_number_id: str,
    db_session: AsyncSession,
) -> None:
    """
    Handle message from client (answer to briefing question).

    Args:
        from_number: Sender's phone number
        text_body: Message text
        wa_message_id: WhatsApp message ID
        phone_number_id: WhatsApp Business phone number ID
        db_session: Database session
    """
    processor = AnswerProcessorService(db_session)
    result = await processor.process_client_answer(
        phone_number=from_number,
        answer_text=text_body,
        wa_message_id=wa_message_id,
        session_id=None,
        phone_number_id=phone_number_id,
    )

    if result.get("success"):
        logger.info(
            f"Successfully processed answer from {from_number}, briefing_id={result.get('briefing_id')}"
        )
    else:
        logger.warning(
            f"Could not process answer from {from_number}: {result.get('error', 'Unknown error')}"
        )


async def _handle_status_update(event: dict[str, Any], db_session: AsyncSession) -> None:
    """
    Handle message status update from WhatsApp.

    Persists status changes to WhatsAppMessage table, including:
    - Status field update (sent, delivered, read, failed)
    - delivered_at timestamp for 'delivered' status
    - read_at timestamp for 'read' status
    - error_code and error_message for 'failed' status

    Args:
        event: Parsed status update event
        db_session: Database session for persistence
    """
    wa_message_id = event.get("wa_message_id")
    new_status = event.get("status")

    logger.info(f"Status update: wa_id={wa_message_id}, status={new_status}")

    result = await db_session.execute(
        select(WhatsAppMessage).where(WhatsAppMessage.wa_message_id == wa_message_id)
    )
    message = result.scalar_one_or_none()

    if not message:
        logger.warning(f"Message {wa_message_id} not found for status update")
        return

    message.status = new_status

    if new_status == "delivered":
        message.delivered_at = datetime.now(UTC)
    elif new_status == "read":
        message.read_at = datetime.now(UTC)
    elif new_status == "failed":
        message.error_code = event.get("error_code")
        message.error_message = event.get("error_message")

    await db_session.commit()
    logger.info(f"Updated message {wa_message_id} status to {new_status}")
