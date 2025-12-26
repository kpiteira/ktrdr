"""create_checkpoints_table

Revision ID: a1b2c3d4e5f6
Revises: 6bfcfd0a377f
Create Date: 2024-12-24 09:00:00.000000

Creates the operation_checkpoints table for persistent checkpoint storage.
This table stores checkpoint metadata and state for long-running operations,
enabling resume functionality after cancellation, failure, or shutdown.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "6bfcfd0a377f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the operation_checkpoints table with all columns and indexes."""
    op.create_table(
        "operation_checkpoints",
        # Primary key with foreign key to operations table
        sa.Column("operation_id", sa.String(length=255), nullable=False),
        # Checkpoint metadata
        sa.Column("checkpoint_type", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # State (JSONB for queryability)
        sa.Column(
            "state",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        # Artifact location (nullable for backtesting which has no large artifacts)
        sa.Column("artifacts_path", sa.String(length=500), nullable=True),
        # Size tracking for monitoring
        sa.Column("state_size_bytes", sa.Integer(), nullable=True),
        sa.Column("artifacts_size_bytes", sa.BigInteger(), nullable=True),
        # Primary key constraint
        sa.PrimaryKeyConstraint("operation_id"),
        # Foreign key to operations table with CASCADE delete
        sa.ForeignKeyConstraint(
            ["operation_id"],
            ["operations.operation_id"],
            ondelete="CASCADE",
        ),
    )

    # Create indexes for common query patterns
    op.create_index(
        "ix_checkpoints_created_at",
        "operation_checkpoints",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_checkpoints_type",
        "operation_checkpoints",
        ["checkpoint_type"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the operation_checkpoints table and its indexes."""
    op.drop_index("ix_checkpoints_type", table_name="operation_checkpoints")
    op.drop_index("ix_checkpoints_created_at", table_name="operation_checkpoints")
    op.drop_table("operation_checkpoints")
