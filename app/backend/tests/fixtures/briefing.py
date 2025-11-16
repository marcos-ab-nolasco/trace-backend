"""Briefing and session-related test fixtures."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.briefing import Briefing
from src.db.models.briefing_template import BriefingTemplate
from src.db.models.end_client import EndClient
from src.db.models.information_requirement import InformationRequirement
from src.db.models.project_type import ProjectType
from src.db.models.template_version import TemplateVersion
from src.db.models.whatsapp_session import WhatsAppSession


@pytest.fixture
async def template_version_simple(
    db_session: AsyncSession, test_project_type: ProjectType
) -> TemplateVersion:
    """Create simple template version with information requirements for testing."""
    template = BriefingTemplate(
        name="Test Template Progression",
        project_type_id=test_project_type.id,
        is_global=True,
    )
    db_session.add(template)
    await db_session.flush()

    version = TemplateVersion(
        template_id=template.id,
        version_number=1,
        is_active=True,
        is_current=True,
    )
    db_session.add(version)
    await db_session.flush()

    # Create information requirements
    requirements = [
        InformationRequirement(
            template_id=version.id,
            field_name="property_type",
            field_type="text",
            required=True,
            priority=10,
            description="Type of property",
            suggested_questions=["Qual é o tipo de imóvel?"],
        ),
        InformationRequirement(
            template_id=version.id,
            field_name="budget",
            field_type="number",
            required=True,
            priority=9,
            description="Available budget",
            suggested_questions=["Qual é o orçamento disponível?"],
        ),
        InformationRequirement(
            template_id=version.id,
            field_name="timeline",
            field_type="text",
            required=False,
            priority=5,
            description="Desired timeline",
            suggested_questions=["Qual é o prazo desejado?"],
        ),
    ]
    for req in requirements:
        db_session.add(req)

    await db_session.commit()
    await db_session.refresh(version)
    return version


@pytest.fixture
async def template_with_conditions(
    db_session: AsyncSession, test_project_type: ProjectType
) -> TemplateVersion:
    """Create template version with requirements (conditions handled by AI now)."""
    template = BriefingTemplate(
        name="Test Template with Conditions",
        project_type_id=test_project_type.id,
        is_global=True,
    )
    db_session.add(template)
    await db_session.flush()

    version = TemplateVersion(
        template_id=template.id,
        version_number=1,
        is_active=True,
        is_current=True,
    )
    db_session.add(version)
    await db_session.flush()

    # Create information requirements
    requirements = [
        InformationRequirement(
            template_id=version.id,
            field_name="property_category",
            field_type="text",
            required=True,
            priority=10,
            description="Property category (residential or commercial)",
            suggested_questions=["É residencial ou comercial?"],
        ),
        InformationRequirement(
            template_id=version.id,
            field_name="rooms",
            field_type="number",
            required=False,
            priority=8,
            description="Number of rooms (for residential)",
            suggested_questions=["Quantos quartos?"],
        ),
        InformationRequirement(
            template_id=version.id,
            field_name="commercial_area",
            field_type="number",
            required=False,
            priority=8,
            description="Commercial area in square meters",
            suggested_questions=["Qual a metragem comercial?"],
        ),
    ]
    for req in requirements:
        db_session.add(req)

    await db_session.commit()
    await db_session.refresh(version)
    return version


@pytest.fixture
async def test_briefing(
    db_session: AsyncSession,
    test_end_client: EndClient,
    template_version_simple: TemplateVersion,
) -> Briefing:
    """Create a test briefing in progress."""
    briefing = Briefing(
        end_client_id=test_end_client.id,
        template_version_id=template_version_simple.id,
        information_state={},
        gathered_information={},
        status="IN_PROGRESS",
    )
    db_session.add(briefing)
    await db_session.commit()
    await db_session.refresh(briefing)
    return briefing


@pytest.fixture
async def test_whatsapp_session(
    db_session: AsyncSession,
    test_end_client: EndClient,
    test_briefing: Briefing,
) -> WhatsAppSession:
    """Create a test WhatsApp session."""
    session = WhatsAppSession(
        end_client_id=test_end_client.id,
        briefing_id=test_briefing.id,
        phone_number=test_end_client.phone,
        status="ACTIVE",
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    return session


@pytest.fixture
async def briefing_with_session(
    db_session: AsyncSession,
    test_end_client,
    template_version_simple,
):
    """Create briefing with associated WhatsApp session for progression tests."""
    from tests.factories import BriefingFactory, WhatsAppSessionFactory

    briefing = await BriefingFactory.create_async(
        end_client=test_end_client,
        template_version=template_version_simple,
        information_state={},
        gathered_information={},
        status="IN_PROGRESS",
    )

    session = await WhatsAppSessionFactory.create_async(
        end_client=test_end_client,
        briefing=briefing,
        phone_number=test_end_client.phone,
        active=True,
    )

    return briefing, session
