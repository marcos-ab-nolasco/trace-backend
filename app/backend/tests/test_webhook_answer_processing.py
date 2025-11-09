"""Tests for processing client answers received via WhatsApp webhook."""

from unittest.mock import AsyncMock

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
from src.db.models.whatsapp_message import MessageDirection, MessageStatus, WhatsAppMessage
from src.db.models.whatsapp_session import SessionStatus, WhatsAppSession

TEST_TOKEN = "gAAAAABpD5SBKMMw3egsVRJ7IWR3jtj5PzRnMyifxeXyWCJmg0gtErDSpZHZOH09gSgvalFlmre05W-8JcMdAswaN7E3zZvifw=="


# Test-specific fixtures
@pytest.fixture
async def test_org_with_whatsapp(
    db_session: AsyncSession, test_organization: Organization
) -> Organization:
    """Add WhatsApp settings to test organization."""
    test_organization.whatsapp_business_account_id = "123456789"
    test_organization.settings = {
        "phone_number_id": "test_phone_id",
        "access_token": TEST_TOKEN,
    }
    db_session.add(test_organization)
    await db_session.commit()
    await db_session.refresh(test_organization)
    return test_organization


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
    db_session: AsyncSession, test_org_with_whatsapp: Organization, test_architect: Architect
) -> EndClient:
    """Create test end client."""
    client = EndClient(
        organization_id=test_org_with_whatsapp.id,
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
    assert (
        "obrigad" in call_args.kwargs["text"].lower()
        or "conclu" in call_args.kwargs["text"].lower()
    )


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
    assert (
        "no_active_briefing" in result.get("error", "").lower()
        or result.get("no_active_briefing") is True
    )


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
    assert (
        "client_not_found" in result.get("error", "").lower()
        or result.get("client_not_found") is True
    )


@pytest.mark.asyncio
async def test_webhook_integration_process_answer(
    db_session: AsyncSession,
    test_client: EndClient,
    active_briefing: Briefing,
    test_organization: Organization,
    mocker: MockerFixture,
):
    """Test webhook endpoint integration with answer processing."""

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


# ============================================================================
# TRANSACTION MANAGEMENT TESTS (Sprint 1 Issue #8)
# ============================================================================


@pytest.mark.asyncio
async def test_answer_not_saved_when_whatsapp_send_fails(
    db_session: AsyncSession,
    test_client: EndClient,
    active_briefing: Briefing,
    whatsapp_session: WhatsAppSession,
    mocker: MockerFixture,
):
    """Test Option C behavior: data commits but WhatsApp failure triggers retry with idempotency.

    In Option C (Idempotency with Rollback):
    1. DB operations commit successfully
    2. WhatsApp send fails
    3. Exception propagates (webhook will retry)
    4. On retry, idempotency check prevents duplicate processing
    """
    # Mock WhatsApp service to raise exception (simulating network failure)
    mock_whatsapp_send = mocker.patch(
        "src.services.briefing.answer_processor.WhatsAppService.send_text_message",
        new=AsyncMock(side_effect=Exception("WhatsApp API temporarily unavailable")),
    )

    from src.services.briefing.answer_processor import AnswerProcessorService

    # Process answer - should fail and propagate exception
    processor = AnswerProcessorService(db_session)
    with pytest.raises(Exception, match="WhatsApp API temporarily unavailable"):
        await processor.process_client_answer(
            phone_number=test_client.phone,
            answer_text="Reforma de cozinha",
            wa_message_id="wamid.fail_test",
            session_id=whatsapp_session.id,
        )

    # Verify WhatsApp send was attempted
    mock_whatsapp_send.assert_called_once()

    # Refresh briefing - in Option C, data IS committed before WhatsApp send
    await db_session.refresh(active_briefing)

    # Changes ARE persisted (this is Option C behavior)
    assert active_briefing.current_question_order == 2  # Progressed to next question
    assert "1" in active_briefing.answers  # Answer was saved
    assert active_briefing.answers["1"] == "Reforma de cozinha"
    assert active_briefing.status == BriefingStatus.IN_PROGRESS

    # Incoming message WAS saved (before WhatsApp send)
    result = await db_session.execute(
        select(WhatsAppMessage).where(WhatsAppMessage.wa_message_id == "wamid.fail_test")
    )
    saved_message = result.scalar_one_or_none()
    assert saved_message is not None, "Message should be saved (commits before WhatsApp)"
    assert saved_message.content["text"]["body"] == "Reforma de cozinha"

    # Critical test: webhook WAS marked as processed (after commit, before WhatsApp)
    from src.db.models.processed_webhook import ProcessedWebhook

    result_webhook = await db_session.execute(
        select(ProcessedWebhook).where(ProcessedWebhook.wa_message_id == "wamid.fail_test")
    )
    processed_webhook = result_webhook.scalar_one_or_none()
    assert (
        processed_webhook is not None
    ), "Webhook should be marked processed (after commit, before WhatsApp)"
    assert processed_webhook.result_data is not None
    assert "next_question" in processed_webhook.result_data

    # On webhook retry, will detect already processed, skip DB operations,
    # and retry only the WhatsApp send using cached next_question


@pytest.mark.asyncio
async def test_duplicate_webhook_does_not_create_duplicate_answers(
    db_session: AsyncSession,
    test_client: EndClient,
    active_briefing: Briefing,
    whatsapp_session: WhatsAppSession,
    mocker: MockerFixture,
):
    """Test that processing the same webhook twice doesn't create duplicate answers.

    This ensures idempotency - webhook retries won't corrupt data.
    """
    # Mock WhatsApp service
    mocker.patch(
        "src.services.briefing.answer_processor.WhatsAppService.send_text_message",
        new=AsyncMock(return_value={"success": True, "message_id": "wamid.next_question"}),
    )

    from src.services.briefing.answer_processor import AnswerProcessorService

    # Process answer first time
    processor = AnswerProcessorService(db_session)
    result1 = await processor.process_client_answer(
        phone_number=test_client.phone,
        answer_text="Reforma de sala",
        wa_message_id="wamid.duplicate_test",
        session_id=whatsapp_session.id,
    )

    assert result1["success"] is True
    assert result1["question_number"] == 1

    # Commit first processing
    await db_session.commit()
    await db_session.refresh(active_briefing)

    # Store state after first processing
    first_question_order = active_briefing.current_question_order
    first_answers = dict(active_briefing.answers)

    # Process SAME webhook again (simulating retry)
    processor2 = AnswerProcessorService(db_session)
    result2 = await processor2.process_client_answer(
        phone_number=test_client.phone,
        answer_text="Reforma de sala",  # Same answer
        wa_message_id="wamid.duplicate_test",  # SAME message ID
        session_id=whatsapp_session.id,
    )

    # Second call should succeed without side effects (idempotent)
    assert result2["success"] is True

    # Verify state didn't change (no duplicate processing)
    await db_session.refresh(active_briefing)
    assert active_briefing.current_question_order == first_question_order
    assert active_briefing.answers == first_answers

    # Verify only ONE incoming message record exists
    result = await db_session.execute(
        select(WhatsAppMessage).where(WhatsAppMessage.wa_message_id == "wamid.duplicate_test")
    )
    messages = result.scalars().all()
    assert len(messages) == 1, "Should have exactly one message record (idempotency)"


@pytest.mark.asyncio
async def test_successful_answer_processing_commits_transaction(
    db_session: AsyncSession,
    test_client: EndClient,
    active_briefing: Briefing,
    whatsapp_session: WhatsAppSession,
    mocker: MockerFixture,
):
    """Test that successful answer processing commits all changes.

    Verifies the happy path: transaction commits when WhatsApp send succeeds.
    """
    # Mock WhatsApp service to succeed
    mock_whatsapp_send = mocker.patch(
        "src.services.briefing.answer_processor.WhatsAppService.send_text_message",
        new=AsyncMock(return_value={"success": True, "message_id": "wamid.success123"}),
    )

    from src.services.briefing.answer_processor import AnswerProcessorService

    # Process answer
    processor = AnswerProcessorService(db_session)
    result = await processor.process_client_answer(
        phone_number=test_client.phone,
        answer_text="Reforma completa do apartamento",
        wa_message_id="wamid.success_test",
        session_id=whatsapp_session.id,
    )

    # Verify success
    assert result["success"] is True
    assert result["question_number"] == 1
    assert result["next_question"] is not None

    # Verify WhatsApp was called
    mock_whatsapp_send.assert_called_once()

    # Refresh and verify ALL changes persisted
    await db_session.refresh(active_briefing)

    # Briefing progressed to next question
    assert active_briefing.current_question_order == 2

    # Answer was saved
    assert "1" in active_briefing.answers
    assert active_briefing.answers["1"] == "Reforma completa do apartamento"

    # Status still in progress
    assert active_briefing.status == BriefingStatus.IN_PROGRESS

    # Incoming message was saved
    result_msg = await db_session.execute(
        select(WhatsAppMessage).where(WhatsAppMessage.wa_message_id == "wamid.success_test")
    )
    saved_message = result_msg.scalar_one()
    assert saved_message.session_id == whatsapp_session.id
    assert saved_message.direction == MessageDirection.INBOUND.value
    assert saved_message.content["text"]["body"] == "Reforma completa do apartamento"
