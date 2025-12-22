"""SQLAlchemy ORM model for operations persistence.

This module defines the OperationRecord model for storing operation state
in PostgreSQL. This is the foundation for the checkpoint and resilience system.

Operations are persisted to survive backend restarts. The model includes:
- Core operation fields (id, type, status)
- Timing fields (created_at, started_at, completed_at)
- Progress tracking (percent, message)
- Worker association (worker_id, is_backend_local)
- Metadata and results (JSONB for flexibility)
- Reconciliation support (heartbeat, reconciliation_status)
"""


from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from ktrdr.api.models.db.base import Base


class OperationRecord(Base):
    """Database model for operation persistence.

    This table stores the state of all operations (training, backtesting, etc.)
    to survive backend restarts. Workers re-register after restart and reconcile
    their operation status with this table.

    Attributes:
        operation_id: Unique identifier for the operation (primary key).
        operation_type: Type of operation (e.g., 'training', 'backtesting').
        status: Current status (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED).
        worker_id: ID of the worker executing this operation (nullable).
        is_backend_local: True if operation runs in backend process (not a worker).
        created_at: When the operation was created.
        started_at: When the operation started executing.
        completed_at: When the operation finished (success, failure, or cancel).
        progress_percent: Completion percentage (0-100).
        progress_message: Human-readable progress message.
        metadata: JSONB containing operation-specific metadata (symbol, timeframe, etc).
        result: JSONB containing operation result data.
        error_message: Error message if operation failed.
        last_heartbeat_at: Last time worker reported heartbeat for this operation.
        reconciliation_status: Status for post-restart reconciliation.
    """

    __tablename__ = "operations"

    # Primary key
    operation_id = Column(String(255), primary_key=True)

    # Core fields
    operation_type = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False)

    # Worker association
    worker_id = Column(String(255), nullable=True)
    is_backend_local = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Progress tracking
    progress_percent = Column(Float, default=0, nullable=False)
    progress_message = Column(String(500), nullable=True)

    # Flexible storage for operation-specific data
    # Note: Use metadata_ as Python attribute to avoid conflict with SQLAlchemy's reserved 'metadata'
    metadata_ = Column("metadata", JSONB, nullable=False, default=dict)
    result = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)

    # Resilience fields
    last_heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    reconciliation_status = Column(String(50), nullable=True)

    # Indexes for common queries
    __table_args__ = (
        Index("ix_operations_status", "status"),
        Index("ix_operations_worker_id", "worker_id"),
        Index("ix_operations_operation_type", "operation_type"),
        Index("ix_operations_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        """Return string representation of the operation record."""
        return (
            f"<OperationRecord("
            f"operation_id='{self.operation_id}', "
            f"type='{self.operation_type}', "
            f"status='{self.status}'"
            f")>"
        )
