"""add processed webhook tracking for idempotency

Revision ID: 811662fad351
Revises: c4696da28d1a
Create Date: 2025-11-08 20:14:07.728304

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '811662fad351'
down_revision: Union[str, None] = 'c4696da28d1a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('processed_webhooks',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('wa_message_id', sa.String(length=255), nullable=False),
    sa.Column('result_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('processed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_processed_webhooks_wa_message_id'), 'processed_webhooks', ['wa_message_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_processed_webhooks_wa_message_id'), table_name='processed_webhooks')
    op.drop_table('processed_webhooks')
