"""
Integration tests for encrypted token storage.

These tests verify that WhatsApp access tokens are stored encrypted in the database
and transparently decrypted when retrieved.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.crypto import decrypt_token, encrypt_token
from src.db.models.organization import Organization
from src.services.whatsapp.whatsapp_account_service import WhatsAppAccountService


@pytest.mark.asyncio
async def test_tokens_stored_encrypted_in_database(
    db_session: AsyncSession,
    test_organization: Organization,
):
    """Test that tokens are actually stored encrypted in the database."""
    plain_token = "my_secret_whatsapp_token_12345"
    encrypted_token = encrypt_token(plain_token)

    # Store encrypted token in organization settings
    test_organization.settings = {
        "phone_number_id": "test_phone_123",
        "access_token": encrypted_token,
    }
    db_session.add(test_organization)
    await db_session.commit()

    # Query database directly to verify token is encrypted
    result = await db_session.execute(
        text("SELECT settings FROM organizations WHERE id = :org_id"),
        {"org_id": test_organization.id},
    )
    row = result.fetchone()
    assert row is not None

    stored_settings = row[0]
    stored_token = stored_settings["access_token"]

    # Verify token is stored encrypted (not plain text)
    assert stored_token != plain_token
    assert stored_token.startswith("gAAAAA")  # Fernet token prefix

    # Verify we can decrypt it back
    assert decrypt_token(stored_token) == plain_token


@pytest.mark.asyncio
async def test_whatsapp_service_receives_decrypted_token(
    db_session: AsyncSession,
    test_organization: Organization,
):
    """Test that WhatsAppAccountService returns decrypted tokens."""
    plain_token = "my_secret_whatsapp_token_67890"
    encrypted_token = encrypt_token(plain_token)

    # Store encrypted token
    test_organization.settings = {
        "phone_number_id": "test_phone_456",
        "access_token": encrypted_token,
    }
    db_session.add(test_organization)
    await db_session.commit()

    # Service should return decrypted token
    service = WhatsAppAccountService(db_session)
    config = await service.get_account_config(test_organization.id)

    assert config is not None
    assert config.access_token == plain_token  # Decrypted
    assert config.access_token != encrypted_token  # Not encrypted
    assert config.phone_number_id == "test_phone_456"
    assert config.source == "organization"


@pytest.mark.asyncio
async def test_backward_compatibility_with_plain_text_tokens(
    db_session: AsyncSession,
    test_organization: Organization,
):
    """Test that plain text tokens (pre-migration) still work via fallback."""
    plain_token = "legacy_plain_text_token"

    # Store plain text token (simulating pre-migration state)
    test_organization.settings = {
        "phone_number_id": "test_phone_789",
        "access_token": plain_token,  # Not encrypted
    }
    db_session.add(test_organization)
    await db_session.commit()

    # Service should handle plain text gracefully (backward compatibility)
    service = WhatsAppAccountService(db_session)
    config = await service.get_account_config(test_organization.id)

    assert config is not None
    assert config.access_token == plain_token
    assert config.phone_number_id == "test_phone_789"
    assert config.source == "organization"


@pytest.mark.asyncio
async def test_multiple_orgs_with_different_encrypted_tokens(
    db_session: AsyncSession,
):
    """Test that multiple organizations can have different encrypted tokens."""
    # Create two organizations with different tokens
    org1 = Organization(
        name="Org 1",
        settings={
            "phone_number_id": "phone_111",
            "access_token": encrypt_token("token_for_org_1"),
        },
    )
    org2 = Organization(
        name="Org 2",
        settings={
            "phone_number_id": "phone_222",
            "access_token": encrypt_token("token_for_org_2"),
        },
    )

    db_session.add(org1)
    db_session.add(org2)
    await db_session.commit()
    await db_session.refresh(org1)
    await db_session.refresh(org2)

    # Retrieve configs for both organizations
    service = WhatsAppAccountService(db_session)
    config1 = await service.get_account_config(org1.id)
    config2 = await service.get_account_config(org2.id)

    # Each should have its own decrypted token
    assert config1.access_token == "token_for_org_1"
    assert config2.access_token == "token_for_org_2"
    assert config1.access_token != config2.access_token


@pytest.mark.asyncio
async def test_empty_or_null_token_handling(
    db_session: AsyncSession,
    test_organization: Organization,
):
    """Test that organizations without tokens fall back to global settings."""
    # Organization with no access_token
    test_organization.settings = {
        "phone_number_id": "phone_999",
        # No access_token key
    }
    db_session.add(test_organization)
    await db_session.commit()

    service = WhatsAppAccountService(db_session)
    config = await service.get_account_config(test_organization.id)

    # Should fall back to global settings
    assert config is not None
    assert config.source == "global"
    assert config.access_token == "global_test_token_xyz"  # From .env.test


@pytest.mark.asyncio
async def test_token_with_special_characters_encrypted_correctly(
    db_session: AsyncSession,
    test_organization: Organization,
):
    """Test that tokens with special characters are encrypted and decrypted correctly."""
    token_with_special_chars = "token!@#$%^&*()_+-=[]{}|;':,.<>?/~`"
    encrypted_token = encrypt_token(token_with_special_chars)

    test_organization.settings = {
        "phone_number_id": "phone_special",
        "access_token": encrypted_token,
    }
    db_session.add(test_organization)
    await db_session.commit()

    service = WhatsAppAccountService(db_session)
    config = await service.get_account_config(test_organization.id)

    assert config is not None
    assert config.access_token == token_with_special_chars
