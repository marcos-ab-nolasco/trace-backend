"""InformationRequirement model for defining information to gather in briefings."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base

if TYPE_CHECKING:
    from src.db.models.template_version import TemplateVersion


class InformationRequirement(Base):
    """Defines WHAT information to gather (not HOW to ask).

    This model represents information requirements for a briefing template,
    focusing on the data that needs to be collected rather than specific questions.
    The AI agents will use these requirements to guide conversational flow.
    """

    __tablename__ = "information_requirements"

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=func.gen_random_uuid(), index=True
    )
    template_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("template_versions.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # What to gather
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    field_type: Mapped[str] = mapped_column(String(50), nullable=False)
    required: Mapped[bool] = mapped_column(nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5)

    # AI-understandable metadata
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_rules: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    suggested_questions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    template_version: Mapped["TemplateVersion"] = relationship(
        "TemplateVersion", back_populates="requirements"
    )

    def __repr__(self) -> str:
        """String representation of InformationRequirement."""
        return f"<InformationRequirement(id={self.id}, field_name={self.field_name}, type={self.field_type})>"
