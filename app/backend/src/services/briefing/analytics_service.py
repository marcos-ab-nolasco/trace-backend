"""Service for calculating and managing briefing analytics."""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.briefing import Briefing, BriefingStatus
from src.db.models.briefing_analytics import BriefingAnalytics
from src.db.models.template_version import TemplateVersion

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for calculating metrics and creating analytics records."""

    def __init__(self, db_session: AsyncSession):
        """Initialize analytics service with database session.

        Args:
            db_session: AsyncSession for database operations
        """
        self.db_session = db_session

    async def calculate_metrics(self, briefing_id: UUID) -> dict[str, Any]:
        """Calculate metrics for a briefing.

        Args:
            briefing_id: ID of the briefing

        Returns:
            Dict with calculated metrics

        Raises:
            ValueError: If briefing not found
        """
        # Get briefing
        result = await self.db_session.execute(
            select(Briefing).where(Briefing.id == briefing_id)
        )
        briefing = result.scalar_one_or_none()
        if not briefing:
            raise ValueError(f"Briefing not found: {briefing_id}")

        # Get template version
        result = await self.db_session.execute(
            select(TemplateVersion).where(TemplateVersion.id == briefing.template_version_id)
        )
        template_version = result.scalar_one_or_none()
        if not template_version:
            raise ValueError(f"TemplateVersion not found: {briefing.template_version_id}")

        # Calculate duration
        duration_seconds = 0
        if briefing.completed_at and briefing.created_at:
            duration = briefing.completed_at - briefing.created_at
            duration_seconds = int(duration.total_seconds())

        # Count questions
        questions = template_version.questions or []
        total_questions = len(questions)
        required_questions = [q for q in questions if q.get("required", False)]
        optional_questions = [q for q in questions if not q.get("required", False)]

        # Count answers
        answers = briefing.answers or {}
        answered_questions = len(answers)

        # Count required vs optional answered
        required_answered = 0
        optional_answered = 0

        for question in questions:
            question_order = str(question["order"])
            is_required = question.get("required", False)

            if question_order in answers:
                if is_required:
                    required_answered += 1
                else:
                    optional_answered += 1

        optional_skipped = len(optional_questions) - optional_answered

        # Calculate completion rate
        completion_rate = answered_questions / total_questions if total_questions > 0 else 0.0

        metrics = {
            "duration_seconds": duration_seconds,
            "total_questions": total_questions,
            "answered_questions": answered_questions,
            "required_questions": len(required_questions),
            "required_answered": required_answered,
            "optional_questions": len(optional_questions),
            "optional_answered": optional_answered,
            "optional_skipped": optional_skipped,
            "completion_rate": round(completion_rate, 2),
        }

        logger.info(f"Calculated metrics for briefing {briefing_id}: {metrics}")
        return metrics

    async def create_analytics_record(
        self, briefing_id: UUID, observations: str | None = None
    ) -> BriefingAnalytics:
        """Create analytics record for a completed briefing.

        Args:
            briefing_id: ID of the briefing
            observations: Optional observations/insights

        Returns:
            Created BriefingAnalytics instance

        Raises:
            ValueError: If briefing not found or not completed
        """
        # Get briefing
        result = await self.db_session.execute(
            select(Briefing).where(Briefing.id == briefing_id)
        )
        briefing = result.scalar_one_or_none()
        if not briefing:
            raise ValueError(f"Briefing not found: {briefing_id}")

        # Verify briefing is completed
        if briefing.status != BriefingStatus.COMPLETED:
            raise ValueError(f"Briefing is not completed: {briefing.status.value}")

        # Check if analytics already exists
        result = await self.db_session.execute(
            select(BriefingAnalytics).where(BriefingAnalytics.briefing_id == briefing_id)
        )
        existing_analytics = result.scalar_one_or_none()

        if existing_analytics:
            logger.info(f"Analytics already exists for briefing {briefing_id}")
            return existing_analytics

        # Calculate metrics
        metrics = await self.calculate_metrics(briefing_id)

        # Create analytics record
        analytics = BriefingAnalytics(
            briefing_id=briefing_id,
            metrics=metrics,
            observations=observations,
        )

        self.db_session.add(analytics)
        await self.db_session.flush()

        logger.info(f"Created analytics record for briefing {briefing_id}")
        return analytics

    async def get_analytics(self, briefing_id: UUID) -> BriefingAnalytics | None:
        """Get analytics record for a briefing.

        Args:
            briefing_id: ID of the briefing

        Returns:
            BriefingAnalytics instance or None if not found
        """
        result = await self.db_session.execute(
            select(BriefingAnalytics).where(BriefingAnalytics.briefing_id == briefing_id)
        )
        return result.scalar_one_or_none()

    async def extract_unexpected_insights(
        self, briefing_id: UUID, use_ai: bool = False
    ) -> str | None:
        """Extract unexpected insights from briefing answers.

        This method can optionally use AI to identify information that wasn't
        directly asked in the questions but might be valuable.

        Args:
            briefing_id: ID of the briefing
            use_ai: Whether to use AI for extraction (future feature)

        Returns:
            Extracted insights as text, or None if none found
        """
        # Get briefing
        result = await self.db_session.execute(
            select(Briefing).where(Briefing.id == briefing_id)
        )
        briefing = result.scalar_one_or_none()
        if not briefing:
            return None

        # For now, return None - AI extraction can be implemented later
        # Future: Use AI service to analyze answers and extract insights
        if use_ai:
            # TODO: Implement AI-based insight extraction
            pass

        return None
