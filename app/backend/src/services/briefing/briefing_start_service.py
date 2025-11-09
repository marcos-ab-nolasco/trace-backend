"""Service for starting briefing sessions with validation."""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.briefing import Briefing, BriefingStatus
from src.db.models.end_client import EndClient

logger = logging.getLogger(__name__)


class ClientHasActiveBriefingError(Exception):
    """Raised when trying to start a briefing for a client who already has an active one."""

    pass


class BriefingStartService:
    """Service for starting briefing sessions with business rule validations."""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def start_briefing(
        self,
        organization_id: UUID,
        architect_id: UUID,
        client_name: str,
        client_phone: str,
        template_version_id: UUID,
    ) -> Briefing:
        """Start or resume a briefing session.

        This method:
        1. Creates or updates the EndClient
        2. Checks for active briefings
        3. If no active briefings: creates new one
        4. If active briefings exist: returns the most recent one (continues it)

        This allows clients to have multiple concurrent briefings (e.g., different projects)
        and automatically resumes the most recent one when they return.

        Args:
            organization_id: Organization ID
            architect_id: Architect ID who is starting the briefing
            client_name: Client's name
            client_phone: Client's phone (normalized)
            template_version_id: Template version to use

        Returns:
            Briefing (new or existing)
        """
        # Step 1: Create or update EndClient
        end_client = await self._create_or_update_client(
            organization_id=organization_id,
            architect_id=architect_id,
            name=client_name,
            phone=client_phone,
        )

        # Step 2: Check for active briefings
        active_briefings = await self._get_active_briefings(end_client.id)

        # Step 3: If active briefings exist, return the most recent one
        if active_briefings:
            existing_briefing = active_briefings[0]  # Most recent (ordered by created_at DESC)
            logger.info(
                "Resuming existing briefing: briefing_id=%s client_id=%s",
                existing_briefing.id,
                end_client.id,
            )
            return existing_briefing

        # Step 4: No active briefings - create new one
        briefing = Briefing(
            end_client_id=end_client.id,
            template_version_id=template_version_id,
            status=BriefingStatus.IN_PROGRESS,
            current_question_order=1,
            answers={},
        )
        self.db.add(briefing)

        try:
            await self.db.flush()
        except IntegrityError as e:
            # Race condition: another request created a briefing simultaneously
            # Rollback and fetch the briefing that was created by the other request
            logger.warning(
                "IntegrityError creating briefing for client %s (race condition): %s",
                end_client.id,
                str(e),
            )
            await self.db.rollback()

            # Fetch the briefing created by the concurrent request
            active_briefings = await self._get_active_briefings(end_client.id)
            if active_briefings:
                existing_briefing = active_briefings[0]
                logger.info(
                    "Resuming briefing created by concurrent request: briefing_id=%s client_id=%s",
                    existing_briefing.id,
                    end_client.id,
                )
                return existing_briefing

            # Should never happen, but re-raise if no briefing found
            raise

        logger.info(
            "Briefing started: briefing_id=%s client_id=%s template_version_id=%s",
            briefing.id,
            end_client.id,
            template_version_id,
        )

        return briefing

    async def _create_or_update_client(
        self,
        organization_id: UUID,
        architect_id: UUID,
        name: str,
        phone: str,
    ) -> EndClient:
        """Create new client or update existing one with same phone number.

        Handles unique constraint on (organization_id, phone) by updating existing client.
        """
        # Try to get existing client with same phone in the organization
        result = await self.db.execute(
            select(EndClient).where(
                EndClient.organization_id == organization_id,
                EndClient.phone == phone,
            )
        )
        existing_client = result.scalar_one_or_none()

        if existing_client:
            # Update existing client (name and architect_id may have changed)
            logger.info(f"Updating existing client {existing_client.id}")
            existing_client.name = name
            existing_client.architect_id = architect_id  # Update architect if needed
            await self.db.flush()
            return existing_client

        # Create new client
        new_client = EndClient(
            organization_id=organization_id,
            architect_id=architect_id,
            name=name,
            phone=phone,
        )
        self.db.add(new_client)
        await self.db.flush()
        logger.info(f"Created new client {new_client.id}")
        return new_client

    async def _get_active_briefings(self, end_client_id: UUID) -> list[Briefing]:
        """Get all active briefings for a client.

        Args:
            end_client_id: EndClient ID

        Returns:
            List of active briefings, ordered by most recent first
        """
        result = await self.db.execute(
            select(Briefing)
            .where(
                Briefing.end_client_id == end_client_id,
                Briefing.status == BriefingStatus.IN_PROGRESS,
            )
            .order_by(Briefing.created_at.desc())
        )
        return list(result.scalars().all())
