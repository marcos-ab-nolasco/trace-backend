"""Briefing model for managing briefing sessions and answers."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base

if TYPE_CHECKING:
    from src.db.models.briefing_analytics import BriefingAnalytics
    from src.db.models.end_client import EndClient
    from src.db.models.template_version import TemplateVersion

import enum


class BriefingStatus(enum.Enum):
    """Briefing status enum."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Briefing(Base):
    """Briefing model - represents a briefing session with a client."""

    __tablename__ = "briefings"

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=func.gen_random_uuid(), index=True
    )
    end_client_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("end_clients.id", ondelete="CASCADE"), index=True
    )
    template_version_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("template_versions.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[BriefingStatus] = mapped_column(
        SQLEnum(BriefingStatus, native_enum=False, length=20),
        nullable=False,
        default=BriefingStatus.IN_PROGRESS,
    )
    current_question_order: Mapped[int] = mapped_column(nullable=False, default=1)
    answers: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    end_client: Mapped["EndClient"] = relationship("EndClient", back_populates="briefings")
    template_version: Mapped["TemplateVersion"] = relationship("TemplateVersion")
    analytics: Mapped["BriefingAnalytics | None"] = relationship(
        "BriefingAnalytics", back_populates="briefing", uselist=False
    )

    def __repr__(self) -> str:
        return f"<Briefing(id={self.id}, status={self.status.value}, client_id={self.end_client_id})>"
