"""updated endclient

Revision ID: d8e31b80feea
Revises: 4d29c51db12f
Create Date: 2025-10-27 16:31:41.873020

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd8e31b80feea'
down_revision: Union[str, None] = '4d29c51db12f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('end_clients', sa.Column('organization_id', sa.Uuid(), nullable=False))
    op.drop_constraint(op.f('uq_architect_phone'), 'end_clients', type_='unique')
    op.create_index(op.f('ix_end_clients_organization_id'), 'end_clients', ['organization_id'], unique=False)
    op.create_unique_constraint('uq_organization_phone', 'end_clients', ['organization_id', 'phone'])
    op.create_foreign_key(None, 'end_clients', 'organizations', ['organization_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    op.drop_constraint(None, 'end_clients', type_='foreignkey')
    op.drop_constraint('uq_organization_phone', 'end_clients', type_='unique')
    op.drop_index(op.f('ix_end_clients_organization_id'), table_name='end_clients')
    op.create_unique_constraint(op.f('uq_architect_phone'), 'end_clients', ['architect_id', 'phone'], postgresql_nulls_not_distinct=False)
    op.drop_column('end_clients', 'organization_id')
