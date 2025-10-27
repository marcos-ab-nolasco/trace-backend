"""API endpoints for briefing template management."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.dependencies import get_current_architect_id
from src.db.session import get_db_session
from src.schemas.template import (
    BriefingTemplateCreate,
    BriefingTemplateList,
    BriefingTemplateUpdate,
    BriefingTemplateWithVersion,
    TemplateVersionRead,
)
from src.services.template_service import TemplateService

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("", response_model=BriefingTemplateList)
async def list_templates(
    project_type: str | None = Query(None, description="Filter by project type slug"),
    db_session: AsyncSession = Depends(get_db_session),
    architect_id: UUID = Depends(get_current_architect_id),
) -> BriefingTemplateList:
    """
    List all templates accessible to the current user.

    Returns global templates and user's custom templates.
    """
    service = TemplateService(db_session)
    templates = await service.list_templates(
        architect_id=architect_id, project_type_slug=project_type
    )

    # Convert to response models
    templates_with_versions = [
        BriefingTemplateWithVersion.model_validate(t) for t in templates
    ]

    return BriefingTemplateList(templates=templates_with_versions, total=len(templates))


@router.post("", response_model=BriefingTemplateWithVersion, status_code=status.HTTP_201_CREATED)
async def create_template(
    template_data: BriefingTemplateCreate,
    db_session: AsyncSession = Depends(get_db_session),
    architect_id: UUID = Depends(get_current_architect_id),
) -> BriefingTemplateWithVersion:
    """
    Create a new custom template.

    Only architects can create templates. Templates are created with an initial version.
    """
    service = TemplateService(db_session)

    try:
        template = await service.create_template(
            architect_id=architect_id, template_data=template_data
        )
        return BriefingTemplateWithVersion.model_validate(template)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{template_id}", response_model=BriefingTemplateWithVersion)
async def get_template(
    template_id: UUID,
    db_session: AsyncSession = Depends(get_db_session),
    architect_id: UUID = Depends(get_current_architect_id),
) -> BriefingTemplateWithVersion:
    """
    Get template details by ID.

    Returns 404 if template not found or user doesn't have access.
    """
    service = TemplateService(db_session)
    template = await service.get_template_by_id(
        template_id=template_id, architect_id=architect_id
    )

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
        )

    return BriefingTemplateWithVersion.model_validate(template)


@router.put("/{template_id}", response_model=BriefingTemplateWithVersion)
async def update_template(
    template_id: UUID,
    update_data: BriefingTemplateUpdate,
    db_session: AsyncSession = Depends(get_db_session),
    architect_id: UUID = Depends(get_current_architect_id),
) -> BriefingTemplateWithVersion:
    """
    Update template by creating a new version.

    Only the template owner can update. Global templates cannot be updated by architects.
    """
    service = TemplateService(db_session)

    try:
        template = await service.update_template(
            template_id=template_id, architect_id=architect_id, update_data=update_data
        )
        return BriefingTemplateWithVersion.model_validate(template)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get("/{template_id}/versions", response_model=dict)
async def get_template_versions(
    template_id: UUID,
    db_session: AsyncSession = Depends(get_db_session),
    architect_id: UUID = Depends(get_current_architect_id),
) -> dict:
    """
    Get version history of a template.

    Returns all versions ordered by version number (most recent first).
    """
    service = TemplateService(db_session)

    try:
        versions = await service.get_template_versions(
            template_id=template_id, architect_id=architect_id
        )
        return {
            "versions": [TemplateVersionRead.model_validate(v) for v in versions],
            "total": len(versions),
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
