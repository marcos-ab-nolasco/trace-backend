"""Tests for WhatsApp webhook endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.architect import Architect
from src.db.models.end_client import EndClient
from src.db.models.organization import Organization
from src.db.models.organization_whatsapp_account import OrganizationWhatsAppAccount
from src.db.models.whatsapp_account import WhatsAppAccount
from src.db.models.whatsapp_message import MessageStatus, WhatsAppMessage
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

    link = OrganizationWhatsAppAccount(
        organization_id=org.id,
        whatsapp_account_id=account.id,
        is_primary=True,
    )
    db_session.add(link)
    await db_session.commit()
    await db_session.refresh(account)
    return account


@pytest.mark.asyncio
async def test_webhook_verification_success(client: AsyncClient, whatsapp_account: WhatsAppAccount):
    """Test webhook verification with correct token."""
    response = await client.get(
        "/api/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "test_verify_token",
            "hub.challenge": "challenge_string_123",
        },
    )

    assert response.status_code == 200
    assert response.text == '"challenge_string_123"'


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
            "hub.mode": "unsubscribe",
            "hub.verify_token": "test_verify_token",
            "hub.challenge": "challenge_string_123",
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_webhook_receive_text_message(
    client: AsyncClient, db_session: AsyncSession, whatsapp_account: WhatsAppAccount
):
    """Test receiving a text message from WhatsApp."""
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

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_webhook_empty_payload(client: AsyncClient):
    """Test webhook with empty payload."""
    response = await client.post("/api/webhooks/whatsapp", json={})

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
                                    "type": "unsupported_type",
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


@pytest.mark.asyncio
async def test_webhook_rate_limit_enforced(client: AsyncClient):
    """Test that webhook POST endpoint enforces rate limit.

    Tests Issue #7 fix: webhook should reject requests exceeding configured limit.
    .env.test sets RATE_LIMIT_WEBHOOK=5/minute for easier testing.
    """
    payload = {
        "object": "whatsapp_business_account",
        "entry": [],
    }

    for i in range(5):
        response = await client.post("/api/webhooks/whatsapp", json=payload)
        assert response.status_code == 200, f"Request {i+1}/5 should succeed"

    response = await client.post("/api/webhooks/whatsapp", json=payload)
    assert response.status_code == 429, "6th request should be rate limited with 429 status"

    response_data = response.json()
    assert (
        "error" in response_data or "detail" in response_data
    ), "Error response should contain error details"


@pytest.mark.asyncio
async def test_status_update_delivered_persisted(
    client: AsyncClient, db_session: AsyncSession, whatsapp_account: WhatsAppAccount
):
    """Test that 'delivered' status update is persisted to database.

    Tests Issue #2 fix: _handle_status_update should save status to WhatsAppMessage.
    """

    org = Organization(name="Test Org Status")
    db_session.add(org)
    await db_session.flush()

    architect = Architect(
        organization_id=org.id,
        email="architect_status@test.com",
        hashed_password="hashed",
        phone="+5511888888888",
        is_authorized=True,
    )
    db_session.add(architect)
    await db_session.flush()

    end_client = EndClient(
        organization_id=org.id,
        architect_id=architect.id,
        name="Test Client Status",
        phone="+5511777777777",
    )
    db_session.add(end_client)
    await db_session.flush()

    session = WhatsAppSession(
        end_client_id=end_client.id,
        phone_number="+5511777777777",
        status=SessionStatus.ACTIVE.value,
    )
    db_session.add(session)
    await db_session.flush()

    message = WhatsAppMessage(
        session_id=session.id,
        wa_message_id="wamid.status_test_123",
        direction="outbound",
        status=MessageStatus.SENT.value,
        content={"text": {"body": "Test question"}},
    )
    db_session.add(message)
    await db_session.commit()

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
                                    "id": "wamid.status_test_123",
                                    "status": "delivered",
                                    "timestamp": "1234567890",
                                    "recipient_id": "5511777777777",
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

    await db_session.refresh(message)
    assert message.status == MessageStatus.DELIVERED.value
    assert message.delivered_at is not None
    assert message.read_at is None


@pytest.mark.asyncio
async def test_status_update_read_persisted(
    client: AsyncClient, db_session: AsyncSession, whatsapp_account: WhatsAppAccount
):
    """Test that 'read' status update is persisted to database."""

    org = Organization(name="Test Org Read")
    db_session.add(org)
    await db_session.flush()

    architect = Architect(
        organization_id=org.id,
        email="architect_read@test.com",
        hashed_password="hashed",
        phone="+5511888888888",
        is_authorized=True,
    )
    db_session.add(architect)
    await db_session.flush()

    end_client = EndClient(
        organization_id=org.id,
        architect_id=architect.id,
        name="Test Client Read",
        phone="+5511666666666",
    )
    db_session.add(end_client)
    await db_session.flush()

    session = WhatsAppSession(
        end_client_id=end_client.id,
        phone_number="+5511666666666",
        status=SessionStatus.ACTIVE.value,
    )
    db_session.add(session)
    await db_session.flush()

    message = WhatsAppMessage(
        session_id=session.id,
        wa_message_id="wamid.read_test_456",
        direction="outbound",
        status=MessageStatus.DELIVERED.value,
        content={"text": {"body": "Test question"}},
    )
    db_session.add(message)
    await db_session.commit()

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
                                    "id": "wamid.read_test_456",
                                    "status": "read",
                                    "timestamp": "1234567890",
                                    "recipient_id": "5511666666666",
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

    await db_session.refresh(message)
    assert message.status == MessageStatus.READ.value
    assert message.read_at is not None


@pytest.mark.asyncio
async def test_status_update_failed_persisted(
    client: AsyncClient, db_session: AsyncSession, whatsapp_account: WhatsAppAccount
):
    """Test that 'failed' status update with error details is persisted."""

    org = Organization(name="Test Org Failed")
    db_session.add(org)
    await db_session.flush()

    architect = Architect(
        organization_id=org.id,
        email="architect_failed@test.com",
        hashed_password="hashed",
        phone="+5511888888888",
        is_authorized=True,
    )
    db_session.add(architect)
    await db_session.flush()

    end_client = EndClient(
        organization_id=org.id,
        architect_id=architect.id,
        name="Test Client Failed",
        phone="+5511555555555",
    )
    db_session.add(end_client)
    await db_session.flush()

    session = WhatsAppSession(
        end_client_id=end_client.id,
        phone_number="+5511555555555",
        status=SessionStatus.ACTIVE.value,
    )
    db_session.add(session)
    await db_session.flush()

    message = WhatsAppMessage(
        session_id=session.id,
        wa_message_id="wamid.failed_test_789",
        direction="outbound",
        status=MessageStatus.SENT.value,
        content={"text": {"body": "Test question"}},
    )
    db_session.add(message)
    await db_session.commit()

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
                                    "id": "wamid.failed_test_789",
                                    "status": "failed",
                                    "timestamp": "1234567890",
                                    "recipient_id": "5511555555555",
                                    "errors": [
                                        {
                                            "code": 131047,
                                            "title": "Re-engagement message",
                                            "message": "Re-engagement message was not delivered because more than 24 hours have passed since the customer last replied to this number.",
                                        }
                                    ],
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

    await db_session.refresh(message)
    assert message.status == MessageStatus.FAILED.value
    assert message.error_code == "131047"
    assert "24 hours" in message.error_message


@pytest.mark.asyncio
async def test_status_update_message_not_found(
    client: AsyncClient, db_session: AsyncSession, whatsapp_account: WhatsAppAccount
):
    """Test that status update for non-existent message doesn't crash (logs warning)."""
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
                                    "id": "wamid.nonexistent_999",
                                    "status": "delivered",
                                    "timestamp": "1234567890",
                                    "recipient_id": "5511000000000",
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
