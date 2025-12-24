"""create_operations_table

Revision ID: 6bfcfd0a377f
Revises:
Create Date: 2025-12-21 18:18:58.849598

Creates the operations table for persistent operation tracking.
This is the foundation for the checkpoint and resilience system.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '6bfcfd0a377f'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the operations table with all columns and indexes."""
    op.create_table(
        'operations',
        sa.Column('operation_id', sa.String(length=255), nullable=False),
        sa.Column('operation_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('worker_id', sa.String(length=255), nullable=True),
        sa.Column('is_backend_local', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('progress_percent', sa.Float(), nullable=False, server_default='0'),
        sa.Column('progress_message', sa.String(length=500), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('last_heartbeat_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reconciliation_status', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('operation_id')
    )

    # Create indexes for common query patterns
    op.create_index('ix_operations_status', 'operations', ['status'], unique=False)
    op.create_index('ix_operations_worker_id', 'operations', ['worker_id'], unique=False)
    op.create_index('ix_operations_operation_type', 'operations', ['operation_type'], unique=False)
    op.create_index('ix_operations_created_at', 'operations', ['created_at'], unique=False)


def downgrade() -> None:
    """Drop the operations table and its indexes."""
    op.drop_index('ix_operations_created_at', table_name='operations')
    op.drop_index('ix_operations_operation_type', table_name='operations')
    op.drop_index('ix_operations_status', table_name='operations')
    op.drop_index('ix_operations_worker_id', table_name='operations')
    op.drop_table('operations')
