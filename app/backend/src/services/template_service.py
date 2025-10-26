"""Service layer for briefing template management."""

from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models.architect import Architect
from src.db.models.briefing_template import BriefingTemplate
from src.db.models.template_version import TemplateVersion
from src.schemas.template import (
    BriefingTemplateCreate,
    BriefingTemplateUpdate,
    QuestionSchema,
)


class TemplateService:
    """Service for managing briefing templates."""

    def __init__(self, db_session: AsyncSession):
        """Initialize service with database session."""
        self.db_session = db_session

    async def list_templates(
        self,
        user_id: UUID,
        category: str | None = None,
    ) -> list[BriefingTemplate]:
        """
        List templates accessible to user (global + user's custom templates).

        Args:
            user_id: User ID to get templates for
            category: Optional category filter

        Returns:
            List of templates with current versions loaded
        """
        # Get architect for user
        architect_result = await self.db_session.execute(
            select(Architect).where(Architect.user_id == user_id)
        )
        architect = architect_result.scalar_one_or_none()

        # Build query: global templates OR templates owned by architect
        query = (
            select(BriefingTemplate)
            .options(selectinload(BriefingTemplate.current_version))
            .where(
                or_(
                    BriefingTemplate.is_global == True,  # noqa: E712
                    BriefingTemplate.architect_id == (architect.id if architect else None),
                )
            )
        )

        # Add category filter if provided
        if category:
            query = query.where(BriefingTemplate.category == category)

        # Order by: global first, then custom, then by name
        query = query.order_by(BriefingTemplate.is_global.desc(), BriefingTemplate.name)

        result = await self.db_session.execute(query)
        templates = result.scalars().all()

        return list(templates)

    async def get_template_by_id(
        self,
        template_id: UUID,
        user_id: UUID,
    ) -> BriefingTemplate | None:
        """
        Get template by ID if user has access to it.

        Args:
            template_id: Template ID
            user_id: User ID requesting the template

        Returns:
            Template if found and accessible, None otherwise
        """
        # Get architect for user
        architect_result = await self.db_session.execute(
            select(Architect).where(Architect.user_id == user_id)
        )
        architect = architect_result.scalar_one_or_none()

        # Query template with access check
        query = (
            select(BriefingTemplate)
            .options(selectinload(BriefingTemplate.current_version))
            .where(
                and_(
                    BriefingTemplate.id == template_id,
                    or_(
                        BriefingTemplate.is_global == True,  # noqa: E712
                        BriefingTemplate.architect_id == (architect.id if architect else None),
                    ),
                )
            )
        )

        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def create_template(
        self,
        user_id: UUID,
        template_data: BriefingTemplateCreate,
    ) -> BriefingTemplate:
        """
        Create a new custom template for architect.

        Args:
            user_id: User ID creating the template
            template_data: Template creation data

        Returns:
            Created template with initial version

        Raises:
            ValueError: If user is not an architect
        """
        # Get architect for user
        architect_result = await self.db_session.execute(
            select(Architect).where(Architect.user_id == user_id)
        )
        architect = architect_result.scalar_one_or_none()

        if not architect:
            raise ValueError("User is not an architect")

        # Create template
        template = BriefingTemplate(
            name=template_data.name,
            category=template_data.category,
            description=template_data.description,
            is_global=False,
            architect_id=architect.id,
        )
        self.db_session.add(template)
        await self.db_session.flush()

        # Create initial version
        version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            questions=[q.model_dump() for q in template_data.initial_version.questions],
            change_description=template_data.initial_version.change_description,
            is_active=True,
        )
        self.db_session.add(version)
        await self.db_session.flush()

        # Set current version
        template.current_version_id = version.id
        await self.db_session.commit()

        # Refresh to load all attributes and relationships
        await self.db_session.refresh(template)
        await self.db_session.refresh(template, ["current_version"])

        return template

    async def update_template(
        self,
        template_id: UUID,
        user_id: UUID,
        update_data: BriefingTemplateUpdate,
    ) -> BriefingTemplate:
        """
        Update template by creating a new version.

        Args:
            template_id: Template ID to update
            user_id: User ID performing the update
            update_data: Update data

        Returns:
            Updated template with new version

        Raises:
            ValueError: If template not found or user lacks permission
        """
        # Get architect for user
        architect_result = await self.db_session.execute(
            select(Architect).where(Architect.user_id == user_id)
        )
        architect = architect_result.scalar_one_or_none()

        if not architect:
            raise ValueError("User is not an architect")

        # Get template
        template_result = await self.db_session.execute(
            select(BriefingTemplate)
            .options(selectinload(BriefingTemplate.current_version))
            .where(BriefingTemplate.id == template_id)
        )
        template = template_result.scalar_one_or_none()

        if not template:
            raise ValueError("Template not found")

        # Check permissions: must own template (not global)
        if template.is_global or template.architect_id != architect.id:
            raise PermissionError("Cannot update this template")

        # Update basic fields if provided
        if update_data.name is not None:
            template.name = update_data.name
        if update_data.description is not None:
            template.description = update_data.description

        # Create new version if questions are provided
        if update_data.questions is not None:
            # Get current max version number
            version_result = await self.db_session.execute(
                select(TemplateVersion.version_number)
                .where(TemplateVersion.template_id == template_id)
                .order_by(TemplateVersion.version_number.desc())
                .limit(1)
            )
            max_version = version_result.scalar_one_or_none() or 0

            # Deactivate current version
            if template.current_version_id:
                current_version_result = await self.db_session.execute(
                    select(TemplateVersion).where(TemplateVersion.id == template.current_version_id)
                )
                current_version = current_version_result.scalar_one_or_none()
                if current_version:
                    current_version.is_active = False

            # Create new version
            new_version = TemplateVersion(
                template_id=template.id,
                version_number=max_version + 1,
                questions=[q.model_dump() for q in update_data.questions],
                change_description=update_data.change_description,
                is_active=True,
            )
            self.db_session.add(new_version)
            await self.db_session.flush()

            # Update current version
            template.current_version_id = new_version.id

        await self.db_session.commit()

        # Refresh to load all attributes and relationships
        await self.db_session.refresh(template)
        await self.db_session.refresh(template, ["current_version"])

        return template

    async def get_template_versions(
        self,
        template_id: UUID,
        user_id: UUID,
    ) -> list[TemplateVersion]:
        """
        Get version history of a template.

        Args:
            template_id: Template ID
            user_id: User ID requesting versions

        Returns:
            List of versions ordered by version_number descending

        Raises:
            ValueError: If template not found or user lacks access
        """
        # First check if user has access to template
        template = await self.get_template_by_id(template_id, user_id)
        if not template:
            raise ValueError("Template not found or access denied")

        # Get all versions
        versions_result = await self.db_session.execute(
            select(TemplateVersion)
            .where(TemplateVersion.template_id == template_id)
            .order_by(TemplateVersion.version_number.desc())
        )
        versions = versions_result.scalars().all()

        return list(versions)
