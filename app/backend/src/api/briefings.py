"""API endpoints for briefing management and WhatsApp integration."""

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.dependencies import get_current_architect
from src.core.organization_access import require_organization_access
from src.db.models.architect import Architect
from src.db.models.briefing import Briefing, BriefingStatus
from src.db.models.conversation import Conversation, ConversationType
from src.db.models.end_client import EndClient
from src.db.models.organization import Organization
from src.db.models.template_version import TemplateVersion
from src.db.session import get_db_session
from src.schemas.briefing import (
    AnalyticsMetrics,
    AnalyticsResponse,
    BriefingDetailRead,
    BriefingListResponse,
    CancelBriefingRequest,
    ExtractedClientInfo,
    StartBriefingRequest,
    StartBriefingResponse,
)
from src.services.ai import get_ai_service
from src.services.briefing.analytics_service import AnalyticsService
from src.services.briefing.extraction_service import ExtractionService
from src.services.briefing.orchestrator import BriefingOrchestrator
from src.services.briefing.phone_utils import normalize_phone
from src.services.template_service import TemplateService
from src.services.whatsapp.whatsapp_account_service import WhatsAppAccountService
from src.services.whatsapp.whatsapp_service import WhatsAppService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/briefings", tags=["briefings"])

# Configuration constants
MIN_EXTRACTION_CONFIDENCE = 0.50
DEFAULT_AI_PROVIDER = "openai"
DEFAULT_EXTRACTION_MODEL = "gpt-4o-mini"


@router.post("/start-from-whatsapp", response_model=StartBriefingResponse)
@require_organization_access("architect_id")
async def start_briefing_from_whatsapp(
    request: StartBriefingRequest,
    current_architect: Architect = Depends(get_current_architect),
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
        whatsapp_service = await _get_whatsapp_service(organization.id, db_session)
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


# CRUD API Endpoints


@router.get("", response_model=BriefingListResponse)
async def list_briefings(
    status_filter: BriefingStatus | None = Query(None, alias="status"),
    end_client_id: UUID | None = Query(None),
    template_id: UUID | None = Query(None),
    created_after: datetime | None = Query(None),
    created_before: datetime | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_architect: Architect = Depends(get_current_architect),
    db_session: AsyncSession = Depends(get_db_session),
) -> BriefingListResponse:
    """
    List briefings for the current architect's organization with optional filters.

    Filters:
    - status: Filter by briefing status (in_progress, completed, cancelled)
    - end_client_id: Filter by specific end client
    - template_id: Filter by template (any version of that template)
    - created_after: Filter by creation date (inclusive)
    - created_before: Filter by creation date (inclusive)

    Pagination:
    - limit: Number of results (1-100, default 20)
    - offset: Number of results to skip (default 0)
    """
    logger.info(
        f"Listing briefings for organization {current_architect.organization_id}",
        extra={
            "organization_id": str(current_architect.organization_id),
            "filters": {
                "status": status_filter.value if status_filter else None,
                "end_client_id": str(end_client_id) if end_client_id else None,
                "template_id": str(template_id) if template_id else None,
            },
        },
    )

    # Build query with organization isolation
    query = (
        select(Briefing)
        .join(EndClient, Briefing.end_client_id == EndClient.id)
        .where(EndClient.organization_id == current_architect.organization_id)
        .options(
            selectinload(Briefing.end_client),
            selectinload(Briefing.template_version),
        )
    )

    # Apply filters
    if status_filter:
        query = query.where(Briefing.status == status_filter)

    if end_client_id:
        query = query.where(Briefing.end_client_id == end_client_id)

    if template_id:
        # Filter by template_id (any version of that template)
        query = query.join(
            TemplateVersion, Briefing.template_version_id == TemplateVersion.id
        ).where(TemplateVersion.template_id == template_id)

    if created_after:
        query = query.where(Briefing.created_at >= created_after)

    if created_before:
        query = query.where(Briefing.created_at <= created_before)

    # Get total count (before pagination)
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db_session.execute(count_query)
    total = total_result.scalar_one()

    # Apply pagination and ordering
    query = query.order_by(Briefing.created_at.desc()).limit(limit).offset(offset)

    # Execute query
    result = await db_session.execute(query)
    briefings = result.scalars().all()

    return BriefingListResponse(
        items=briefings,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{briefing_id}", response_model=BriefingDetailRead)
async def get_briefing(
    briefing_id: UUID,
    current_architect: Architect = Depends(get_current_architect),
    db_session: AsyncSession = Depends(get_db_session),
) -> BriefingDetailRead:
    """
    Get detailed information about a specific briefing.

    Includes:
    - Briefing status and progress
    - End client information
    - Template version details
    - All answers provided so far
    """
    logger.info(
        f"Getting briefing {briefing_id}",
        extra={"briefing_id": str(briefing_id)},
    )

    # Query with organization isolation
    query = (
        select(Briefing)
        .join(EndClient, Briefing.end_client_id == EndClient.id)
        .where(
            Briefing.id == briefing_id,
            EndClient.organization_id == current_architect.organization_id,
        )
        .options(
            selectinload(Briefing.end_client),
            selectinload(Briefing.template_version),
        )
    )

    result = await db_session.execute(query)
    briefing = result.scalar_one_or_none()

    if not briefing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Briefing not found",
        )

    return briefing


@router.post("/{briefing_id}/complete", status_code=status.HTTP_200_OK)
async def complete_briefing(
    briefing_id: UUID,
    current_architect: Architect = Depends(get_current_architect),
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Manually complete a briefing.

    This endpoint allows manually marking a briefing as complete,
    which will:
    1. Update status to COMPLETED
    2. Set completed_at timestamp
    3. Generate analytics metrics

    Only IN_PROGRESS briefings can be completed.
    """
    logger.info(
        f"Completing briefing {briefing_id}",
        extra={"briefing_id": str(briefing_id)},
    )

    # Verify briefing exists and belongs to organization
    query = (
        select(Briefing)
        .join(EndClient, Briefing.end_client_id == EndClient.id)
        .where(
            Briefing.id == briefing_id,
            EndClient.organization_id == current_architect.organization_id,
        )
    )

    result = await db_session.execute(query)
    briefing = result.scalar_one_or_none()

    if not briefing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Briefing not found",
        )

    # Check if briefing is in progress
    if briefing.status != BriefingStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot complete briefing with status {briefing.status.value}",
        )

    # Complete briefing using orchestrator
    orchestrator = BriefingOrchestrator(db_session)
    try:
        await orchestrator.complete_briefing(briefing_id)
    except ValueError as e:
        # Handle validation errors (e.g., missing required answers, template issues)
        logger.warning(f"Cannot complete briefing {briefing_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot complete briefing: {str(e)}",
        ) from e

    await db_session.commit()

    logger.info(f"Briefing {briefing_id} completed successfully")

    return {
        "success": True,
        "message": "Briefing completed successfully",
        "briefing_id": str(briefing_id),
    }


@router.post("/{briefing_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_briefing(
    briefing_id: UUID,
    request: CancelBriefingRequest,
    current_architect: Architect = Depends(get_current_architect),
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Cancel a briefing.

    This endpoint allows cancelling a briefing with an optional reason.
    The briefing status will be set to CANCELLED.

    This operation is idempotent - cancelling an already cancelled briefing
    will succeed.
    """
    logger.info(
        f"Cancelling briefing {briefing_id}",
        extra={
            "briefing_id": str(briefing_id),
            "reason": request.reason,
        },
    )

    # Verify briefing exists and belongs to organization
    query = (
        select(Briefing)
        .join(EndClient, Briefing.end_client_id == EndClient.id)
        .where(
            Briefing.id == briefing_id,
            EndClient.organization_id == current_architect.organization_id,
        )
    )

    result = await db_session.execute(query)
    briefing = result.scalar_one_or_none()

    if not briefing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Briefing not found",
        )

    # Idempotent: if already cancelled, return success
    if briefing.status == BriefingStatus.CANCELLED:
        logger.info(f"Briefing {briefing_id} already cancelled")
        return {
            "success": True,
            "message": "Briefing already cancelled",
            "briefing_id": str(briefing_id),
        }

    # Cannot cancel completed briefings
    if briefing.status == BriefingStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel a completed briefing",
        )

    # Cancel briefing using orchestrator
    orchestrator = BriefingOrchestrator(db_session)
    await orchestrator.cancel_briefing(briefing_id)

    await db_session.commit()

    logger.info(f"Briefing {briefing_id} cancelled successfully")

    return {
        "success": True,
        "message": "Briefing cancelled successfully",
        "briefing_id": str(briefing_id),
        "reason": request.reason,
    }


@router.get("/{briefing_id}/analytics", response_model=AnalyticsResponse)
async def get_briefing_analytics(
    briefing_id: UUID,
    current_architect: Architect = Depends(get_current_architect),
    db_session: AsyncSession = Depends(get_db_session),
) -> AnalyticsResponse:
    """
    Get analytics for a completed briefing.

    Analytics are only available for COMPLETED briefings.
    The analytics are automatically generated when a briefing is completed.

    Metrics include:
    - Duration in seconds
    - Total questions
    - Answered questions (required/optional breakdown)
    - Completion rate
    - Optional observations
    """
    logger.info(
        f"Getting analytics for briefing {briefing_id}",
        extra={"briefing_id": str(briefing_id)},
    )

    # Verify briefing exists and belongs to organization
    query = (
        select(Briefing)
        .join(EndClient, Briefing.end_client_id == EndClient.id)
        .where(
            Briefing.id == briefing_id,
            EndClient.organization_id == current_architect.organization_id,
        )
    )

    result = await db_session.execute(query)
    briefing = result.scalar_one_or_none()

    if not briefing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Briefing not found",
        )

    # Check if briefing is completed
    if briefing.status != BriefingStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Analytics are only available for completed briefings",
        )

    # Get analytics using service
    analytics_service = AnalyticsService(db_session)
    analytics = await analytics_service.get_analytics(briefing_id)

    if not analytics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analytics not found for this briefing",
        )

    # Parse metrics into schema
    metrics = AnalyticsMetrics(**analytics.metrics)

    return AnalyticsResponse(
        id=analytics.id,
        briefing_id=analytics.briefing_id,
        metrics=metrics,
        observations=analytics.observations,
        created_at=analytics.created_at,
    )


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


async def _get_whatsapp_service(
    organization_id: UUID,
    db_session: AsyncSession,
) -> WhatsAppService:
    """Get WhatsApp service from organization settings (with decrypted token)."""
    account_service = WhatsAppAccountService(db_session)
    config = await account_service.get_account_config(organization_id)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="WhatsApp não configurado para esta organização.",
        )

    return WhatsAppService(
        phone_number_id=config.phone_number_id,
        access_token=config.access_token,  # Already decrypted by WhatsAppAccountService
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
