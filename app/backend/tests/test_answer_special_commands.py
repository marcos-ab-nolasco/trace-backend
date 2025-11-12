"""Tests for special command handling in answer processing.

Tests cover:
- "pular" command: skip optional questions, reject on required
- "voltar" command: go back to previous question
- "não sei" command: handle gracefully based on required/optional
- Case-insensitive command detection
- Command variants
"""


import pytest
from pytest_mock import MockerFixture
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.briefing import Briefing
from src.db.models.briefing_template import BriefingTemplate
from src.db.models.end_client import EndClient
from src.db.models.template_version import TemplateVersion
from src.db.models.whatsapp_session import WhatsAppSession
from src.services.briefing.answer_processor import AnswerProcessorService


@pytest.fixture
async def template_with_mixed_questions(
    db_session: AsyncSession, test_project_type
) -> TemplateVersion:
    """Create template with mix of required/optional questions for command testing."""
    template = BriefingTemplate(
        name="Command Test Template",
        project_type_id=test_project_type.id,
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
                "question": "Nome do projeto? (obrigatório)",
                "type": "text",
                "required": True,
            },
            {
                "order": 2,
                "question": "Orçamento disponível? (obrigatório)",
                "type": "number",
                "required": True,
            },
            {
                "order": 3,
                "question": "Possui plantas antigas? (opcional)",
                "type": "text",
                "required": False,
            },
            {
                "order": 4,
                "question": "Prazo desejado? (opcional)",
                "type": "text",
                "required": False,
            },
            {
                "order": 5,
                "question": "Observações finais? (obrigatório)",
                "type": "text",
                "required": True,
            },
        ],
        is_active=True,
    )
    db_session.add(version)
    await db_session.flush()

    template.current_version_id = version.id
    await db_session.commit()
    await db_session.refresh(version)
    return version


@pytest.fixture
async def briefing_with_mixed_template(
    db_session: AsyncSession,
    test_end_client: EndClient,
    template_with_mixed_questions: TemplateVersion,
) -> tuple[Briefing, WhatsAppSession]:
    """Create briefing with mixed required/optional questions."""
    briefing = Briefing(
        end_client_id=test_end_client.id,
        template_version_id=template_with_mixed_questions.id,
        current_question_order=1,
        answers={},
        status="IN_PROGRESS",
    )
    db_session.add(briefing)
    await db_session.commit()
    await db_session.refresh(briefing)

    session = WhatsAppSession(
        end_client_id=test_end_client.id,
        briefing_id=briefing.id,
        phone_number=test_end_client.phone,
        status="ACTIVE",
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    return briefing, session


# ==================== PULAR COMMAND TESTS ====================


@pytest.mark.asyncio
async def test_pular_command_skips_optional_question(
    db_session: AsyncSession,
    test_end_client: EndClient,
    briefing_with_mixed_template: tuple[Briefing, WhatsAppSession],
    mock_whatsapp_service: MockerFixture,
):
    """Test that 'pular' command skips an optional question and moves to next."""
    briefing, session = briefing_with_mixed_template

    # Answer first 2 required questions
    briefing.answers = {1: "Projeto Casa", 2: "100000"}
    briefing.current_question_order = 3  # Question 3 is optional
    session.current_question_index = 3
    await db_session.commit()

    service = AnswerProcessorService(db_session)

    result = await service.process_client_answer(
        phone_number=test_end_client.phone,
        answer_text="pular",
        wa_message_id="msg_pular_optional",
        session_id=session.id,
    )

    assert result["success"] is True
    assert result.get("command_executed") == "pular"

    # Should move to question 4 (next optional)
    await db_session.refresh(briefing)
    await db_session.refresh(session)

    assert briefing.current_question_order == 4
    assert session.current_question_index == 4
    # Question 3 should not have an answer
    assert "3" not in briefing.answers


@pytest.mark.asyncio
async def test_pular_command_rejected_on_required_question(
    db_session: AsyncSession,
    test_end_client: EndClient,
    briefing_with_mixed_template: tuple[Briefing, WhatsAppSession],
    mock_whatsapp_service: MockerFixture,
):
    """Test that 'pular' command is rejected on required questions."""
    briefing, session = briefing_with_mixed_template

    # At question 1 (required)
    service = AnswerProcessorService(db_session)

    result = await service.process_client_answer(
        phone_number=test_end_client.phone,
        answer_text="pular",
        wa_message_id="msg_pular_required",
        session_id=session.id,
    )

    # Should return error
    assert result["success"] is False
    assert result.get("error") == "cannot_skip_required"
    assert "obrigatória" in result.get("message", "").lower()

    # Should stay on question 1
    await db_session.refresh(briefing)
    await db_session.refresh(session)
    assert briefing.current_question_order == 1
    assert session.current_question_index == 1


@pytest.mark.asyncio
async def test_pular_command_case_insensitive(
    db_session: AsyncSession,
    test_end_client: EndClient,
    briefing_with_mixed_template: tuple[Briefing, WhatsAppSession],
    mock_whatsapp_service: MockerFixture,
):
    """Test that 'pular' command works with different cases."""
    briefing, session = briefing_with_mixed_template

    # Move to optional question 3
    briefing.answers = {1: "Projeto", 2: "50000"}
    briefing.current_question_order = 3
    session.current_question_index = 3
    await db_session.commit()

    service = AnswerProcessorService(db_session)

    # Test uppercase
    result = await service.process_client_answer(
        phone_number=test_end_client.phone,
        answer_text="PULAR",
        wa_message_id="msg_pular_upper",
        session_id=session.id,
    )

    assert result["success"] is True
    assert result.get("command_executed") == "pular"


@pytest.mark.asyncio
async def test_pula_variant_command_works(
    db_session: AsyncSession,
    test_end_client: EndClient,
    briefing_with_mixed_template: tuple[Briefing, WhatsAppSession],
    mock_whatsapp_service: MockerFixture,
):
    """Test that 'pula' (without 'r') is also recognized."""
    briefing, session = briefing_with_mixed_template

    # Move to optional question
    briefing.answers = {1: "Projeto", 2: "50000"}
    briefing.current_question_order = 3
    session.current_question_index = 3
    await db_session.commit()

    service = AnswerProcessorService(db_session)

    result = await service.process_client_answer(
        phone_number=test_end_client.phone,
        answer_text="pula",
        wa_message_id="msg_pula_variant",
        session_id=session.id,
    )

    assert result["success"] is True
    assert result.get("command_executed") == "pular"


# ==================== VOLTAR COMMAND TESTS ====================


@pytest.mark.asyncio
async def test_voltar_command_goes_back_to_previous_question(
    db_session: AsyncSession,
    test_end_client: EndClient,
    briefing_with_mixed_template: tuple[Briefing, WhatsAppSession],
    mock_whatsapp_service: MockerFixture,
):
    """Test that 'voltar' command returns to previous question."""
    briefing, session = briefing_with_mixed_template

    # Answer questions 1 and 2, now at question 3
    briefing.answers = {1: "Projeto X", 2: "75000"}
    briefing.current_question_order = 3
    session.current_question_index = 3
    await db_session.commit()

    service = AnswerProcessorService(db_session)

    result = await service.process_client_answer(
        phone_number=test_end_client.phone,
        answer_text="voltar",
        wa_message_id="msg_voltar_success",
        session_id=session.id,
    )

    assert result["success"] is True
    assert result.get("command_executed") == "voltar"

    # Should be back at question 2
    await db_session.refresh(briefing)
    await db_session.refresh(session)

    assert briefing.current_question_order == 2
    assert session.current_question_index == 2

    # Previous answer should still exist
    assert "2" in briefing.answers


@pytest.mark.asyncio
async def test_voltar_command_rejected_on_first_question(
    db_session: AsyncSession,
    test_end_client: EndClient,
    briefing_with_mixed_template: tuple[Briefing, WhatsAppSession],
    mock_whatsapp_service: MockerFixture,
):
    """Test that 'voltar' command is rejected on first question."""
    briefing, session = briefing_with_mixed_template

    # At question 1 (first question)
    service = AnswerProcessorService(db_session)

    result = await service.process_client_answer(
        phone_number=test_end_client.phone,
        answer_text="voltar",
        wa_message_id="msg_voltar_first",
        session_id=session.id,
    )

    # Should return error
    assert result["success"] is False
    assert result.get("error") == "cannot_go_back"
    assert "primeira" in result.get("message", "").lower()

    # Should stay on question 1
    await db_session.refresh(briefing)
    await db_session.refresh(session)
    assert briefing.current_question_order == 1
    assert session.current_question_index == 1


@pytest.mark.asyncio
async def test_voltar_command_allows_answer_update(
    db_session: AsyncSession,
    test_end_client: EndClient,
    briefing_with_mixed_template: tuple[Briefing, WhatsAppSession],
    mock_whatsapp_service: MockerFixture,
):
    """Test that after 'voltar', user can update their previous answer."""
    briefing, session = briefing_with_mixed_template

    # Answer questions 1 and 2
    briefing.answers = {1: "Projeto Antigo", 2: "50000"}
    briefing.current_question_order = 3
    session.current_question_index = 3
    await db_session.commit()

    service = AnswerProcessorService(db_session)

    # Go back
    await service.process_client_answer(
        phone_number=test_end_client.phone,
        answer_text="voltar",
        wa_message_id="msg_voltar_setup",
        session_id=session.id,
    )

    # Now answer question 2 with new value
    result = await service.process_client_answer(
        phone_number=test_end_client.phone,
        answer_text="100000",  # New answer
        wa_message_id="msg_update_after_voltar",
        session_id=session.id,
    )

    assert result["success"] is True

    await db_session.refresh(briefing)

    # Answer should be updated
    assert briefing.answers["2"] == "100000"
    # Should progress to question 3
    assert briefing.current_question_order == 3


@pytest.mark.asyncio
async def test_voltar_command_case_insensitive(
    db_session: AsyncSession,
    test_end_client: EndClient,
    briefing_with_mixed_template: tuple[Briefing, WhatsAppSession],
    mock_whatsapp_service: MockerFixture,
):
    """Test that 'voltar' command works with different cases."""
    briefing, session = briefing_with_mixed_template

    briefing.answers = {1: "Projeto", 2: "50000"}
    briefing.current_question_order = 3
    session.current_question_index = 3
    await db_session.commit()

    service = AnswerProcessorService(db_session)

    result = await service.process_client_answer(
        phone_number=test_end_client.phone,
        answer_text="VOLTAR",
        wa_message_id="msg_voltar_upper",
        session_id=session.id,
    )

    assert result["success"] is True
    assert result.get("command_executed") == "voltar"


# ==================== NÃO SEI COMMAND TESTS ====================


@pytest.mark.asyncio
async def test_nao_sei_command_skips_optional_question(
    db_session: AsyncSession,
    test_end_client: EndClient,
    briefing_with_mixed_template: tuple[Briefing, WhatsAppSession],
    mock_whatsapp_service: MockerFixture,
):
    """Test that 'não sei' command skips optional question."""
    briefing, session = briefing_with_mixed_template

    # Move to optional question 3
    briefing.answers = {1: "Projeto", 2: "50000"}
    briefing.current_question_order = 3
    session.current_question_index = 3
    await db_session.commit()

    service = AnswerProcessorService(db_session)

    result = await service.process_client_answer(
        phone_number=test_end_client.phone,
        answer_text="não sei",
        wa_message_id="msg_nao_sei_optional",
        session_id=session.id,
    )

    assert result["success"] is True
    assert result.get("command_executed") == "não sei"

    await db_session.refresh(briefing)
    await db_session.refresh(session)

    # Should move to next question
    assert briefing.current_question_order == 4
    # Question 3 should not have answer
    assert "3" not in briefing.answers


@pytest.mark.asyncio
async def test_nao_sei_command_saves_partial_answer_on_required(
    db_session: AsyncSession,
    test_end_client: EndClient,
    briefing_with_mixed_template: tuple[Briefing, WhatsAppSession],
    mock_whatsapp_service: MockerFixture,
):
    """Test that 'não sei' on required question saves partial answer and progresses."""
    briefing, session = briefing_with_mixed_template

    # At required question 1
    service = AnswerProcessorService(db_session)

    result = await service.process_client_answer(
        phone_number=test_end_client.phone,
        answer_text="não sei",
        wa_message_id="msg_nao_sei_required",
        session_id=session.id,
    )

    assert result["success"] is True
    assert result.get("command_executed") == "não sei"

    await db_session.refresh(briefing)

    # Should save "não sei" as the answer
    assert briefing.answers["1"] == "não sei"
    # Should progress to question 2
    assert briefing.current_question_order == 2


@pytest.mark.asyncio
async def test_nao_sei_variants(
    db_session: AsyncSession,
    test_end_client: EndClient,
    briefing_with_mixed_template: tuple[Briefing, WhatsAppSession],
    mock_whatsapp_service: MockerFixture,
):
    """Test various 'não sei' variants (nao sei, n sei, etc)."""
    briefing, session = briefing_with_mixed_template

    # Move to optional question
    briefing.answers = {1: "Projeto", 2: "50000"}
    briefing.current_question_order = 3
    session.current_question_index = 3
    await db_session.commit()

    service = AnswerProcessorService(db_session)

    # Test "nao sei" (without tilde)
    result = await service.process_client_answer(
        phone_number=test_end_client.phone,
        answer_text="nao sei",
        wa_message_id="msg_nao_sei_variant",
        session_id=session.id,
    )

    assert result["success"] is True
    assert result.get("command_executed") == "não sei"


# ==================== COMMAND WITH TEXT TESTS ====================


@pytest.mark.asyncio
async def test_command_mixed_with_text_treated_as_answer(
    db_session: AsyncSession,
    test_end_client: EndClient,
    briefing_with_mixed_template: tuple[Briefing, WhatsAppSession],
    mock_whatsapp_service: MockerFixture,
):
    """Test that commands mixed with other text are treated as regular answers."""
    briefing, session = briefing_with_mixed_template

    service = AnswerProcessorService(db_session)

    # Text that contains command word but isn't just the command
    result = await service.process_client_answer(
        phone_number=test_end_client.phone,
        answer_text="quero pular essa etapa",  # Contains "pular" but not standalone
        wa_message_id="msg_mixed_text",
        session_id=session.id,
    )

    assert result["success"] is True
    assert result.get("command_executed") is None  # Should NOT be treated as command

    await db_session.refresh(briefing)

    # Should save as regular answer
    assert briefing.answers["1"] == "quero pular essa etapa"
    # Should progress normally
    assert briefing.current_question_order == 2


# ==================== VALIDATION TESTS ====================


@pytest.mark.asyncio
async def test_number_type_validation_rejects_text(
    db_session: AsyncSession,
    test_end_client: EndClient,
    briefing_with_mixed_template: tuple[Briefing, WhatsAppSession],
    mock_whatsapp_service: MockerFixture,
):
    """Test that number type questions reject non-numeric answers."""
    briefing, session = briefing_with_mixed_template

    # Move to question 2 (type: number)
    briefing.answers = {1: "Projeto Casa"}
    briefing.current_question_order = 2
    session.current_question_index = 2
    await db_session.commit()

    service = AnswerProcessorService(db_session)

    result = await service.process_client_answer(
        phone_number=test_end_client.phone,
        answer_text="muito caro",  # Not a number
        wa_message_id="msg_invalid_number",
        session_id=session.id,
    )

    # Should return validation error
    assert result["success"] is False
    assert result.get("error") == "validation_error"
    assert "número" in result.get("message", "").lower()

    await db_session.refresh(briefing)
    await db_session.refresh(session)

    # Should stay on question 2, not save invalid answer
    assert briefing.current_question_order == 2
    assert "2" not in briefing.answers


@pytest.mark.asyncio
async def test_number_type_validation_accepts_numeric_string(
    db_session: AsyncSession,
    test_end_client: EndClient,
    briefing_with_mixed_template: tuple[Briefing, WhatsAppSession],
    mock_whatsapp_service: MockerFixture,
):
    """Test that number type questions accept numeric strings."""
    briefing, session = briefing_with_mixed_template

    # Move to question 2 (type: number)
    briefing.answers = {1: "Projeto Casa"}
    briefing.current_question_order = 2
    session.current_question_index = 2
    await db_session.commit()

    service = AnswerProcessorService(db_session)

    result = await service.process_client_answer(
        phone_number=test_end_client.phone,
        answer_text="150000",  # Valid number
        wa_message_id="msg_valid_number",
        session_id=session.id,
    )

    # Should succeed
    assert result["success"] is True

    await db_session.refresh(briefing)

    # Should save and progress
    assert briefing.answers["2"] == "150000"
    assert briefing.current_question_order == 3


@pytest.mark.asyncio
async def test_number_validation_accepts_formatted_numbers(
    db_session: AsyncSession,
    test_end_client: EndClient,
    briefing_with_mixed_template: tuple[Briefing, WhatsAppSession],
    mock_whatsapp_service: MockerFixture,
):
    """Test that number validation accepts numbers with formatting (dots, commas)."""
    briefing, session = briefing_with_mixed_template

    # Move to question 2 (type: number)
    briefing.answers = {1: "Projeto Casa"}
    briefing.current_question_order = 2
    session.current_question_index = 2
    await db_session.commit()

    service = AnswerProcessorService(db_session)

    # Test with thousand separator
    result = await service.process_client_answer(
        phone_number=test_end_client.phone,
        answer_text="150.000",  # Brazilian format
        wa_message_id="msg_formatted_number",
        session_id=session.id,
    )

    assert result["success"] is True

    await db_session.refresh(briefing)
    assert "2" in briefing.answers


# ==================== MULTIPLE CHOICE VALIDATION TESTS ====================


@pytest.fixture
async def template_with_multiple_choice(
    db_session: AsyncSession, test_project_type
) -> TemplateVersion:
    """Create template with multiple choice questions for validation testing."""
    template = BriefingTemplate(
        name="Multiple Choice Template",
        project_type_id=test_project_type.id,
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
                "question": "Qual o tipo de projeto?",
                "type": "multiple_choice",
                "required": True,
                "options": ["Residencial", "Comercial", "Industrial", "Misto"],
            },
            {
                "order": 2,
                "question": "Qual o estilo preferido?",
                "type": "multiple_choice",
                "required": False,
                "options": ["Moderno", "Clássico", "Minimalista", "Rústico"],
            },
        ],
        is_active=True,
    )
    db_session.add(version)
    await db_session.flush()

    template.current_version_id = version.id
    await db_session.commit()
    await db_session.refresh(version)
    return version


@pytest.fixture
async def briefing_with_multiple_choice(
    db_session: AsyncSession,
    test_end_client: EndClient,
    template_with_multiple_choice: TemplateVersion,
) -> tuple[Briefing, WhatsAppSession]:
    """Create briefing with multiple choice template."""
    briefing = Briefing(
        end_client_id=test_end_client.id,
        template_version_id=template_with_multiple_choice.id,
        current_question_order=1,
        answers={},
        status="IN_PROGRESS",
    )
    db_session.add(briefing)
    await db_session.commit()
    await db_session.refresh(briefing)

    session = WhatsAppSession(
        end_client_id=test_end_client.id,
        briefing_id=briefing.id,
        phone_number=test_end_client.phone,
        status="ACTIVE",
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    return briefing, session


@pytest.mark.asyncio
async def test_multiple_choice_validation_rejects_invalid_option(
    db_session: AsyncSession,
    test_end_client: EndClient,
    briefing_with_multiple_choice: tuple[Briefing, WhatsAppSession],
    mock_whatsapp_service: MockerFixture,
):
    """Test that multiple choice questions reject invalid options."""
    briefing, session = briefing_with_multiple_choice

    service = AnswerProcessorService(db_session)

    result = await service.process_client_answer(
        phone_number=test_end_client.phone,
        answer_text="Espacial",  # Not in options
        wa_message_id="msg_invalid_choice",
        session_id=session.id,
    )

    # Should return validation error
    assert result["success"] is False
    assert result.get("error") == "validation_error"
    assert (
        "opção inválida" in result.get("message", "").lower()
        or "opções válidas" in result.get("message", "").lower()
    )

    await db_session.refresh(briefing)

    # Should not save invalid answer
    assert "1" not in briefing.answers
    assert briefing.current_question_order == 1


@pytest.mark.asyncio
async def test_multiple_choice_validation_accepts_valid_option(
    db_session: AsyncSession,
    test_end_client: EndClient,
    briefing_with_multiple_choice: tuple[Briefing, WhatsAppSession],
    mock_whatsapp_service: MockerFixture,
):
    """Test that multiple choice questions accept valid options."""
    briefing, session = briefing_with_multiple_choice

    service = AnswerProcessorService(db_session)

    result = await service.process_client_answer(
        phone_number=test_end_client.phone,
        answer_text="Comercial",  # Valid option
        wa_message_id="msg_valid_choice",
        session_id=session.id,
    )

    # Should succeed
    assert result["success"] is True

    await db_session.refresh(briefing)

    # Should save and progress
    assert briefing.answers["1"] == "Comercial"
    assert briefing.current_question_order == 2


@pytest.mark.asyncio
async def test_multiple_choice_validation_case_insensitive(
    db_session: AsyncSession,
    test_end_client: EndClient,
    briefing_with_multiple_choice: tuple[Briefing, WhatsAppSession],
    mock_whatsapp_service: MockerFixture,
):
    """Test that multiple choice validation is case-insensitive."""
    briefing, session = briefing_with_multiple_choice

    service = AnswerProcessorService(db_session)

    result = await service.process_client_answer(
        phone_number=test_end_client.phone,
        answer_text="comercial",  # Lowercase but valid
        wa_message_id="msg_choice_lowercase",
        session_id=session.id,
    )

    # Should succeed
    assert result["success"] is True

    await db_session.refresh(briefing)

    # Should save with original case from option
    assert briefing.answers["1"] == "Comercial"


@pytest.mark.asyncio
async def test_multiple_choice_validation_with_partial_match(
    db_session: AsyncSession,
    test_end_client: EndClient,
    briefing_with_multiple_choice: tuple[Briefing, WhatsAppSession],
    mock_whatsapp_service: MockerFixture,
):
    """Test that multiple choice accepts partial matches (e.g., 'moderno' for 'Moderno')."""
    briefing, session = briefing_with_multiple_choice

    # Move to question 2
    briefing.answers = {1: "Residencial"}
    briefing.current_question_order = 2
    session.current_question_index = 2
    await db_session.commit()

    service = AnswerProcessorService(db_session)

    result = await service.process_client_answer(
        phone_number=test_end_client.phone,
        answer_text="modern",  # Partial match
        wa_message_id="msg_partial_match",
        session_id=session.id,
    )

    # Should succeed and match "Moderno"
    assert result["success"] is True

    await db_session.refresh(briefing)
    assert briefing.answers["2"] == "Moderno"


# ==================== VALIDATION ERROR MESSAGING TESTS ====================


@pytest.mark.asyncio
async def test_validation_error_sends_helpful_message_via_whatsapp(
    db_session: AsyncSession,
    test_end_client: EndClient,
    briefing_with_mixed_template: tuple[Briefing, WhatsAppSession],
    mock_whatsapp_service: MockerFixture,
):
    """Test that validation errors send helpful messages to user via WhatsApp."""
    briefing, session = briefing_with_mixed_template

    # Move to number question
    briefing.answers = {1: "Projeto"}
    briefing.current_question_order = 2
    session.current_question_index = 2
    await db_session.commit()

    service = AnswerProcessorService(db_session)

    result = await service.process_client_answer(
        phone_number=test_end_client.phone,
        answer_text="muito caro",  # Invalid for number type
        wa_message_id="msg_validation_message",
        session_id=session.id,
    )

    # Should have helpful message
    assert result["success"] is False
    assert result.get("error") == "validation_error"
    message = result.get("message", "")
    assert len(message) > 0
    # Should explain what's expected
    assert "número" in message.lower()


@pytest.mark.asyncio
async def test_validation_maintains_idempotency(
    db_session: AsyncSession,
    test_end_client: EndClient,
    briefing_with_mixed_template: tuple[Briefing, WhatsAppSession],
    mock_whatsapp_service: MockerFixture,
):
    """Test that validation errors maintain idempotency on webhook retry."""
    briefing, session = briefing_with_mixed_template

    # Move to number question
    briefing.answers = {1: "Projeto"}
    briefing.current_question_order = 2
    session.current_question_index = 2
    await db_session.commit()

    service = AnswerProcessorService(db_session)

    # First attempt - invalid number
    result1 = await service.process_client_answer(
        phone_number=test_end_client.phone,
        answer_text="texto inválido",
        wa_message_id="msg_validation_idempotency",
        session_id=session.id,
    )

    # Second attempt - same webhook (retry)
    result2 = await service.process_client_answer(
        phone_number=test_end_client.phone,
        answer_text="texto inválido",
        wa_message_id="msg_validation_idempotency",  # Same ID
        session_id=session.id,
    )

    # Both should fail with same error
    assert result1["success"] is False
    assert result2["success"] is False
    assert result1.get("error") == result2.get("error")
