"""
Test Question Progression Logic - Issue 1.1

Tests for session-based question progression with condition infrastructure support.
Following TDD RED-GREEN-REFACTOR methodology.
"""

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.briefing import Briefing
from src.db.models.template_version import TemplateVersion
from src.db.models.whatsapp_session import WhatsAppSession
from src.services.briefing.orchestrator import BriefingOrchestrator

# All fixtures are centralized in tests/fixtures/
# Used: briefing_with_session, template_version_simple, template_with_conditions


@pytest.mark.asyncio
async def test_session_starts_with_question_index_1(
    db_session: AsyncSession,
    briefing_with_session: tuple[Briefing, WhatsAppSession],
):
    """
    RED TEST: New WhatsApp sessions should start with current_question_index=1.

    This test will FAIL because current_question_index field doesn't exist yet.
    """
    _, session = briefing_with_session

    # Refresh to get latest state
    await db_session.refresh(session)

    # Assert session has current_question_index field with default value 1
    assert hasattr(
        session, "current_question_index"
    ), "WhatsAppSession missing current_question_index field"
    assert session.current_question_index == 1


@pytest.mark.asyncio
async def test_get_next_question_uses_session_index(
    db_session: AsyncSession,
    briefing_with_session: tuple[Briefing, WhatsAppSession],
    template_version_simple: TemplateVersion,
):
    """
    RED TEST: get_next_question_for_session should use session.current_question_index.

    This test will FAIL because the method doesn't exist yet.
    """
    briefing, session = briefing_with_session

    # Manually set session index to question 2
    session.current_question_index = 2
    await db_session.commit()

    # Create orchestrator
    orchestrator = BriefingOrchestrator(db_session)

    # Get next question for session (should return question order 2)
    question = await orchestrator.get_next_question_for_session(
        session_id=session.id,
        template_version_id=template_version_simple.id,
    )

    assert question is not None
    assert question["order"] == 2
    assert "orçamento" in question["question"].lower()


@pytest.mark.asyncio
async def test_process_answer_increments_session_index(
    db_session: AsyncSession,
    briefing_with_session: tuple[Briefing, WhatsAppSession],
):
    """
    RED TEST: Processing an answer should increment session.current_question_index.

    This test will FAIL because orchestrator doesn't update session state yet.
    """
    briefing, session = briefing_with_session

    orchestrator = BriefingOrchestrator(db_session)

    # Process answer to question 1
    await orchestrator.process_answer(
        briefing_id=briefing.id,
        question_order=1,
        answer="Casa residencial",
        session_id=session.id,
    )

    # Refresh session to get updated state
    await db_session.refresh(session)

    # Session index should now be 2
    assert session.current_question_index == 2


@pytest.mark.asyncio
async def test_skip_already_answered_questions(
    db_session: AsyncSession,
    briefing_with_session: tuple[Briefing, WhatsAppSession],
    template_version_simple: TemplateVersion,
):
    """
    RED TEST: When resuming, should skip questions that already have answers.

    This test will FAIL because skip logic doesn't exist yet.
    """
    briefing, session = briefing_with_session

    # Simulate scenario: user answered questions 1 and 2, but session index is still at 1
    briefing.answers = {
        "1": "Casa residencial",
        "2": "R$ 500.000",
    }
    briefing.current_question_order = 2
    session.current_question_index = 1  # Out of sync
    await db_session.commit()

    orchestrator = BriefingOrchestrator(db_session)

    # Get next question - should skip to question 3 (first unanswered)
    question = await orchestrator.get_next_question_for_session(
        session_id=session.id,
        template_version_id=template_version_simple.id,
    )

    assert question is not None
    assert question["order"] == 3
    assert "prazo" in question["question"].lower()


@pytest.mark.asyncio
async def test_question_with_conditions_field_parses(
    db_session: AsyncSession,
    template_with_conditions: TemplateVersion,
):
    """
    RED TEST: Template questions should support optional 'conditions' field.

    This test validates infrastructure for future branching logic (Issue 2.2).
    Will FAIL if schema doesn't accept conditions.
    """
    # Template already created in fixture with conditions
    questions = template_with_conditions.questions

    # Find question 2 (conditional on residencial)
    q2 = next(q for q in questions if q["order"] == 2)

    assert "conditions" in q2
    assert q2["conditions"]["depends_on_order"] == 1
    assert q2["conditions"]["answer_contains"] == "residencial"

    # Find question 3 (conditional on comercial)
    q3 = next(q for q in questions if q["order"] == 3)

    assert "conditions" in q3
    assert q3["conditions"]["depends_on_order"] == 1
    assert q3["conditions"]["answer_contains"] == "comercial"


@pytest.mark.asyncio
async def test_session_and_briefing_stay_in_sync(
    db_session: AsyncSession,
    briefing_with_session: tuple[Briefing, WhatsAppSession],
):
    """
    RED TEST: Session and Briefing progression should stay synchronized.

    This test will FAIL because sync logic doesn't exist yet.
    """
    briefing, session = briefing_with_session

    orchestrator = BriefingOrchestrator(db_session)

    # Process three answers
    for order, answer_text in [(1, "Casa"), (2, "R$ 300k"), (3, "6 meses")]:
        await orchestrator.process_answer(
            briefing_id=briefing.id,
            question_order=order,
            answer=answer_text,
            session_id=session.id,
        )

    # Refresh both entities
    await db_session.refresh(briefing)
    await db_session.refresh(session)

    # Both should be at question 4 (next unanswered)
    assert briefing.current_question_order == 4
    assert session.current_question_index == 4


@pytest.mark.asyncio
async def test_get_next_question_for_session_handles_missing_session(
    db_session: AsyncSession,
    template_version_simple: TemplateVersion,
):
    """
    RED TEST: Should raise appropriate error for non-existent session.

    This test will FAIL because the method doesn't exist yet.
    """
    orchestrator = BriefingOrchestrator(db_session)

    with pytest.raises(ValueError, match="Session not found"):
        await orchestrator.get_next_question_for_session(
            session_id=uuid4(),  # Non-existent UUID
            template_version_id=template_version_simple.id,
        )


@pytest.mark.asyncio
async def test_process_answer_with_session_id_updates_both(
    db_session: AsyncSession,
    briefing_with_session: tuple[Briefing, WhatsAppSession],
):
    """
    RED TEST: process_answer should accept optional session_id and update both states.

    This test will FAIL because session_id parameter doesn't exist yet.
    """
    briefing, session = briefing_with_session

    orchestrator = BriefingOrchestrator(db_session)

    # Process answer with session_id provided
    await orchestrator.process_answer(
        briefing_id=briefing.id,
        question_order=1,
        answer="Apartamento",
        session_id=session.id,  # New parameter
    )

    # Refresh both
    await db_session.refresh(briefing)
    await db_session.refresh(session)

    # Both should be updated
    assert briefing.current_question_order == 2
    assert session.current_question_index == 2
    assert briefing.answers["1"] == "Apartamento"
