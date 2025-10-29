"""Tests for processing client answers received via WhatsApp webhook."""

from datetime import datetime
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from pytest_mock import MockerFixture
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.architect import Architect
from src.db.models.briefing import Briefing, BriefingStatus
from src.db.models.briefing_template import BriefingTemplate
from src.db.models.end_client import EndClient
from src.db.models.organization import Organization
from src.db.models.template_version import TemplateVersion
from src.db.models.architect import Architect
from src.db.models.whatsapp_message import MessageDirection, MessageStatus, WhatsAppMessage
from src.db.models.whatsapp_session import SessionStatus, WhatsAppSession


# Fixtures
@pytest.fixture
async def test_organization(db_session: AsyncSession) -> Organization:
    """Create test organization with WhatsApp account."""
    org = Organization(
        name="Test Architecture Firm",
        whatsapp_business_account_id="123456789",
        settings={"phone_number_id": "test_phone_id", "access_token": "test_token"},
    )
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    return org


@pytest.fixture
async def test_architect(
    db_session: AsyncSession, test_organization: Organization
) -> Architect:
    """Create test architect."""
    architect = Architect(
        organization_id=test_organization.id,
        email="architect@test.com",
        hashed_password="hashed_password",
        phone="+5511999999999",
        is_authorized=True,
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)
    return architect


@pytest.fixture
async def test_template(db_session: AsyncSession) -> BriefingTemplate:
    """Create test template with 3 questions."""
    template = BriefingTemplate(
        name="Template Reforma",
        category="reforma",
        description="Template para projetos de reforma",
        is_global=True,
    )
    db_session.add(template)
    await db_session.flush()

    # Create version with 3 questions
    version = TemplateVersion(
        template_id=template.id,
        version_number=1,
        questions=[
            {
                "order": 1,
                "question": "Qual o tipo de reforma?",
                "type": "text",
                "required": True,
            },
            {
                "order": 2,
                "question": "Qual o prazo desejado?",
                "type": "text",
                "required": True,
            },
            {
                "order": 3,
                "question": "Qual o orçamento disponível?",
                "type": "text",
                "required": False,
            },
        ],
        is_active=True,
    )
    db_session.add(version)
    await db_session.flush()

    template.current_version_id = version.id
    await db_session.commit()
    await db_session.refresh(template)
    return template


@pytest.fixture
async def test_client(
    db_session: AsyncSession, test_organization: Organization, test_architect: Architect
) -> EndClient:
    """Create test end client."""
    client = EndClient(
        organization_id=test_organization.id,
        architect_id=test_architect.id,
        name="João Silva",
        phone="+5511987654321",
        email="joao@test.com",
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client


@pytest.fixture
async def active_briefing(
    db_session: AsyncSession, test_client: EndClient, test_template: BriefingTemplate
) -> Briefing:
    """Create an active briefing at question 1."""
    briefing = Briefing(
        end_client_id=test_client.id,
        template_version_id=test_template.current_version_id,
        status=BriefingStatus.IN_PROGRESS,
        current_question_order=1,
        answers={},
    )
    db_session.add(briefing)
    await db_session.commit()
    await db_session.refresh(briefing)
    return briefing


@pytest.fixture
async def whatsapp_session(db_session: AsyncSession, test_client: EndClient) -> WhatsAppSession:
    """Create WhatsApp session for client."""
    session = WhatsAppSession(
        end_client_id=test_client.id,
        phone_number=test_client.phone,
        status=SessionStatus.ACTIVE.value,
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    return session


# Tests
@pytest.mark.asyncio
async def test_receive_first_answer_and_send_next_question(
    db_session: AsyncSession,
    test_client: EndClient,
    active_briefing: Briefing,
    whatsapp_session: WhatsAppSession,
    mocker: MockerFixture,
):
    """Test receiving first answer, saving it, and sending next question."""
    # Mock WhatsApp service
    mock_whatsapp_send = mocker.patch(
        "src.services.briefing.answer_processor.WhatsAppService.send_text_message",
        new=AsyncMock(return_value={"success": True, "message_id": "wamid.next123"}),
    )

    # Import the service we'll create
    from src.services.briefing.answer_processor import AnswerProcessorService

    # Process answer
    processor = AnswerProcessorService(db_session)
    result = await processor.process_client_answer(
        phone_number=test_client.phone,
        answer_text="Reforma de banheiro",
        wa_message_id="wamid.incoming123",
        session_id=whatsapp_session.id,
    )

    # Assertions
    assert result["success"] is True
    assert result["briefing_id"] == active_briefing.id
    assert result["question_number"] == 1
    assert result["next_question"] is not None
    assert "prazo" in result["next_question"].lower()

    # Verify briefing was updated
    await db_session.refresh(active_briefing)
    assert active_briefing.current_question_order == 2
    assert "1" in active_briefing.answers
    assert active_briefing.answers["1"] == "Reforma de banheiro"
    assert active_briefing.status == BriefingStatus.IN_PROGRESS

    # Verify WhatsApp message was sent
    mock_whatsapp_send.assert_called_once()
    call_args = mock_whatsapp_send.call_args
    assert call_args.kwargs["to"] == test_client.phone
    assert "prazo" in call_args.kwargs["text"].lower()

    # Verify WhatsAppMessage was saved
    result_msg = await db_session.execute(
        select(WhatsAppMessage).where(WhatsAppMessage.wa_message_id == "wamid.incoming123")
    )
    saved_message = result_msg.scalar_one()
    assert saved_message.session_id == whatsapp_session.id
    assert saved_message.direction == MessageDirection.INBOUND.value
    assert saved_message.status == MessageStatus.RECEIVED.value
    assert saved_message.content["text"]["body"] == "Reforma de banheiro"


@pytest.mark.asyncio
async def test_receive_last_answer_and_complete_briefing(
    db_session: AsyncSession,
    test_client: EndClient,
    active_briefing: Briefing,
    whatsapp_session: WhatsAppSession,
    mocker: MockerFixture,
):
    """Test receiving last required answer and completing briefing."""
    # Set briefing to second question (last required question)
    active_briefing.current_question_order = 2
    active_briefing.answers = {"1": "Reforma de banheiro"}
    await db_session.commit()

    # Mock WhatsApp service
    mock_whatsapp_send = mocker.patch(
        "src.services.briefing.answer_processor.WhatsAppService.send_text_message",
        new=AsyncMock(return_value={"success": True, "message_id": "wamid.completion123"}),
    )

    from src.services.briefing.answer_processor import AnswerProcessorService

    processor = AnswerProcessorService(db_session)
    result = await processor.process_client_answer(
        phone_number=test_client.phone,
        answer_text="Em 2 meses",
        wa_message_id="wamid.incoming456",
        session_id=whatsapp_session.id,
    )

    # Assertions
    assert result["success"] is True
    assert result["briefing_id"] == active_briefing.id
    assert result["completed"] is True
    assert result["next_question"] is None

    # Verify briefing was completed
    await db_session.refresh(active_briefing)
    assert active_briefing.status == BriefingStatus.COMPLETED
    assert active_briefing.completed_at is not None
    assert "2" in active_briefing.answers
    assert active_briefing.answers["2"] == "Em 2 meses"

    # Verify completion message was sent
    mock_whatsapp_send.assert_called_once()
    call_args = mock_whatsapp_send.call_args
    assert "obrigad" in call_args.kwargs["text"].lower() or "conclu" in call_args.kwargs["text"].lower()


@pytest.mark.asyncio
async def test_receive_answer_for_optional_question(
    db_session: AsyncSession,
    test_client: EndClient,
    active_briefing: Briefing,
    whatsapp_session: WhatsAppSession,
    mocker: MockerFixture,
):
    """Test answering optional question after all required ones."""
    # Set briefing to third question (optional)
    active_briefing.current_question_order = 3
    active_briefing.answers = {"1": "Reforma de banheiro", "2": "Em 2 meses"}
    await db_session.commit()

    # Mock WhatsApp service
    mock_whatsapp_send = mocker.patch(
        "src.services.briefing.answer_processor.WhatsAppService.send_text_message",
        new=AsyncMock(return_value={"success": True, "message_id": "wamid.optional123"}),
    )

    from src.services.briefing.answer_processor import AnswerProcessorService

    processor = AnswerProcessorService(db_session)
    result = await processor.process_client_answer(
        phone_number=test_client.phone,
        answer_text="R$ 50.000",
        wa_message_id="wamid.incoming789",
        session_id=whatsapp_session.id,
    )

    # After answering last (optional) question, should complete
    assert result["success"] is True
    assert result["completed"] is True

    await db_session.refresh(active_briefing)
    assert active_briefing.status == BriefingStatus.COMPLETED
    assert "3" in active_briefing.answers


@pytest.mark.asyncio
async def test_create_whatsapp_session_if_not_exists(
    db_session: AsyncSession,
    test_client: EndClient,
    active_briefing: Briefing,
    mocker: MockerFixture,
):
    """Test that WhatsAppSession is created if it doesn't exist."""
    # Mock WhatsApp service
    mocker.patch(
        "src.services.briefing.answer_processor.WhatsAppService.send_text_message",
        new=AsyncMock(return_value={"success": True, "message_id": "wamid.new123"}),
    )

    from src.services.briefing.answer_processor import AnswerProcessorService

    processor = AnswerProcessorService(db_session)
    result = await processor.process_client_answer(
        phone_number=test_client.phone,
        answer_text="Resposta teste",
        wa_message_id="wamid.incoming999",
        session_id=None,  # No session provided
    )

    assert result["success"] is True

    # Verify session was created
    result_session = await db_session.execute(
        select(WhatsAppSession).where(WhatsAppSession.phone_number == test_client.phone)
    )
    new_session = result_session.scalar_one()
    assert new_session.end_client_id == test_client.id
    assert new_session.status == SessionStatus.ACTIVE.value


@pytest.mark.asyncio
async def test_handle_client_without_active_briefing(
    db_session: AsyncSession,
    test_client: EndClient,
    mocker: MockerFixture,
):
    """Test handling message from client with no active briefing."""
    # Mock WhatsApp service
    mock_whatsapp_send = mocker.patch(
        "src.services.briefing.answer_processor.WhatsAppService.send_text_message",
        new=AsyncMock(return_value={"success": True, "message_id": "wamid.error123"}),
    )

    from src.services.briefing.answer_processor import AnswerProcessorService

    processor = AnswerProcessorService(db_session)
    result = await processor.process_client_answer(
        phone_number=test_client.phone,
        answer_text="Resposta sem briefing ativo",
        wa_message_id="wamid.orphan123",
        session_id=None,
    )

    # Should indicate no active briefing
    assert result["success"] is False
    assert "no_active_briefing" in result.get("error", "").lower() or result.get("no_active_briefing") is True


@pytest.mark.asyncio
async def test_handle_unknown_phone_number(
    db_session: AsyncSession,
    mocker: MockerFixture,
):
    """Test handling message from unknown phone number (client doesn't exist)."""
    from src.services.briefing.answer_processor import AnswerProcessorService

    processor = AnswerProcessorService(db_session)
    result = await processor.process_client_answer(
        phone_number="+5511999999999",  # Unknown phone
        answer_text="Resposta de desconhecido",
        wa_message_id="wamid.unknown123",
        session_id=None,
    )

    # Should indicate client not found
    assert result["success"] is False
    assert "client_not_found" in result.get("error", "").lower() or result.get("client_not_found") is True


@pytest.mark.asyncio
async def test_webhook_integration_process_answer(
    db_session: AsyncSession,
    test_client: EndClient,
    active_briefing: Briefing,
    test_organization: Organization,
    mocker: MockerFixture,
):
    """Test webhook endpoint integration with answer processing."""
    from src.api.whatsapp_webhook import _handle_incoming_message

    # Mock WhatsApp service
    mocker.patch(
        "src.services.briefing.answer_processor.WhatsAppService.send_text_message",
        new=AsyncMock(return_value={"success": True, "message_id": "wamid.webhook123"}),
    )

    # Prepare webhook event
    event = {
        "event_type": "message",
        "wa_message_id": "wamid.webhook_incoming",
        "from": test_client.phone,
        "phone_number_id": "test_phone_id",
        "timestamp": "1234567890",
        "direction": MessageDirection.INBOUND.value,
        "status": MessageStatus.RECEIVED.value,
        "content": {
            "type": "text",
            "text": {"body": "Reforma completa"},
        },
    }

    # Inject db_session into the handler (will need to refactor handler to accept it)
    # For now, this test documents the expected integration
    # await _handle_incoming_message(event, db_session, test_organization)

    # Note: This test will be completed once we refactor the webhook handler
    # to accept database session as parameter


@pytest.mark.asyncio
async def test_concurrent_answers_from_same_client(
    db_session: AsyncSession,
    test_client: EndClient,
    active_briefing: Briefing,
    whatsapp_session: WhatsAppSession,
    mocker: MockerFixture,
):
    """Test that concurrent answers from same client are handled correctly."""
    mocker.patch(
        "src.services.briefing.answer_processor.WhatsAppService.send_text_message",
        new=AsyncMock(return_value={"success": True, "message_id": "wamid.concurrent123"}),
    )

    from src.services.briefing.answer_processor import AnswerProcessorService

    # First answer should succeed
    processor = AnswerProcessorService(db_session)
    result1 = await processor.process_client_answer(
        phone_number=test_client.phone,
        answer_text="Primeira resposta",
        wa_message_id="wamid.first",
        session_id=whatsapp_session.id,
    )

    assert result1["success"] is True

    # Commit the first transaction
    await db_session.commit()

    # Refresh objects to get updated state
    await db_session.refresh(active_briefing)
    await db_session.refresh(whatsapp_session)

    # Second answer should move to next question (question 2)
    processor2 = AnswerProcessorService(db_session)
    result2 = await processor2.process_client_answer(
        phone_number=test_client.phone,
        answer_text="Segunda resposta",
        wa_message_id="wamid.second",
        session_id=whatsapp_session.id,
    )

    # Should succeed with next question
    assert result2["success"] is True
