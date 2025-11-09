from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base

if TYPE_CHECKING:
    from src.db.models.architect import Architect
    from src.db.models.briefing import Briefing
    from src.db.models.end_client import EndClient
    from src.db.models.message import Message


class ConversationType(str, Enum):
    """Enum for conversation types."""

    WEB_CHAT = "web_chat"
    WHATSAPP_BRIEFING = "whatsapp_briefing"


class Conversation(Base):
    """Conversation model for chat interactions."""

    __tablename__ = "conversations"

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=func.gen_random_uuid(), index=True
    )
    architect_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("architects.id", ondelete="SET NULL"), index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    ai_provider: Mapped[str] = mapped_column(String(50), nullable=False, default="openai")
    ai_model: Mapped[str] = mapped_column(String(100), nullable=False, default="gpt-4")
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

    conversation_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ConversationType.WEB_CHAT.value
    )
    end_client_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("end_clients.id", ondelete="CASCADE"), index=True, nullable=True
    )
    whatsapp_context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    architect: Mapped["Architect | None"] = relationship(
        "Architect", back_populates="conversations"
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )
    end_client: Mapped["EndClient | None"] = relationship(
        "EndClient", back_populates="conversations"
    )
    briefing: Mapped["Briefing | None"] = relationship(
        "Briefing", back_populates="conversation", uselist=False
    )

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, architect_id={self.architect_id}, title={self.title})>"
