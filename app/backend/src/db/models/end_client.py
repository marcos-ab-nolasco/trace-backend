"""EndClient model - represents final clients of architects."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base

if TYPE_CHECKING:
    from src.db.models.architect import Architect


class EndClient(Base):
    """EndClient model - final clients who receive briefing services."""

    __tablename__ = "end_clients"

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=func.gen_random_uuid(), index=True
    )
    architect_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("architects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Unique constraint: phone number must be unique per architect
    __table_args__ = (UniqueConstraint("architect_id", "phone", name="uq_architect_phone"),)

    # Relationships
    architect: Mapped["Architect"] = relationship("Architect", back_populates="end_clients")

    def __repr__(self) -> str:
        return f"<EndClient(id={self.id}, name={self.name}, architect_id={self.architect_id})>"
