"""API endpoints for briefing management and WhatsApp integration."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.architect import Architect
from src.db.models.briefing import Briefing
from src.db.models.conversation import Conversation, ConversationType
from src.db.models.end_client import EndClient
from src.db.models.organization import Organization
from src.db.session import get_db_session
from src.schemas.briefing import ExtractedClientInfo, StartBriefingRequest, StartBriefingResponse
from src.services.ai import get_ai_service
from src.services.briefing.extraction_service import ExtractionService
from src.services.briefing.orchestrator import BriefingOrchestrator
from src.services.briefing.phone_utils import normalize_phone
from src.services.template_service import TemplateService
from src.services.whatsapp.whatsapp_service import WhatsAppService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/briefings", tags=["briefings"])

# Configuration constants
MIN_EXTRACTION_CONFIDENCE = 0.50
DEFAULT_AI_PROVIDER = "openai"
DEFAULT_EXTRACTION_MODEL = "gpt-4o-mini"


@router.post("/start-from-whatsapp", response_model=StartBriefingResponse)
async def start_briefing_from_whatsapp(
    request: StartBriefingRequest,
    db_session: AsyncSession = Depends(get_db_session),
) -> StartBriefingResponse:
    """
    Start a new briefing session from architect message via WhatsApp.

    This endpoint orchestrates the complete E2E flow:
    1. Extract client info from architect message using AI
    2. Validate extraction quality
    3. Create or update EndClient
    4. Identify appropriate template
    5. Start briefing session
    6. Send first question via WhatsApp
    7. Create conversation record

    All operations are wrapped in a transaction for atomicity.
    """
    logger.info(
        f"Starting briefing from WhatsApp for architect {request.architect_id}",
        extra={"architect_id": str(request.architect_id)},
    )

    try:
        # Step 1: Verify architect exists and get organization
        architect, organization = await _get_architect_and_organization(
            db_session, request.architect_id
        )

        # Step 2: Extract client information using AI
        extraction_service = _get_extraction_service()
        extracted_info = await extraction_service.extract_client_info(
            message=request.architect_message,
            architect_id=request.architect_id,
            model=DEFAULT_EXTRACTION_MODEL,
        )

        logger.info(
            f"Extracted client info with confidence {extracted_info.confidence:.2f}",
            extra={
                "client_name": extracted_info.name,
                "client_phone": extracted_info.phone,
                "project_type": extracted_info.project_type,
                "confidence": extracted_info.confidence,
            },
        )

        # Step 3: Validate extraction
        _validate_extraction(extracted_info)

        # Step 4: Normalize phone number
        normalized_phone = normalize_phone(extracted_info.phone)

        # Step 5: Create or update EndClient
        end_client = await _create_or_update_client(
            db_session=db_session,
            organization_id=organization.id,
            architect_id=request.architect_id,
            name=extracted_info.name,
            phone=normalized_phone,
        )

        # Step 6: Identify appropriate template
        template_service = TemplateService(db_session)
        template_version = await template_service.select_template_version_for_project(
            architect_id=request.architect_id,
            project_type_slug=(extracted_info.project_type or "residencial"),
        )

        # Step 7: Start briefing session
        template_version_id = template_version.id

        orchestrator = BriefingOrchestrator(db_session)
        briefing = await orchestrator.start_briefing(
            end_client_id=end_client.id,
            template_version_id=template_version_id,
        )

        # Step 8: Get first question
        first_question_data = await orchestrator.next_question(briefing.id)
        first_question = first_question_data["question"]

        # Step 9: Get WhatsApp service and send first question
        whatsapp_service = _get_whatsapp_service(organization)
        whatsapp_result = await whatsapp_service.send_text_message(
            to=normalized_phone,
            text=first_question,
        )

        if not whatsapp_result.get("success"):
            error_msg = whatsapp_result.get("error", "Unknown WhatsApp error")
            logger.error(f"Failed to send WhatsApp message: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to send WhatsApp message: {error_msg}",
            )

        # Step 10: Create conversation record
        await _create_conversation(
            db_session=db_session,
            architect=architect,
            end_client=end_client,
            briefing=briefing,
            whatsapp_context={
                "phone_number": normalized_phone,
                "architect_id": str(request.architect_id),
                "initial_message": request.architect_message,
                "whatsapp_message_id": whatsapp_result.get("message_id"),
            },
        )

        # Commit transaction
        await db_session.commit()

        logger.info(
            f"Successfully started briefing {briefing.id} for client {end_client.name}",
            extra={
                "briefing_id": str(briefing.id),
                "client_id": str(end_client.id),
                "template_category": (
                    template_version.template.project_type.slug
                    if template_version.template and template_version.template.project_type
                    else template_version.template.category if template_version.template else ""
                ),
            },
        )

        # Return response
        return StartBriefingResponse(
            briefing_id=briefing.id,
            client_id=end_client.id,
            client_name=end_client.name,
            client_phone=end_client.phone,
            first_question=first_question,
            template_category=(
                template_version.template.project_type.slug
                if template_version.template and template_version.template.project_type
                else template_version.template.category if template_version.template else ""
            ),
            whatsapp_message_id=whatsapp_result.get("message_id"),
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        await db_session.rollback()
        raise
    except Exception as e:
        # Rollback and log unexpected errors
        await db_session.rollback()
        logger.exception("Unexpected error starting briefing from WhatsApp")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start briefing: {str(e)}",
        ) from e


# Helper functions
async def _get_architect_and_organization(
    db_session: AsyncSession, architect_id: UUID
) -> tuple[Architect, Organization]:
    """Get architect and organization, raising 404 if not found."""
    result = await db_session.execute(
        select(Architect, Organization)
        .join(Organization, Architect.organization_id == Organization.id)
        .where(Architect.id == architect_id)
    )
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Architect not found: {architect_id}",
        )

    architect, organization = row
    return architect, organization


def _get_extraction_service() -> ExtractionService:
    """Get extraction service with default AI provider."""
    ai_service = get_ai_service(DEFAULT_AI_PROVIDER)
    return ExtractionService(ai_service)


def _validate_extraction(extracted_info: ExtractedClientInfo) -> None:
    """Validate that extraction has required fields and sufficient confidence."""
    # Check confidence threshold
    if extracted_info.confidence < MIN_EXTRACTION_CONFIDENCE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Extração de dados com baixa confiança ({extracted_info.confidence:.0%}). "
                "Por favor, forneça informações mais claras sobre o cliente."
            ),
        )

    # Check required fields
    if not extracted_info.name or not extracted_info.name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nome do cliente não encontrado na mensagem. Por favor, inclua o nome completo do cliente.",
        )

    if not extracted_info.phone or not extracted_info.phone.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telefone do cliente não encontrado na mensagem. Por favor, inclua o número de telefone do cliente.",
        )


async def _create_or_update_client(
    db_session: AsyncSession,
    organization_id: UUID,
    architect_id: UUID,
    name: str,
    phone: str,
) -> EndClient:
    """Create new client or update existing one with same phone number.

    Handles unique constraint on (organization_id, phone) by updating existing client.
    """
    try:
        # Try to get existing client with same phone in the organization
        result = await db_session.execute(
            select(EndClient).where(
                EndClient.organization_id == organization_id,
                EndClient.phone == phone,
            )
        )
        existing_client = result.scalar_one_or_none()

        if existing_client:
            # Update existing client (name and architect_id may have changed)
            logger.info(f"Updating existing client {existing_client.id}")
            existing_client.name = name
            existing_client.architect_id = architect_id  # Update architect if needed
            await db_session.flush()
            return existing_client

        # Create new client
        new_client = EndClient(
            organization_id=organization_id,
            architect_id=architect_id,
            name=name,
            phone=phone,
        )
        db_session.add(new_client)
        await db_session.flush()
        logger.info(f"Created new client {new_client.id}")
        return new_client

    except IntegrityError as e:
        logger.error(f"Database integrity error creating client: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Erro ao criar cliente. O telefone pode já estar cadastrado.",
        ) from e


def _get_whatsapp_service(organization: Organization) -> WhatsAppService:
    """Get WhatsApp service from organization settings."""
    settings = organization.settings or {}
    phone_number_id = settings.get("phone_number_id")
    access_token = settings.get("access_token")

    if not phone_number_id or not access_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="WhatsApp não configurado para esta organização.",
        )

    return WhatsAppService(
        phone_number_id=phone_number_id,
        access_token=access_token,
    )


async def _create_conversation(
    db_session: AsyncSession,
    architect: Architect,
    end_client: EndClient,
    briefing: Briefing,
    whatsapp_context: dict,
) -> Conversation:
    """Create conversation record linking briefing to WhatsApp context."""
    conversation = Conversation(
        architect_id=architect.id,
        title=f"Briefing - {end_client.name}",
        ai_provider=DEFAULT_AI_PROVIDER,
        ai_model=DEFAULT_EXTRACTION_MODEL,
        conversation_type=ConversationType.WHATSAPP_BRIEFING.value,
        end_client_id=end_client.id,
        whatsapp_context=whatsapp_context,
    )
    conversation.briefing = briefing
    db_session.add(conversation)
    await db_session.flush()
    logger.info(f"Created conversation {conversation.id} for briefing {briefing.id}")
    return conversation
