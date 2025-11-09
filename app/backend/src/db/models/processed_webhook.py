"""ProcessedWebhook model for tracking processed webhooks (idempotency)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class ProcessedWebhook(Base):
    """Tracks processed webhooks to ensure idempotency on retries.

    When a webhook is successfully processed, we record its message_id
    to prevent duplicate processing if the webhook is redelivered.
    """

    __tablename__ = "processed_webhooks"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, server_default=func.gen_random_uuid())

    wa_message_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)

    result_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        """String representation of ProcessedWebhook."""
        return f"<ProcessedWebhook(id={self.id}, wa_message_id={self.wa_message_id})>"
