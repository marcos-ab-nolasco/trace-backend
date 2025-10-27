"""Tests for BriefingOrchestrator - conversational briefing state machine."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.architect import Architect
from src.db.models.briefing import Briefing, BriefingStatus
from src.db.models.briefing_template import BriefingTemplate
from src.db.models.end_client import EndClient
from src.db.models.organization import Organization
from src.db.models.template_version import TemplateVersion
from src.db.models.architect import Architect
from src.services.briefing.orchestrator import BriefingOrchestrator


# Fixtures
@pytest.fixture
async def test_organization(db_session: AsyncSession) -> Organization:
    """Create test organization."""
    org = Organization(name="Test Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    return org


@pytest.fixture
async def test_architect(db_session: AsyncSession, test_organization: Organization) -> Architect:
    """Create test architect."""
    architect = Architect(
        organization_id=test_organization.id,
        email="architect@test.com",
        hashed_password="hash123",
        phone="+5511999999999",
        is_authorized=True,
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)
    return architect


@pytest.fixture
async def test_end_client(db_session: AsyncSession, test_architect: Architect) -> EndClient:
    """Create test end client."""
    client = EndClient(
        architect_id=test_architect.id,
        name="João Silva",
        phone="+5511987654321",
        email="joao@example.com",
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client


@pytest.fixture
async def test_template_version(db_session: AsyncSession) -> TemplateVersion:
    """Create test template with version."""
    template = BriefingTemplate(
        name="Template Reforma",
        category="reforma",
        description="Template para reformas",
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
                "question": "Qual é o tamanho aproximado em m²?",
                "type": "number",
                "required": True,
            },
            {
                "order": 3,
                "question": "Qual é o orçamento disponível?",
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
def orchestrator(db_session: AsyncSession) -> BriefingOrchestrator:
    """Create orchestrator instance."""
    return BriefingOrchestrator(db_session=db_session)


# Start Briefing Tests
@pytest.mark.asyncio
async def test_start_briefing(
    orchestrator: BriefingOrchestrator,
    test_end_client: EndClient,
    test_template_version: TemplateVersion,
    db_session: AsyncSession,
):
    """Test starting a new briefing session."""
    briefing = await orchestrator.start_briefing(
        end_client_id=test_end_client.id, template_version_id=test_template_version.id
    )

    assert briefing.id is not None
    assert briefing.end_client_id == test_end_client.id
    assert briefing.template_version_id == test_template_version.id
    assert briefing.status == BriefingStatus.IN_PROGRESS
    assert briefing.current_question_order == 1
    assert briefing.answers == {}


@pytest.mark.asyncio
async def test_start_briefing_invalid_client(
    orchestrator: BriefingOrchestrator, test_template_version: TemplateVersion
):
    """Test starting briefing with non-existent client."""
    from uuid import uuid4

    with pytest.raises(ValueError, match="EndClient not found"):
        await orchestrator.start_briefing(
            end_client_id=uuid4(), template_version_id=test_template_version.id
        )


# Next Question Tests
@pytest.mark.asyncio
async def test_next_question_first(
    orchestrator: BriefingOrchestrator,
    test_end_client: EndClient,
    test_template_version: TemplateVersion,
):
    """Test getting the first question."""
    briefing = await orchestrator.start_briefing(
        end_client_id=test_end_client.id, template_version_id=test_template_version.id
    )

    question = await orchestrator.next_question(briefing_id=briefing.id)

    assert question is not None
    assert question["order"] == 1
    assert question["question"] == "Qual é o tipo de imóvel?"
    assert question["type"] == "text"
    assert question["required"] is True


@pytest.mark.asyncio
async def test_next_question_after_answer(
    orchestrator: BriefingOrchestrator,
    test_end_client: EndClient,
    test_template_version: TemplateVersion,
):
    """Test getting next question after answering current one."""
    briefing = await orchestrator.start_briefing(
        end_client_id=test_end_client.id, template_version_id=test_template_version.id
    )

    # Answer first question
    await orchestrator.process_answer(
        briefing_id=briefing.id, question_order=1, answer="Apartamento"
    )

    # Get next question
    question = await orchestrator.next_question(briefing_id=briefing.id)

    assert question is not None
    assert question["order"] == 2
    assert question["question"] == "Qual é o tamanho aproximado em m²?"


@pytest.mark.asyncio
async def test_next_question_completed_briefing(
    orchestrator: BriefingOrchestrator,
    test_end_client: EndClient,
    test_template_version: TemplateVersion,
):
    """Test that next_question returns None when briefing is complete."""
    briefing = await orchestrator.start_briefing(
        end_client_id=test_end_client.id, template_version_id=test_template_version.id
    )

    # Answer all questions
    await orchestrator.process_answer(
        briefing_id=briefing.id, question_order=1, answer="Apartamento"
    )
    await orchestrator.process_answer(briefing_id=briefing.id, question_order=2, answer="80")
    await orchestrator.process_answer(
        briefing_id=briefing.id, question_order=3, answer="R$ 50.000"
    )

    # Try to get next question
    question = await orchestrator.next_question(briefing_id=briefing.id)

    assert question is None


# Process Answer Tests
@pytest.mark.asyncio
async def test_process_answer_valid(
    orchestrator: BriefingOrchestrator,
    test_end_client: EndClient,
    test_template_version: TemplateVersion,
    db_session: AsyncSession,
):
    """Test processing a valid answer."""
    briefing = await orchestrator.start_briefing(
        end_client_id=test_end_client.id, template_version_id=test_template_version.id
    )

    updated_briefing = await orchestrator.process_answer(
        briefing_id=briefing.id, question_order=1, answer="Apartamento"
    )

    assert updated_briefing.answers == {"1": "Apartamento"}
    assert updated_briefing.current_question_order == 2


@pytest.mark.asyncio
async def test_process_answer_multiple(
    orchestrator: BriefingOrchestrator,
    test_end_client: EndClient,
    test_template_version: TemplateVersion,
):
    """Test processing multiple answers in sequence."""
    briefing = await orchestrator.start_briefing(
        end_client_id=test_end_client.id, template_version_id=test_template_version.id
    )

    # Answer question 1
    await orchestrator.process_answer(
        briefing_id=briefing.id, question_order=1, answer="Apartamento"
    )

    # Answer question 2
    updated_briefing = await orchestrator.process_answer(
        briefing_id=briefing.id, question_order=2, answer="80"
    )

    assert updated_briefing.answers == {"1": "Apartamento", "2": "80"}
    assert updated_briefing.current_question_order == 3


@pytest.mark.asyncio
async def test_process_answer_out_of_order(
    orchestrator: BriefingOrchestrator,
    test_end_client: EndClient,
    test_template_version: TemplateVersion,
):
    """Test that answering out of order raises error."""
    briefing = await orchestrator.start_briefing(
        end_client_id=test_end_client.id, template_version_id=test_template_version.id
    )

    # Try to answer question 2 before question 1
    with pytest.raises(ValueError, match="Must answer current question"):
        await orchestrator.process_answer(
            briefing_id=briefing.id, question_order=2, answer="80"
        )


# Complete Briefing Tests
@pytest.mark.asyncio
async def test_complete_briefing_all_required_answered(
    orchestrator: BriefingOrchestrator,
    test_end_client: EndClient,
    test_template_version: TemplateVersion,
    db_session: AsyncSession,
):
    """Test completing briefing when all required questions are answered."""
    briefing = await orchestrator.start_briefing(
        end_client_id=test_end_client.id, template_version_id=test_template_version.id
    )

    # Answer required questions (1 and 2)
    await orchestrator.process_answer(
        briefing_id=briefing.id, question_order=1, answer="Apartamento"
    )
    await orchestrator.process_answer(briefing_id=briefing.id, question_order=2, answer="80")

    # Complete briefing
    completed_briefing = await orchestrator.complete_briefing(briefing_id=briefing.id)

    assert completed_briefing.status == BriefingStatus.COMPLETED
    assert completed_briefing.completed_at is not None


@pytest.mark.asyncio
async def test_complete_briefing_missing_required(
    orchestrator: BriefingOrchestrator,
    test_end_client: EndClient,
    test_template_version: TemplateVersion,
):
    """Test that completing briefing with missing required questions fails."""
    briefing = await orchestrator.start_briefing(
        end_client_id=test_end_client.id, template_version_id=test_template_version.id
    )

    # Only answer question 1 (question 2 is also required)
    await orchestrator.process_answer(
        briefing_id=briefing.id, question_order=1, answer="Apartamento"
    )

    # Try to complete
    with pytest.raises(ValueError, match="required questions not answered"):
        await orchestrator.complete_briefing(briefing_id=briefing.id)


@pytest.mark.asyncio
async def test_cancel_briefing(
    orchestrator: BriefingOrchestrator,
    test_end_client: EndClient,
    test_template_version: TemplateVersion,
):
    """Test cancelling a briefing."""
    briefing = await orchestrator.start_briefing(
        end_client_id=test_end_client.id, template_version_id=test_template_version.id
    )

    cancelled_briefing = await orchestrator.cancel_briefing(briefing_id=briefing.id)

    assert cancelled_briefing.status == BriefingStatus.CANCELLED


# Get Briefing Status Tests
@pytest.mark.asyncio
async def test_get_briefing_progress(
    orchestrator: BriefingOrchestrator,
    test_end_client: EndClient,
    test_template_version: TemplateVersion,
):
    """Test getting briefing progress."""
    briefing = await orchestrator.start_briefing(
        end_client_id=test_end_client.id, template_version_id=test_template_version.id
    )

    # Answer 1 of 3 questions
    await orchestrator.process_answer(
        briefing_id=briefing.id, question_order=1, answer="Apartamento"
    )

    progress = await orchestrator.get_briefing_progress(briefing_id=briefing.id)

    assert progress["total_questions"] == 3
    assert progress["answered_questions"] == 1
    assert progress["remaining_questions"] == 2
    assert progress["progress_percentage"] == pytest.approx(33.33, rel=0.1)
    assert progress["status"] == BriefingStatus.IN_PROGRESS.value
