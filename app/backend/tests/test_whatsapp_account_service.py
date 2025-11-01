"""Tests for WhatsAppAccountService."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.db.models.organization import Organization
from src.services.whatsapp.whatsapp_account_service import (
    WhatsAppAccountService,
    WhatsAppAccountConfig,
)


@pytest.mark.asyncio
async def test_get_account_config_uses_organization_settings_when_available(
    db_session: AsyncSession,
    test_organization: Organization,
):
    """Test that organization settings are used when available."""
    # Set organization WhatsApp settings
    test_organization.settings = {
        "phone_number_id": "org_phone_123",
        "access_token": "org_token_abc",
    }
    db_session.add(test_organization)
    await db_session.commit()

    service = WhatsAppAccountService(db_session)
    config = await service.get_account_config(test_organization.id)

    assert config is not None
    assert config.phone_number_id == "org_phone_123"
    assert config.access_token == "org_token_abc"
    assert config.source == "organization"


@pytest.mark.asyncio
async def test_get_account_config_uses_global_when_org_settings_missing(
    db_session: AsyncSession,
    test_organization: Organization,
):
    """Test that global settings are used when organization settings are missing."""
    # Organization has no WhatsApp settings
    test_organization.settings = {}
    db_session.add(test_organization)
    await db_session.commit()

    service = WhatsAppAccountService(db_session)
    config = await service.get_account_config(test_organization.id)

    # Should use global settings from .env.test
    assert config is not None
    assert config.phone_number_id == "global_test_phone_123"
    assert config.access_token == "global_test_token_xyz"
    assert config.source == "global"


@pytest.mark.asyncio
async def test_get_account_config_uses_global_when_org_settings_incomplete(
    db_session: AsyncSession,
    test_organization: Organization,
):
    """Test that global settings are used when organization settings are incomplete."""
    # Organization has incomplete WhatsApp settings (missing access_token)
    test_organization.settings = {
        "phone_number_id": "org_phone_123",
        # access_token missing
    }
    db_session.add(test_organization)
    await db_session.commit()

    service = WhatsAppAccountService(db_session)
    config = await service.get_account_config(test_organization.id)

    # Should fall back to global settings
    assert config is not None
    assert config.phone_number_id == "global_test_phone_123"
    assert config.access_token == "global_test_token_xyz"
    assert config.source == "global"


@pytest.mark.asyncio
async def test_get_account_config_prefers_org_over_global(
    db_session: AsyncSession,
    test_organization: Organization,
):
    """Test that organization settings take priority over global settings."""
    # Set organization WhatsApp settings
    test_organization.settings = {
        "phone_number_id": "org_phone_123",
        "access_token": "org_token_abc",
    }
    db_session.add(test_organization)
    await db_session.commit()

    service = WhatsAppAccountService(db_session)
    config = await service.get_account_config(test_organization.id)

    # Should use org settings, not global
    assert config.phone_number_id == "org_phone_123"
    assert config.access_token == "org_token_abc"
    assert config.source == "organization"


@pytest.mark.asyncio
async def test_get_account_config_raises_when_organization_not_found(
    db_session: AsyncSession,
):
    """Test that ValueError is raised when organization is not found."""
    from uuid import uuid4

    service = WhatsAppAccountService(db_session)

    with pytest.raises(ValueError, match="Organization not found"):
        await service.get_account_config(uuid4())


@pytest.mark.asyncio
async def test_get_account_config_can_override_phone_number_id(
    db_session: AsyncSession,
    test_organization: Organization,
):
    """Test that phone_number_id can be overridden (from webhook)."""
    # Organization has access_token but no phone_number_id
    test_organization.settings = {
        "access_token": "org_token_abc",
    }
    db_session.add(test_organization)
    await db_session.commit()

    service = WhatsAppAccountService(db_session)

    # Pass phone_number_id from webhook
    config = await service.get_account_config(
        test_organization.id, phone_number_id_override="webhook_phone_789"
    )

    assert config is not None
    assert config.phone_number_id == "webhook_phone_789"
    assert config.access_token == "org_token_abc"
    assert config.source == "organization"
