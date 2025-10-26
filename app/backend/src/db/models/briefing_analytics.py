"""Briefing Analytics model for storing metrics and observations."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base

if TYPE_CHECKING:
    from src.db.models.briefing import Briefing


class BriefingAnalytics(Base):
    """Analytics and metrics for completed briefings."""

    __tablename__ = "briefing_analytics"

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=func.gen_random_uuid(), index=True
    )
    briefing_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("briefings.id", ondelete="CASCADE"),
        unique=True,  # One analytics record per briefing
        index=True,
    )

    # Metrics stored as JSONB for flexibility
    # Expected fields: duration_seconds, total_questions, answered_questions,
    # required_answered, optional_answered, optional_skipped, completion_rate
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Optional observations and insights
    observations: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    briefing: Mapped["Briefing"] = relationship("Briefing", back_populates="analytics")

    def __repr__(self) -> str:
        return f"<BriefingAnalytics(id={self.id}, briefing_id={self.briefing_id})>"
