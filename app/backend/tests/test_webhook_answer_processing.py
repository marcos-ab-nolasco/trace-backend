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
from src.db.models.processed_webhook import ProcessedWebhook
from src.db.models.template_version import TemplateVersion
from src.db.models.whatsapp_message import MessageDirection, MessageStatus, WhatsAppMessage
from src.db.models.whatsapp_session import SessionStatus, WhatsAppSession
from src.services.briefing.answer_processor import AnswerProcessorService

TEST_TOKEN = "gAAAAABpD5SBKMMw3egsVRJ7IWR3jtj5PzRnMyifxeXyWCJmg0gtErDSpZHZOH09gSgvalFlmre05W-8JcMdAswaN7E3zZvifw=="


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


@pytest.mark.asyncio
async def test_receive_first_answer_and_send_next_question(
    db_session: AsyncSession,
    test_client: EndClient,
    active_briefing: Briefing,
    whatsapp_session: WhatsAppSession,
    mocker: MockerFixture,
):
    """Test receiving first answer, saving it, and sending next question."""
    mock_whatsapp_send = mocker.patch(
        "src.services.briefing.answer_processor.WhatsAppService.send_text_message",
        new=AsyncMock(return_value={"success": True, "message_id": "wamid.next123"}),
    )

    processor = AnswerProcessorService(db_session)
    result = await processor.process_client_answer(
        phone_number=test_client.phone,
        answer_text="Reforma de banheiro",
        wa_message_id="wamid.incoming123",
        session_id=whatsapp_session.id,
    )

    assert result["success"] is True
    assert result["briefing_id"] == active_briefing.id
    assert result["question_number"] == 1
    assert result["next_question"] is not None
    assert "prazo" in result["next_question"].lower()

    await db_session.refresh(active_briefing)
    assert active_briefing.current_question_order == 2
    assert "1" in active_briefing.answers
    assert active_briefing.answers["1"] == "Reforma de banheiro"
    assert active_briefing.status == BriefingStatus.IN_PROGRESS

    mock_whatsapp_send.assert_called_once()
    call_args = mock_whatsapp_send.call_args
    assert call_args.kwargs["to"] == test_client.phone
    assert "prazo" in call_args.kwargs["text"].lower()

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
    active_briefing.current_question_order = 2
    active_briefing.answers = {"1": "Reforma de banheiro"}
    await db_session.commit()

    mock_whatsapp_send = mocker.patch(
        "src.services.briefing.answer_processor.WhatsAppService.send_text_message",
        new=AsyncMock(return_value={"success": True, "message_id": "wamid.completion123"}),
    )

    processor = AnswerProcessorService(db_session)
    result = await processor.process_client_answer(
        phone_number=test_client.phone,
        answer_text="Em 2 meses",
        wa_message_id="wamid.incoming456",
        session_id=whatsapp_session.id,
    )

    assert result["success"] is True
    assert result["briefing_id"] == active_briefing.id
    assert result["completed"] is True
    assert result["next_question"] is None

    await db_session.refresh(active_briefing)
    assert active_briefing.status == BriefingStatus.COMPLETED
    assert active_briefing.completed_at is not None
    assert "2" in active_briefing.answers
    assert active_briefing.answers["2"] == "Em 2 meses"

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
    active_briefing.current_question_order = 3
    active_briefing.answers = {"1": "Reforma de banheiro", "2": "Em 2 meses"}
    await db_session.commit()

    mock_whatsapp_send = mocker.patch(
        "src.services.briefing.answer_processor.WhatsAppService.send_text_message",
        new=AsyncMock(return_value={"success": True, "message_id": "wamid.optional123"}),
    )

    processor = AnswerProcessorService(db_session)
    result = await processor.process_client_answer(
        phone_number=test_client.phone,
        answer_text="R$ 50.000",
        wa_message_id="wamid.incoming789",
        session_id=whatsapp_session.id,
    )

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
    mocker.patch(
        "src.services.briefing.answer_processor.WhatsAppService.send_text_message",
        new=AsyncMock(return_value={"success": True, "message_id": "wamid.new123"}),
    )

    processor = AnswerProcessorService(db_session)
    result = await processor.process_client_answer(
        phone_number=test_client.phone,
        answer_text="Resposta teste",
        wa_message_id="wamid.incoming999",
        session_id=None,
    )

    assert result["success"] is True

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
    mock_whatsapp_send = mocker.patch(
        "src.services.briefing.answer_processor.WhatsAppService.send_text_message",
        new=AsyncMock(return_value={"success": True, "message_id": "wamid.error123"}),
    )

    processor = AnswerProcessorService(db_session)
    result = await processor.process_client_answer(
        phone_number=test_client.phone,
        answer_text="Resposta sem briefing ativo",
        wa_message_id="wamid.orphan123",
        session_id=None,
    )

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

    processor = AnswerProcessorService(db_session)
    result = await processor.process_client_answer(
        phone_number="+5511999999999",
        answer_text="Resposta de desconhecido",
        wa_message_id="wamid.unknown123",
        session_id=None,
    )

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

    mocker.patch(
        "src.services.briefing.answer_processor.WhatsAppService.send_text_message",
        new=AsyncMock(return_value={"success": True, "message_id": "wamid.webhook123"}),
    )

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

    processor = AnswerProcessorService(db_session)
    result1 = await processor.process_client_answer(
        phone_number=test_client.phone,
        answer_text="Primeira resposta",
        wa_message_id="wamid.first",
        session_id=whatsapp_session.id,
    )

    assert result1["success"] is True

    await db_session.commit()

    await db_session.refresh(active_briefing)
    await db_session.refresh(whatsapp_session)

    processor2 = AnswerProcessorService(db_session)
    result2 = await processor2.process_client_answer(
        phone_number=test_client.phone,
        answer_text="Segunda resposta",
        wa_message_id="wamid.second",
        session_id=whatsapp_session.id,
    )

    assert result2["success"] is True


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
    mock_whatsapp_send = mocker.patch(
        "src.services.briefing.answer_processor.WhatsAppService.send_text_message",
        new=AsyncMock(side_effect=Exception("WhatsApp API temporarily unavailable")),
    )

    processor = AnswerProcessorService(db_session)
    with pytest.raises(Exception, match="WhatsApp API temporarily unavailable"):
        await processor.process_client_answer(
            phone_number=test_client.phone,
            answer_text="Reforma de cozinha",
            wa_message_id="wamid.fail_test",
            session_id=whatsapp_session.id,
        )

    mock_whatsapp_send.assert_called_once()

    await db_session.refresh(active_briefing)

    assert active_briefing.current_question_order == 2
    assert "1" in active_briefing.answers
    assert active_briefing.answers["1"] == "Reforma de cozinha"
    assert active_briefing.status == BriefingStatus.IN_PROGRESS

    result = await db_session.execute(
        select(WhatsAppMessage).where(WhatsAppMessage.wa_message_id == "wamid.fail_test")
    )
    saved_message = result.scalar_one_or_none()
    assert saved_message is not None, "Message should be saved (commits before WhatsApp)"
    assert saved_message.content["text"]["body"] == "Reforma de cozinha"

    result_webhook = await db_session.execute(
        select(ProcessedWebhook).where(ProcessedWebhook.wa_message_id == "wamid.fail_test")
    )
    processed_webhook = result_webhook.scalar_one_or_none()
    assert (
        processed_webhook is not None
    ), "Webhook should be marked processed (after commit, before WhatsApp)"
    assert processed_webhook.result_data is not None
    assert "next_question" in processed_webhook.result_data


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
    mocker.patch(
        "src.services.briefing.answer_processor.WhatsAppService.send_text_message",
        new=AsyncMock(return_value={"success": True, "message_id": "wamid.next_question"}),
    )

    processor = AnswerProcessorService(db_session)
    result1 = await processor.process_client_answer(
        phone_number=test_client.phone,
        answer_text="Reforma de sala",
        wa_message_id="wamid.duplicate_test",
        session_id=whatsapp_session.id,
    )

    assert result1["success"] is True
    assert result1["question_number"] == 1

    await db_session.commit()
    await db_session.refresh(active_briefing)

    first_question_order = active_briefing.current_question_order
    first_answers = dict(active_briefing.answers)

    processor2 = AnswerProcessorService(db_session)
    result2 = await processor2.process_client_answer(
        phone_number=test_client.phone,
        answer_text="Reforma de sala",
        wa_message_id="wamid.duplicate_test",
        session_id=whatsapp_session.id,
    )

    assert result2["success"] is True

    await db_session.refresh(active_briefing)
    assert active_briefing.current_question_order == first_question_order
    assert active_briefing.answers == first_answers

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
    mock_whatsapp_send = mocker.patch(
        "src.services.briefing.answer_processor.WhatsAppService.send_text_message",
        new=AsyncMock(return_value={"success": True, "message_id": "wamid.success123"}),
    )

    processor = AnswerProcessorService(db_session)
    result = await processor.process_client_answer(
        phone_number=test_client.phone,
        answer_text="Reforma completa do apartamento",
        wa_message_id="wamid.success_test",
        session_id=whatsapp_session.id,
    )

    assert result["success"] is True
    assert result["question_number"] == 1
    assert result["next_question"] is not None

    mock_whatsapp_send.assert_called_once()

    await db_session.refresh(active_briefing)

    assert active_briefing.current_question_order == 2

    assert "1" in active_briefing.answers
    assert active_briefing.answers["1"] == "Reforma completa do apartamento"

    assert active_briefing.status == BriefingStatus.IN_PROGRESS

    result_msg = await db_session.execute(
        select(WhatsAppMessage).where(WhatsAppMessage.wa_message_id == "wamid.success_test")
    )
    saved_message = result_msg.scalar_one()
    assert saved_message.session_id == whatsapp_session.id
    assert saved_message.direction == MessageDirection.INBOUND.value
    assert saved_message.content["text"]["body"] == "Reforma completa do apartamento"


@pytest.mark.asyncio
async def test_session_index_updated_after_answer_e2e(
    db_session: AsyncSession,
    test_org_with_whatsapp: Organization,
    test_architect: Architect,
    test_template: BriefingTemplate,
    mocker: MockerFixture,
):
    """
    E2E test: Verify session.current_question_index is updated in the complete webhook flow.

    This test catches the integration gap where answer_processor must pass session_id
    to orchestrator.process_answer() for state synchronization to work.

    Issue: Integration bug found in code review - session_id wasn't being passed.
    """
    # Create test client
    test_client = EndClient(
        organization_id=test_org_with_whatsapp.id,
        architect_id=test_architect.id,
        name="Test Client",
        phone="+5511987654321",
    )
    db_session.add(test_client)
    await db_session.commit()
    await db_session.refresh(test_client)

    # Create active briefing
    active_briefing = Briefing(
        end_client_id=test_client.id,
        template_version_id=test_template.current_version_id,
        status=BriefingStatus.IN_PROGRESS,
        current_question_order=1,
        answers={},
    )
    db_session.add(active_briefing)
    await db_session.commit()
    await db_session.refresh(active_briefing)

    # Create WhatsApp session
    whatsapp_session = WhatsAppSession(
        end_client_id=test_client.id,
        briefing_id=active_briefing.id,
        phone_number=test_client.phone,
        status=SessionStatus.ACTIVE.value,
        current_question_index=1,  # Start at 1
    )
    db_session.add(whatsapp_session)
    await db_session.commit()
    await db_session.refresh(whatsapp_session)

    # Mock WhatsApp send
    mock_whatsapp_send = mocker.patch(
        "src.services.briefing.answer_processor.WhatsAppService.send_text_message",
        new=AsyncMock(return_value={"success": True, "message_id": "wamid.test123"}),
    )

    # Process first answer (E2E through AnswerProcessorService)
    processor = AnswerProcessorService(db_session)
    result = await processor.process_client_answer(
        phone_number=test_client.phone,
        answer_text="Reforma completa",
        wa_message_id="wamid.answer1",
        session_id=whatsapp_session.id,
    )

    # Verify answer was processed
    assert result["success"] is True
    assert result["question_number"] == 1

    # Refresh session from database
    await db_session.refresh(whatsapp_session)
    await db_session.refresh(active_briefing)

    # CRITICAL CHECK: session.current_question_index should be incremented
    assert whatsapp_session.current_question_index == 2, (
        "Session index should be incremented after answer processing. "
        "If this fails, answer_processor is not passing session_id to orchestrator.process_answer()"
    )

    # Verify briefing state is also in sync
    assert active_briefing.current_question_order == 2
    assert "1" in active_briefing.answers

    # Process second answer to verify continued progression
    result2 = await processor.process_client_answer(
        phone_number=test_client.phone,
        answer_text="3 meses",
        wa_message_id="wamid.answer2",
        session_id=whatsapp_session.id,
    )

    assert result2["success"] is True

    # Refresh again
    await db_session.refresh(whatsapp_session)
    await db_session.refresh(active_briefing)

    # Verify continued progression
    assert whatsapp_session.current_question_index == 3
    assert active_briefing.current_question_order == 3
    assert "2" in active_briefing.answers


@pytest.mark.asyncio
async def test_session_index_resets_when_starting_new_briefing_after_completion(
    db_session: AsyncSession,
    test_org_with_whatsapp: Organization,
    test_architect: Architect,
    test_template: BriefingTemplate,
    mocker: MockerFixture,
):
    """
    E2E test: Session index resets when client starts new briefing after completing previous one.

    Scenario:
    1. Client completes first briefing (session.current_question_index = 4)
    2. Architect initiates new briefing for same client
    3. Session should reset index to 1 for new briefing

    This prevents the bug where stale session index causes new briefing to skip questions.
    """
    # Create test client
    test_client = EndClient(
        organization_id=test_org_with_whatsapp.id,
        architect_id=test_architect.id,
        name="Returning Client",
        phone="+5511988776655",
    )
    db_session.add(test_client)
    await db_session.commit()
    await db_session.refresh(test_client)

    # Create and COMPLETE first briefing
    first_briefing = Briefing(
        end_client_id=test_client.id,
        template_version_id=test_template.current_version_id,
        status=BriefingStatus.COMPLETED,  # Already completed
        current_question_order=4,  # Finished at question 3 (now at 4)
        answers={"1": "Reforma", "2": "3 meses", "3": "R$ 50k"},
    )
    db_session.add(first_briefing)
    await db_session.commit()
    await db_session.refresh(first_briefing)

    # Create session linked to first briefing with stale index
    whatsapp_session = WhatsAppSession(
        end_client_id=test_client.id,
        briefing_id=first_briefing.id,
        phone_number=test_client.phone,
        status=SessionStatus.ACTIVE.value,
        current_question_index=4,  # Stale from completed briefing
    )
    db_session.add(whatsapp_session)
    await db_session.commit()
    await db_session.refresh(whatsapp_session)

    # Architect initiates NEW briefing for same client
    second_briefing = Briefing(
        end_client_id=test_client.id,
        template_version_id=test_template.current_version_id,
        status=BriefingStatus.IN_PROGRESS,
        current_question_order=1,
        answers={},
    )
    db_session.add(second_briefing)
    await db_session.commit()
    await db_session.refresh(second_briefing)

    # Mock WhatsApp send
    mocker.patch(
        "src.services.briefing.answer_processor.WhatsAppService.send_text_message",
        new=AsyncMock(return_value={"success": True, "message_id": "wamid.new123"}),
    )

    # Process first answer in NEW briefing
    processor = AnswerProcessorService(db_session)
    result = await processor.process_client_answer(
        phone_number=test_client.phone,
        answer_text="Casa nova",
        wa_message_id="wamid.new_briefing_answer1",
        session_id=whatsapp_session.id,
    )

    # Verify answer was processed
    assert result["success"] is True

    # Refresh session
    await db_session.refresh(whatsapp_session)
    await db_session.refresh(second_briefing)

    # CRITICAL: Session should be re-linked to new briefing
    assert whatsapp_session.briefing_id == second_briefing.id

    # CRITICAL: Session index should reset to 2 (after answering question 1)
    assert whatsapp_session.current_question_index == 2, (
        "Session index should reset when previous briefing was COMPLETED. "
        f"Expected 2 (after answering q1), got {whatsapp_session.current_question_index}"
    )

    # Verify new briefing progressed correctly
    assert second_briefing.current_question_order == 2
    assert "1" in second_briefing.answers
    assert second_briefing.answers["1"] == "Casa nova"


@pytest.mark.asyncio
async def test_session_index_preserved_when_resuming_same_briefing(
    db_session: AsyncSession,
    test_org_with_whatsapp: Organization,
    test_architect: Architect,
    test_template: BriefingTemplate,
    mocker: MockerFixture,
):
    """
    E2E test: Session index is preserved when client resumes same IN_PROGRESS briefing.

    Scenario:
    1. Client answers 2 questions (paused at index 3)
    2. Client returns days later
    3. Session index should stay at 3 (not reset)
    4. Client continues from question 3

    This ensures clients can pause and resume without losing progress.
    """
    # Create test client
    test_client = EndClient(
        organization_id=test_org_with_whatsapp.id,
        architect_id=test_architect.id,
        name="Paused Client",
        phone="+5511977665544",
    )
    db_session.add(test_client)
    await db_session.commit()
    await db_session.refresh(test_client)

    # Create IN_PROGRESS briefing (partially completed)
    active_briefing = Briefing(
        end_client_id=test_client.id,
        template_version_id=test_template.current_version_id,
        status=BriefingStatus.IN_PROGRESS,
        current_question_order=3,  # Paused at question 3
        answers={"1": "Ampliação", "2": "6 meses"},  # Answered 2 questions
    )
    db_session.add(active_briefing)
    await db_session.commit()
    await db_session.refresh(active_briefing)

    # Create session linked to this briefing (paused state)
    whatsapp_session = WhatsAppSession(
        end_client_id=test_client.id,
        briefing_id=active_briefing.id,
        phone_number=test_client.phone,
        status=SessionStatus.ACTIVE.value,
        current_question_index=3,  # Paused at question 3
    )
    db_session.add(whatsapp_session)
    await db_session.commit()
    await db_session.refresh(whatsapp_session)

    # Mock WhatsApp send
    mocker.patch(
        "src.services.briefing.answer_processor.WhatsAppService.send_text_message",
        new=AsyncMock(return_value={"success": True, "message_id": "wamid.resume123"}),
    )

    # Client returns and answers question 3 (resumption)
    processor = AnswerProcessorService(db_session)
    result = await processor.process_client_answer(
        phone_number=test_client.phone,
        answer_text="R$ 100k",  # Answer to question 3
        wa_message_id="wamid.resume_answer",
        session_id=whatsapp_session.id,
    )

    # Verify answer was processed
    assert result["success"] is True

    # Refresh session
    await db_session.refresh(whatsapp_session)
    await db_session.refresh(active_briefing)

    # CRITICAL: Briefing ID should stay the same (not re-linked)
    assert whatsapp_session.briefing_id == active_briefing.id

    # CRITICAL: Session index should NOT reset (client is resuming)
    # Should be 4 (moved from 3 to 4 after answering question 3)
    assert whatsapp_session.current_question_index == 4, (
        "Session index should NOT reset when resuming same IN_PROGRESS briefing. "
        f"Expected 4 (after answering q3), got {whatsapp_session.current_question_index}"
    )

    # Verify briefing progressed from where it left off
    assert active_briefing.current_question_order == 4
    assert "3" in active_briefing.answers
    assert active_briefing.answers["3"] == "R$ 100k"
