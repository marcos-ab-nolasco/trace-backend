"""add authorized_phones table

Revision ID: 4d29c51db12f
Revises: 7470fd7ba768
Create Date: 2025-10-27 15:06:25.014211

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '4d29c51db12f'
down_revision: Union[str, None] = '7470fd7ba768'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('authorized_phones',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('phone_number', sa.String(length=20), nullable=False),
    sa.Column('added_by_architect_id', sa.Uuid(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['added_by_architect_id'], ['architects.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'phone_number', name='uq_organization_phone_number')
    )
    op.create_index(op.f('ix_authorized_phones_id'), 'authorized_phones', ['id'], unique=False)
    op.create_index(op.f('ix_authorized_phones_organization_id'), 'authorized_phones', ['organization_id'], unique=False)
    op.create_index(op.f('ix_authorized_phones_phone_number'), 'authorized_phones', ['phone_number'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_authorized_phones_phone_number'), table_name='authorized_phones')
    op.drop_index(op.f('ix_authorized_phones_organization_id'), table_name='authorized_phones')
    op.drop_index(op.f('ix_authorized_phones_id'), table_name='authorized_phones')
    op.drop_table('authorized_phones')
