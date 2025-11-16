"""Tests for briefing analytics functionality."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.briefing import Briefing, BriefingStatus
from src.db.models.briefing_analytics import BriefingAnalytics
from src.services.briefing.analytics_service import AnalyticsService
from tests.factories import BriefingFactory, BriefingTemplateFactory, EndClientFactory


@pytest.fixture
async def test_template(db_session: AsyncSession, test_project_type):
    """Create test template."""
    from sqlalchemy.orm import selectinload

    from src.db.models.briefing_template import BriefingTemplate

    template = await BriefingTemplateFactory.create_with_version_async(
        name="Template Reforma",
        category="reforma",
        description="Template para projetos de reforma",
        is_global=True,
        project_type=test_project_type,
        version_kwargs={
            "questions": [
                {"order": 1, "question": "Pergunta 1?", "type": "text", "required": True},
                {"order": 2, "question": "Pergunta 2?", "type": "text", "required": True},
                {"order": 3, "question": "Pergunta 3?", "type": "text", "required": False},
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
    return result.scalar_one()


@pytest.fixture
async def test_client(db_session: AsyncSession):
    """Create test end client."""
    return await EndClientFactory.create_async(
        name="João Silva",
        phone="+5511987654321",
    )


@pytest.fixture
async def completed_briefing(db_session: AsyncSession, test_client, test_template):
    """Create a completed briefing."""
    created_time = datetime.now(UTC) - timedelta(hours=2)
    completed_time = datetime.now(UTC)

    return await BriefingFactory.create_async(
        end_client=test_client,
        template_version=test_template.current_version,
        status=BriefingStatus.COMPLETED,
        current_question_order=3,
        answers={
            "1": "Resposta 1",
            "2": "Resposta 2",
        },
        created_at=created_time,
        completed_at=completed_time,
    )


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
    test_client,
    test_template,
):
    """Test accurate duration calculation."""
    start_time = datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)
    end_time = datetime(2025, 1, 1, 11, 30, 0, tzinfo=UTC)

    briefing = await BriefingFactory.create_async(
        end_client=test_client,
        template_version=test_template.current_version,
        status=BriefingStatus.COMPLETED,
        current_question_order=3,
        answers={"1": "A", "2": "B", "3": "C"},
        created_at=start_time,
        completed_at=end_time,
    )

    service = AnalyticsService(db_session)
    metrics = await service.calculate_metrics(briefing.id)

    assert metrics["duration_seconds"] == 5400


@pytest.mark.asyncio
async def test_analytics_completion_rate(
    db_session: AsyncSession,
    test_client,
    test_template,
):
    """Test completion rate calculation with different answer counts."""
    briefing_full = await BriefingFactory.create_async(
        end_client=test_client,
        template_version=test_template.current_version,
        status=BriefingStatus.COMPLETED,
        current_question_order=4,
        answers={"1": "A", "2": "B", "3": "C"},
        completed_at=datetime.now(UTC),
    )

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
    test_client,
    test_template,
):
    """Test that analytics should not be created for incomplete briefings."""
    incomplete_briefing = await BriefingFactory.create_async(
        end_client=test_client,
        template_version=test_template.current_version,
        status=BriefingStatus.IN_PROGRESS,
        current_question_order=2,
        answers={"1": "Only first answer"},
    )

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
