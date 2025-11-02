"""Project type model defining canonical template keywords."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base


class ProjectType(Base):
    """Canonical project type (e.g., reforma, residencial)."""

    __tablename__ = "project_types"

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=func.gen_random_uuid(), index=True
    )
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    templates = relationship("BriefingTemplate", back_populates="project_type")

    def __repr__(self) -> str:
        return f"<ProjectType(id={self.id}, slug={self.slug})>"
