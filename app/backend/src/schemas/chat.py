from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ===== Conversation Schemas =====


class ConversationCreate(BaseModel):
    """Schema for creating a new conversation."""

    title: str = Field(..., min_length=1, max_length=255)
    ai_provider: str = Field(default="openai", pattern="^(openai|anthropic|gemini|grok)$")
    ai_model: str = Field(
        default="gpt-3.5-turbo", min_length=1, max_length=100
    )  # gpt-3.5-turbo-0125, gpt-4.1-mini-2025-04-14, gpt-5-nano-2025-08-07
    system_prompt: str | None = Field(default=None)


class ConversationUpdate(BaseModel):
    """Schema for updating a conversation."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    system_prompt: str | None = Field(default=None)


class ConversationRead(BaseModel):
    """Schema for reading a conversation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    title: str
    ai_provider: str
    ai_model: str
    system_prompt: str | None
    created_at: datetime
    updated_at: datetime


class ConversationList(BaseModel):
    """Schema for listing conversations."""

    conversations: list[ConversationRead]
    total: int


# ===== Message Schemas =====


class MessageCreate(BaseModel):
    """Schema for creating a new message."""

    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str = Field(..., min_length=1)
    tokens_used: int | None = Field(default=None)
    meta: dict | None = Field(default=None)


class MessageRead(BaseModel):
    """Schema for reading a message."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    role: str
    content: str
    tokens_used: int | None
    meta: dict | None
    created_at: datetime


class MessageList(BaseModel):
    """Schema for listing messages."""

    messages: list[MessageRead]
    total: int


class MessageCreateResponse(BaseModel):
    """Schema for the message creation workflow."""

    user_message: MessageRead
    assistant_message: MessageRead


class AIModelOption(BaseModel):
    """Schema describing a model option for an AI provider."""

    value: str
    label: str


class AIProvider(BaseModel):
    """Schema describing available AI providers."""

    id: str
    label: str
    models: list[AIModelOption]
    is_configured: bool


class AIProviderList(BaseModel):
    """Response wrapper for provider listing."""

    providers: list[AIProvider]
