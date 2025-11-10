"""Briefing and session-related test fixtures."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.briefing import Briefing
from src.db.models.briefing_template import BriefingTemplate
from src.db.models.end_client import EndClient
from src.db.models.project_type import ProjectType
from src.db.models.template_version import TemplateVersion
from src.db.models.whatsapp_session import WhatsAppSession


@pytest.fixture
async def template_version_simple(
    db_session: AsyncSession, test_project_type: ProjectType
) -> TemplateVersion:
    """Create simple template version with sequential questions for testing progression."""
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
        questions=[
            {
                "order": 1,
                "question": "Qual é o tipo de imóvel?",
                "type": "text",
                "required": True,
            },
            {
                "order": 2,
                "question": "Qual é o orçamento disponível?",
                "type": "text",
                "required": True,
            },
            {
                "order": 3,
                "question": "Qual é o prazo desejado?",
                "type": "text",
                "required": False,
            },
        ],
        is_active=True,
    )
    db_session.add(version)
    await db_session.flush()

    template.current_version_id = version.id
    await db_session.commit()
    await db_session.refresh(version)
    return version


@pytest.fixture
async def template_with_conditions(
    db_session: AsyncSession, test_project_type: ProjectType
) -> TemplateVersion:
    """Create template version with conditional questions for testing branching infrastructure."""
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
        questions=[
            {
                "order": 1,
                "question": "É residencial ou comercial?",
                "type": "text",
                "required": True,
            },
            {
                "order": 2,
                "question": "Quantos quartos?",
                "type": "text",
                "required": True,
                "conditions": {
                    "depends_on_order": 1,
                    "answer_contains": "residencial",
                },
            },
            {
                "order": 3,
                "question": "Qual o metragem comercial?",
                "type": "text",
                "required": True,
                "conditions": {
                    "depends_on_order": 1,
                    "answer_contains": "comercial",
                },
            },
        ],
        is_active=True,
    )
    db_session.add(version)
    await db_session.flush()

    template.current_version_id = version.id
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
        current_question_order=1,
        answers={},
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
    test_end_client: EndClient,
    template_version_simple: TemplateVersion,
) -> tuple[Briefing, WhatsAppSession]:
    """Create briefing with associated WhatsApp session for progression tests."""
    briefing = Briefing(
        end_client_id=test_end_client.id,
        template_version_id=template_version_simple.id,
        current_question_order=1,
        answers={},
        status="IN_PROGRESS",
    )
    db_session.add(briefing)
    await db_session.commit()
    await db_session.refresh(briefing)

    session = WhatsAppSession(
        end_client_id=test_end_client.id,
        briefing_id=briefing.id,
        phone_number=test_end_client.phone,
        status="ACTIVE",
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    return briefing, session
