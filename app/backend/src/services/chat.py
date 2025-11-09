import logging
import time
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.cache.decorator import redis_cache_decorator
from src.db.models import Conversation, Message
from src.schemas.chat import ConversationCreate, ConversationUpdate, MessageCreate
from src.services.ai import get_ai_service

logger = logging.getLogger(__name__)


async def get_conversation_by_id(
    db: AsyncSession, conversation_id: UUID, architect_id: UUID
) -> Conversation:
    """Get a conversation by ID with authorization check.

    Args:
        db: Database session
        conversation_id: Conversation ID
        architect_id: Current architect ID

    Returns:
        Conversation object

    Raises:
        HTTPException: 404 if not found, 403 if not authorized
    """
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    if conversation.architect_id != architect_id:
        logger.warning(
            "Unauthorized conversation access: conv_id=%s architect_id=%s owner_id=%s",
            conversation_id,
            architect_id,
            conversation.architect_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this conversation",
        )

    return conversation


@redis_cache_decorator(
    ttl=300,
    ignore_positionals=[0],
    namespace="chat.user_conversations",
)
async def get_user_conversations(db: AsyncSession, architect_id: UUID) -> list[Conversation]:
    """Get all conversations for an architect.

    Args:
        db: Database session
        architect_id: Architect ID

    Returns:
        List of conversations ordered by updated_at desc
    """
    result = await db.execute(
        select(Conversation)
        .where(Conversation.architect_id == architect_id)
        .order_by(desc(Conversation.updated_at))
    )
    return list(result.scalars().all())


async def create_conversation(
    db: AsyncSession, conversation_data: ConversationCreate, architect_id: UUID
) -> Conversation:
    """Create a new conversation.

    Args:
        db: Database session
        conversation_data: Conversation creation data
        architect_id: Architect ID

    Returns:
        Created conversation
    """
    new_conversation = Conversation(
        architect_id=architect_id,
        title=conversation_data.title,
        ai_provider=conversation_data.ai_provider,
        ai_model=conversation_data.ai_model,
        system_prompt=conversation_data.system_prompt,
    )

    db.add(new_conversation)
    await db.commit()
    await db.refresh(new_conversation)

    logger.info(
        "Conversation created: conv_id=%s architect_id=%s provider=%s model=%s",
        new_conversation.id,
        architect_id,
        conversation_data.ai_provider,
        conversation_data.ai_model,
    )

    await get_user_conversations.invalidate(db, architect_id)

    return new_conversation


async def update_conversation(
    db: AsyncSession,
    conversation_id: UUID,
    conversation_data: ConversationUpdate,
    architect_id: UUID,
) -> Conversation:
    """Update a conversation.

    Args:
        db: Database session
        conversation_id: Conversation ID
        conversation_data: Update data
        architect_id: Current architect ID

    Returns:
        Updated conversation

    Raises:
        HTTPException: 404 if not found, 403 if not authorized
    """
    conversation = await get_conversation_by_id(db, conversation_id, architect_id)

    if conversation_data.title is not None:
        conversation.title = conversation_data.title
    if conversation_data.system_prompt is not None:
        conversation.system_prompt = conversation_data.system_prompt

    await db.commit()
    await db.refresh(conversation)

    await get_user_conversations.invalidate(db, architect_id)

    return conversation


async def delete_conversation(db: AsyncSession, conversation_id: UUID, architect_id: UUID) -> None:
    """Delete a conversation.

    Args:
        db: Database session
        conversation_id: Conversation ID
        architect_id: Current architect ID

    Raises:
        HTTPException: 404 if not found, 403 if not authorized
    """
    conversation = await get_conversation_by_id(db, conversation_id, architect_id)

    await db.delete(conversation)
    await db.commit()

    logger.info("Conversation deleted: conv_id=%s architect_id=%s", conversation_id, architect_id)

    await get_user_conversations.invalidate(db, architect_id)


@redis_cache_decorator(
    ttl=300,
    ignore_positionals=[0],
    namespace="chat.conversation_messages",
)
async def get_conversation_messages(
    db: AsyncSession, conversation_id: UUID, architect_id: UUID
) -> list[Message]:
    """Get all messages for a conversation.

    Args:
        db: Database session
        conversation_id: Conversation ID
        architect_id: Current architect ID

    Returns:
        List of messages ordered by created_at asc

    Raises:
        HTTPException: 404 if conversation not found, 403 if not authorized
    """
    await get_conversation_by_id(db, conversation_id, architect_id)

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    return list(result.scalars().all())


async def create_message(
    db: AsyncSession, conversation_id: UUID, message_data: MessageCreate, architect_id: UUID
) -> tuple[Message, Message]:
    """Create a user message and generate the AI response in the same transaction flow.

    Args:
        db: Database session
        conversation_id: Conversation ID
        message_data: Message creation data
        architect_id: Current architect ID

    Returns:
        Tuple with (user_message, assistant_message)

    Raises:
        HTTPException: 404 if conversation not found, 403 if not authorized
    """
    conversation = await get_conversation_by_id(db, conversation_id, architect_id)

    user_message = Message(
        conversation_id=conversation_id,
        role=message_data.role,
        content=message_data.content,
        tokens_used=message_data.tokens_used,
        meta=message_data.meta,
    )

    db.add(user_message)
    await db.commit()
    await db.refresh(user_message)

    messages_history = await get_conversation_messages(db, conversation_id, architect_id)
    ai_messages = [{"role": msg.role, "content": msg.content} for msg in messages_history]

    logger.info(
        f"AI request started: conv_id={conversation_id} provider={conversation.ai_provider} "
        f"model={conversation.ai_model}"
    )

    start_time = time.time()
    try:
        ai_service = get_ai_service(conversation.ai_provider)
        ai_response = await ai_service.generate_response(
            ai_messages,
            conversation.ai_model,
            conversation.system_prompt,
        )
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(
            f"AI request completed: conv_id={conversation_id} provider={conversation.ai_provider} "
            f"duration_ms={duration_ms} response_length={len(ai_response)}"
        )
    except HTTPException:
        raise
    except ValueError as exc:
        logger.error(
            f"AI request failed: conv_id={conversation_id} provider={conversation.ai_provider} "
            f"error=ValueError: {str(exc)}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error(
            f"AI request failed: conv_id={conversation_id} provider={conversation.ai_provider} "
            f"error={type(exc).__name__}: {str(exc)}"
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to generate AI response: {exc}",
        ) from exc

    assistant_message = Message(
        conversation_id=conversation_id,
        role="assistant",
        content=ai_response,
        tokens_used=None,
    )

    db.add(assistant_message)
    await db.commit()
    await db.refresh(assistant_message)

    await get_conversation_messages.invalidate(db, conversation_id, architect_id)

    return user_message, assistant_message
