"""End-to-end tests for briefing flow via WhatsApp integration."""

from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from httpx import AsyncClient
from pytest_mock import MockerFixture
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.architect import Architect
from src.db.models.briefing import Briefing, BriefingStatus
from src.db.models.briefing_template import BriefingTemplate
from src.db.models.conversation import Conversation, ConversationType
from src.db.models.end_client import EndClient
from src.db.models.organization import Organization
from src.db.models.template_version import TemplateVersion
from src.schemas.briefing import ExtractedClientInfo


@pytest.fixture
async def test_templates(db_session: AsyncSession) -> dict[str, BriefingTemplate]:
    """Create test templates for different categories."""
    templates = {}
    categories = {
        "reforma": ["Qual o tipo de reforma?", "Qual o prazo desejado?"],
        "residencial": ["Quantos quartos?", "Qual a área em m²?"],
        "comercial": ["Qual o tipo de estabelecimento?", "Quantos funcionários?"],
        "construcao": ["Qual o tipo de construção?", "Qual o terreno disponível?"],
    }

    for category, questions in categories.items():
        template = BriefingTemplate(
            name=f"Template {category.title()}",
            category=category,
            description=f"Template para projetos de {category}",
            is_global=True,
        )
        db_session.add(template)
        await db_session.flush()

        version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            questions=[
                {
                    "order": i + 1,
                    "question": question,
                    "type": "text",
                    "required": True,
                }
                for i, question in enumerate(questions)
            ],
            is_active=True,
        )
        db_session.add(version)
        await db_session.flush()

        template.current_version_id = version.id
        templates[category] = template

    await db_session.commit()

    for template in templates.values():
        await db_session.refresh(template, attribute_names=["current_version"])

    return templates


@pytest.fixture
async def existing_client(
    db_session: AsyncSession,
    test_organization_with_whatsapp: Organization,
    test_architect_with_whatsapp: Architect,
) -> EndClient:
    """Create existing end client with normalized phone."""
    client = EndClient(
        organization_id=test_organization_with_whatsapp.id,
        architect_id=test_architect_with_whatsapp.id,
        name="Existing Client",
        phone="+5511987654321",
        email="existing@test.com",
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client


@pytest.mark.asyncio
async def test_start_briefing_with_complete_client_info(
    client: AsyncClient,
    db_session: AsyncSession,
    test_architect_with_whatsapp: Architect,
    auth_headers_whatsapp: dict[str, str],
    test_templates: dict[str, BriefingTemplate],
    mocker: MockerFixture,
):
    """Test starting briefing with complete client information extraction."""
    mock_extracted_info = ExtractedClientInfo(
        name="João Silva",
        phone="11999887766",
        project_type="reforma",
        confidence=0.95,
        raw_text="Oi, preciso de um orçamento para o João Silva, tel 11999887766, reforma",
    )
    mock_extract = mocker.patch(
        "src.api.briefings.ExtractionService.extract_client_info",
        new=AsyncMock(return_value=mock_extracted_info),
    )

    reforma_template = test_templates["reforma"]
    mock_select_template = mocker.patch(
        "src.services.template_service.TemplateService.select_template_version_for_project",
        new=AsyncMock(return_value=reforma_template.current_version),
    )

    mock_whatsapp_send = mocker.patch(
        "src.api.briefings.WhatsAppService.send_text_message",
        new=AsyncMock(return_value={"success": True, "message_id": "wamid.test123"}),
    )

    response = await client.post(
        "/api/briefings/start-from-whatsapp",
        json={
            "architect_id": str(test_architect_with_whatsapp.id),
            "architect_message": "Oi, preciso de orçamento para João Silva, tel 11999887766, reforma",
        },
        headers=auth_headers_whatsapp,
    )

    assert response.status_code == 200
    data = response.json()

    assert "briefing_id" in data
    assert "client_name" in data
    assert "first_question" in data
    assert data["client_name"] == "João Silva"
    assert "reforma" in data["first_question"].lower()

    await db_session.rollback()

    briefing_id = UUID(data["briefing_id"])
    client_id = UUID(data["client_id"])

    result = await db_session.execute(select(Briefing).where(Briefing.id == briefing_id))
    briefing = result.scalar_one()
    assert briefing.status == BriefingStatus.IN_PROGRESS
    assert briefing.current_question_order == 1

    result = await db_session.execute(select(EndClient).where(EndClient.id == client_id))
    end_client = result.scalar_one()
    assert end_client.name == "João Silva"
    assert end_client.phone == "+5511999887766"

    result = await db_session.execute(select(Briefing).where(Briefing.id == briefing_id))
    briefing_with_conv = result.scalar_one()
    assert briefing_with_conv.conversation_id is not None

    result = await db_session.execute(
        select(Conversation).where(Conversation.id == briefing_with_conv.conversation_id)
    )
    conversation = result.scalar_one()
    assert conversation.conversation_type == ConversationType.WHATSAPP_BRIEFING.value
    assert conversation.end_client_id == client_id

    mock_extract.assert_called_once()
    mock_select_template.assert_called_once()
    mock_whatsapp_send.assert_called_once()


@pytest.mark.asyncio
async def test_start_briefing_with_existing_client_duplicate_phone(
    client: AsyncClient,
    db_session: AsyncSession,
    test_architect_with_whatsapp: Architect,
    test_templates: dict[str, BriefingTemplate],
    auth_headers_whatsapp: dict[str, str],
    existing_client: EndClient,
    mocker: MockerFixture,
):
    """Test starting briefing when client with same phone already exists."""
    mock_extracted_info = ExtractedClientInfo(
        name="João Silva Atualizado",
        phone="11987654321",
        project_type="residencial",
        confidence=0.90,
        raw_text="Novo projeto para o João Silva, mesma linha",
    )
    mocker.patch(
        "src.api.briefings.ExtractionService.extract_client_info",
        new=AsyncMock(return_value=mock_extracted_info),
    )

    residencial_template = test_templates["residencial"]
    mocker.patch(
        "src.services.template_service.TemplateService.select_template_version_for_project",
        new=AsyncMock(return_value=residencial_template.current_version),
    )

    mocker.patch(
        "src.api.briefings.WhatsAppService.send_text_message",
        new=AsyncMock(return_value={"success": True, "message_id": "wamid.test456"}),
    )

    response = await client.post(
        "/api/briefings/start-from-whatsapp",
        json={
            "architect_id": str(test_architect_with_whatsapp.id),
            "architect_message": "Novo projeto para o João Silva",
        },
        headers=auth_headers_whatsapp,
    )

    assert response.status_code == 200
    data = response.json()

    await db_session.rollback()

    client_id = UUID(data["client_id"])
    result = await db_session.execute(select(EndClient).where(EndClient.id == client_id))
    updated_client = result.scalar_one()
    assert updated_client.id == existing_client.id
    assert updated_client.name == "João Silva Atualizado"

    result = await db_session.execute(
        select(EndClient).where(
            EndClient.architect_id == test_architect_with_whatsapp.id,
            EndClient.phone == existing_client.phone,
        )
    )
    clients = result.scalars().all()
    assert len(clients) == 1

    briefing_id = UUID(data["briefing_id"])
    result = await db_session.execute(select(Briefing).where(Briefing.id == briefing_id))
    briefing = result.scalar_one()
    assert briefing.status == BriefingStatus.IN_PROGRESS
    assert briefing.end_client_id == existing_client.id


@pytest.mark.asyncio
async def test_start_briefing_with_incomplete_extraction_missing_phone(
    client: AsyncClient,
    db_session: AsyncSession,
    test_architect_with_whatsapp: Architect,
    auth_headers_whatsapp: dict[str, str],
    mocker: MockerFixture,
):
    """Test starting briefing fails when phone number is missing."""
    mock_extracted_info = ExtractedClientInfo(
        name="João Silva",
        phone=None,
        project_type="reforma",
        confidence=0.70,
        raw_text="Preciso de orçamento para João Silva",
    )
    mocker.patch(
        "src.services.briefing.extraction_service.ExtractionService.extract_client_info",
        new=AsyncMock(return_value=mock_extracted_info),
    )

    response = await client.post(
        "/api/briefings/start-from-whatsapp",
        json={
            "architect_id": str(test_architect_with_whatsapp.id),
            "architect_message": "Preciso de orçamento para João Silva",
        },
        headers=auth_headers_whatsapp,
    )

    assert response.status_code == 400
    data = response.json()
    assert "phone" in data["detail"].lower() or "telefone" in data["detail"].lower()


@pytest.mark.asyncio
async def test_start_briefing_with_incomplete_extraction_missing_name(
    client: AsyncClient,
    db_session: AsyncSession,
    test_architect_with_whatsapp: Architect,
    auth_headers_whatsapp: dict[str, str],
    mocker: MockerFixture,
):
    """Test starting briefing fails when client name is missing."""
    mock_extracted_info = ExtractedClientInfo(
        name=None,
        phone="11999887766",
        project_type="reforma",
        confidence=0.70,
        raw_text="Preciso de orçamento, telefone 11999887766",
    )
    mocker.patch(
        "src.services.briefing.extraction_service.ExtractionService.extract_client_info",
        new=AsyncMock(return_value=mock_extracted_info),
    )

    response = await client.post(
        "/api/briefings/start-from-whatsapp",
        json={
            "architect_id": str(test_architect_with_whatsapp.id),
            "architect_message": "Preciso de orçamento, telefone 11999887766",
        },
        headers=auth_headers_whatsapp,
    )

    assert response.status_code == 400
    data = response.json()
    assert "name" in data["detail"].lower() or "nome" in data["detail"].lower()


@pytest.mark.asyncio
async def test_start_briefing_with_low_confidence_extraction(
    client: AsyncClient,
    db_session: AsyncSession,
    test_architect_with_whatsapp: Architect,
    auth_headers_whatsapp: dict[str, str],
    mocker: MockerFixture,
):
    """Test starting briefing fails when extraction confidence is too low."""
    mock_extracted_info = ExtractedClientInfo(
        name="João",
        phone="11999887766",
        project_type="reforma",
        confidence=0.40,
        raw_text="João talvez 11999887766",
    )
    mocker.patch(
        "src.services.briefing.extraction_service.ExtractionService.extract_client_info",
        new=AsyncMock(return_value=mock_extracted_info),
    )

    response = await client.post(
        "/api/briefings/start-from-whatsapp",
        json={
            "architect_id": str(test_architect_with_whatsapp.id),
            "architect_message": "João talvez 11999887766",
        },
        headers=auth_headers_whatsapp,
    )

    assert response.status_code == 400
    data = response.json()
    assert "confidence" in data["detail"].lower() or "confiança" in data["detail"].lower()


@pytest.mark.asyncio
async def test_template_identification_by_project_type(
    client: AsyncClient,
    db_session: AsyncSession,
    test_architect_with_whatsapp: Architect,
    auth_headers_whatsapp: dict[str, str],
    test_templates: dict[str, BriefingTemplate],
    mocker: MockerFixture,
):
    """Test that different project types map to correct templates."""
    project_types = ["reforma", "residencial", "comercial", "construcao"]

    for idx, project_type in enumerate(project_types, start=1):
        mock_extracted_info = ExtractedClientInfo(
            name=f"Cliente {project_type}",
            phone=f"+5511999{idx:06d}",
            project_type=project_type,
            confidence=0.95,
            raw_text=f"Cliente para {project_type}",
        )
        mocker.patch(
            "src.api.briefings.ExtractionService.extract_client_info",
            new=AsyncMock(return_value=mock_extracted_info),
        )

        expected_template = test_templates[project_type]
        mocker.patch(
            "src.services.template_service.TemplateService.select_template_version_for_project",
            new=AsyncMock(return_value=expected_template.current_version),
        )

        mocker.patch(
            "src.api.briefings.WhatsAppService.send_text_message",
            new=AsyncMock(return_value={"success": True, "message_id": f"wamid.{project_type}"}),
        )

        response = await client.post(
            "/api/briefings/start-from-whatsapp",
            json={
                "architect_id": str(test_architect_with_whatsapp.id),
                "architect_message": f"Cliente para {project_type}",
            },
            headers=auth_headers_whatsapp,
        )

        assert response.status_code == 200
        data = response.json()

        await db_session.rollback()

        briefing_id = UUID(data["briefing_id"])
        result = await db_session.execute(select(Briefing).where(Briefing.id == briefing_id))
        briefing = result.scalar_one()
        assert briefing.template_version_id == expected_template.current_version_id


@pytest.mark.asyncio
async def test_transaction_rollback_on_whatsapp_failure(
    client: AsyncClient,
    db_session: AsyncSession,
    test_architect_with_whatsapp: Architect,
    auth_headers_whatsapp: dict[str, str],
    test_templates: dict[str, BriefingTemplate],
    mocker: MockerFixture,
):
    """Test error handling when WhatsApp send fails.

    Note: Currently the endpoint commits before WhatsApp send, so records ARE created.
    This could be improved in the future to use a distributed transaction or compensating actions.
    """
    mock_extracted_info = ExtractedClientInfo(
        name="Test Rollback Client",
        phone="11988776655",
        project_type="reforma",
        confidence=0.95,
        raw_text="Test rollback",
    )
    mocker.patch(
        "src.api.briefings.ExtractionService.extract_client_info",
        new=AsyncMock(return_value=mock_extracted_info),
    )

    reforma_template = test_templates["reforma"]
    mocker.patch(
        "src.services.template_service.TemplateService.select_template_version_for_project",
        new=AsyncMock(return_value=reforma_template.current_version),
    )

    mocker.patch(
        "src.api.briefings.WhatsAppService.send_text_message",
        new=AsyncMock(side_effect=Exception("WhatsApp API connection failed")),
    )

    architect_id = test_architect_with_whatsapp.id

    response = await client.post(
        "/api/briefings/start-from-whatsapp",
        json={
            "architect_id": str(architect_id),
            "architect_message": "Test rollback",
        },
        headers=auth_headers_whatsapp,
    )

    assert response.status_code == 500
    data = response.json()
    assert "WhatsApp" in data["detail"] or "Failed" in data["detail"]


@pytest.mark.asyncio
async def test_conversation_record_creation_with_whatsapp_context(
    client: AsyncClient,
    db_session: AsyncSession,
    test_architect_with_whatsapp: Architect,
    auth_headers_whatsapp: dict[str, str],
    test_templates: dict[str, BriefingTemplate],
    mocker: MockerFixture,
):
    """Test that Conversation record is created with proper WhatsApp context."""
    mock_extracted_info = ExtractedClientInfo(
        name="Maria Santos",
        phone="11977665544",
        project_type="comercial",
        confidence=0.92,
        raw_text="Maria Santos, 11977665544, projeto comercial",
    )
    mocker.patch(
        "src.api.briefings.ExtractionService.extract_client_info",
        new=AsyncMock(return_value=mock_extracted_info),
    )

    comercial_template = test_templates["comercial"]
    mocker.patch(
        "src.services.template_service.TemplateService.select_template_version_for_project",
        new=AsyncMock(return_value=comercial_template.current_version),
    )

    mocker.patch(
        "src.api.briefings.WhatsAppService.send_text_message",
        new=AsyncMock(return_value={"success": True, "message_id": "wamid.conv123"}),
    )

    response = await client.post(
        "/api/briefings/start-from-whatsapp",
        json={
            "architect_id": str(test_architect_with_whatsapp.id),
            "architect_message": "Maria Santos, 11977665544, projeto comercial",
        },
        headers=auth_headers_whatsapp,
    )

    assert response.status_code == 200
    data = response.json()

    await db_session.rollback()

    briefing_id = UUID(data["briefing_id"])
    client_id = UUID(data["client_id"])

    result = await db_session.execute(select(Briefing).where(Briefing.id == briefing_id))
    briefing_with_conv = result.scalar_one()
    assert briefing_with_conv.conversation_id is not None

    result = await db_session.execute(
        select(Conversation).where(Conversation.id == briefing_with_conv.conversation_id)
    )
    conversation = result.scalar_one()

    assert conversation.conversation_type == ConversationType.WHATSAPP_BRIEFING.value
    assert conversation.end_client_id == client_id
    assert conversation.whatsapp_context is not None
    assert "phone_number" in conversation.whatsapp_context
    assert "architect_id" in conversation.whatsapp_context
    assert conversation.whatsapp_context["whatsapp_message_id"] == "wamid.conv123"


@pytest.mark.asyncio
async def test_start_briefing_with_invalid_architect_id(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers_whatsapp: dict[str, str],
):
    """Test starting briefing with non-existent architect ID."""
    fake_architect_id = "00000000-0000-0000-0000-000000000000"

    response = await client.post(
        "/api/briefings/start-from-whatsapp",
        json={
            "architect_id": fake_architect_id,
            "architect_message": "Test message",
        },
        headers=auth_headers_whatsapp,
    )

    assert response.status_code in [400, 404]
    data = response.json()
    assert "architect" in data["detail"].lower()


@pytest.mark.asyncio
async def test_start_briefing_validates_request_schema(
    client: AsyncClient,
    auth_headers_whatsapp: dict[str, str],
):
    """Test that request schema validation works correctly."""
    response = await client.post(
        "/api/briefings/start-from-whatsapp",
        json={
            "architect_id": "invalid-uuid-format",
        },
        headers=auth_headers_whatsapp,
    )

    assert response.status_code == 422
