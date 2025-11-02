"""Tests for WhatsApp webhook endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.architect import Architect
from src.db.models.end_client import EndClient
from src.db.models.organization import Organization
from src.db.models.organization_whatsapp_account import OrganizationWhatsAppAccount
from src.db.models.whatsapp_account import WhatsAppAccount
from src.db.models.whatsapp_session import SessionStatus, WhatsAppSession


@pytest.fixture
async def whatsapp_account(db_session: AsyncSession) -> WhatsAppAccount:
    """Create test WhatsApp account with organization link."""
    org = Organization(name="Test Org")
    db_session.add(org)
    await db_session.flush()

    account = WhatsAppAccount(
        phone_number_id="test_phone_123",
        phone_number="+5511999999999",
        access_token="test_token",
        webhook_verify_token="test_verify_token",
    )
    db_session.add(account)
    await db_session.flush()

    # Create N:N relationship
    link = OrganizationWhatsAppAccount(
        organization_id=org.id,
        whatsapp_account_id=account.id,
        is_primary=True,
    )
    db_session.add(link)
    await db_session.commit()
    await db_session.refresh(account)
    return account


# Webhook Verification Tests (GET)
@pytest.mark.asyncio
async def test_webhook_verification_success(client: AsyncClient, whatsapp_account: WhatsAppAccount):
    """Test webhook verification with correct token."""
    # .env.test has WHATSAPP_WEBHOOK_VERIFY_TOKEN=test_verify_token
    response = await client.get(
        "/api/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "test_verify_token",
            "hub.challenge": "challenge_string_123",
        },
    )

    assert response.status_code == 200
    assert response.text == '"challenge_string_123"'  # JSON string response


@pytest.mark.asyncio
async def test_webhook_verification_invalid_token(
    client: AsyncClient, whatsapp_account: WhatsAppAccount
):
    """Test webhook verification with incorrect token."""
    response = await client.get(
        "/api/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "challenge_string_123",
        },
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_webhook_verification_missing_params(client: AsyncClient):
    """Test webhook verification with missing parameters."""
    response = await client.get("/api/webhooks/whatsapp")

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_webhook_verification_wrong_mode(
    client: AsyncClient, whatsapp_account: WhatsAppAccount
):
    """Test webhook verification with wrong mode."""
    response = await client.get(
        "/api/webhooks/whatsapp",
        params={
            "hub.mode": "unsubscribe",  # Wrong mode
            "hub.verify_token": "test_verify_token",
            "hub.challenge": "challenge_string_123",
        },
    )

    assert response.status_code == 400


# Webhook Message Handling Tests (POST)
@pytest.mark.asyncio
async def test_webhook_receive_text_message(
    client: AsyncClient, db_session: AsyncSession, whatsapp_account: WhatsAppAccount
):
    """Test receiving a text message from WhatsApp."""
    # Create end client and session
    org = Organization(name="Test Org 2")
    db_session.add(org)
    await db_session.flush()

    architect = Architect(
        organization_id=org.id,
        email="architect@test.com",
        hashed_password="hashed",
        phone="+5511888888888",
        is_authorized=True,
    )
    db_session.add(architect)
    await db_session.flush()

    end_client = EndClient(
        organization_id=org.id,
        architect_id=architect.id,
        name="Test Client",
        phone="+5511999999999",
    )
    db_session.add(end_client)
    await db_session.flush()

    session = WhatsAppSession(
        end_client_id=end_client.id,
        phone_number="+5511999999999",
        status=SessionStatus.ACTIVE.value,
    )
    db_session.add(session)
    await db_session.commit()

    # WhatsApp webhook payload (text message)
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+5511999999999",
                                "phone_number_id": "test_phone_123",
                            },
                            "contacts": [
                                {"profile": {"name": "Test Architect"}, "wa_id": "5511999999999"}
                            ],
                            "messages": [
                                {
                                    "from": "5511999999999",
                                    "id": "wamid.test123",
                                    "timestamp": "1234567890",
                                    "type": "text",
                                    "text": {"body": "Hello, this is a test message"},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }

    response = await client.post("/api/webhooks/whatsapp", json=payload)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_webhook_receive_status_update(client: AsyncClient):
    """Test receiving a message status update from WhatsApp."""
    # WhatsApp webhook payload (status update)
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+5511999999999",
                                "phone_number_id": "test_phone_123",
                            },
                            "statuses": [
                                {
                                    "id": "wamid.test123",
                                    "status": "delivered",
                                    "timestamp": "1234567890",
                                    "recipient_id": "5511999999999",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }

    response = await client.post("/api/webhooks/whatsapp", json=payload)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_webhook_invalid_payload(client: AsyncClient):
    """Test webhook with invalid payload structure."""
    payload = {"invalid": "payload"}

    response = await client.post("/api/webhooks/whatsapp", json=payload)

    # Should still return 200 to avoid retries from WhatsApp
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_webhook_empty_payload(client: AsyncClient):
    """Test webhook with empty payload."""
    response = await client.post("/api/webhooks/whatsapp", json={})

    # Should still return 200 to avoid retries from WhatsApp
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_webhook_handles_unsupported_message_type(client: AsyncClient):
    """Test webhook gracefully handles unsupported message types."""
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+5511999999999",
                                "phone_number_id": "test_phone_123",
                            },
                            "messages": [
                                {
                                    "from": "5511999999999",
                                    "id": "wamid.test456",
                                    "timestamp": "1234567890",
                                    "type": "unsupported_type",  # Unsupported
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }

    response = await client.post("/api/webhooks/whatsapp", json=payload)

    # Should return 200 even for unsupported types
    assert response.status_code == 200
