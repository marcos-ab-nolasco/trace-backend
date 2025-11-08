"""Service for selecting WhatsApp account configuration."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.crypto import decrypt_token
from src.db.models.organization import Organization


@dataclass
class WhatsAppAccountConfig:
    """WhatsApp account configuration."""

    phone_number_id: str
    access_token: str
    source: Literal["organization", "global"]


class WhatsAppAccountService:
    """Service for selecting which WhatsApp account to use."""

    def __init__(self, db_session: AsyncSession):
        """Initialize service.

        Args:
            db_session: Database session
            settings: Application settings
        """
        self.db = db_session

    async def get_account_config(
        self,
        organization_id: UUID,
        phone_number_id_override: str | None = None,
    ) -> WhatsAppAccountConfig | None:
        """Get WhatsApp account configuration for organization.

        Priority:
        1. Organization settings (if complete)
        2. Global settings from environment

        Args:
            organization_id: Organization ID
            phone_number_id_override: Optional phone_number_id from webhook
                (overrides organization phone_number_id)

        Returns:
            WhatsApp account config or None if no config available

        Raises:
            ValueError: If organization not found
        """
        # Get organization
        result = await self.db.execute(
            select(Organization).where(Organization.id == organization_id)
        )
        organization = result.scalar_one_or_none()

        if not organization:
            raise ValueError(f"Organization not found: {organization_id}")

        # Try organization settings first
        org_settings = organization.settings or {}
        org_phone_id = org_settings.get("phone_number_id")
        org_access_token_encrypted = org_settings.get("access_token")
        org_access_token = decrypt_token(org_access_token_encrypted)

        # Use override if provided, otherwise use org phone_id
        phone_id_to_use = phone_number_id_override or org_phone_id

        # If org has access_token and phone_id (either from settings or override)
        if org_access_token and phone_id_to_use:
            return WhatsAppAccountConfig(
                phone_number_id=phone_id_to_use,
                access_token=org_access_token,
                source="organization",
            )

        # Fall back to global settings
        global_phone_id = get_settings().WHATSAPP_PHONE_NUMBER_ID
        global_access_token = get_settings().WHATSAPP_ACCESS_TOKEN.get_secret_value()

        if global_phone_id and global_access_token:
            return WhatsAppAccountConfig(
                phone_number_id=global_phone_id,
                access_token=global_access_token,
                source="global",
            )

        # No config available
        return None
