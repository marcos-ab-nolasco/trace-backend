"""API endpoints for briefing management.

NOTE: This file has been simplified during Phase 2 refactoring.
Endpoints that depended on the old question-based system have been removed.
TODO: Reimplement missing endpoints using the new conversation-based system.
"""

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.dependencies import get_current_architect
from src.db.models.architect import Architect
from src.db.models.briefing import Briefing, BriefingStatus
from src.db.models.end_client import EndClient
from src.db.models.template_version import TemplateVersion
from src.db.session import get_db_session
from src.schemas.briefing import (
    BriefingDetailRead,
    BriefingListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/briefings", tags=["briefings"])


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

    query = (
        select(Briefing)
        .join(EndClient, Briefing.end_client_id == EndClient.id)
        .where(EndClient.organization_id == current_architect.organization_id)
        .options(
            selectinload(Briefing.end_client),
            selectinload(Briefing.template_version).selectinload(TemplateVersion.requirements),
        )
    )

    if status_filter:
        query = query.where(Briefing.status == status_filter)

    if end_client_id:
        query = query.where(Briefing.end_client_id == end_client_id)

    if template_id:
        query = query.join(Briefing.template_version).where(
            Briefing.template_version.has(template_id=template_id)
        )

    if created_after:
        query = query.where(Briefing.created_at >= created_after)

    if created_before:
        query = query.where(Briefing.created_at <= created_before)

    # Get total count for pagination
    from sqlalchemy import func

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db_session.execute(count_query)
    total = total_result.scalar_one()

    # Apply pagination
    query = query.order_by(Briefing.created_at.desc()).limit(limit).offset(offset)

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

    Returns full briefing details including:
    - Client information
    - Template version used
    - Information gathering state
    - Gathered information
    - Conversation messages
    - Timestamps
    """
    logger.info(
        f"Retrieving briefing {briefing_id}",
        extra={"briefing_id": str(briefing_id)},
    )

    query = (
        select(Briefing)
        .join(EndClient, Briefing.end_client_id == EndClient.id)
        .where(
            Briefing.id == briefing_id,
            EndClient.organization_id == current_architect.organization_id,
        )
        .options(
            selectinload(Briefing.end_client),
            selectinload(Briefing.template_version).selectinload(TemplateVersion.requirements),
            selectinload(Briefing.conversation_messages),
        )
    )

    result = await db_session.execute(query)
    briefing = result.scalar_one_or_none()

    if not briefing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Briefing not found",
        )

    return BriefingDetailRead.model_validate(briefing)


@router.post("/{briefing_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_briefing(
    briefing_id: UUID,
    current_architect: Architect = Depends(get_current_architect),
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Cancel a briefing.

    This endpoint allows cancelling a briefing.
    The briefing status will be set to CANCELLED.

    This operation is idempotent - cancelling an already cancelled briefing
    will succeed.
    """
    logger.info(
        f"Cancelling briefing {briefing_id}",
        extra={"briefing_id": str(briefing_id)},
    )

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

    if briefing.status == BriefingStatus.CANCELLED:
        logger.info(f"Briefing {briefing_id} already cancelled")
        return {
            "success": True,
            "message": "Briefing already cancelled",
            "briefing_id": str(briefing_id),
        }

    if briefing.status == BriefingStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel a completed briefing",
        )

    briefing.status = BriefingStatus.CANCELLED
    await db_session.commit()

    logger.info(f"Briefing {briefing_id} cancelled successfully")

    return {
        "success": True,
        "message": "Briefing cancelled successfully",
        "briefing_id": str(briefing_id),
    }
