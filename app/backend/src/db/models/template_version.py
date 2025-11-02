"""TemplateVersion model for versioning briefing templates."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base

if TYPE_CHECKING:
    from src.db.models.briefing_template import BriefingTemplate


class TemplateVersion(Base):
    """TemplateVersion model - stores versions of briefing templates."""

    __tablename__ = "template_versions"

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=func.gen_random_uuid(), index=True
    )
    template_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("briefing_templates.id", ondelete="CASCADE"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    questions: Mapped[list] = mapped_column(JSONB, nullable=False)
    change_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    template: Mapped["BriefingTemplate"] = relationship(
        "BriefingTemplate",
        back_populates="versions",
        foreign_keys=[template_id],
    )

    def __repr__(self) -> str:
        return f"<TemplateVersion(id={self.id}, template_id={self.template_id}, version={self.version_number})>"
