"""Tests for WhatsAppAccountService."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.organization import Organization
from src.services.whatsapp.whatsapp_account_service import (
    WhatsAppAccountService,
)

TEST_TOKEN_ABC = "gAAAAABpD54TeLG4dS70mfIW2CTouovwNoWK66Qgww3D0Sse4SACmBXOcFY8W-Z-tKlZXONY90ProGP92VJBioibMzc35eUhGg=="


@pytest.mark.asyncio
async def test_get_account_config_uses_organization_settings_when_available(
    db_session: AsyncSession,
    test_organization: Organization,
):
    """Test that organization settings are used when available."""
    test_organization.settings = {
        "phone_number_id": "org_phone_123",
        "access_token": TEST_TOKEN_ABC,
    }
    db_session.add(test_organization)
    await db_session.commit()

    service = WhatsAppAccountService(db_session)
    config = await service.get_account_config(test_organization.id)

    assert config is not None
    assert config.phone_number_id == "org_phone_123"
    assert config.access_token == "test_token_abc"
    assert config.source == "organization"


@pytest.mark.asyncio
async def test_get_account_config_prefers_org_over_global(
    db_session: AsyncSession,
    test_organization: Organization,
):
    """Test that organization settings take priority over global settings."""
    test_organization.settings = {
        "phone_number_id": "org_phone_123",
        "access_token": TEST_TOKEN_ABC,
    }
    db_session.add(test_organization)
    await db_session.commit()

    service = WhatsAppAccountService(db_session)
    config = await service.get_account_config(test_organization.id)

    assert config.phone_number_id == "org_phone_123"
    assert config.access_token == "test_token_abc"
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
    test_organization.settings = {
        "access_token": TEST_TOKEN_ABC,
    }
    db_session.add(test_organization)
    await db_session.commit()

    service = WhatsAppAccountService(db_session)

    config = await service.get_account_config(
        test_organization.id, phone_number_id_override="webhook_phone_789"
    )

    assert config is not None
    assert config.phone_number_id == "webhook_phone_789"
    assert config.access_token == "test_token_abc"
    assert config.source == "organization"
