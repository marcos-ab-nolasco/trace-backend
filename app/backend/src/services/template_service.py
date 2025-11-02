"""Service layer for briefing template management."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import and_, case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models.architect import Architect
from src.db.models.briefing_template import BriefingTemplate
from src.db.models.project_type import ProjectType
from src.db.models.template_version import TemplateVersion
from src.schemas.template import BriefingTemplateCreate, BriefingTemplateUpdate

logger = logging.getLogger(__name__)


class TemplateService:
    """Service for managing briefing templates."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def _get_architect(self, architect_id: UUID) -> Architect:
        result = await self.db_session.execute(
            select(Architect).where(Architect.id == architect_id)
        )
        architect = result.scalar_one_or_none()
        if not architect:
            raise ValueError("Architect not found")
        return architect

    async def _get_project_type(self, slug: str) -> ProjectType | None:
        result = await self.db_session.execute(
            select(ProjectType).where(
                ProjectType.slug == slug.lower(), ProjectType.is_active == True  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def list_templates(
        self,
        architect_id: UUID,
        project_type_slug: str | None = None,
    ) -> list[BriefingTemplate]:
        """List templates accessible to an architect (global + organization-owned)."""

        architect = await self._get_architect(architect_id)

        filters = [
            or_(
                BriefingTemplate.is_global == True,  # noqa: E712
                BriefingTemplate.organization_id == architect.organization_id,
            )
        ]

        if project_type_slug:
            project_type = await self._get_project_type(project_type_slug)
            if project_type:
                filters.append(BriefingTemplate.project_type_id == project_type.id)
            else:
                logger.warning(
                    "Project type slug %s not found; returning all templates",
                    project_type_slug,
                )

        query = (
            select(BriefingTemplate)
            .options(
                selectinload(BriefingTemplate.current_version),
                selectinload(BriefingTemplate.project_type),
            )
            .where(and_(*filters))
            .order_by(
                BriefingTemplate.is_global.asc(),
                BriefingTemplate.name,
            )
        )

        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_template_by_id(
        self,
        template_id: UUID,
        architect_id: UUID,
    ) -> BriefingTemplate | None:
        """Return template if architect has access."""

        architect = await self._get_architect(architect_id)

        query = (
            select(BriefingTemplate)
            .options(
                selectinload(BriefingTemplate.current_version),
                selectinload(BriefingTemplate.project_type),
            )
            .where(
                and_(
                    BriefingTemplate.id == template_id,
                    or_(
                        BriefingTemplate.is_global == True,  # noqa: E712
                        BriefingTemplate.organization_id == architect.organization_id,
                    ),
                )
            )
        )

        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def create_template(
        self,
        architect_id: UUID,
        template_data: BriefingTemplateCreate,
    ) -> BriefingTemplate:
        """Create a new organization-level template."""

        architect = await self._get_architect(architect_id)
        project_type = await self._get_project_type(template_data.project_type_slug)
        if not project_type:
            raise ValueError(f"Unknown project type: {template_data.project_type_slug}")

        template = BriefingTemplate(
            name=template_data.name,
            category=template_data.project_type_slug,
            description=template_data.description,
            is_global=False,
            organization_id=architect.organization_id,
            created_by_architect_id=architect.id,
            project_type_id=project_type.id,
        )
        self.db_session.add(template)
        await self.db_session.flush()

        version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            questions=[q.model_dump() for q in template_data.initial_version.questions],
            change_description=template_data.initial_version.change_description,
            is_active=True,
        )
        self.db_session.add(version)
        await self.db_session.flush()

        template.current_version_id = version.id
        await self.db_session.commit()

        await self.db_session.refresh(template)
        await self.db_session.refresh(template, ["current_version"])

        return template

    async def update_template(
        self,
        template_id: UUID,
        architect_id: UUID,
        update_data: BriefingTemplateUpdate,
    ) -> BriefingTemplate:
        """Create a new version for an organization-owned template."""

        architect = await self._get_architect(architect_id)

        template_result = await self.db_session.execute(
            select(BriefingTemplate)
            .options(selectinload(BriefingTemplate.current_version))
            .where(BriefingTemplate.id == template_id)
        )
        template = template_result.scalar_one_or_none()

        if not template:
            raise ValueError("Template not found")

        if template.is_global or template.organization_id != architect.organization_id:
            raise PermissionError("Cannot update this template")

        if update_data.name is not None:
            template.name = update_data.name
        if update_data.description is not None:
            template.description = update_data.description
        if update_data.project_type_slug is not None:
            project_type = await self._get_project_type(update_data.project_type_slug)
            if not project_type:
                raise ValueError(f"Unknown project type: {update_data.project_type_slug}")
            template.project_type_id = project_type.id
            template.category = update_data.project_type_slug

        if update_data.questions is not None:
            version_result = await self.db_session.execute(
                select(TemplateVersion.version_number)
                .where(TemplateVersion.template_id == template_id)
                .order_by(TemplateVersion.version_number.desc())
                .limit(1)
            )
            max_version = version_result.scalar_one_or_none() or 0

            if template.current_version_id:
                current_version_result = await self.db_session.execute(
                    select(TemplateVersion).where(TemplateVersion.id == template.current_version_id)
                )
                current_version = current_version_result.scalar_one_or_none()
                if current_version:
                    current_version.is_active = False

            new_version = TemplateVersion(
                template_id=template.id,
                version_number=max_version + 1,
                questions=[q.model_dump() for q in update_data.questions],
                change_description=update_data.change_description,
                is_active=True,
            )
            self.db_session.add(new_version)
            await self.db_session.flush()
            template.current_version_id = new_version.id

        await self.db_session.commit()
        await self.db_session.refresh(template)
        await self.db_session.refresh(template, ["current_version"])

        return template

    async def get_template_versions(
        self,
        template_id: UUID,
        architect_id: UUID,
    ) -> list[TemplateVersion]:
        """List template versions if architect can access the template."""

        template = await self.get_template_by_id(template_id, architect_id)
        if not template:
            raise ValueError("Template not found or access denied")

        versions_result = await self.db_session.execute(
            select(TemplateVersion)
            .where(TemplateVersion.template_id == template_id)
            .order_by(TemplateVersion.version_number.desc())
        )
        return list(versions_result.scalars().all())

    async def select_template_version_for_project(
        self,
        architect_id: UUID,
        project_type_slug: str,
    ) -> TemplateVersion:
        """Select the best template version for the given project type."""

        architect = await self._get_architect(architect_id)
        project_type = await self._get_project_type(project_type_slug)

        filters = [
            TemplateVersion.id == BriefingTemplate.current_version_id,
            TemplateVersion.is_active == True,  # noqa: E712
            or_(
                BriefingTemplate.is_global == True,  # noqa: E712
                BriefingTemplate.organization_id == architect.organization_id,
            ),
        ]

        if project_type:
            filters.append(BriefingTemplate.project_type_id == project_type.id)
        else:
            logger.warning(
                "Project type slug %s not found; falling back to any accessible template",
                project_type_slug,
            )

        query = (
            select(TemplateVersion)
            .join(BriefingTemplate, TemplateVersion.template_id == BriefingTemplate.id)
            .options(
                selectinload(TemplateVersion.template).selectinload(BriefingTemplate.project_type)
            )
            .where(and_(*filters))
            .order_by(
                case(
                    (BriefingTemplate.organization_id == architect.organization_id, 0),
                    else_=1,
                ),
                TemplateVersion.created_at.desc(),
            )
            .limit(1)
        )

        result = await self.db_session.execute(query)
        version = result.scalar_one_or_none()

        if version:
            return version

        fallback_query = (
            select(TemplateVersion)
            .join(BriefingTemplate, TemplateVersion.template_id == BriefingTemplate.id)
            .options(
                selectinload(TemplateVersion.template).selectinload(BriefingTemplate.project_type)
            )
            .where(
                TemplateVersion.id == BriefingTemplate.current_version_id,
                TemplateVersion.is_active == True,  # noqa: E712
                BriefingTemplate.is_global == True,  # noqa: E712
            )
            .order_by(TemplateVersion.created_at.desc())
            .limit(1)
        )
        fallback_result = await self.db_session.execute(fallback_query)
        fallback_version = fallback_result.scalar_one_or_none()

        if fallback_version:
            return fallback_version

        raise ValueError("No template version available for the requested project type")
