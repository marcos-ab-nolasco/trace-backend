"""Template and project type related test fixtures."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.briefing_template import BriefingTemplate
from src.db.models.project_type import ProjectType
from src.db.models.template_version import TemplateVersion


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
    template = BriefingTemplate(
        name="Template Residencial",
        project_type_id=test_project_type.id,
        is_global=True,
        description="Template para projetos residenciais",
    )
    db_session.add(template)
    await db_session.flush()

    version = TemplateVersion(
        template_id=template.id,
        version_number=1,
        questions=[
            {"order": 1, "question": "Qual tipo de imóvel?", "type": "text", "required": True},
            {"order": 2, "question": "Quantos quartos?", "type": "text", "required": True},
            {"order": 3, "question": "Possui terreno?", "type": "text", "required": True},
        ],
        is_active=True,
    )
    db_session.add(version)
    await db_session.flush()

    template.current_version_id = version.id
    await db_session.commit()
    await db_session.refresh(template)
    return template
