"""INITIAL_BASELINE

Revision ID: 7470fd7ba768
Revises: 
Create Date: 2025-10-26 22:28:34.702167

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '7470fd7ba768'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('organizations',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('whatsapp_business_account_id', sa.String(length=255), nullable=True),
    sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('whatsapp_business_account_id')
    )
    op.create_index(op.f('ix_organizations_id'), 'organizations', ['id'], unique=False)
    op.create_index(op.f('ix_organizations_name'), 'organizations', ['name'], unique=True)
    op.create_table('project_types',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('slug', sa.String(length=50), nullable=False),
    sa.Column('label', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_project_types_id'), 'project_types', ['id'], unique=False)
    op.create_index(op.f('ix_project_types_slug'), 'project_types', ['slug'], unique=True)
    op.create_table('whatsapp_accounts',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('phone_number_id', sa.String(length=255), nullable=False),
    sa.Column('phone_number', sa.String(length=20), nullable=False),
    sa.Column('access_token', sa.String(length=500), nullable=False),
    sa.Column('webhook_verify_token', sa.String(length=255), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('is_global', sa.Boolean(), nullable=False),
    sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_whatsapp_accounts_phone_number_id'), 'whatsapp_accounts', ['phone_number_id'], unique=True)
    op.create_table('architects',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('hashed_password', sa.String(length=255), nullable=False),
    sa.Column('full_name', sa.String(length=255), nullable=True),
    sa.Column('phone', sa.String(length=20), nullable=False),
    sa.Column('is_authorized', sa.Boolean(), nullable=False),
    sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_architects_email'), 'architects', ['email'], unique=True)
    op.create_index(op.f('ix_architects_id'), 'architects', ['id'], unique=False)
    op.create_index(op.f('ix_architects_organization_id'), 'architects', ['organization_id'], unique=False)
    op.create_table('organization_whatsapp_accounts',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('whatsapp_account_id', sa.Uuid(), nullable=False),
    sa.Column('is_primary', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['whatsapp_account_id'], ['whatsapp_accounts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'whatsapp_account_id', name='uq_organization_whatsapp_account')
    )
    op.create_index(op.f('ix_organization_whatsapp_accounts_id'), 'organization_whatsapp_accounts', ['id'], unique=False)
    op.create_index(op.f('ix_organization_whatsapp_accounts_organization_id'), 'organization_whatsapp_accounts', ['organization_id'], unique=False)
    op.create_index(op.f('ix_organization_whatsapp_accounts_whatsapp_account_id'), 'organization_whatsapp_accounts', ['whatsapp_account_id'], unique=False)
    op.create_table('briefing_templates',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('category', sa.String(length=100), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('is_global', sa.Boolean(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=True),
    sa.Column('created_by_architect_id', sa.Uuid(), nullable=True),
    sa.Column('project_type_id', sa.Uuid(), nullable=True),
    sa.Column('current_version_id', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by_architect_id'], ['architects.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['project_type_id'], ['project_types.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name', 'organization_id', name='uq_template_name_organization')
    )
    op.create_index(op.f('ix_briefing_templates_created_by_architect_id'), 'briefing_templates', ['created_by_architect_id'], unique=False)
    op.create_index(op.f('ix_briefing_templates_id'), 'briefing_templates', ['id'], unique=False)
    op.create_index(op.f('ix_briefing_templates_organization_id'), 'briefing_templates', ['organization_id'], unique=False)
    op.create_index(op.f('ix_briefing_templates_project_type_id'), 'briefing_templates', ['project_type_id'], unique=False)
    op.create_table('end_clients',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('architect_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('phone', sa.String(length=20), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['architect_id'], ['architects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('architect_id', 'phone', name='uq_architect_phone')
    )
    op.create_index(op.f('ix_end_clients_architect_id'), 'end_clients', ['architect_id'], unique=False)
    op.create_index(op.f('ix_end_clients_id'), 'end_clients', ['id'], unique=False)
    op.create_table('conversations',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('architect_id', sa.Uuid(), nullable=True),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('ai_provider', sa.String(length=50), nullable=False),
    sa.Column('ai_model', sa.String(length=100), nullable=False),
    sa.Column('system_prompt', sa.Text(), nullable=True),
    sa.Column('conversation_type', sa.String(length=50), nullable=False),
    sa.Column('end_client_id', sa.Uuid(), nullable=True),
    sa.Column('whatsapp_context', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['architect_id'], ['architects.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['end_client_id'], ['end_clients.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_conversations_architect_id'), 'conversations', ['architect_id'], unique=False)
    op.create_index(op.f('ix_conversations_end_client_id'), 'conversations', ['end_client_id'], unique=False)
    op.create_index(op.f('ix_conversations_id'), 'conversations', ['id'], unique=False)
    op.create_table('template_versions',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('template_id', sa.Uuid(), nullable=False),
    sa.Column('version_number', sa.Integer(), nullable=False),
    sa.Column('questions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('change_description', sa.String(length=500), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['template_id'], ['briefing_templates.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_template_versions_id'), 'template_versions', ['id'], unique=False)
    op.create_index(op.f('ix_template_versions_template_id'), 'template_versions', ['template_id'], unique=False)
    op.create_table('briefings',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('end_client_id', sa.Uuid(), nullable=False),
    sa.Column('template_version_id', sa.Uuid(), nullable=False),
    sa.Column('conversation_id', sa.Uuid(), nullable=True),
    sa.Column('status', sa.Enum('IN_PROGRESS', 'COMPLETED', 'CANCELLED', name='briefingstatus', native_enum=False, length=20), nullable=False),
    sa.Column('current_question_order', sa.Integer(), nullable=False),
    sa.Column('answers', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['end_client_id'], ['end_clients.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['template_version_id'], ['template_versions.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_briefings_conversation_id'), 'briefings', ['conversation_id'], unique=True)
    op.create_index(op.f('ix_briefings_end_client_id'), 'briefings', ['end_client_id'], unique=False)
    op.create_index(op.f('ix_briefings_id'), 'briefings', ['id'], unique=False)
    op.create_index(op.f('ix_briefings_template_version_id'), 'briefings', ['template_version_id'], unique=False)
    op.create_table('messages',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('conversation_id', sa.Uuid(), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('tokens_used', sa.Integer(), nullable=True),
    sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_messages_conversation_id'), 'messages', ['conversation_id'], unique=False)
    op.create_index(op.f('ix_messages_id'), 'messages', ['id'], unique=False)
    op.create_table('briefing_analytics',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('briefing_id', sa.Uuid(), nullable=False),
    sa.Column('metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('observations', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['briefing_id'], ['briefings.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_briefing_analytics_briefing_id'), 'briefing_analytics', ['briefing_id'], unique=True)
    op.create_index(op.f('ix_briefing_analytics_id'), 'briefing_analytics', ['id'], unique=False)
    op.create_table('whatsapp_sessions',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('end_client_id', sa.UUID(), nullable=False),
    sa.Column('briefing_id', sa.UUID(), nullable=True),
    sa.Column('phone_number', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_interaction_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['briefing_id'], ['briefings.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['end_client_id'], ['end_clients.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_whatsapp_sessions_briefing_id'), 'whatsapp_sessions', ['briefing_id'], unique=False)
    op.create_index(op.f('ix_whatsapp_sessions_end_client_id'), 'whatsapp_sessions', ['end_client_id'], unique=False)
    op.create_table('whatsapp_messages',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('session_id', sa.UUID(), nullable=False),
    sa.Column('wa_message_id', sa.String(length=255), nullable=False),
    sa.Column('direction', sa.String(length=50), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('content', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('error_code', sa.String(length=50), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('timestamp', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['session_id'], ['whatsapp_sessions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_whatsapp_messages_session_id'), 'whatsapp_messages', ['session_id'], unique=False)
    op.create_index(op.f('ix_whatsapp_messages_wa_message_id'), 'whatsapp_messages', ['wa_message_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_whatsapp_messages_wa_message_id'), table_name='whatsapp_messages')
    op.drop_index(op.f('ix_whatsapp_messages_session_id'), table_name='whatsapp_messages')
    op.drop_table('whatsapp_messages')
    op.drop_index(op.f('ix_whatsapp_sessions_end_client_id'), table_name='whatsapp_sessions')
    op.drop_index(op.f('ix_whatsapp_sessions_briefing_id'), table_name='whatsapp_sessions')
    op.drop_table('whatsapp_sessions')
    op.drop_index(op.f('ix_briefing_analytics_id'), table_name='briefing_analytics')
    op.drop_index(op.f('ix_briefing_analytics_briefing_id'), table_name='briefing_analytics')
    op.drop_table('briefing_analytics')
    op.drop_index(op.f('ix_messages_id'), table_name='messages')
    op.drop_index(op.f('ix_messages_conversation_id'), table_name='messages')
    op.drop_table('messages')
    op.drop_index(op.f('ix_briefings_template_version_id'), table_name='briefings')
    op.drop_index(op.f('ix_briefings_id'), table_name='briefings')
    op.drop_index(op.f('ix_briefings_end_client_id'), table_name='briefings')
    op.drop_index(op.f('ix_briefings_conversation_id'), table_name='briefings')
    op.drop_table('briefings')
    op.drop_index(op.f('ix_template_versions_template_id'), table_name='template_versions')
    op.drop_index(op.f('ix_template_versions_id'), table_name='template_versions')
    op.drop_table('template_versions')
    op.drop_index(op.f('ix_conversations_id'), table_name='conversations')
    op.drop_index(op.f('ix_conversations_end_client_id'), table_name='conversations')
    op.drop_index(op.f('ix_conversations_architect_id'), table_name='conversations')
    op.drop_table('conversations')
    op.drop_index(op.f('ix_end_clients_id'), table_name='end_clients')
    op.drop_index(op.f('ix_end_clients_architect_id'), table_name='end_clients')
    op.drop_table('end_clients')
    op.drop_index(op.f('ix_briefing_templates_project_type_id'), table_name='briefing_templates')
    op.drop_index(op.f('ix_briefing_templates_organization_id'), table_name='briefing_templates')
    op.drop_index(op.f('ix_briefing_templates_id'), table_name='briefing_templates')
    op.drop_index(op.f('ix_briefing_templates_created_by_architect_id'), table_name='briefing_templates')
    op.drop_table('briefing_templates')
    op.drop_index(op.f('ix_organization_whatsapp_accounts_whatsapp_account_id'), table_name='organization_whatsapp_accounts')
    op.drop_index(op.f('ix_organization_whatsapp_accounts_organization_id'), table_name='organization_whatsapp_accounts')
    op.drop_index(op.f('ix_organization_whatsapp_accounts_id'), table_name='organization_whatsapp_accounts')
    op.drop_table('organization_whatsapp_accounts')
    op.drop_index(op.f('ix_architects_organization_id'), table_name='architects')
    op.drop_index(op.f('ix_architects_id'), table_name='architects')
    op.drop_index(op.f('ix_architects_email'), table_name='architects')
    op.drop_table('architects')
    op.drop_index(op.f('ix_whatsapp_accounts_phone_number_id'), table_name='whatsapp_accounts')
    op.drop_table('whatsapp_accounts')
    op.drop_index(op.f('ix_project_types_slug'), table_name='project_types')
    op.drop_index(op.f('ix_project_types_id'), table_name='project_types')
    op.drop_table('project_types')
    op.drop_index(op.f('ix_organizations_name'), table_name='organizations')
    op.drop_index(op.f('ix_organizations_id'), table_name='organizations')
    op.drop_table('organizations')
