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
        unique=True,
        index=True,
    )

    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)

    observations: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    briefing: Mapped["Briefing"] = relationship("Briefing", back_populates="analytics")

    def __repr__(self) -> str:
        return f"<BriefingAnalytics(id={self.id}, briefing_id={self.briefing_id})>"
