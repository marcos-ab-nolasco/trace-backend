"""Conversation memory service for managing chat history and context."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.briefing import Briefing
from src.db.models.conversation_message import ConversationMessage
from src.services.ai.base import BaseAIService
from src.services.conversation.memory.token_counter import TokenCounter


class ConversationMemory:
    """Manages conversation history, context, and AI-powered summarization."""

    def __init__(
        self,
        db_session: AsyncSession,
        briefing_id: UUID,
        ai_service: BaseAIService,
        context_window_tokens: int = 4000,
        model_name: str = "gpt-4o-mini",
    ) -> None:
        """Initialize ConversationMemory service.

        Args:
            db_session: SQLAlchemy async session for database operations
            briefing_id: UUID of the briefing this conversation belongs to
            ai_service: AI service instance for generating summaries
            context_window_tokens: Maximum tokens for context window (default: 4000)
            model_name: Model name for token counting (default: "gpt-4o-mini")
        """
        self.db_session = db_session
        self.briefing_id = briefing_id
        self.ai_service = ai_service
        self.context_window_tokens = context_window_tokens
        self.model_name = model_name
        self.token_counter = TokenCounter(model_name=model_name)

    async def add_message(
        self,
        role: str,
        content: str,
        extracted_info: dict[str, Any] | None = None,
        ai_metadata: dict[str, Any] | None = None,
    ) -> UUID:
        """Add a new message to the conversation.

        Args:
            role: Message role ("user" or "assistant")
            content: Message content text
            extracted_info: Optional extracted information from the message
            ai_metadata: Optional AI-specific metadata (model, tokens, etc.)

        Returns:
            UUID of the created message
        """
        message = ConversationMessage(
            briefing_id=self.briefing_id,
            role=role,
            content=content,
            extracted_info=extracted_info,
            ai_metadata=ai_metadata,
            timestamp=datetime.now(UTC),
        )

        self.db_session.add(message)
        await self.db_session.commit()
        await self.db_session.refresh(message)

        return message.id

    async def get_messages(self) -> list[ConversationMessage]:
        """Retrieve all messages for this conversation in chronological order.

        Returns:
            List of ConversationMessage objects ordered by timestamp
        """
        result = await self.db_session.execute(
            select(ConversationMessage)
            .where(ConversationMessage.briefing_id == self.briefing_id)
            .order_by(ConversationMessage.timestamp.asc())
        )
        return list(result.scalars().all())

    async def get_recent_messages(self, limit: int) -> list[ConversationMessage]:
        """Retrieve N most recent messages.

        Args:
            limit: Maximum number of messages to retrieve

        Returns:
            List of most recent ConversationMessage objects
        """
        result = await self.db_session.execute(
            select(ConversationMessage)
            .where(ConversationMessage.briefing_id == self.briefing_id)
            .order_by(ConversationMessage.timestamp.asc())
            .limit(limit)
            .offset(
                select(func.count(ConversationMessage.id))
                .where(ConversationMessage.briefing_id == self.briefing_id)
                .scalar_subquery()
                - limit
            )
        )
        return list(result.scalars().all())

    async def get_message_count(self) -> int:
        """Get total number of messages in this conversation.

        Returns:
            Count of messages
        """
        result = await self.db_session.execute(
            select(func.count(ConversationMessage.id)).where(
                ConversationMessage.briefing_id == self.briefing_id
            )
        )
        return result.scalar() or 0

    async def format_for_ai(self, limit: int | None = None) -> list[dict[str, str]]:
        """Format messages for AI API calls.

        Args:
            limit: Optional limit on number of messages (most recent)

        Returns:
            List of message dicts with 'role' and 'content' keys
        """
        if limit is not None:
            messages = await self.get_recent_messages(limit=limit)
        else:
            messages = await self.get_messages()

        return [{"role": msg.role, "content": msg.content} for msg in messages]

    async def generate_summary(self, model: str = "gpt-4o-mini") -> str:
        """Generate AI-powered summary of the conversation.

        Args:
            model: Model to use for summary generation

        Returns:
            Summary text generated by AI
        """
        messages = await self.get_messages()

        if not messages:
            return "No conversation yet."

        # Format messages for summarization
        formatted_messages = [{"role": msg.role, "content": msg.content} for msg in messages]

        system_prompt = (
            "You are a conversation summarizer. "
            "Summarize the following conversation concisely, "
            "focusing on key information gathered and any decisions made."
        )

        # Generate summary using AI service
        summary = await self.ai_service.generate_response(
            messages=formatted_messages,
            model=model,
            system_prompt=system_prompt,
        )

        return summary

    async def update_briefing_summary(self, model: str = "gpt-4o-mini") -> None:
        """Update the briefing with a fresh conversation summary.

        Args:
            model: Model to use for summary generation
        """
        summary = await self.generate_summary(model=model)

        # Update briefing
        result = await self.db_session.execute(
            select(Briefing).where(Briefing.id == self.briefing_id)
        )
        briefing = result.scalar_one()
        briefing.conversation_summary = summary

        await self.db_session.commit()

    async def get_context_window(self) -> list[dict[str, str]]:
        """Get messages within the configured token budget.

        Returns most recent messages that fit within context_window_tokens.

        Returns:
            List of message dicts formatted for AI, within token limit
        """
        all_messages = await self.format_for_ai()

        # Truncate to fit within token budget
        truncated = self.token_counter.truncate_to_limit(
            all_messages, token_limit=self.context_window_tokens
        )

        return truncated
