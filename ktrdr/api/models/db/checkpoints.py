"""SQLAlchemy ORM model for checkpoint persistence.

This module defines the CheckpointRecord model for storing checkpoint state
in PostgreSQL. Checkpoints enable resume functionality for long-running
operations (training, backtesting) by persisting state and artifact locations.

Checkpoints are saved:
- Periodically during operation (every N epochs/bars)
- On cancellation (user Ctrl+C)
- On failure (caught exceptions)
- On graceful shutdown (SIGTERM)

Storage strategy:
- Metadata & state: PostgreSQL (JSONB, queryable)
- Artifacts (model weights): Filesystem (artifacts_path points to directory)
"""

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from ktrdr.api.models.db.base import Base


class CheckpointRecord(Base):
    """Database model for checkpoint persistence.

    This table stores checkpoint metadata for operations. Each operation
    has at most one checkpoint (UPSERT behavior with operation_id as PK).
    Large artifacts (model weights) are stored on filesystem, with the
    path stored in this table.

    Attributes:
        operation_id: Unique identifier linking to the operation (primary key, FK).
        checkpoint_type: Type of checkpoint (periodic, cancellation, failure, shutdown).
        created_at: When the checkpoint was created.
        state: JSONB containing checkpoint state (epoch, loss values, etc).
        artifacts_path: Path to filesystem directory containing artifacts (nullable).
        state_size_bytes: Size of the state JSON (for monitoring).
        artifacts_size_bytes: Size of artifacts on filesystem (for monitoring).
    """

    __tablename__ = "operation_checkpoints"

    # Primary key with foreign key to operations table
    operation_id = Column(
        String(255),
        ForeignKey("operations.operation_id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Checkpoint metadata
    checkpoint_type = Column(
        String(50),
        nullable=False,
    )  # periodic, cancellation, failure, shutdown

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # State (JSONB for queryability and flexibility)
    # Contains: epoch, train_loss, val_loss, learning_rate, best_val_loss, etc.
    state = Column(JSONB, nullable=False)

    # Artifact location (NULL for backtesting which has no large artifacts)
    artifacts_path = Column(String(500), nullable=True)

    # Size tracking for monitoring and cleanup decisions
    state_size_bytes = Column(Integer, nullable=True)
    artifacts_size_bytes = Column(BigInteger, nullable=True)

    # Indexes for common queries
    __table_args__ = (
        Index("ix_checkpoints_created_at", "created_at"),
        Index("ix_checkpoints_type", "checkpoint_type"),
    )

    def __repr__(self) -> str:
        """Return string representation of the checkpoint record."""
        return (
            f"<CheckpointRecord("
            f"operation_id='{self.operation_id}', "
            f"type='{self.checkpoint_type}'"
            f")>"
        )
