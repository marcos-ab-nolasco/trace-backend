"""Tests for briefing analytics functionality."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.architect import Architect
from src.db.models.briefing import Briefing, BriefingStatus
from src.db.models.briefing_analytics import BriefingAnalytics
from src.db.models.briefing_template import BriefingTemplate
from src.db.models.end_client import EndClient
from src.db.models.organization import Organization
from src.db.models.template_version import TemplateVersion
from src.services.briefing.analytics_service import AnalyticsService


@pytest.fixture
async def test_template(db_session: AsyncSession) -> BriefingTemplate:
    """Create test template."""
    template = BriefingTemplate(
        name="Template Reforma",
        category="reforma",
        description="Template para projetos de reforma",
        is_global=True,
    )
    db_session.add(template)
    await db_session.flush()

    version = TemplateVersion(
        template_id=template.id,
        version_number=1,
        questions=[
            {"order": 1, "question": "Pergunta 1?", "type": "text", "required": True},
            {"order": 2, "question": "Pergunta 2?", "type": "text", "required": True},
            {"order": 3, "question": "Pergunta 3?", "type": "text", "required": False},
        ],
        is_active=True,
    )
    db_session.add(version)
    await db_session.flush()

    template.current_version_id = version.id
    await db_session.commit()
    await db_session.refresh(template)
    return template


@pytest.fixture
async def test_client(
    db_session: AsyncSession, test_organization: Organization, test_architect: Architect
) -> EndClient:
    """Create test end client."""
    client = EndClient(
        organization_id=test_organization.id,
        architect_id=test_architect.id,
        name="João Silva",
        phone="+5511987654321",
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client


@pytest.fixture
async def completed_briefing(
    db_session: AsyncSession, test_client: EndClient, test_template: BriefingTemplate
) -> Briefing:
    """Create a completed briefing."""

    created_time = datetime.now(UTC) - timedelta(hours=2)
    completed_time = datetime.now(UTC)

    briefing = Briefing(
        end_client_id=test_client.id,
        template_version_id=test_template.current_version_id,
        status=BriefingStatus.COMPLETED,
        current_question_order=3,
        answers={
            "1": "Resposta 1",
            "2": "Resposta 2",
        },
        created_at=created_time,
        completed_at=completed_time,
    )
    db_session.add(briefing)
    await db_session.commit()
    await db_session.refresh(briefing)
    return briefing


@pytest.mark.asyncio
async def test_briefing_analytics_model_creation(
    db_session: AsyncSession,
    completed_briefing: Briefing,
):
    """Test creating a BriefingAnalytics record."""
    analytics = BriefingAnalytics(
        briefing_id=completed_briefing.id,
        metrics={
            "duration_seconds": 7200,
            "total_questions": 3,
            "answered_questions": 2,
            "completion_rate": 0.67,
        },
        observations="Cliente respondeu rapidamente às perguntas principais.",
    )

    db_session.add(analytics)
    await db_session.commit()
    await db_session.refresh(analytics)

    assert analytics.id is not None
    assert analytics.briefing_id == completed_briefing.id
    assert analytics.metrics["duration_seconds"] == 7200
    assert analytics.metrics["total_questions"] == 3
    assert analytics.created_at is not None


@pytest.mark.asyncio
async def test_calculate_briefing_metrics(
    db_session: AsyncSession,
    completed_briefing: Briefing,
):
    """Test calculating metrics for a completed briefing."""
    service = AnalyticsService(db_session)
    metrics = await service.calculate_metrics(completed_briefing.id)

    assert "duration_seconds" in metrics
    assert metrics["duration_seconds"] > 0
    assert metrics["total_questions"] == 3
    assert metrics["answered_questions"] == 2
    assert metrics["required_answered"] == 2
    assert metrics["optional_answered"] == 0
    assert 0 <= metrics["completion_rate"] <= 1.0


@pytest.mark.asyncio
async def test_create_analytics_record_automatically(
    db_session: AsyncSession,
    completed_briefing: Briefing,
):
    """Test that analytics record is created automatically."""

    service = AnalyticsService(db_session)
    analytics = await service.create_analytics_record(completed_briefing.id)

    assert analytics.id is not None
    assert analytics.briefing_id == completed_briefing.id
    assert analytics.metrics is not None
    assert "duration_seconds" in analytics.metrics

    result = await db_session.execute(
        select(BriefingAnalytics).where(BriefingAnalytics.briefing_id == completed_briefing.id)
    )
    saved_analytics = result.scalar_one()
    assert saved_analytics.id == analytics.id


@pytest.mark.asyncio
async def test_analytics_duration_calculation(
    db_session: AsyncSession,
    test_client: EndClient,
    test_template: BriefingTemplate,
):
    """Test accurate duration calculation."""

    start_time = datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)
    end_time = datetime(2025, 1, 1, 11, 30, 0, tzinfo=UTC)

    briefing = Briefing(
        end_client_id=test_client.id,
        template_version_id=test_template.current_version_id,
        status=BriefingStatus.COMPLETED,
        current_question_order=3,
        answers={"1": "A", "2": "B", "3": "C"},
        created_at=start_time,
        completed_at=end_time,
    )
    db_session.add(briefing)
    await db_session.commit()

    service = AnalyticsService(db_session)
    metrics = await service.calculate_metrics(briefing.id)

    assert metrics["duration_seconds"] == 5400


@pytest.mark.asyncio
async def test_analytics_completion_rate(
    db_session: AsyncSession,
    test_client: EndClient,
    test_template: BriefingTemplate,
):
    """Test completion rate calculation with different answer counts."""

    briefing_full = Briefing(
        end_client_id=test_client.id,
        template_version_id=test_template.current_version_id,
        status=BriefingStatus.COMPLETED,
        current_question_order=4,
        answers={"1": "A", "2": "B", "3": "C"},
        completed_at=datetime.now(UTC),
    )
    db_session.add(briefing_full)
    await db_session.flush()

    service = AnalyticsService(db_session)
    metrics_full = await service.calculate_metrics(briefing_full.id)

    assert metrics_full["completion_rate"] == 1.0


@pytest.mark.asyncio
async def test_analytics_identifies_optional_questions_not_answered(
    db_session: AsyncSession,
    completed_briefing: Briefing,
):
    """Test that analytics identifies which optional questions were skipped."""

    service = AnalyticsService(db_session)
    metrics = await service.calculate_metrics(completed_briefing.id)

    assert metrics["optional_answered"] == 0
    assert metrics["optional_skipped"] == 1


@pytest.mark.asyncio
async def test_get_analytics_for_briefing(
    db_session: AsyncSession,
    completed_briefing: Briefing,
):
    """Test retrieving analytics for a briefing."""

    service = AnalyticsService(db_session)
    created_analytics = await service.create_analytics_record(completed_briefing.id)

    retrieved_analytics = await service.get_analytics(completed_briefing.id)

    assert retrieved_analytics is not None
    assert retrieved_analytics.id == created_analytics.id
    assert retrieved_analytics.briefing_id == completed_briefing.id


@pytest.mark.asyncio
async def test_analytics_not_created_for_incomplete_briefing(
    db_session: AsyncSession,
    test_client: EndClient,
    test_template: BriefingTemplate,
):
    """Test that analytics should not be created for incomplete briefings."""
    incomplete_briefing = Briefing(
        end_client_id=test_client.id,
        template_version_id=test_template.current_version_id,
        status=BriefingStatus.IN_PROGRESS,
        current_question_order=2,
        answers={"1": "Only first answer"},
    )
    db_session.add(incomplete_briefing)
    await db_session.commit()

    service = AnalyticsService(db_session)

    with pytest.raises(ValueError, match="not completed"):
        await service.create_analytics_record(incomplete_briefing.id)


@pytest.mark.asyncio
async def test_analytics_prevents_duplicate_creation(
    db_session: AsyncSession,
    completed_briefing: Briefing,
):
    """Test that duplicate analytics records are not created."""

    service = AnalyticsService(db_session)

    analytics1 = await service.create_analytics_record(completed_briefing.id)
    assert analytics1 is not None

    analytics2 = await service.create_analytics_record(completed_briefing.id)

    assert analytics2.briefing_id == completed_briefing.id

    result = await db_session.execute(
        select(BriefingAnalytics).where(BriefingAnalytics.briefing_id == completed_briefing.id)
    )
    all_analytics = result.scalars().all()
    assert len(all_analytics) == 1
