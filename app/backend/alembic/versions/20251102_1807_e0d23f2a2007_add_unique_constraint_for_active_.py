"""add unique constraint for active briefings per client

Revision ID: e0d23f2a2007
Revises: d8e31b80feea
Create Date: 2025-11-02 18:07:31.000991

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e0d23f2a2007'
down_revision: Union[str, None] = 'd8e31b80feea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create partial unique index to prevent duplicate IN_PROGRESS briefings per client
    # This prevents race conditions when two webhooks arrive simultaneously
    op.create_index(
        'uq_client_active_briefing',
        'briefings',
        ['end_client_id'],
        unique=True,
        postgresql_where=sa.text("status = 'IN_PROGRESS'")
    )


def downgrade() -> None:
    # Remove the partial unique index
    op.drop_index(
        'uq_client_active_briefing',
        table_name='briefings',
        postgresql_where=sa.text("status = 'IN_PROGRESS'")
    )
