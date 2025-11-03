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
        """Start a new briefing session.

        This method:
        1. Creates or updates the EndClient
        2. Validates that client doesn't have an active briefing
        3. Creates the briefing in IN_PROGRESS status

        Args:
            organization_id: Organization ID
            architect_id: Architect ID who is starting the briefing
            client_name: Client's name
            client_phone: Client's phone (normalized)
            template_version_id: Template version to use

        Returns:
            Created Briefing

        Raises:
            ClientHasActiveBriefingError: If client already has an active briefing
        """
        # Step 1: Create or update EndClient
        end_client = await self._create_or_update_client(
            organization_id=organization_id,
            architect_id=architect_id,
            name=client_name,
            phone=client_phone,
        )

        # Step 2: Check if client has active briefing
        await self._validate_no_active_briefing(end_client.id)

        # Step 3: Create briefing
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
            # Constraint violation - client already has active briefing
            # This handles race conditions where both requests pass validation
            # but database constraint prevents duplicate
            logger.warning(
                "IntegrityError creating briefing for client %s: %s",
                end_client.id,
                str(e),
            )
            raise ClientHasActiveBriefingError(
                "Client already has an active briefing. "
                "Please complete or cancel the existing briefing before starting a new one."
            ) from e

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

    async def _validate_no_active_briefing(self, end_client_id: UUID) -> None:
        """Validate that client doesn't have an active briefing.

        Args:
            end_client_id: EndClient ID

        Raises:
            ClientHasActiveBriefingError: If client has active briefing
        """
        result = await self.db.execute(
            select(Briefing).where(
                Briefing.end_client_id == end_client_id,
                Briefing.status == BriefingStatus.IN_PROGRESS,
            )
        )
        active_briefing = result.scalar_one_or_none()

        if active_briefing:
            raise ClientHasActiveBriefingError(
                f"Client already has an active briefing (ID: {active_briefing.id}). "
                "Please complete or cancel the existing briefing before starting a new one."
            )
