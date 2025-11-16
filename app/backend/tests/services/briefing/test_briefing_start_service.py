"""Tests for BriefingStartService."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.architect import Architect
from src.db.models.briefing import BriefingStatus
from src.db.models.end_client import EndClient
from src.db.models.organization import Organization
from src.db.models.template_version import TemplateVersion
from src.services.briefing.briefing_start_service import (
    BriefingStartService,
)
from tests.factories import (
    BriefingFactory,
    BriefingTemplateFactory,
)


@pytest.fixture
async def test_template_version(db_session: AsyncSession, test_project_type):
    """Create test template with version."""
    template = await BriefingTemplateFactory.create_with_version_async(
        name="Test Template",
        description="Test template for briefings",
        is_global=True,
        project_type=test_project_type,
        version_kwargs={
            "questions": [
                {"order": 1, "question": "Question 1?", "type": "text", "required": True},
                {"order": 2, "question": "Question 2?", "type": "text", "required": False},
            ]
        },
    )
    return template.current_version


@pytest.mark.asyncio
async def test_start_briefing_creates_briefing(
    db_session: AsyncSession,
    test_organization: Organization,
    test_architect: Architect,
    test_end_client: EndClient,
    test_template_version: TemplateVersion,
):
    """Test that start_briefing creates a new briefing."""
    service = BriefingStartService(db_session)

    briefing = await service.start_briefing(
        organization_id=test_organization.id,
        architect_id=test_architect.id,
        client_name="João Silva",
        client_phone="+5511999888777",
        template_version_id=test_template_version.id,
    )

    assert briefing.id is not None
    assert briefing.status == BriefingStatus.IN_PROGRESS
    assert briefing.template_version_id == test_template_version.id
    assert briefing.current_question_order == 1
    assert briefing.answers == {}


@pytest.mark.asyncio
async def test_start_briefing_creates_or_updates_client(
    db_session: AsyncSession,
    test_organization: Organization,
    test_architect: Architect,
    test_template_version: TemplateVersion,
):
    """Test that start_briefing creates client if not exists."""
    service = BriefingStartService(db_session)

    briefing = await service.start_briefing(
        organization_id=test_organization.id,
        architect_id=test_architect.id,
        client_name="Maria Santos",
        client_phone="+5511888777666",
        template_version_id=test_template_version.id,
    )

    result = await db_session.execute(
        select(EndClient).where(EndClient.id == briefing.end_client_id)
    )
    client = result.scalar_one()

    assert client is not None
    assert client.name == "Maria Santos"
    assert client.phone == "+5511888777666"
    assert client.organization_id == test_organization.id


@pytest.mark.asyncio
async def test_start_briefing_updates_existing_client(
    db_session: AsyncSession,
    test_organization: Organization,
    test_architect: Architect,
    test_end_client: EndClient,
    test_template_version: TemplateVersion,
):
    """Test that start_briefing updates existing client name."""
    service = BriefingStartService(db_session)

    old_name = test_end_client.name
    original_phone = test_end_client.phone

    briefing = await service.start_briefing(
        organization_id=test_organization.id,
        architect_id=test_architect.id,
        client_name="Updated Name",
        client_phone=original_phone,
        template_version_id=test_template_version.id,
    )

    assert briefing.end_client_id == test_end_client.id
    await db_session.refresh(test_end_client)
    assert test_end_client.name == "Updated Name"
    assert test_end_client.name != old_name


@pytest.mark.asyncio
async def test_start_briefing_resumes_if_active_briefing_exists(
    db_session: AsyncSession,
    test_organization,
    test_architect,
    test_end_client,
    test_template_version,
):
    """Test that starting briefing returns existing one if client has active briefing."""
    existing_briefing = await BriefingFactory.create_async(
        end_client=test_end_client,
        template_version=test_template_version,
        status=BriefingStatus.IN_PROGRESS,
        current_question_order=2,
        answers={"question_1": "answer_1"},
    )
    existing_id = existing_briefing.id

    service = BriefingStartService(db_session)

    briefing = await service.start_briefing(
        organization_id=test_organization.id,
        architect_id=test_architect.id,
        client_name=test_end_client.name,
        client_phone=test_end_client.phone,
        template_version_id=test_template_version.id,
    )

    assert briefing.id == existing_id
    assert briefing.current_question_order == 2
    assert briefing.answers == {"question_1": "answer_1"}


@pytest.mark.asyncio
async def test_start_briefing_allows_if_previous_completed(
    db_session: AsyncSession,
    test_organization,
    test_architect,
    test_end_client,
    test_template_version,
):
    """Test that starting briefing is allowed if previous briefing is completed."""
    completed_briefing = await BriefingFactory.create_async(
        end_client=test_end_client,
        template_version=test_template_version,
        status=BriefingStatus.COMPLETED,
        current_question_order=2,
        answers={"1": "Answer 1"},
    )

    service = BriefingStartService(db_session)

    briefing = await service.start_briefing(
        organization_id=test_organization.id,
        architect_id=test_architect.id,
        client_name=test_end_client.name,
        client_phone=test_end_client.phone,
        template_version_id=test_template_version.id,
    )

    assert briefing.id is not None
    assert briefing.status == BriefingStatus.IN_PROGRESS
    assert briefing.id != completed_briefing.id


@pytest.mark.asyncio
async def test_start_briefing_allows_if_previous_cancelled(
    db_session: AsyncSession,
    test_organization,
    test_architect,
    test_end_client,
    test_template_version,
):
    """Test that starting briefing is allowed if previous briefing is cancelled."""
    cancelled_briefing = await BriefingFactory.create_async(
        end_client=test_end_client,
        template_version=test_template_version,
        status=BriefingStatus.CANCELLED,
        current_question_order=1,
        answers={},
    )

    service = BriefingStartService(db_session)

    briefing = await service.start_briefing(
        organization_id=test_organization.id,
        architect_id=test_architect.id,
        client_name=test_end_client.name,
        client_phone=test_end_client.phone,
        template_version_id=test_template_version.id,
    )

    assert briefing.id is not None
    assert briefing.status == BriefingStatus.IN_PROGRESS
    assert briefing.id != cancelled_briefing.id
