"""BriefingTemplate model for managing briefing templates."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base

if TYPE_CHECKING:
    from src.db.models.architect import Architect
    from src.db.models.template_version import TemplateVersion


class BriefingTemplate(Base):
    """BriefingTemplate model - defines briefing questionnaires."""

    __tablename__ = "briefing_templates"

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=func.gen_random_uuid(), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)  # reforma, construcao, etc
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_global: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    architect_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("architects.id", ondelete="CASCADE"), index=True, nullable=True
    )
    current_version_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Unique constraint: name must be unique per architect (or for global templates)
    # Global templates have architect_id = NULL
    __table_args__ = (
        UniqueConstraint("name", "architect_id", name="uq_template_name_architect"),
    )

    # Relationships
    architect: Mapped["Architect | None"] = relationship("Architect", back_populates="templates")
    versions: Mapped[list["TemplateVersion"]] = relationship(
        "TemplateVersion",
        back_populates="template",
        cascade="all, delete-orphan",
        foreign_keys="TemplateVersion.template_id",
    )
    current_version: Mapped["TemplateVersion | None"] = relationship(
        "TemplateVersion",
        primaryjoin="BriefingTemplate.current_version_id == TemplateVersion.id",
        foreign_keys="[BriefingTemplate.current_version_id]",
        post_update=True,
        uselist=False,
    )

    def __repr__(self) -> str:
        return f"<BriefingTemplate(id={self.id}, name={self.name}, category={self.category})>"
