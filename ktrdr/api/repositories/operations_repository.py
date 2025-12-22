"""Repository for operations CRUD with the database.

This repository isolates database access from business logic, providing
async CRUD operations for the operations table.
"""

from datetime import datetime, timezone
from typing import Any, Optional, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ktrdr.api.models.db.operations import OperationRecord
from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationProgress,
    OperationStatus,
    OperationType,
)
from ktrdr.logging import get_logger

logger = get_logger(__name__)


class OperationsRepository:
    """Repository for operations CRUD operations.

    Provides async database access for operations, converting between
    the database model (OperationRecord) and domain model (OperationInfo).

    Args:
        session: Async SQLAlchemy session for database access.
    """

    # Terminal statuses that should set completed_at timestamp
    TERMINAL_STATUSES = {"completed", "failed", "cancelled"}

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session.

        Args:
            session: Async SQLAlchemy session for database access.
        """
        self._session = session

    async def create(self, operation: OperationInfo) -> OperationInfo:
        """Create a new operation record in the database.

        Args:
            operation: The OperationInfo to persist.

        Returns:
            The created OperationInfo (may have updated timestamps).
        """
        record = self._info_to_record(operation)
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)

        logger.debug(f"Created operation record: {operation.operation_id}")
        return self._record_to_info(record)

    async def get(self, operation_id: str) -> Optional[OperationInfo]:
        """Get an operation by ID.

        Args:
            operation_id: The operation's unique identifier.

        Returns:
            OperationInfo if found, None otherwise.
        """
        stmt = select(OperationRecord).where(
            OperationRecord.operation_id == operation_id
        )
        result = await self._session.execute(stmt)
        record = result.scalar_one_or_none()

        if record is None:
            return None

        return self._record_to_info(record)

    async def update(self, operation_id: str, **fields) -> Optional[OperationInfo]:
        """Update an operation's fields.

        Args:
            operation_id: The operation's unique identifier.
            **fields: Fields to update (e.g., status='completed', progress_percent=100.0).

        Returns:
            Updated OperationInfo if found, None otherwise.
        """
        stmt = select(OperationRecord).where(
            OperationRecord.operation_id == operation_id
        )
        result = await self._session.execute(stmt)
        record = result.scalar_one_or_none()

        if record is None:
            return None

        # Apply field updates
        for field_name, value in fields.items():
            if hasattr(record, field_name):
                setattr(record, field_name, value)

        # Auto-set completed_at when transitioning to terminal status
        if "status" in fields and fields["status"] in self.TERMINAL_STATUSES:
            if record.completed_at is None:
                record.completed_at = datetime.now(timezone.utc)

        await self._session.commit()
        await self._session.refresh(record)

        logger.debug(
            f"Updated operation record: {operation_id} with {list(fields.keys())}"
        )
        return self._record_to_info(record)

    async def list(
        self,
        status: Optional[str] = None,
        worker_id: Optional[str] = None,
    ) -> list[OperationInfo]:
        """List operations with optional filters.

        Args:
            status: Filter by operation status.
            worker_id: Filter by worker ID.

        Returns:
            List of matching OperationInfo objects.
        """
        stmt = select(OperationRecord)

        if status is not None:
            stmt = stmt.where(OperationRecord.status == status)
        if worker_id is not None:
            stmt = stmt.where(OperationRecord.worker_id == worker_id)

        result = await self._session.execute(stmt)
        records = result.scalars().all()

        return [self._record_to_info(record) for record in records]

    async def delete(self, operation_id: str) -> bool:
        """Delete an operation by ID.

        Args:
            operation_id: The operation's unique identifier.

        Returns:
            True if deleted, False if not found.
        """
        stmt = select(OperationRecord).where(
            OperationRecord.operation_id == operation_id
        )
        result = await self._session.execute(stmt)
        record = result.scalar_one_or_none()

        if record is None:
            return False

        await self._session.delete(record)
        await self._session.commit()

        logger.debug(f"Deleted operation record: {operation_id}")
        return True

    @staticmethod
    def _record_to_info(record: OperationRecord) -> OperationInfo:
        """Convert OperationRecord (DB model) to OperationInfo (domain model).

        Args:
            record: The database record.

        Returns:
            The domain model representation.

        Note:
            SQLAlchemy Column types require cast() for mypy compatibility.
        """
        # Parse metadata from JSONB (cast for mypy - SQLAlchemy Column type)
        metadata_dict: dict[str, Any] = cast(dict[str, Any], record.metadata_) or {}
        metadata = OperationMetadata(
            symbol=metadata_dict.get("symbol"),
            timeframe=metadata_dict.get("timeframe"),
            mode=metadata_dict.get("mode"),
            start_date=_parse_datetime(metadata_dict.get("start_date")),
            end_date=_parse_datetime(metadata_dict.get("end_date")),
            parameters=metadata_dict.get("parameters", {}),
        )

        # Build progress from stored fields (cast for mypy)
        progress = OperationProgress(
            percentage=cast(float, record.progress_percent) or 0.0,
            current_step=cast(Optional[str], record.progress_message),
            steps_completed=0,  # Not stored in DB
            steps_total=0,  # Not stored in DB
            items_processed=0,  # Not stored in DB
            items_total=None,  # Not stored in DB
            current_item=None,  # Not stored in DB
        )

        # Map operation type string to enum
        try:
            operation_type = OperationType(cast(str, record.operation_type))
        except ValueError:
            # Handle unknown operation types gracefully
            operation_type = OperationType.DUMMY
            logger.warning(f"Unknown operation type: {record.operation_type}")

        # Map status string to enum
        try:
            status = OperationStatus(cast(str, record.status))
        except ValueError:
            status = OperationStatus.PENDING
            logger.warning(f"Unknown status: {record.status}")

        return OperationInfo(
            operation_id=cast(str, record.operation_id),
            parent_operation_id=None,  # Not stored in DB (yet)
            operation_type=operation_type,
            status=status,
            created_at=cast(datetime, record.created_at),
            started_at=cast(Optional[datetime], record.started_at),
            completed_at=cast(Optional[datetime], record.completed_at),
            progress=progress,
            metadata=metadata,
            error_message=cast(Optional[str], record.error_message),
            result_summary=cast(Optional[dict[str, Any]], record.result),
            metrics=None,  # Not stored in DB (yet)
        )

    @staticmethod
    def _info_to_record(info: OperationInfo) -> OperationRecord:
        """Convert OperationInfo (domain model) to OperationRecord (DB model).

        Args:
            info: The domain model.

        Returns:
            The database record representation.
        """
        # Flatten metadata for JSONB storage
        metadata_dict: dict[str, Any] = {}
        if info.metadata:
            if info.metadata.symbol:
                metadata_dict["symbol"] = info.metadata.symbol
            if info.metadata.timeframe:
                metadata_dict["timeframe"] = info.metadata.timeframe
            if info.metadata.mode:
                metadata_dict["mode"] = info.metadata.mode
            if info.metadata.start_date:
                metadata_dict["start_date"] = info.metadata.start_date.isoformat()
            if info.metadata.end_date:
                metadata_dict["end_date"] = info.metadata.end_date.isoformat()
            if info.metadata.parameters:
                metadata_dict["parameters"] = info.metadata.parameters

        return OperationRecord(
            operation_id=info.operation_id,
            operation_type=info.operation_type.value,
            status=info.status.value,
            created_at=info.created_at,
            started_at=info.started_at,
            completed_at=info.completed_at,
            progress_percent=info.progress.percentage if info.progress else 0.0,
            progress_message=info.progress.current_step if info.progress else None,
            metadata_=metadata_dict,
            result=info.result_summary,
            error_message=info.error_message,
        )


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO datetime string.

    Args:
        value: ISO format datetime string or None.

    Returns:
        Parsed datetime or None.
    """
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
