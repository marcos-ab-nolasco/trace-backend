"""ConversationMessage model for storing full conversation history for AI context."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base

if TYPE_CHECKING:
    from src.db.models.briefing import Briefing
    from src.schemas.information_state import AIMetadata, ExtractedInfo


class ConversationMessage(Base):
    """Full conversation history for AI context.

    Stores all messages exchanged during a briefing conversation, including
    AI-extracted information and metadata. This enables the AI to maintain
    context throughout the conversation and make intelligent decisions about
    what information to gather next.
    """

    __tablename__ = "conversation_messages"

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=func.gen_random_uuid(), index=True
    )
    briefing_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("briefings.id", ondelete="CASCADE"), index=True, nullable=False
    )

    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # AI metadata
    extracted_info: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ai_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Vector embedding reference (stored separately in ChromaDB)
    embedding_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Relationships
    briefing: Mapped[Briefing] = relationship("Briefing", back_populates="conversation_messages")

    def __repr__(self) -> str:
        """String representation of ConversationMessage."""
        return (
            f"<ConversationMessage(id={self.id}, role={self.role}, briefing_id={self.briefing_id})>"
        )

    # Type-safe accessors for JSONB fields using Pydantic schemas

    def get_extracted_info(self) -> ExtractedInfo | None:
        """Get typed extracted info using Pydantic validation."""
        if not self.extracted_info:
            return None

        from src.schemas.information_state import ExtractedInfo

        return ExtractedInfo(**self.extracted_info)

    def set_extracted_info(self, info: ExtractedInfo) -> None:
        """Set extracted info with Pydantic validation."""
        self.extracted_info = info.model_dump()

    def get_ai_metadata(self) -> AIMetadata | None:
        """Get typed AI metadata using Pydantic validation."""
        if not self.ai_metadata:
            return None

        from src.schemas.information_state import AIMetadata

        return AIMetadata(**self.ai_metadata)

    def set_ai_metadata(self, metadata: AIMetadata) -> None:
        """Set AI metadata with Pydantic validation."""
        self.ai_metadata = metadata.model_dump()
