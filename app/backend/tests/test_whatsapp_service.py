"""Tests for WhatsApp message sending service."""

import pytest
from httpx import AsyncClient as HttpxAsyncClient
from httpx import Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.organization import Organization
from src.db.models.organization_whatsapp_account import OrganizationWhatsAppAccount
from src.db.models.whatsapp_account import WhatsAppAccount
from src.services.whatsapp.whatsapp_service import WhatsAppService


@pytest.fixture
async def whatsapp_account(db_session: AsyncSession) -> WhatsAppAccount:
    """Create test WhatsApp account with organization link."""
    org = Organization(name="Test Org")
    db_session.add(org)
    await db_session.flush()

    account = WhatsAppAccount(
        phone_number_id="test_phone_123",
        phone_number="+5511999999999",
        access_token="test_access_token",
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


@pytest.fixture
def whatsapp_service(whatsapp_account: WhatsAppAccount) -> WhatsAppService:
    """Create WhatsApp service instance."""
    return WhatsAppService(
        phone_number_id=whatsapp_account.phone_number_id,
        access_token=whatsapp_account.access_token,
    )


# Send Text Message Tests
@pytest.mark.asyncio
async def test_send_text_message_success(whatsapp_service: WhatsAppService, mocker):
    """Test sending a text message successfully."""
    # Mock httpx client
    mock_response = Response(
        200,
        json={
            "messaging_product": "whatsapp",
            "contacts": [{"input": "5511999999999", "wa_id": "5511999999999"}],
            "messages": [{"id": "wamid.test123"}],
        },
    )
    mock_post = mocker.patch("httpx.AsyncClient.post", return_value=mock_response)

    result = await whatsapp_service.send_text_message(
        to="+5511999999999", text="Hello, this is a test message"
    )

    assert result["success"] is True
    assert result["message_id"] == "wamid.test123"
    assert mock_post.called

    # Verify API call
    call_args = mock_post.call_args
    assert "5511999999999" in str(call_args)
    assert "Hello, this is a test message" in str(call_args)


@pytest.mark.asyncio
async def test_send_text_message_api_error(whatsapp_service: WhatsAppService, mocker):
    """Test handling API error when sending text message."""
    # Mock httpx client to return error
    mock_response = Response(
        400,
        json={
            "error": {
                "message": "Invalid phone number",
                "type": "OAuthException",
                "code": 100,
            }
        },
    )
    mocker.patch("httpx.AsyncClient.post", return_value=mock_response)

    result = await whatsapp_service.send_text_message(
        to="invalid", text="Test"
    )

    assert result["success"] is False
    assert "error" in result
    assert "Invalid phone number" in result["error"]


@pytest.mark.asyncio
async def test_send_text_message_with_preview_url(whatsapp_service: WhatsAppService, mocker):
    """Test sending text message with URL preview enabled."""
    mock_response = Response(
        200,
        json={
            "messaging_product": "whatsapp",
            "contacts": [{"input": "5511999999999", "wa_id": "5511999999999"}],
            "messages": [{"id": "wamid.test456"}],
        },
    )
    mock_post = mocker.patch("httpx.AsyncClient.post", return_value=mock_response)

    result = await whatsapp_service.send_text_message(
        to="+5511999999999",
        text="Check this out: https://example.com",
        preview_url=True,
    )

    assert result["success"] is True

    # Verify preview_url was sent
    call_json = mock_post.call_args.kwargs.get("json", {})
    assert call_json.get("text", {}).get("preview_url") is True


# Send Template Message Tests
@pytest.mark.asyncio
async def test_send_template_message_success(whatsapp_service: WhatsAppService, mocker):
    """Test sending a template message successfully."""
    mock_response = Response(
        200,
        json={
            "messaging_product": "whatsapp",
            "contacts": [{"input": "5511999999999", "wa_id": "5511999999999"}],
            "messages": [{"id": "wamid.template123"}],
        },
    )
    mock_post = mocker.patch("httpx.AsyncClient.post", return_value=mock_response)

    result = await whatsapp_service.send_template_message(
        to="+5511999999999",
        template_name="hello_world",
        language_code="pt_BR",
    )

    assert result["success"] is True
    assert result["message_id"] == "wamid.template123"

    # Verify template structure
    call_json = mock_post.call_args.kwargs.get("json", {})
    assert call_json["type"] == "template"
    assert call_json["template"]["name"] == "hello_world"
    assert call_json["template"]["language"]["code"] == "pt_BR"


@pytest.mark.asyncio
async def test_send_template_message_with_components(whatsapp_service: WhatsAppService, mocker):
    """Test sending template message with parameter components."""
    mock_response = Response(
        200,
        json={
            "messaging_product": "whatsapp",
            "messages": [{"id": "wamid.template456"}],
        },
    )
    mock_post = mocker.patch("httpx.AsyncClient.post", return_value=mock_response)

    components = [
        {
            "type": "body",
            "parameters": [{"type": "text", "text": "John Doe"}],
        }
    ]

    result = await whatsapp_service.send_template_message(
        to="+5511999999999",
        template_name="welcome_message",
        language_code="en",
        components=components,
    )

    assert result["success"] is True

    # Verify components were sent
    call_json = mock_post.call_args.kwargs.get("json", {})
    assert call_json["template"]["components"] == components


# Mark as Read Tests
@pytest.mark.asyncio
async def test_mark_message_as_read_success(whatsapp_service: WhatsAppService, mocker):
    """Test marking a message as read successfully."""
    mock_response = Response(
        200,
        json={"success": True},
    )
    mock_post = mocker.patch("httpx.AsyncClient.post", return_value=mock_response)

    result = await whatsapp_service.mark_as_read(message_id="wamid.abc123")

    assert result["success"] is True

    # Verify API call
    call_json = mock_post.call_args.kwargs.get("json", {})
    assert call_json["messaging_product"] == "whatsapp"
    assert call_json["status"] == "read"
    assert call_json["message_id"] == "wamid.abc123"


@pytest.mark.asyncio
async def test_mark_message_as_read_api_error(whatsapp_service: WhatsAppService, mocker):
    """Test handling error when marking message as read."""
    mock_response = Response(
        400,
        json={"error": {"message": "Message not found"}},
    )
    mocker.patch("httpx.AsyncClient.post", return_value=mock_response)

    result = await whatsapp_service.mark_as_read(message_id="invalid_id")

    assert result["success"] is False
    assert "error" in result


# Phone Number Formatting Tests
@pytest.mark.asyncio
async def test_phone_number_formatting(whatsapp_service: WhatsAppService, mocker):
    """Test phone number is properly formatted (removes + and spaces)."""
    mock_response = Response(
        200,
        json={"messages": [{"id": "wamid.test"}]},
    )
    mock_post = mocker.patch("httpx.AsyncClient.post", return_value=mock_response)

    # Test with +, spaces, and dashes
    await whatsapp_service.send_text_message(
        to="+55 (11) 99999-9999", text="Test"
    )

    call_json = mock_post.call_args.kwargs.get("json", {})
    # Should be cleaned to just digits
    assert call_json["to"] == "5511999999999"


# API URL Construction Tests
def test_messages_api_url(whatsapp_service: WhatsAppService):
    """Test messages API URL is correctly constructed."""
    expected_url = f"https://graph.facebook.com/v18.0/{whatsapp_service.phone_number_id}/messages"
    assert whatsapp_service._get_messages_url() == expected_url


# Retry Logic Tests
@pytest.mark.asyncio
async def test_send_message_retries_on_network_error(whatsapp_service: WhatsAppService, mocker):
    """Test service retries on network errors."""
    # First call fails, second succeeds
    mock_post = mocker.patch(
        "httpx.AsyncClient.post",
        side_effect=[
            Exception("Network error"),
            Response(200, json={"messages": [{"id": "wamid.retry123"}]}),
        ],
    )

    result = await whatsapp_service.send_text_message(
        to="+5511999999999", text="Test retry"
    )

    assert result["success"] is True
    assert result["message_id"] == "wamid.retry123"
    assert mock_post.call_count == 2  # Should have retried once


@pytest.mark.asyncio
async def test_send_message_fails_after_max_retries(whatsapp_service: WhatsAppService, mocker):
    """Test service gives up after max retries."""
    # All calls fail
    mocker.patch(
        "httpx.AsyncClient.post",
        side_effect=Exception("Network error"),
    )

    result = await whatsapp_service.send_text_message(
        to="+5511999999999", text="Test"
    )

    assert result["success"] is False
    assert "error" in result
