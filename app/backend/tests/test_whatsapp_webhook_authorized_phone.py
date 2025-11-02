"""Tests for WhatsApp webhook with authorized phone detection."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.architect import Architect
from src.db.models.authorized_phone import AuthorizedPhone
from src.db.models.briefing import Briefing, BriefingStatus
from src.db.models.briefing_template import BriefingTemplate
from src.db.models.end_client import EndClient
from src.db.models.organization import Organization
from src.db.models.project_type import ProjectType


@pytest.mark.asyncio
async def test_webhook_detects_authorized_phone_and_starts_briefing(
    client: AsyncClient,
    db_session: AsyncSession,
    test_organization: Organization,
    test_architect: Architect,
    test_project_type: ProjectType,
    test_template: BriefingTemplate,
):
    """Test that webhook detects authorized phone and starts briefing."""
    # Add WhatsApp settings to organization
    test_organization.settings = {
        "phone_number_id": "123456",
        "access_token": "test_token_123",
    }
    db_session.add(test_organization)

    # Add authorized phone
    auth_phone = AuthorizedPhone(
        organization_id=test_organization.id,
        phone_number="+5511987654321",
        added_by_architect_id=test_architect.id,
        is_active=True,
    )
    db_session.add(auth_phone)
    await db_session.commit()

    # Mock extraction service to return client info
    with patch("src.api.whatsapp_webhook.ExtractionService") as mock_extraction:
        mock_service = AsyncMock()
        mock_service.extract_client_info.return_value = type(
            "ExtractedInfo",
            (),
            {
                "name": "João Silva",
                "phone": "+5511999888777",
                "project_type": "residencial",
                "confidence": 0.95,
            },
        )()
        mock_extraction.return_value = mock_service

        # Mock WhatsApp service to avoid real API calls
        with patch("src.api.whatsapp_webhook.WhatsAppService") as mock_whatsapp:
            mock_wa_service = AsyncMock()
            mock_wa_service.send_text_message.return_value = {
                "success": True,
                "message_id": "wamid.test123",
            }
            mock_whatsapp.return_value = mock_wa_service

            # Send webhook from authorized phone
            webhook_payload = {
                "object": "whatsapp_business_account",
                "entry": [
                    {
                        "changes": [
                            {
                                "field": "messages",
                                "value": {
                                    "messaging_product": "whatsapp",
                                    "metadata": {"phone_number_id": "123456"},
                                    "messages": [
                                        {
                                            "from": "+5511987654321",
                                            "id": "wamid.incoming123",
                                            "timestamp": "1234567890",
                                            "type": "text",
                                            "text": {
                                                "body": "Cliente João Silva, tel 11999888777, quer fazer projeto residencial"
                                            },
                                        }
                                    ],
                                },
                            }
                        ]
                    }
                ],
            }

            response = await client.post("/api/webhooks/whatsapp", json=webhook_payload)

            assert response.status_code == 200

            # Verify briefing was created
            result = await db_session.execute(
                select(Briefing).join(EndClient).where(EndClient.phone == "+5511999888777")
            )
            briefing = result.scalar_one_or_none()

            assert briefing is not None
            assert briefing.status == BriefingStatus.IN_PROGRESS

            # Verify WhatsApp message was sent to client
            mock_wa_service.send_text_message.assert_called_once()
            call_args = mock_wa_service.send_text_message.call_args
            assert call_args[1]["to"] == "+5511999888777"  # Client phone, not authorized phone


@pytest.mark.asyncio
async def test_webhook_from_client_phone_processes_answer(
    client: AsyncClient,
    db_session: AsyncSession,
    test_organization: Organization,
    test_architect: Architect,
    test_end_client: EndClient,
    test_template: BriefingTemplate,
):
    """Test that webhook from client phone processes answer (existing behavior)."""
    # Create active briefing
    briefing = Briefing(
        end_client_id=test_end_client.id,
        template_version_id=test_template.current_version_id,
        status=BriefingStatus.IN_PROGRESS,
        current_question_order=1,
        answers={},
    )
    db_session.add(briefing)
    await db_session.commit()

    # Mock WhatsApp service
    with patch("src.services.briefing.answer_processor.WhatsAppService") as mock_whatsapp:
        mock_wa_service = AsyncMock()
        mock_wa_service.send_text_message.return_value = {
            "success": True,
            "message_id": "wamid.test456",
        }
        mock_whatsapp.return_value = mock_wa_service

        # Send webhook from client phone
        webhook_payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {"phone_number_id": "123456"},
                                "messages": [
                                    {
                                        "from": test_end_client.phone,
                                        "id": "wamid.incoming456",
                                        "timestamp": "1234567890",
                                        "type": "text",
                                        "text": {"body": "Casa"},
                                    }
                                ],
                            },
                        }
                    ]
                },
            ],
        }

        response = await client.post("/api/webhooks/whatsapp", json=webhook_payload)

        assert response.status_code == 200

        # Verify answer was processed
        await db_session.refresh(briefing)
        assert "1" in briefing.answers
        assert briefing.answers["1"] == "Casa"


@pytest.mark.asyncio
async def test_webhook_from_unknown_phone_does_nothing(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Test that webhook from unknown phone is ignored."""
    webhook_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": "123456"},
                            "messages": [
                                {
                                    "from": "+5511000000000",  # Unknown phone
                                    "id": "wamid.unknown",
                                    "timestamp": "1234567890",
                                    "type": "text",
                                    "text": {"body": "Hello"},
                                }
                            ],
                        },
                    }
                ]
            }
        ],
    }

    response = await client.post("/api/webhooks/whatsapp", json=webhook_payload)

    # Should still return 200 (to avoid WhatsApp retries)
    assert response.status_code == 200

    # Verify no briefing was created
    result = await db_session.execute(select(Briefing))
    briefings = result.scalars().all()
    assert len(briefings) == 0


@pytest.mark.asyncio
async def test_webhook_extraction_failure_sends_error_to_sender(
    client: AsyncClient,
    db_session: AsyncSession,
    test_organization: Organization,
    test_architect: Architect,
):
    """Test that extraction failure sends error message back to authorized phone."""
    # Add WhatsApp settings to organization
    test_organization.settings = {
        "phone_number_id": "123456",
        "access_token": "test_token_123",
    }
    db_session.add(test_organization)

    # Add authorized phone
    auth_phone = AuthorizedPhone(
        organization_id=test_organization.id,
        phone_number="+5511987654321",
        added_by_architect_id=test_architect.id,
        is_active=True,
    )
    db_session.add(auth_phone)
    await db_session.commit()

    # Mock extraction service to return low confidence
    with patch("src.api.whatsapp_webhook.ExtractionService") as mock_extraction:
        mock_service = AsyncMock()
        mock_service.extract_client_info.return_value = type(
            "ExtractedInfo",
            (),
            {
                "name": None,
                "phone": None,
                "project_type": None,
                "confidence": 0.3,  # Low confidence
            },
        )()
        mock_extraction.return_value = mock_service

        # Mock WhatsApp service
        with patch("src.api.whatsapp_webhook.WhatsAppService") as mock_whatsapp:
            mock_wa_service = AsyncMock()
            mock_wa_service.send_text_message.return_value = {
                "success": True,
                "message_id": "wamid.error",
            }
            mock_whatsapp.return_value = mock_wa_service

            webhook_payload = {
                "object": "whatsapp_business_account",
                "entry": [
                    {
                        "changes": [
                            {
                                "field": "messages",
                                "value": {
                                    "messaging_product": "whatsapp",
                                    "metadata": {"phone_number_id": "123456"},
                                    "messages": [
                                        {
                                            "from": "+5511987654321",
                                            "id": "wamid.bad",
                                            "timestamp": "1234567890",
                                            "type": "text",
                                            "text": {"body": "msg confusa sem dados"},
                                        }
                                    ],
                                },
                            }
                        ]
                    }
                ],
            }

            response = await client.post("/api/webhooks/whatsapp", json=webhook_payload)

            assert response.status_code == 200

            # Verify error message was sent back to authorized phone
            mock_wa_service.send_text_message.assert_called_once()
            call_args = mock_wa_service.send_text_message.call_args
            assert call_args[1]["to"] == "+5511987654321"  # Back to sender
            assert "erro" in call_args[1]["text"].lower() or "dados" in call_args[1]["text"].lower()
