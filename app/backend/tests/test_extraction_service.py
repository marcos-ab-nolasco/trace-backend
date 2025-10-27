"""Tests for AI-based extraction service for client info and template identification."""

from uuid import uuid4

import pytest
from pytest_mock import MockerFixture
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.architect import Architect
from src.db.models.briefing_template import BriefingTemplate
from src.db.models.organization import Organization
from src.db.models.template_version import TemplateVersion
from src.schemas.briefing import ExtractedClientInfo, TemplateRecommendation
from src.services.ai.openai_service import OpenAIService
from src.services.briefing.extraction_service import ExtractionService


# Fixtures
@pytest.fixture
async def test_organization(db_session: AsyncSession) -> Organization:
    """Create test organization."""
    org = Organization(name="Test Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    return org


@pytest.fixture
async def test_architect(db_session: AsyncSession, test_organization: Organization) -> Architect:
    """Create test architect."""
    architect = Architect(
        organization_id=test_organization.id,
        email="architect@test.com",
        hashed_password="hash123",
        phone="+5511999999999",
        is_authorized=True,
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)
    return architect


@pytest.fixture
async def test_templates(db_session: AsyncSession, test_architect: Architect) -> list[BriefingTemplate]:
    """Create test templates for different categories."""
    templates = []
    categories = ["reforma", "residencial", "comercial", "incorporacao"]

    for category in categories:
        template = BriefingTemplate(
            name=f"Template {category.title()}",
            category=category,
            description=f"Template para projetos de {category}",
            is_global=True,
        )
        db_session.add(template)
        await db_session.flush()

        # Create initial version
        version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            questions=[
                {"order": 1, "question": "Qual o tipo de projeto?", "type": "text", "required": True}
            ],
            is_active=True,
        )
        db_session.add(version)
        await db_session.flush()

        template.current_version_id = version.id
        templates.append(template)

    await db_session.commit()
    for template in templates:
        await db_session.refresh(template)

    return templates


@pytest.fixture
def extraction_service(mocker: MockerFixture) -> ExtractionService:
    """Create extraction service with mocked AI service."""
    mock_ai_service = mocker.Mock(spec=OpenAIService)
    return ExtractionService(ai_service=mock_ai_service)


# Tests for extract_client_info()
@pytest.mark.asyncio
async def test_extract_client_info_complete_data(
    extraction_service: ExtractionService, test_architect: Architect, mocker: MockerFixture
):
    """Test extracting complete client info from well-formatted message."""
    message = "Cliente João Silva, telefone (11) 98765-4321, reforma de apartamento"

    # Mock AI response
    mock_response = ExtractedClientInfo(
        name="João Silva",
        phone="11987654321",
        project_type="reforma",
        confidence=0.95,
        raw_text=message,
    )
    mocker.patch.object(
        extraction_service.ai_service,
        "generate_structured_response",
        return_value=mock_response,
    )

    result = await extraction_service.extract_client_info(
        message=message, architect_id=test_architect.id
    )

    assert result.name == "João Silva"
    assert result.phone == "11987654321"
    assert result.project_type == "reforma"
    assert result.confidence >= 0.9
    assert result.raw_text == message


@pytest.mark.asyncio
async def test_extract_client_info_varied_format(
    extraction_service: ExtractionService, test_architect: Architect, mocker: MockerFixture
):
    """Test extracting from message with varied formatting."""
    message = "Preciso de briefing para Maria Santos, cel 11 9 8765-4321, construção residencial nova"

    mock_response = ExtractedClientInfo(
        name="Maria Santos",
        phone="11987654321",
        project_type="residencial",
        confidence=0.90,
        raw_text=message,
    )
    mocker.patch.object(
        extraction_service.ai_service,
        "generate_structured_response",
        return_value=mock_response,
    )

    result = await extraction_service.extract_client_info(
        message=message, architect_id=test_architect.id
    )

    assert result.name == "Maria Santos"
    assert result.phone == "11987654321"
    assert result.project_type == "residencial"


@pytest.mark.asyncio
async def test_extract_client_info_missing_phone(
    extraction_service: ExtractionService, test_architect: Architect, mocker: MockerFixture
):
    """Test extraction when phone number is missing."""
    message = "Briefing para Pedro Costa, projeto de incorporação"

    mock_response = ExtractedClientInfo(
        name="Pedro Costa",
        phone=None,
        project_type="incorporacao",
        confidence=0.75,
        raw_text=message,
    )
    mocker.patch.object(
        extraction_service.ai_service,
        "generate_structured_response",
        return_value=mock_response,
    )

    result = await extraction_service.extract_client_info(
        message=message, architect_id=test_architect.id
    )

    assert result.name == "Pedro Costa"
    assert result.phone is None
    assert result.project_type == "incorporacao"
    assert result.confidence < 0.9  # Lower confidence when data is incomplete


@pytest.mark.asyncio
async def test_extract_client_info_missing_name(
    extraction_service: ExtractionService, test_architect: Architect, mocker: MockerFixture
):
    """Test extraction when client name is missing."""
    message = "Cliente quer fazer reforma, telefone 11987654321"

    mock_response = ExtractedClientInfo(
        name=None,
        phone="11987654321",
        project_type="reforma",
        confidence=0.70,
        raw_text=message,
    )
    mocker.patch.object(
        extraction_service.ai_service,
        "generate_structured_response",
        return_value=mock_response,
    )

    result = await extraction_service.extract_client_info(
        message=message, architect_id=test_architect.id
    )

    assert result.name is None
    assert result.phone == "11987654321"
    assert result.project_type == "reforma"


@pytest.mark.asyncio
async def test_extract_client_info_phone_formats(
    extraction_service: ExtractionService, test_architect: Architect, mocker: MockerFixture
):
    """Test extraction handles various phone formats."""
    test_cases = [
        ("Cliente Ana, tel (11) 98765-4321", "11987654321"),
        ("Cliente Ana, tel 11987654321", "11987654321"),
        ("Cliente Ana, tel 11 9 8765 4321", "11987654321"),
        ("Cliente Ana, tel +55 11 98765-4321", "5511987654321"),
    ]

    for message, expected_phone in test_cases:
        mock_response = ExtractedClientInfo(
            name="Ana",
            phone=expected_phone,
            project_type="reforma",
            confidence=0.90,
            raw_text=message,
        )
        mocker.patch.object(
            extraction_service.ai_service,
            "generate_structured_response",
            return_value=mock_response,
        )

        result = await extraction_service.extract_client_info(
            message=message, architect_id=test_architect.id
        )

        assert result.phone == expected_phone


