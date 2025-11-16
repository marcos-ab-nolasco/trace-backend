"""Tests for ConversationMemory service."""

from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import select

from src.db.models.conversation_message import ConversationMessage
from src.services.ai.base import BaseAIService
from src.services.conversation.memory.conversation_memory import ConversationMemory
from tests.factories import (
    ArchitectFactory,
    BriefingFactory,
    BriefingTemplateFactory,
    EndClientFactory,
    OrganizationFactory,
    TemplateVersionFactory,
)


@pytest.fixture
def mock_ai_service() -> Mock:
    """Create a mock AI service for testing."""
    mock = Mock(spec=BaseAIService)
    mock.generate_response = AsyncMock(return_value="This is a test summary of the conversation.")
    return mock


@pytest.fixture
async def test_briefing(db_session, test_project_type):
    """Create a test briefing with all required relationships."""
    org = await OrganizationFactory.create_async(name="Test Org")

    template = await BriefingTemplateFactory.create_async(
        name="Test Template",
        is_global=False,
        organization_id=org.id,
        project_type=test_project_type,
    )

    version = await TemplateVersionFactory.create_async(
        template_id=template.id,
        version_number=1,
        questions=[],
        context_prompt="Test context",
    )

    architect = await ArchitectFactory.create_async(
        email="architect@test.com",
        full_name="Test Architect",
        phone="+5511999999999",
        organization_id=org.id,
    )

    end_client = await EndClientFactory.create_async(
        name="Test Client",
        phone="+5511888888888",
        architect_id=architect.id,
        organization_id=org.id,
    )

    briefing = await BriefingFactory.create_async(
        end_client_id=end_client.id,
        template_version_id=version.id,
        current_question_order=1,
        answers={},
        information_state={},
        gathered_information={},
    )

    return briefing


class TestConversationMemory:
    """Test suite for ConversationMemory class."""

    @pytest.mark.asyncio
    async def test_add_message(self, db_session, test_briefing, mock_ai_service) -> None:
        """Test adding a message to conversation."""
        memory = ConversationMemory(
            db_session=db_session,
            briefing_id=test_briefing.id,
            ai_service=mock_ai_service,
        )

        message_id = await memory.add_message(
            role="user",
            content="Hello, I need help with my project.",
        )

        # Verify message was saved
        assert message_id is not None
        result = await db_session.execute(
            select(ConversationMessage).where(ConversationMessage.id == message_id)
        )
        saved_message = result.scalar_one()

        assert saved_message.role == "user"
        assert saved_message.content == "Hello, I need help with my project."
        assert saved_message.briefing_id == test_briefing.id
        assert isinstance(saved_message.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_add_message_with_metadata(
        self, db_session, test_briefing, mock_ai_service
    ) -> None:
        """Test adding a message with metadata."""
        memory = ConversationMemory(
            db_session=db_session,
            briefing_id=test_briefing.id,
            ai_service=mock_ai_service,
        )

        metadata = {"model": "gpt-4", "tokens": 150}
        message_id = await memory.add_message(
            role="assistant",
            content="I can help you with that.",
            ai_metadata=metadata,
        )

        result = await db_session.execute(
            select(ConversationMessage).where(ConversationMessage.id == message_id)
        )
        saved_message = result.scalar_one()

        assert saved_message.ai_metadata == metadata

    @pytest.mark.asyncio
    async def test_get_messages(self, db_session, test_briefing, mock_ai_service) -> None:
        """Test retrieving all messages in chronological order."""
        memory = ConversationMemory(
            db_session=db_session,
            briefing_id=test_briefing.id,
            ai_service=mock_ai_service,
        )

        # Add multiple messages
        await memory.add_message(role="user", content="First message")
        await memory.add_message(role="assistant", content="Second message")
        await memory.add_message(role="user", content="Third message")

        messages = await memory.get_messages()

        assert len(messages) == 3
        assert messages[0].content == "First message"
        assert messages[1].content == "Second message"
        assert messages[2].content == "Third message"

    @pytest.mark.asyncio
    async def test_get_recent_messages(self, db_session, test_briefing, mock_ai_service) -> None:
        """Test retrieving N most recent messages."""
        memory = ConversationMemory(
            db_session=db_session,
            briefing_id=test_briefing.id,
            ai_service=mock_ai_service,
        )

        # Add 5 messages
        for i in range(5):
            await memory.add_message(role="user", content=f"Message {i + 1}")

        # Get only the 3 most recent
        recent = await memory.get_recent_messages(limit=3)

        assert len(recent) == 3
        assert recent[0].content == "Message 3"
        assert recent[1].content == "Message 4"
        assert recent[2].content == "Message 5"

    @pytest.mark.asyncio
    async def test_get_message_count(self, db_session, test_briefing, mock_ai_service) -> None:
        """Test counting messages in conversation."""
        memory = ConversationMemory(
            db_session=db_session,
            briefing_id=test_briefing.id,
            ai_service=mock_ai_service,
        )

        # Initially no messages
        count = await memory.get_message_count()
        assert count == 0

        # Add messages
        await memory.add_message(role="user", content="Message 1")
        await memory.add_message(role="assistant", content="Message 2")

        count = await memory.get_message_count()
        assert count == 2

    @pytest.mark.asyncio
    async def test_format_for_ai(self, db_session, test_briefing, mock_ai_service) -> None:
        """Test formatting messages for AI API calls."""
        memory = ConversationMemory(
            db_session=db_session,
            briefing_id=test_briefing.id,
            ai_service=mock_ai_service,
        )

        await memory.add_message(role="user", content="Hello!")
        await memory.add_message(role="assistant", content="Hi there!")

        formatted = await memory.format_for_ai()

        assert len(formatted) == 2
        assert formatted[0] == {"role": "user", "content": "Hello!"}
        assert formatted[1] == {"role": "assistant", "content": "Hi there!"}

    @pytest.mark.asyncio
    async def test_format_for_ai_with_limit(
        self, db_session, test_briefing, mock_ai_service
    ) -> None:
        """Test formatting messages with a limit."""
        memory = ConversationMemory(
            db_session=db_session,
            briefing_id=test_briefing.id,
            ai_service=mock_ai_service,
        )

        for i in range(5):
            await memory.add_message(role="user", content=f"Message {i + 1}")

        formatted = await memory.format_for_ai(limit=2)

        assert len(formatted) == 2
        assert formatted[0]["content"] == "Message 4"
        assert formatted[1]["content"] == "Message 5"

    @pytest.mark.asyncio
    async def test_generate_summary(self, db_session, test_briefing, mock_ai_service) -> None:
        """Test generating AI-powered conversation summary."""
        memory = ConversationMemory(
            db_session=db_session,
            briefing_id=test_briefing.id,
            ai_service=mock_ai_service,
        )

        await memory.add_message(role="user", content="I need a website")
        await memory.add_message(role="assistant", content="What kind of website?")
        await memory.add_message(role="user", content="E-commerce")

        summary = await memory.generate_summary()

        # Verify AI service was called
        mock_ai_service.generate_response.assert_called_once()
        assert summary == "This is a test summary of the conversation."

    @pytest.mark.asyncio
    async def test_generate_summary_empty_conversation(
        self, db_session, test_briefing, mock_ai_service
    ) -> None:
        """Test generating summary with no messages."""
        memory = ConversationMemory(
            db_session=db_session,
            briefing_id=test_briefing.id,
            ai_service=mock_ai_service,
        )

        summary = await memory.generate_summary()

        # Should return empty or default message
        assert summary == "No conversation yet."

    @pytest.mark.asyncio
    async def test_update_briefing_summary(
        self, db_session, test_briefing, mock_ai_service
    ) -> None:
        """Test updating briefing with conversation summary."""
        memory = ConversationMemory(
            db_session=db_session,
            briefing_id=test_briefing.id,
            ai_service=mock_ai_service,
        )

        await memory.add_message(role="user", content="Test message")

        await memory.update_briefing_summary()

        # Refresh briefing and check summary
        await db_session.refresh(test_briefing)
        assert test_briefing.conversation_summary == "This is a test summary of the conversation."

    @pytest.mark.asyncio
    async def test_get_context_window(self, db_session, test_briefing, mock_ai_service) -> None:
        """Test getting messages within token budget."""
        memory = ConversationMemory(
            db_session=db_session,
            briefing_id=test_briefing.id,
            ai_service=mock_ai_service,
            context_window_tokens=4000,
        )

        # Add several messages
        await memory.add_message(role="user", content="Short message 1")
        await memory.add_message(role="assistant", content="Short message 2")
        await memory.add_message(role="user", content="Short message 3")

        # Get context window
        context = await memory.get_context_window()

        # Should return messages within token limit
        assert len(context) > 0
        assert all(isinstance(msg, dict) for msg in context)
        assert all("role" in msg and "content" in msg for msg in context)

    @pytest.mark.asyncio
    async def test_get_context_window_respects_token_limit(
        self, db_session, test_briefing, mock_ai_service
    ) -> None:
        """Test that context window respects token limits."""
        memory = ConversationMemory(
            db_session=db_session,
            briefing_id=test_briefing.id,
            ai_service=mock_ai_service,
            context_window_tokens=50,  # Very small limit
        )

        # Add messages with long content
        long_content = "This is a very long message. " * 20
        for _ in range(5):
            await memory.add_message(role="user", content=long_content)

        context = await memory.get_context_window()

        # Should return fewer messages due to token limit
        assert len(context) < 5

    @pytest.mark.asyncio
    async def test_messages_isolated_by_briefing(
        self, db_session, test_briefing, mock_ai_service
    ) -> None:
        """Test that messages are isolated by briefing_id."""
        # Create another briefing
        other_briefing = await BriefingFactory.create_async(
            end_client_id=test_briefing.end_client_id,
            template_version_id=test_briefing.template_version_id,
            current_question_order=1,
            answers={},
            information_state={},
            gathered_information={},
        )

        # Create two memory instances
        memory1 = ConversationMemory(
            db_session=db_session,
            briefing_id=test_briefing.id,
            ai_service=mock_ai_service,
        )
        memory2 = ConversationMemory(
            db_session=db_session,
            briefing_id=other_briefing.id,
            ai_service=mock_ai_service,
        )

        # Add messages to each
        await memory1.add_message(role="user", content="Briefing 1 message")
        await memory2.add_message(role="user", content="Briefing 2 message")

        # Verify isolation
        messages1 = await memory1.get_messages()
        messages2 = await memory2.get_messages()

        assert len(messages1) == 1
        assert len(messages2) == 1
        assert messages1[0].content == "Briefing 1 message"
        assert messages2[0].content == "Briefing 2 message"
