"""Briefing orchestrator for managing conversational briefing sessions."""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.briefing import Briefing, BriefingStatus
from src.db.models.end_client import EndClient
from src.db.models.template_version import TemplateVersion
from src.db.models.whatsapp_session import WhatsAppSession
from src.services.briefing.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)


class BriefingOrchestrator:
    """Orchestrates briefing conversations with state management."""

    def __init__(self, db_session: AsyncSession):
        """Initialize orchestrator with database session.

        Args:
            db_session: AsyncSession for database operations
        """
        self.db_session = db_session

    async def start_briefing(self, end_client_id: UUID, template_version_id: UUID) -> Briefing:
        """Start a new briefing session.

        Args:
            end_client_id: ID of the end client
            template_version_id: ID of the template version to use

        Returns:
            Created Briefing instance

        Raises:
            ValueError: If client or template not found
        """
        result = await self.db_session.execute(
            select(EndClient).where(EndClient.id == end_client_id)
        )
        client = result.scalar_one_or_none()
        if not client:
            raise ValueError(f"EndClient not found: {end_client_id}")

        result = await self.db_session.execute(
            select(TemplateVersion).where(TemplateVersion.id == template_version_id)
        )
        template_version = result.scalar_one_or_none()
        if not template_version:
            raise ValueError(f"TemplateVersion not found: {template_version_id}")

        briefing = Briefing(
            end_client_id=end_client_id,
            template_version_id=template_version_id,
            status=BriefingStatus.IN_PROGRESS,
            current_question_order=1,
            answers={},
        )
        self.db_session.add(briefing)
        await self.db_session.commit()
        await self.db_session.refresh(briefing)

        logger.info(
            f"Started briefing {briefing.id} for client {end_client_id} "
            f"with template version {template_version_id}"
        )
        return briefing

    async def next_question(self, briefing_id: UUID) -> dict[str, Any] | None:
        """Get the next question for the briefing.

        Args:
            briefing_id: ID of the briefing

        Returns:
            Next question dict or None if briefing is complete

        Raises:
            ValueError: If briefing not found
        """
        result = await self.db_session.execute(select(Briefing).where(Briefing.id == briefing_id))
        briefing = result.scalar_one_or_none()
        if not briefing:
            raise ValueError(f"Briefing not found: {briefing_id}")

        result = await self.db_session.execute(
            select(TemplateVersion).where(TemplateVersion.id == briefing.template_version_id)
        )
        template_version = result.scalar_one_or_none()
        if not template_version:
            raise ValueError(f"TemplateVersion not found: {briefing.template_version_id}")

        questions = template_version.questions
        for question in questions:
            if question["order"] == briefing.current_question_order:
                return dict(question)

        return None

    async def get_next_question_for_session(
        self, session_id: UUID, template_version_id: UUID
    ) -> dict[str, Any] | None:
        """Get the next question for a WhatsApp session.

        Uses session.current_question_index to determine which question to return.
        Skips already-answered questions by checking briefing.answers.

        Args:
            session_id: ID of the WhatsApp session
            template_version_id: ID of the template version

        Returns:
            Next question dict or None if all questions answered

        Raises:
            ValueError: If session or template not found
        """
        # Get session
        result = await self.db_session.execute(
            select(WhatsAppSession).where(WhatsAppSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        # Get template
        result = await self.db_session.execute(
            select(TemplateVersion).where(TemplateVersion.id == template_version_id)
        )
        template_version = result.scalar_one_or_none()
        if not template_version:
            raise ValueError(f"TemplateVersion not found: {template_version_id}")

        # Get briefing if exists
        briefing = None
        if session.briefing_id:
            result = await self.db_session.execute(
                select(Briefing).where(Briefing.id == session.briefing_id)
            )
            briefing = result.scalar_one_or_none()

        # Collect answered question orders
        answered_orders = set()
        if briefing and briefing.answers:
            answered_orders = {int(order) for order in briefing.answers.keys()}

        # Find next unanswered question starting from session's current index
        questions = template_version.questions
        for question in sorted(questions, key=lambda q: q["order"]):
            question_order = question["order"]

            # Skip if already answered
            if question_order in answered_orders:
                continue

            # If we've reached or passed the session index, return this question
            if question_order >= session.current_question_index:
                logger.info(
                    f"Returning question {question_order} for session {session_id} "
                    f"(index: {session.current_question_index})"
                )
                return dict(question)

        # No more questions
        return None

    async def process_answer(
        self,
        briefing_id: UUID,
        question_order: int,
        answer: str,
        auto_commit: bool = True,
        session_id: UUID | None = None,
    ) -> Briefing:
        """Process an answer to a question.

        Args:
            briefing_id: ID of the briefing
            question_order: Order of the question being answered
            answer: Answer text
            auto_commit: If True (default), commits changes immediately.
                        If False, only flushes changes, leaving transaction control to caller.
            session_id: Optional WhatsApp session ID to sync progression state

        Returns:
            Updated Briefing instance

        Raises:
            ValueError: If briefing not found or answer is out of order
        """
        result = await self.db_session.execute(select(Briefing).where(Briefing.id == briefing_id))
        briefing = result.scalar_one_or_none()
        if not briefing:
            raise ValueError(f"Briefing not found: {briefing_id}")

        if briefing.status != BriefingStatus.IN_PROGRESS:
            raise ValueError(f"Briefing is not in progress: {briefing.status.value}")

        if question_order != briefing.current_question_order:
            raise ValueError(
                f"Must answer current question {briefing.current_question_order}, "
                f"got {question_order}"
            )

        answers = briefing.answers.copy() if briefing.answers else {}
        answers[str(question_order)] = answer
        briefing.answers = answers

        briefing.current_question_order = question_order + 1

        # Sync session state if session_id provided
        if session_id:
            result = await self.db_session.execute(
                select(WhatsAppSession).where(WhatsAppSession.id == session_id)
            )
            session = result.scalar_one_or_none()
            if session:
                session.current_question_index = question_order + 1
                logger.info(
                    f"Synced session {session_id} index to {session.current_question_index}"
                )

        if auto_commit:
            await self.db_session.commit()
            await self.db_session.refresh(briefing)
        else:
            await self.db_session.flush()

        logger.info(f"Processed answer for briefing {briefing_id}, question {question_order}")
        return briefing

    async def complete_briefing(self, briefing_id: UUID, auto_commit: bool = True) -> Briefing:
        """Complete a briefing session.

        Args:
            briefing_id: ID of the briefing
            auto_commit: If True (default), commits changes immediately.
                        If False, only flushes changes, leaving transaction control to caller.

        Returns:
            Completed Briefing instance

        Raises:
            ValueError: If briefing not found or required questions not answered
        """
        result = await self.db_session.execute(select(Briefing).where(Briefing.id == briefing_id))
        briefing = result.scalar_one_or_none()
        if not briefing:
            raise ValueError(f"Briefing not found: {briefing_id}")

        result = await self.db_session.execute(
            select(TemplateVersion).where(TemplateVersion.id == briefing.template_version_id)
        )
        template_version = result.scalar_one_or_none()
        if not template_version:
            raise ValueError(f"TemplateVersion not found: {briefing.template_version_id}")

        required_questions = [
            q["order"] for q in template_version.questions if q.get("required", False)
        ]
        answered_questions = [int(k) for k in (briefing.answers or {}).keys()]

        missing_required = [q for q in required_questions if q not in answered_questions]
        if missing_required:
            raise ValueError(
                f"Cannot complete briefing: required questions not answered: {missing_required}"
            )

        briefing.status = BriefingStatus.COMPLETED
        briefing.completed_at = datetime.now()

        await self.db_session.flush()

        analytics_service = AnalyticsService(self.db_session)
        try:
            await analytics_service.create_analytics_record(briefing_id)
            logger.info(f"Created analytics for completed briefing {briefing_id}")
        except Exception as e:
            logger.error(f"Failed to create analytics for briefing {briefing_id}: {e}")

        if auto_commit:
            await self.db_session.commit()
            await self.db_session.refresh(briefing)
        else:
            await self.db_session.flush()

        logger.info(f"Completed briefing {briefing_id}")
        return briefing

    async def cancel_briefing(self, briefing_id: UUID) -> Briefing:
        """Cancel a briefing session.

        Args:
            briefing_id: ID of the briefing

        Returns:
            Cancelled Briefing instance

        Raises:
            ValueError: If briefing not found
        """
        result = await self.db_session.execute(select(Briefing).where(Briefing.id == briefing_id))
        briefing = result.scalar_one_or_none()
        if not briefing:
            raise ValueError(f"Briefing not found: {briefing_id}")

        briefing.status = BriefingStatus.CANCELLED

        await self.db_session.commit()
        await self.db_session.refresh(briefing)

        logger.info(f"Cancelled briefing {briefing_id}")
        return briefing

    async def get_briefing_progress(self, briefing_id: UUID) -> dict[str, Any]:
        """Get progress information for a briefing.

        Args:
            briefing_id: ID of the briefing

        Returns:
            Dict with progress information

        Raises:
            ValueError: If briefing not found
        """
        result = await self.db_session.execute(select(Briefing).where(Briefing.id == briefing_id))
        briefing = result.scalar_one_or_none()
        if not briefing:
            raise ValueError(f"Briefing not found: {briefing_id}")

        result = await self.db_session.execute(
            select(TemplateVersion).where(TemplateVersion.id == briefing.template_version_id)
        )
        template_version = result.scalar_one_or_none()
        if not template_version:
            raise ValueError(f"TemplateVersion not found: {briefing.template_version_id}")

        total_questions = len(template_version.questions)
        answered_questions = len(briefing.answers or {})
        remaining_questions = total_questions - answered_questions
        progress_percentage = (
            (answered_questions / total_questions * 100) if total_questions > 0 else 0
        )

        return {
            "total_questions": total_questions,
            "answered_questions": answered_questions,
            "remaining_questions": remaining_questions,
            "progress_percentage": progress_percentage,
            "status": briefing.status.value,
            "current_question_order": briefing.current_question_order,
        }
