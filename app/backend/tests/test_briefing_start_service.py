"""Tests for BriefingStartService."""

import asyncio
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from src.db.models.architect import Architect
from src.db.models.briefing import Briefing, BriefingStatus
from src.db.models.briefing_template import BriefingTemplate
from src.db.models.end_client import EndClient
from src.db.models.organization import Organization
from src.db.models.template_version import TemplateVersion
from src.services.briefing.briefing_start_service import (
    BriefingStartService,
    ClientHasActiveBriefingError,
)


@pytest.fixture
async def test_template_version(db_session: AsyncSession) -> TemplateVersion:
    """Create test template with version."""
    template = BriefingTemplate(
        name="Test Template",
        description="Test template for briefings",
        is_global=True,
    )
    db_session.add(template)
    await db_session.flush()

    version = TemplateVersion(
        template_id=template.id,
        version_number=1,
        questions=[
            {"order": 1, "question": "Question 1?", "type": "text", "required": True},
            {"order": 2, "question": "Question 2?", "type": "text", "required": False},
        ],
        is_active=True,
    )
    db_session.add(version)
    await db_session.flush()

    template.current_version_id = version.id
    await db_session.commit()
    await db_session.refresh(version)
    return version


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
    from sqlalchemy import select

    from src.db.models.end_client import EndClient

    service = BriefingStartService(db_session)

    # Start briefing with new client
    briefing = await service.start_briefing(
        organization_id=test_organization.id,
        architect_id=test_architect.id,
        client_name="Maria Santos",
        client_phone="+5511888777666",
        template_version_id=test_template_version.id,
    )

    # Load the client separately to avoid MissingGreenlet error
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

    # Start briefing with same phone but different name
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
async def test_start_briefing_blocks_if_active_briefing_exists(
    db_session: AsyncSession,
    test_organization: Organization,
    test_architect: Architect,
    test_end_client: EndClient,
    test_template_version: TemplateVersion,
):
    """Test that starting briefing fails if client has active briefing."""
    # Create an active briefing
    existing_briefing = Briefing(
        end_client_id=test_end_client.id,
        template_version_id=test_template_version.id,
        status=BriefingStatus.IN_PROGRESS,
        current_question_order=0,
        answers={},
    )
    db_session.add(existing_briefing)
    await db_session.commit()

    service = BriefingStartService(db_session)

    # Try to start another briefing for same client
    with pytest.raises(ClientHasActiveBriefingError) as exc_info:
        await service.start_briefing(
            organization_id=test_organization.id,
            architect_id=test_architect.id,
            client_name=test_end_client.name,
            client_phone=test_end_client.phone,
            template_version_id=test_template_version.id,
        )

    assert "already has an active briefing" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_start_briefing_allows_if_previous_completed(
    db_session: AsyncSession,
    test_organization: Organization,
    test_architect: Architect,
    test_end_client: EndClient,
    test_template_version: TemplateVersion,
):
    """Test that starting briefing is allowed if previous briefing is completed."""
    # Create a completed briefing
    completed_briefing = Briefing(
        end_client_id=test_end_client.id,
        template_version_id=test_template_version.id,
        status=BriefingStatus.COMPLETED,
        current_question_order=2,
        answers={"1": "Answer 1"},
    )
    db_session.add(completed_briefing)
    await db_session.commit()

    service = BriefingStartService(db_session)

    # Should succeed - previous is completed
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
    test_organization: Organization,
    test_architect: Architect,
    test_end_client: EndClient,
    test_template_version: TemplateVersion,
):
    """Test that starting briefing is allowed if previous briefing is cancelled."""
    # Create a cancelled briefing
    cancelled_briefing = Briefing(
        end_client_id=test_end_client.id,
        template_version_id=test_template_version.id,
        status=BriefingStatus.CANCELLED,
        current_question_order=1,
        answers={},
    )
    db_session.add(cancelled_briefing)
    await db_session.commit()

    service = BriefingStartService(db_session)

    # Should succeed - previous is cancelled
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


@pytest.mark.asyncio
async def test_concurrent_briefing_creation_race_condition(
    db_session: AsyncSession,
    test_end_client: EndClient,
    test_template_version: TemplateVersion,
):
    """Test race condition protection: database constraint prevents duplicate IN_PROGRESS briefings.

    Tests Issue #3 fix: partial unique index ensures only one IN_PROGRESS briefing per client.
    Simulates race condition by attempting to create two IN_PROGRESS briefings for same client.

    Expected behavior after fix:
    - First briefing creation succeeds
    - Second briefing creation fails with IntegrityError due to constraint violation
    """
    # Store IDs before any operations
    client_id = test_end_client.id
    template_id = test_template_version.id

    # Create first briefing
    briefing1 = Briefing(
        end_client_id=client_id,
        template_version_id=template_id,
        status=BriefingStatus.IN_PROGRESS,
        current_question_order=1,
        answers={},
    )
    db_session.add(briefing1)
    await db_session.commit()

    # Try to create second IN_PROGRESS briefing for same client - should fail
    briefing2 = Briefing(
        end_client_id=client_id,
        template_version_id=template_id,
        status=BriefingStatus.IN_PROGRESS,
        current_question_order=1,
        answers={},
    )
    db_session.add(briefing2)

    # This should raise IntegrityError due to unique constraint
    try:
        await db_session.commit()
        # If we reach here, constraint is not working - fail test explicitly
        assert False, "Expected IntegrityError but commit succeeded"
    except IntegrityError as e:
        # Expected - verify it's the unique constraint violation
        assert "uq_client_active_briefing" in str(e).lower(), f"Expected constraint error, got: {e}"
        await db_session.rollback()

    # Verify only one IN_PROGRESS briefing exists
    from sqlalchemy import select

    result = await db_session.execute(
        select(Briefing).where(
            Briefing.end_client_id == client_id,
            Briefing.status == BriefingStatus.IN_PROGRESS,
        )
    )
    active_briefings = result.scalars().all()
    assert len(active_briefings) == 1, "Only one IN_PROGRESS briefing should exist"

    # Verify COMPLETED briefings are still allowed (constraint is partial)
    await db_session.refresh(briefing1)
    briefing1.status = BriefingStatus.COMPLETED
    await db_session.commit()

    briefing3 = Briefing(
        end_client_id=client_id,
        template_version_id=template_id,
        status=BriefingStatus.IN_PROGRESS,
        current_question_order=1,
        answers={},
    )
    db_session.add(briefing3)
    await db_session.commit()  # Should succeed now

    assert briefing3.id is not None
