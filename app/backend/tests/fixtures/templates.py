"""Template and project type related test fixtures."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.briefing_template import BriefingTemplate
from src.db.models.project_type import ProjectType


@pytest.fixture
async def test_project_type(db_session: AsyncSession) -> ProjectType:
    """Create a default test project type (residencial)."""
    project_type = ProjectType(
        slug="residencial",
        label="Residencial",
        description="Projetos residenciais",
        is_active=True,
    )
    db_session.add(project_type)
    await db_session.commit()
    await db_session.refresh(project_type)
    return project_type


@pytest.fixture
async def project_type_residencial(db_session: AsyncSession) -> ProjectType:
    """Create a 'residencial' project type."""
    project_type = ProjectType(
        slug="residencial",
        label="Residencial",
        description="Projetos residenciais (casas, apartamentos)",
        is_active=True,
    )
    db_session.add(project_type)
    await db_session.commit()
    await db_session.refresh(project_type)
    return project_type


@pytest.fixture
async def project_type_reforma(db_session: AsyncSession) -> ProjectType:
    """Create a 'reforma' project type."""
    project_type = ProjectType(
        slug="reforma",
        label="Reforma",
        description="Reformas e renovações",
        is_active=True,
    )
    db_session.add(project_type)
    await db_session.commit()
    await db_session.refresh(project_type)
    return project_type


@pytest.fixture
async def project_type_comercial(db_session: AsyncSession) -> ProjectType:
    """Create a 'comercial' project type."""
    project_type = ProjectType(
        slug="comercial",
        label="Comercial",
        description="Projetos comerciais",
        is_active=True,
    )
    db_session.add(project_type)
    await db_session.commit()
    await db_session.refresh(project_type)
    return project_type


@pytest.fixture
async def test_template(
    db_session: AsyncSession, test_project_type: ProjectType
) -> BriefingTemplate:
    """Create test briefing template with 3 questions."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from tests.factories import BriefingTemplateFactory

    template = await BriefingTemplateFactory.create_with_version_async(
        name="Template Residencial",
        project_type=test_project_type,
        is_global=True,
        description="Template para projetos residenciais",
        version_kwargs={
            "questions": [
                {"order": 1, "question": "Qual tipo de imóvel?", "type": "text", "required": True},
                {"order": 2, "question": "Quantos quartos?", "type": "text", "required": True},
                {"order": 3, "question": "Possui terreno?", "type": "text", "required": True},
            ]
        },
    )

    # Eager load current_version to avoid lazy loading issues
    stmt = (
        select(BriefingTemplate)
        .where(BriefingTemplate.id == template.id)
        .options(selectinload(BriefingTemplate.current_version))
    )
    result = await db_session.execute(stmt)
    template = result.scalar_one()

    return template
