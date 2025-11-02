"""End-to-end tests for complete WhatsApp briefing flows."""

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


@pytest.mark.asyncio
async def test_e2e_complete_briefing_flow_from_authorized_phone(
    client: AsyncClient,
    db_session: AsyncSession,
    test_organization: Organization,
    test_architect: Architect,
    test_template: BriefingTemplate,
):
    """Test complete E2E flow: architect initiates briefing, client answers all questions."""
    # Setup: Add WhatsApp settings to organization
    test_organization.settings = {
        "phone_number_id": "test_phone_123",
        "access_token": "test_token_abc",
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

    # Mock extraction and WhatsApp services
    with (
        patch("src.api.whatsapp_webhook.ExtractionService") as mock_extraction,
        patch("src.api.whatsapp_webhook.WhatsAppService") as mock_whatsapp,
    ):
        # Configure extraction mock
        mock_extraction_instance = AsyncMock()
        mock_extraction_instance.extract_client_info.return_value = type(
            "ExtractedInfo",
            (),
            {
                "name": "João Silva",
                "phone": "+5511999888777",
                "project_type": "residencial",
                "confidence": 0.95,
            },
        )()
        mock_extraction.return_value = mock_extraction_instance

        # Configure WhatsApp mock
        mock_whatsapp_instance = AsyncMock()
        mock_whatsapp_instance.send_text_message.return_value = {
            "success": True,
            "message_id": "wamid.test",
        }
        mock_whatsapp.return_value = mock_whatsapp_instance

        # STEP 1: Architect sends message to initiate briefing
        webhook_payload_init = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {"phone_number_id": "test_phone_123"},
                                "messages": [
                                    {
                                        "from": "+5511987654321",
                                        "id": "wamid.init",
                                        "timestamp": "1234567890",
                                        "type": "text",
                                        "text": {
                                            "body": "Cliente João Silva, tel 11999888777, projeto residencial"
                                        },
                                    }
                                ],
                            },
                        }
                    ]
                }
            ],
        }

        response = await client.post("/api/webhooks/whatsapp", json=webhook_payload_init)
        assert response.status_code == 200

        # Verify: Briefing created
        result = await db_session.execute(
            select(Briefing).join(EndClient).where(EndClient.phone == "+5511999888777")
        )
        briefing = result.scalar_one()
        assert briefing.status == BriefingStatus.IN_PROGRESS
        assert briefing.current_question_order == 1  # Starts at question 1
        assert briefing.answers == {}

        # Verify: EndClient created
        result = await db_session.execute(
            select(EndClient).where(EndClient.phone == "+5511999888777")
        )
        end_client = result.scalar_one()
        assert end_client.name == "João Silva"
        assert end_client.organization_id == test_organization.id

        # Verify: First question sent to CLIENT (not architect)
        mock_whatsapp_instance.send_text_message.assert_called()
        last_call = mock_whatsapp_instance.send_text_message.call_args
        assert last_call.kwargs["to"] == "+5511999888777"  # Sent to client

        # Reset mock for next steps
        mock_whatsapp_instance.reset_mock()

        # STEP 2: Client answers question 1
        webhook_payload_q1 = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {"phone_number_id": "test_phone_123"},
                                "messages": [
                                    {
                                        "from": "+5511999888777",
                                        "id": "wamid.answer1",
                                        "timestamp": "1234567891",
                                        "type": "text",
                                        "text": {"body": "Casa de 150m2"},
                                    }
                                ],
                            },
                        }
                    ]
                }
            ],
        }

        response = await client.post("/api/webhooks/whatsapp", json=webhook_payload_q1)
        assert response.status_code == 200

        await db_session.refresh(briefing)
        assert briefing.current_question_order == 2
        assert "1" in briefing.answers
        assert briefing.answers["1"] == "Casa de 150m2"
        assert briefing.status == BriefingStatus.IN_PROGRESS

        # STEP 3: Client answers question 2
        mock_whatsapp_instance.reset_mock()
        webhook_payload_q2 = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {"phone_number_id": "test_phone_123"},
                                "messages": [
                                    {
                                        "from": "+5511999888777",
                                        "id": "wamid.answer2",
                                        "timestamp": "1234567892",
                                        "type": "text",
                                        "text": {"body": "3 quartos"},
                                    }
                                ],
                            },
                        }
                    ]
                }
            ],
        }

        response = await client.post("/api/webhooks/whatsapp", json=webhook_payload_q2)
        assert response.status_code == 200

        await db_session.refresh(briefing)
        assert briefing.current_question_order == 3
        assert "2" in briefing.answers
        assert briefing.answers["2"] == "3 quartos"
        assert briefing.status == BriefingStatus.IN_PROGRESS

        # STEP 4: Client answers question 3 (last question)
        mock_whatsapp_instance.reset_mock()
        webhook_payload_q3 = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {"phone_number_id": "test_phone_123"},
                                "messages": [
                                    {
                                        "from": "+5511999888777",
                                        "id": "wamid.answer3",
                                        "timestamp": "1234567893",
                                        "type": "text",
                                        "text": {"body": "Sim, tenho o terreno"},
                                    }
                                ],
                            },
                        }
                    ]
                }
            ],
        }

        response = await client.post("/api/webhooks/whatsapp", json=webhook_payload_q3)
        assert response.status_code == 200

        # Verify: Briefing completed
        await db_session.refresh(briefing)
        assert briefing.status == BriefingStatus.COMPLETED
        assert briefing.current_question_order == 4  # Advanced past last question
        assert len(briefing.answers) == 3
        assert "3" in briefing.answers
        assert briefing.answers["3"] == "Sim, tenho o terreno"


@pytest.mark.asyncio
async def test_e2e_extraction_failure_sends_error_to_architect(
    client: AsyncClient,
    db_session: AsyncSession,
    test_organization: Organization,
    test_architect: Architect,
):
    """Test that extraction failure sends error message back to architect."""
    # Setup
    test_organization.settings = {
        "phone_number_id": "test_phone_123",
        "access_token": "test_token_abc",
    }
    db_session.add(test_organization)

    auth_phone = AuthorizedPhone(
        organization_id=test_organization.id,
        phone_number="+5511987654321",
        added_by_architect_id=test_architect.id,
        is_active=True,
    )
    db_session.add(auth_phone)
    await db_session.commit()

    with (
        patch("src.api.whatsapp_webhook.ExtractionService") as mock_extraction,
        patch("src.api.whatsapp_webhook.WhatsAppService") as mock_whatsapp,
    ):
        # Configure extraction mock to return low confidence
        mock_extraction_instance = AsyncMock()
        mock_extraction_instance.extract_client_info.return_value = type(
            "ExtractedInfo",
            (),
            {
                "name": None,
                "phone": None,
                "project_type": None,
                "confidence": 0.2,  # Low confidence
            },
        )()
        mock_extraction.return_value = mock_extraction_instance

        # Configure WhatsApp mock
        mock_whatsapp_instance = AsyncMock()
        mock_whatsapp_instance.send_text_message.return_value = {
            "success": True,
            "message_id": "wamid.error",
        }
        mock_whatsapp.return_value = mock_whatsapp_instance

        # Send confusing message from architect
        webhook_payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {"phone_number_id": "test_phone_123"},
                                "messages": [
                                    {
                                        "from": "+5511987654321",
                                        "id": "wamid.confusing",
                                        "timestamp": "1234567890",
                                        "type": "text",
                                        "text": {"body": "oi tudo bem?"},
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

        # Verify: No briefing created
        result = await db_session.execute(select(Briefing))
        briefings = result.scalars().all()
        assert len(briefings) == 0

        # Verify: Error message sent back to ARCHITECT (not client)
        mock_whatsapp_instance.send_text_message.assert_called_once()
        call_args = mock_whatsapp_instance.send_text_message.call_args
        assert call_args.kwargs["to"] == "+5511987654321"  # Sent to architect
        assert "não consegui extrair" in call_args.kwargs["text"].lower()


@pytest.mark.asyncio
async def test_e2e_duplicate_briefing_blocked(
    client: AsyncClient,
    db_session: AsyncSession,
    test_organization: Organization,
    test_architect: Architect,
    test_template: BriefingTemplate,
):
    """Test that system blocks duplicate briefings for same client."""
    # Setup
    test_organization.settings = {
        "phone_number_id": "test_phone_123",
        "access_token": "test_token_abc",
    }
    db_session.add(test_organization)

    auth_phone = AuthorizedPhone(
        organization_id=test_organization.id,
        phone_number="+5511987654321",
        added_by_architect_id=test_architect.id,
        is_active=True,
    )
    db_session.add(auth_phone)

    # Create existing active briefing for client
    existing_client = EndClient(
        name="João Silva",
        phone="+5511999888777",
        organization_id=test_organization.id,
        architect_id=test_architect.id,
    )
    db_session.add(existing_client)
    await db_session.flush()

    # Get template version
    from src.db.models.template_version import TemplateVersion

    result = await db_session.execute(
        select(TemplateVersion).where(TemplateVersion.template_id == test_template.id)
    )
    template_version = result.scalar_one()

    existing_briefing = Briefing(
        end_client_id=existing_client.id,
        template_version_id=template_version.id,
        status=BriefingStatus.IN_PROGRESS,
        current_question_order=1,
        answers={},
    )
    db_session.add(existing_briefing)
    await db_session.commit()

    with (
        patch("src.api.whatsapp_webhook.ExtractionService") as mock_extraction,
        patch("src.api.whatsapp_webhook.WhatsAppService") as mock_whatsapp,
    ):
        # Configure mocks
        mock_extraction_instance = AsyncMock()
        mock_extraction_instance.extract_client_info.return_value = type(
            "ExtractedInfo",
            (),
            {
                "name": "João Silva",
                "phone": "+5511999888777",  # Same client
                "project_type": "residencial",
                "confidence": 0.95,
            },
        )()
        mock_extraction.return_value = mock_extraction_instance

        mock_whatsapp_instance = AsyncMock()
        mock_whatsapp_instance.send_text_message.return_value = {
            "success": True,
            "message_id": "wamid.error",
        }
        mock_whatsapp.return_value = mock_whatsapp_instance

        # Architect tries to start new briefing for same client
        webhook_payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {"phone_number_id": "test_phone_123"},
                                "messages": [
                                    {
                                        "from": "+5511987654321",
                                        "id": "wamid.duplicate",
                                        "timestamp": "1234567890",
                                        "type": "text",
                                        "text": {
                                            "body": "Cliente João Silva, tel 11999888777, projeto residencial"
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

        # Verify: Only one briefing exists (the original)
        result = await db_session.execute(select(Briefing))
        briefings = result.scalars().all()
        assert len(briefings) == 1
        assert briefings[0].id == existing_briefing.id

        # Verify: Error message sent to architect
        mock_whatsapp_instance.send_text_message.assert_called_once()
        call_args = mock_whatsapp_instance.send_text_message.call_args
        assert call_args.kwargs["to"] == "+5511987654321"
        assert "já possui um briefing ativo" in call_args.kwargs["text"].lower()


@pytest.mark.asyncio
async def test_e2e_unknown_phone_ignored(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Test that messages from unknown phones are ignored."""
    # No setup - no authorized phones, no clients with briefings

    with patch("src.api.whatsapp_webhook.WhatsAppService") as mock_whatsapp:
        mock_whatsapp_instance = AsyncMock()
        mock_whatsapp.return_value = mock_whatsapp_instance

        # Send message from unknown phone
        webhook_payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {"phone_number_id": "test_phone_123"},
                                "messages": [
                                    {
                                        "from": "+5511000000000",  # Unknown
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

        # Verify: Returns 200 (to avoid WhatsApp retries)
        assert response.status_code == 200

        # Verify: No briefings created
        result = await db_session.execute(select(Briefing))
        briefings = result.scalars().all()
        assert len(briefings) == 0

        # Verify: No WhatsApp messages sent
        mock_whatsapp_instance.send_text_message.assert_not_called()
