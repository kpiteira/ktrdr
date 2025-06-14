"""
Operations service for managing long-running operations.

This service provides a central registry for tracking and managing
async operations across the KTRDR system.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict

from ktrdr.logging import get_logger
from ktrdr.errors import DataError
from ktrdr.api.models.operations import (
    OperationInfo,
    OperationStatus,
    OperationType,
    OperationProgress,
    OperationMetadata,
)

logger = get_logger(__name__)


class OperationsService:
    """
    Service for managing long-running operations.

    Provides a central registry for tracking operations, their status,
    progress, and cancellation capabilities.
    """

    def __init__(self):
        """Initialize the operations service."""
        # Global operation registry
        self._operations: Dict[str, OperationInfo] = {}

        # Operation tasks registry (for cancellation)
        self._operation_tasks: Dict[str, asyncio.Task] = {}

        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

        logger.info("Operations service initialized")

    def generate_operation_id(
        self, operation_type: OperationType, prefix: Optional[str] = None
    ) -> str:
        """
        Generate a unique operation ID.

        Args:
            operation_type: Type of operation
            prefix: Optional prefix for the ID

        Returns:
            Unique operation identifier
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]

        if prefix:
            return f"op_{prefix}_{operation_type.value}_{timestamp}_{unique_id}"
        else:
            return f"op_{operation_type.value}_{timestamp}_{unique_id}"

    async def create_operation(
        self,
        operation_type: OperationType,
        metadata: OperationMetadata,
        operation_id: Optional[str] = None,
    ) -> OperationInfo:
        """
        Create a new operation in the registry.

        Args:
            operation_type: Type of operation
            metadata: Operation metadata
            operation_id: Optional custom operation ID

        Returns:
            Created operation info
        """
        async with self._lock:
            if operation_id is None:
                operation_id = self.generate_operation_id(operation_type)

            # Ensure operation ID is unique
            if operation_id in self._operations:
                raise DataError(
                    message=f"Operation ID already exists: {operation_id}",
                    error_code="OPERATIONS-DuplicateID",
                    details={"operation_id": operation_id},
                )

            # Create operation
            operation = OperationInfo(
                operation_id=operation_id,
                operation_type=operation_type,
                status=OperationStatus.PENDING,
                created_at=datetime.now(timezone.utc),
                metadata=metadata,
            )

            # Add to registry
            self._operations[operation_id] = operation

            logger.info(f"Created operation: {operation_id} (type: {operation_type})")
            return operation

    async def start_operation(self, operation_id: str, task: asyncio.Task) -> None:
        """
        Mark an operation as started and register its task.

        Args:
            operation_id: Operation identifier
            task: Asyncio task for the operation
        """
        async with self._lock:
            if operation_id not in self._operations:
                raise DataError(
                    message=f"Operation not found: {operation_id}",
                    error_code="OPERATIONS-NotFound",
                    details={"operation_id": operation_id},
                )

            # Update operation status
            operation = self._operations[operation_id]
            operation.status = OperationStatus.RUNNING
            operation.started_at = datetime.now(timezone.utc)

            # Register task for cancellation
            self._operation_tasks[operation_id] = task

            logger.info(f"Started operation: {operation_id}")

    async def update_progress(
        self,
        operation_id: str,
        progress: OperationProgress,
    ) -> None:
        """
        Update operation progress.

        Args:
            operation_id: Operation identifier
            progress: Updated progress information
        """
        async with self._lock:
            if operation_id not in self._operations:
                logger.warning(
                    f"Cannot update progress - operation not found: {operation_id}"
                )
                return

            operation = self._operations[operation_id]
            operation.progress = progress

            # Log progress at intervals
            if progress.percentage % 10 == 0:  # Log every 10%
                logger.debug(
                    f"Operation {operation_id} progress: {progress.percentage:.1f}%"
                )

    async def complete_operation(
        self,
        operation_id: str,
        result_summary: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Mark an operation as completed.

        Args:
            operation_id: Operation identifier
            result_summary: Optional summary of results
        """
        async with self._lock:
            if operation_id not in self._operations:
                logger.warning(f"Cannot complete - operation not found: {operation_id}")
                return

            operation = self._operations[operation_id]
            operation.status = OperationStatus.COMPLETED
            operation.completed_at = datetime.now(timezone.utc)
            operation.result_summary = result_summary
            operation.progress.percentage = 100.0

            # Clean up task reference
            if operation_id in self._operation_tasks:
                del self._operation_tasks[operation_id]

            logger.info(f"Completed operation: {operation_id}")

    async def fail_operation(
        self,
        operation_id: str,
        error_message: str,
    ) -> None:
        """
        Mark an operation as failed.

        Args:
            operation_id: Operation identifier
            error_message: Error description
        """
        async with self._lock:
            if operation_id not in self._operations:
                logger.warning(f"Cannot fail - operation not found: {operation_id}")
                return

            operation = self._operations[operation_id]
            operation.status = OperationStatus.FAILED
            operation.completed_at = datetime.now(timezone.utc)
            operation.error_message = error_message

            # Clean up task reference
            if operation_id in self._operation_tasks:
                del self._operation_tasks[operation_id]

            logger.error(f"Failed operation: {operation_id} - {error_message}")

    async def cancel_operation(
        self,
        operation_id: str,
        reason: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Cancel a running operation.

        Args:
            operation_id: Operation identifier
            reason: Optional cancellation reason
            force: Force cancellation even if operation is in critical section

        Returns:
            Cancellation result dictionary
        """
        async with self._lock:
            if operation_id not in self._operations:
                return {
                    "success": False,
                    "error": f"Operation not found: {operation_id}",
                }

            operation = self._operations[operation_id]

            # Check if operation can be cancelled
            if operation.status in [
                OperationStatus.COMPLETED,
                OperationStatus.FAILED,
                OperationStatus.CANCELLED,
            ]:
                return {
                    "success": False,
                    "error": f"Operation {operation_id} is already finished (status: {operation.status})",
                }

            # Cancel the asyncio task if it exists
            cancelled_task = False
            if operation_id in self._operation_tasks:
                task = self._operation_tasks[operation_id]
                if not task.done():
                    task.cancel()
                    cancelled_task = True
                del self._operation_tasks[operation_id]

            # Update operation status
            operation.status = OperationStatus.CANCELLED
            operation.completed_at = datetime.now(timezone.utc)
            operation.error_message = reason or "Operation cancelled by user"

            logger.info(
                f"Cancelled operation: {operation_id} (task_cancelled: {cancelled_task})"
            )

            return {
                "success": True,
                "operation_id": operation_id,
                "status": "cancelled",
                "cancelled_at": operation.completed_at.isoformat(),
                "cancellation_reason": reason,
                "task_cancelled": cancelled_task,
            }

    async def get_operation(self, operation_id: str) -> Optional[OperationInfo]:
        """
        Get operation information.

        Args:
            operation_id: Operation identifier

        Returns:
            Operation info or None if not found
        """
        async with self._lock:
            return self._operations.get(operation_id)

    async def list_operations(
        self,
        status: Optional[OperationStatus] = None,
        operation_type: Optional[OperationType] = None,
        limit: int = 100,
        offset: int = 0,
        active_only: bool = False,
    ) -> Tuple[List[OperationInfo], int, int]:
        """
        List operations with filtering.

        Args:
            status: Filter by status
            operation_type: Filter by operation type
            limit: Maximum number of operations to return
            offset: Number of operations to skip
            active_only: Only return active operations

        Returns:
            Tuple of (operations, total_count, active_count)
        """
        async with self._lock:
            # Get all operations
            all_operations = list(self._operations.values())

            # Apply filters
            filtered_operations = all_operations

            if active_only:
                filtered_operations = [
                    op
                    for op in filtered_operations
                    if op.status in [OperationStatus.PENDING, OperationStatus.RUNNING]
                ]

            if status:
                filtered_operations = [
                    op for op in filtered_operations if op.status == status
                ]

            if operation_type:
                filtered_operations = [
                    op
                    for op in filtered_operations
                    if op.operation_type == operation_type
                ]

            # Sort by creation date (newest first)
            filtered_operations.sort(key=lambda op: op.created_at, reverse=True)

            # Apply pagination
            total_count = len(filtered_operations)
            paginated_operations = filtered_operations[offset : offset + limit]

            # Count active operations
            active_count = len(
                [
                    op
                    for op in all_operations
                    if op.status in [OperationStatus.PENDING, OperationStatus.RUNNING]
                ]
            )

            return paginated_operations, total_count, active_count

    async def retry_operation(self, operation_id: str) -> OperationInfo:
        """
        Retry a failed operation.

        Args:
            operation_id: Operation identifier to retry

        Returns:
            New operation info for the retry

        Raises:
            DataError: If operation cannot be retried
        """
        async with self._lock:
            original_operation = self._operations.get(operation_id)

            if not original_operation:
                raise DataError(
                    message=f"Cannot retry - operation not found: {operation_id}",
                    error_code="OPERATIONS-RetryNotFound",
                    details={"operation_id": operation_id},
                )

            if original_operation.status != OperationStatus.FAILED:
                raise DataError(
                    message=f"Cannot retry - operation not failed: {operation_id}",
                    error_code="OPERATIONS-RetryNotFailed",
                    details={
                        "operation_id": operation_id,
                        "status": original_operation.status,
                    },
                )

            # Create new operation with same parameters
            new_operation_id = self.generate_operation_id(
                original_operation.operation_type, prefix="retry"
            )

            new_operation = OperationInfo(
                operation_id=new_operation_id,
                operation_type=original_operation.operation_type,
                status=OperationStatus.PENDING,
                created_at=datetime.now(timezone.utc),
                metadata=original_operation.metadata,
            )

            # Add to registry
            self._operations[new_operation_id] = new_operation

            logger.info(
                f"Created retry operation: {new_operation_id} (original: {operation_id})"
            )
            return new_operation

    async def cleanup_old_operations(self, max_age_hours: int = 24) -> int:
        """
        Clean up old completed/failed operations.

        Args:
            max_age_hours: Maximum age in hours for keeping operations

        Returns:
            Number of operations cleaned up
        """
        async with self._lock:
            cutoff_time = datetime.now(timezone.utc).replace(
                hour=datetime.now(timezone.utc).hour - max_age_hours
            )

            operations_to_remove = []
            for operation_id, operation in self._operations.items():
                if (
                    operation.status
                    in [
                        OperationStatus.COMPLETED,
                        OperationStatus.FAILED,
                        OperationStatus.CANCELLED,
                    ]
                    and operation.completed_at
                    and operation.completed_at < cutoff_time
                ):
                    operations_to_remove.append(operation_id)

            # Remove old operations
            for operation_id in operations_to_remove:
                del self._operations[operation_id]
                # Clean up any remaining task references
                if operation_id in self._operation_tasks:
                    del self._operation_tasks[operation_id]

            if operations_to_remove:
                logger.info(f"Cleaned up {len(operations_to_remove)} old operations")

            return len(operations_to_remove)


# Global operations service instance
_operations_service: Optional[OperationsService] = None


def get_operations_service() -> OperationsService:
    """
    Get the global operations service instance.

    Returns:
        OperationsService singleton instance
    """
    global _operations_service
    if _operations_service is None:
        _operations_service = OperationsService()
    return _operations_service
