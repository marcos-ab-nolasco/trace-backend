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
from src.db.models.template_version import TemplateVersion

TEST_TOKEN_ABC = "gAAAAABpD51IfAJp9XpUYWHmCx0gMDsRH0khVM99XovlHDcjkQLVr77FZ0Xsqm7rfgDNVW2edr4UnGTBzcvF7bVgJ9ptkKvJyg=="


@pytest.mark.asyncio
async def test_e2e_complete_briefing_flow_from_authorized_phone(
    client: AsyncClient,
    db_session: AsyncSession,
    test_organization: Organization,
    test_architect: Architect,
    test_template: BriefingTemplate,
):
    """Test complete E2E flow: architect initiates briefing, client answers all questions."""
    test_organization.settings = {
        "phone_number_id": "test_phone_123",
        "access_token": TEST_TOKEN_ABC,
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

        mock_whatsapp_instance = AsyncMock()
        mock_whatsapp_instance.send_text_message.return_value = {
            "success": True,
            "message_id": "wamid.test",
        }
        mock_whatsapp.return_value = mock_whatsapp_instance

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

        result = await db_session.execute(
            select(Briefing).join(EndClient).where(EndClient.phone == "+5511999888777")
        )
        briefing = result.scalar_one()
        assert briefing.status == BriefingStatus.IN_PROGRESS
        assert briefing.current_question_order == 1
        assert briefing.answers == {}

        result = await db_session.execute(
            select(EndClient).where(EndClient.phone == "+5511999888777")
        )
        end_client = result.scalar_one()
        assert end_client.name == "João Silva"
        assert end_client.organization_id == test_organization.id

        mock_whatsapp_instance.send_text_message.assert_called()
        last_call = mock_whatsapp_instance.send_text_message.call_args
        assert last_call.kwargs["to"] == "+5511999888777"

        mock_whatsapp_instance.reset_mock()

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

        await db_session.refresh(briefing)
        assert briefing.status == BriefingStatus.COMPLETED
        assert briefing.current_question_order == 4
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
    test_organization.settings = {
        "phone_number_id": "test_phone_123",
        "access_token": TEST_TOKEN_ABC,
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
        mock_extraction_instance = AsyncMock()
        mock_extraction_instance.extract_client_info.return_value = type(
            "ExtractedInfo",
            (),
            {
                "name": None,
                "phone": None,
                "project_type": None,
                "confidence": 0.2,
            },
        )()
        mock_extraction.return_value = mock_extraction_instance

        mock_whatsapp_instance = AsyncMock()
        mock_whatsapp_instance.send_text_message.return_value = {
            "success": True,
            "message_id": "wamid.error",
        }
        mock_whatsapp.return_value = mock_whatsapp_instance

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

        result = await db_session.execute(select(Briefing))
        briefings = result.scalars().all()
        assert len(briefings) == 0

        mock_whatsapp_instance.send_text_message.assert_called_once()
        call_args = mock_whatsapp_instance.send_text_message.call_args
        assert call_args.kwargs["to"] == "+5511987654321"
        assert "não consegui extrair" in call_args.kwargs["text"].lower()


@pytest.mark.asyncio
async def test_e2e_duplicate_briefing_resumes_existing(
    client: AsyncClient,
    db_session: AsyncSession,
    test_organization: Organization,
    test_architect: Architect,
    test_template: BriefingTemplate,
):
    """Test that system resumes existing briefing instead of creating duplicate."""
    test_organization.settings = {
        "phone_number_id": "test_phone_123",
        "access_token": TEST_TOKEN_ABC,
    }
    db_session.add(test_organization)

    auth_phone = AuthorizedPhone(
        organization_id=test_organization.id,
        phone_number="+5511987654321",
        added_by_architect_id=test_architect.id,
        is_active=True,
    )
    db_session.add(auth_phone)

    existing_client = EndClient(
        name="João Silva",
        phone="+5511999888777",
        organization_id=test_organization.id,
        architect_id=test_architect.id,
    )
    db_session.add(existing_client)
    await db_session.flush()

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

        mock_whatsapp_instance = AsyncMock()
        mock_whatsapp_instance.send_text_message.return_value = {
            "success": True,
            "message_id": "wamid.error",
        }
        mock_whatsapp.return_value = mock_whatsapp_instance

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

        result = await db_session.execute(select(Briefing))
        briefings = result.scalars().all()
        assert len(briefings) == 1
        assert briefings[0].id == existing_briefing.id

        mock_whatsapp_instance.send_text_message.assert_called_once()
        call_args = mock_whatsapp_instance.send_text_message.call_args
        assert call_args.kwargs["to"] == "+5511999888777"
        assert "já possui um briefing ativo" not in call_args.kwargs["text"].lower()


@pytest.mark.asyncio
async def test_e2e_unknown_phone_ignored(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Test that messages from unknown phones are ignored."""

    with patch("src.api.whatsapp_webhook.WhatsAppService") as mock_whatsapp:
        mock_whatsapp_instance = AsyncMock()
        mock_whatsapp.return_value = mock_whatsapp_instance

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
                                        "from": "+5511000000000",
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

        assert response.status_code == 200

        result = await db_session.execute(select(Briefing))
        briefings = result.scalars().all()
        assert len(briefings) == 0

        mock_whatsapp_instance.send_text_message.assert_not_called()
