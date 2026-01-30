"""Add Xpert Panel tables

Revision ID: xpert_001
Revises: 
Create Date: 2024-01-30

"""
from alembic import op
import sqlalchemy as sa


revision = 'xpert_001'
down_revision = '015cf1dc6eca'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'subscription_sources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('url', sa.String(1024), nullable=False),
        sa.Column('enabled', sa.Boolean(), default=True),
        sa.Column('priority', sa.Integer(), default=1),
        sa.Column('last_fetched', sa.DateTime(), nullable=True),
        sa.Column('config_count', sa.Integer(), default=0),
        sa.Column('success_rate', sa.Float(), default=0.0),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_subscription_sources_id', 'subscription_sources', ['id'])
    
    op.create_table(
        'aggregated_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('raw', sa.Text(), nullable=False),
        sa.Column('protocol', sa.String(50), nullable=False),
        sa.Column('server', sa.String(255), nullable=False),
        sa.Column('port', sa.Integer(), nullable=False),
        sa.Column('remarks', sa.String(255), nullable=True),
        sa.Column('source_id', sa.Integer(), nullable=True),
        sa.Column('ping_ms', sa.Float(), default=999.0),
        sa.Column('jitter_ms', sa.Float(), default=0.0),
        sa.Column('packet_loss', sa.Float(), default=0.0),
        sa.Column('is_active', sa.Boolean(), default=False),
        sa.Column('last_check', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_aggregated_configs_id', 'aggregated_configs', ['id'])


def downgrade() -> None:
    op.drop_index('ix_aggregated_configs_id', 'aggregated_configs')
    op.drop_table('aggregated_configs')
    op.drop_index('ix_subscription_sources_id', 'subscription_sources')
    op.drop_table('subscription_sources')
