from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.dependencies import get_current_user
from src.core.rate_limit import limiter_authenticated
from src.db.models import User
from src.db.session import get_db
from src.schemas.chat import (
    AIProviderList,
    ConversationCreate,
    ConversationList,
    ConversationRead,
    ConversationUpdate,
    MessageCreate,
    MessageCreateResponse,
    MessageList,
    MessageRead,
)
from src.services import chat as chat_service
from src.services.ai import list_ai_providers

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/conversations", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    conversation_data: ConversationCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ConversationRead:
    """Create a new conversation."""
    conversation = await chat_service.create_conversation(db, conversation_data, current_user.id)
    return ConversationRead.model_validate(conversation)


@router.get("/conversations", response_model=ConversationList)
async def list_conversations(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ConversationList:
    """List all conversations for the current user."""
    conversations = await chat_service.get_user_conversations(db, current_user.id)
    return ConversationList(
        conversations=[ConversationRead.model_validate(c) for c in conversations],
        total=len(conversations),
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationRead)
async def get_conversation(
    conversation_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ConversationRead:
    """Get a conversation by ID."""
    conversation = await chat_service.get_conversation_by_id(db, conversation_id, current_user.id)
    return ConversationRead.model_validate(conversation)


@router.patch("/conversations/{conversation_id}", response_model=ConversationRead)
async def update_conversation(
    conversation_id: UUID,
    conversation_data: ConversationUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ConversationRead:
    """Update a conversation."""
    conversation = await chat_service.update_conversation(
        db, conversation_id, conversation_data, current_user.id
    )
    return ConversationRead.model_validate(conversation)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Delete a conversation."""
    await chat_service.delete_conversation(db, conversation_id, current_user.id)


@router.get("/conversations/{conversation_id}/messages", response_model=MessageList)
async def list_messages(
    conversation_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> MessageList:
    """List all messages in a conversation."""
    messages = await chat_service.get_conversation_messages(db, conversation_id, current_user.id)
    return MessageList(
        messages=[MessageRead.model_validate(m) for m in messages],
        total=len(messages),
    )


@router.get("/providers", response_model=AIProviderList)
async def list_providers(
    current_user: Annotated[User, Depends(get_current_user)],
) -> AIProviderList:
    """Expose configured AI providers for the frontend UI."""

    providers = await list_ai_providers()
    return AIProviderList(providers=providers)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter_authenticated.limit("10/minute")
async def create_message(
    request: Request,
    conversation_id: UUID,
    message_data: MessageCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> MessageCreateResponse:
    """Create a new message and trigger the AI-generated assistant reply."""
    user_message, assistant_message = await chat_service.create_message(
        db, conversation_id, message_data, current_user.id
    )
    return MessageCreateResponse(
        user_message=MessageRead.model_validate(user_message),
        assistant_message=MessageRead.model_validate(assistant_message),
    )
