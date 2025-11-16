"""Briefing model for managing briefing sessions and answers."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Text, Uuid, func, text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base

if TYPE_CHECKING:
    from src.db.models.briefing_analytics import BriefingAnalytics
    from src.db.models.conversation_message import ConversationMessage
    from src.db.models.end_client import EndClient
    from src.db.models.template_version import TemplateVersion
    from src.db.models.whatsapp_session import WhatsAppSession
    from src.schemas.information_state import (
        GatheredInformationDict,
        InformationStateDict,
    )

import enum


class BriefingStatus(enum.Enum):
    """Briefing status enum."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Briefing(Base):
    """Briefing model - represents a briefing session with a client."""

    __tablename__ = "briefings"
    __table_args__ = (
        Index(
            "uq_client_active_briefing",
            "end_client_id",
            unique=True,
            postgresql_where=text("status = 'in_progress'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=func.gen_random_uuid(), index=True
    )
    end_client_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("end_clients.id", ondelete="CASCADE"), index=True
    )
    template_version_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("template_versions.id", ondelete="RESTRICT"), index=True
    )
    # conversation_id REMOVED - web chat feature deprecated
    status: Mapped[BriefingStatus] = mapped_column(
        SQLEnum(BriefingStatus, native_enum=False, length=20),
        nullable=False,
        default=BriefingStatus.IN_PROGRESS,
    )

    # OLD FIELDS - TO BE REMOVED IN MIGRATION (use information-based state instead)
    # current_question_order: Mapped[int] = mapped_column(nullable=False, default=1)
    # answers: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Conversational AI state fields (validated with Pydantic schemas)
    information_state: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    gathered_information: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    conversation_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    end_client: Mapped[EndClient] = relationship("EndClient", back_populates="briefings")
    template_version: Mapped[TemplateVersion] = relationship("TemplateVersion")
    analytics: Mapped[BriefingAnalytics | None] = relationship(
        "BriefingAnalytics", back_populates="briefing", uselist=False
    )
    whatsapp_sessions: Mapped[list[WhatsAppSession]] = relationship(
        "WhatsAppSession", back_populates="briefing"
    )
    conversation_messages: Mapped[list[ConversationMessage]] = relationship(
        "ConversationMessage", back_populates="briefing", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Briefing(id={self.id}, status={self.status.value}, client_id={self.end_client_id})>"
        )

    # Type-safe accessors for JSONB fields using Pydantic schemas

    def get_information_state(self) -> InformationStateDict:
        """Get typed information state using Pydantic validation."""
        from src.schemas.information_state import InformationStateDict

        return InformationStateDict(fields=self.information_state)

    def set_information_state(self, state: InformationStateDict) -> None:
        """Set information state with Pydantic validation."""
        self.information_state = state.fields

    def get_gathered_information(self) -> GatheredInformationDict:
        """Get typed gathered information using Pydantic validation."""
        from src.schemas.information_state import GatheredInformationDict

        return GatheredInformationDict(fields=self.gathered_information)

    def set_gathered_information(self, info: GatheredInformationDict) -> None:
        """Set gathered information with Pydantic validation."""
        self.gathered_information = info.fields

    def get_completion_percentage(self, required_fields: list[str]) -> float:
        """Calculate completion percentage based on required fields."""
        state: InformationStateDict = self.get_information_state()
        return state.get_completion_percentage(required_fields)
