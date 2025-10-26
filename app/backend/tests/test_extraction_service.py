"""Tests for AI-based extraction service for client info and template identification."""

from uuid import uuid4

import pytest
from pytest_mock import MockerFixture
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.architect import Architect
from src.db.models.briefing_template import BriefingTemplate
from src.db.models.organization import Organization
from src.db.models.template_version import TemplateVersion
from src.db.models.user import User
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
    user = User(email="architect@test.com", hashed_password="hash123")
    db_session.add(user)
    await db_session.flush()

    architect = Architect(
        user_id=user.id,
        organization_id=test_organization.id,
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


# Tests for identify_template()
@pytest.mark.asyncio
async def test_identify_template_reforma(
    extraction_service: ExtractionService,
    test_templates: list[BriefingTemplate],
    mocker: MockerFixture,
):
    """Test template identification for reforma project."""
    project_description = "Cliente quer fazer uma reforma completa do apartamento"

    reforma_template = next(t for t in test_templates if t.category == "reforma")
    mock_response = TemplateRecommendation(
        template_id=reforma_template.id,
        category="reforma",
        confidence=0.92,
        reasoning="Projeto claramente descrito como reforma de apartamento",
    )
    mocker.patch.object(
        extraction_service.ai_service,
        "generate_structured_response",
        return_value=mock_response,
    )

    result = await extraction_service.identify_template(
        project_description=project_description, available_templates=test_templates
    )

    assert result.template_id == reforma_template.id
    assert result.category == "reforma"
    assert result.confidence >= 0.9


@pytest.mark.asyncio
async def test_identify_template_residencial(
    extraction_service: ExtractionService,
    test_templates: list[BriefingTemplate],
    mocker: MockerFixture,
):
    """Test template identification for residencial project."""
    project_description = "Construção de casa nova, projeto residencial unifamiliar"

    residencial_template = next(t for t in test_templates if t.category == "residencial")
    mock_response = TemplateRecommendation(
        template_id=residencial_template.id,
        category="residencial",
        confidence=0.95,
        reasoning="Projeto de construção residencial nova identificado",
    )
    mocker.patch.object(
        extraction_service.ai_service,
        "generate_structured_response",
        return_value=mock_response,
    )

    result = await extraction_service.identify_template(
        project_description=project_description, available_templates=test_templates
    )

    assert result.template_id == residencial_template.id
    assert result.category == "residencial"


@pytest.mark.asyncio
async def test_identify_template_comercial(
    extraction_service: ExtractionService,
    test_templates: list[BriefingTemplate],
    mocker: MockerFixture,
):
    """Test template identification for comercial project."""
    project_description = "Projeto de loja comercial, preciso de plantas para estabelecimento"

    comercial_template = next(t for t in test_templates if t.category == "comercial")
    mock_response = TemplateRecommendation(
        template_id=comercial_template.id,
        category="comercial",
        confidence=0.88,
        reasoning="Projeto comercial identificado - loja/estabelecimento",
    )
    mocker.patch.object(
        extraction_service.ai_service,
        "generate_structured_response",
        return_value=mock_response,
    )

    result = await extraction_service.identify_template(
        project_description=project_description, available_templates=test_templates
    )

    assert result.template_id == comercial_template.id
    assert result.category == "comercial"


@pytest.mark.asyncio
async def test_identify_template_incorporacao(
    extraction_service: ExtractionService,
    test_templates: list[BriefingTemplate],
    mocker: MockerFixture,
):
    """Test template identification for incorporacao project."""
    project_description = "Projeto de incorporação, prédio de 10 andares com múltiplas unidades"

    incorporacao_template = next(t for t in test_templates if t.category == "incorporacao")
    mock_response = TemplateRecommendation(
        template_id=incorporacao_template.id,
        category="incorporacao",
        confidence=0.93,
        reasoning="Projeto de incorporação com múltiplas unidades identificado",
    )
    mocker.patch.object(
        extraction_service.ai_service,
        "generate_structured_response",
        return_value=mock_response,
    )

    result = await extraction_service.identify_template(
        project_description=project_description, available_templates=test_templates
    )

    assert result.template_id == incorporacao_template.id
    assert result.category == "incorporacao"


@pytest.mark.asyncio
async def test_identify_template_ambiguous(
    extraction_service: ExtractionService,
    test_templates: list[BriefingTemplate],
    mocker: MockerFixture,
):
    """Test template identification with ambiguous description."""
    project_description = "Projeto de imóvel"

    # When ambiguous, should still return a template but with lower confidence
    reforma_template = next(t for t in test_templates if t.category == "reforma")
    mock_response = TemplateRecommendation(
        template_id=reforma_template.id,
        category="reforma",
        confidence=0.60,
        reasoning="Descrição ambígua, sugerindo template de reforma como padrão",
    )
    mocker.patch.object(
        extraction_service.ai_service,
        "generate_structured_response",
        return_value=mock_response,
    )

    result = await extraction_service.identify_template(
        project_description=project_description, available_templates=test_templates
    )

    assert result.confidence < 0.7  # Lower confidence for ambiguous cases


# Tests for error handling
@pytest.mark.asyncio
async def test_extract_client_info_ai_service_error(
    extraction_service: ExtractionService, test_architect: Architect, mocker: MockerFixture
):
    """Test handling of AI service errors during extraction."""
    message = "Cliente João Silva"

    # Mock AI service raising an error
    mocker.patch.object(
        extraction_service.ai_service,
        "generate_structured_response",
        side_effect=Exception("AI service unavailable"),
    )

    with pytest.raises(Exception, match="AI service unavailable"):
        await extraction_service.extract_client_info(
            message=message, architect_id=test_architect.id
        )


@pytest.mark.asyncio
async def test_identify_template_no_templates(
    extraction_service: ExtractionService, mocker: MockerFixture
):
    """Test template identification when no templates are available."""
    project_description = "Projeto de reforma"

    with pytest.raises(ValueError, match="No templates available"):
        await extraction_service.identify_template(
            project_description=project_description, available_templates=[]
        )


@pytest.mark.asyncio
async def test_identify_template_ai_service_error(
    extraction_service: ExtractionService,
    test_templates: list[BriefingTemplate],
    mocker: MockerFixture,
):
    """Test handling of AI service errors during template identification."""
    project_description = "Projeto de reforma"

    mocker.patch.object(
        extraction_service.ai_service,
        "generate_structured_response",
        side_effect=Exception("AI service timeout"),
    )

    with pytest.raises(Exception, match="AI service timeout"):
        await extraction_service.identify_template(
            project_description=project_description, available_templates=test_templates
        )
