"""
Operations service for managing long-running operations.

This service provides a central registry for tracking and managing
async operations across the KTRDR system.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationProgress,
    OperationStatus,
    OperationType,
)
from ktrdr.async_infrastructure.cancellation import (
    AsyncCancellationToken,
    get_global_coordinator,
)
from ktrdr.errors import DataError
from ktrdr.logging import get_logger

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
        self._operations: dict[str, OperationInfo] = {}

        # Operation tasks registry (for cancellation)
        self._operation_tasks: dict[str, asyncio.Task] = {}

        # Use global unified cancellation coordinator instead of local events
        self._cancellation_coordinator = get_global_coordinator()

        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

        logger.info("Operations service initialized with unified cancellation system")

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
                started_at=None,
                completed_at=None,
                error_message=None,
                result_summary=None,
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
        warnings: Optional[list[str]] = None,
        errors: Optional[list[str]] = None,
    ) -> None:
        """
        Update operation progress (lock-free for performance).

        Args:
            operation_id: Operation identifier
            progress: Updated progress information
            warnings: Optional list of warning messages
            errors: Optional list of error messages
        """
        # Lock-free progress updates for performance
        if operation_id not in self._operations:
            logger.warning(
                f"Cannot update progress - operation not found: {operation_id}"
            )
            return

        operation = self._operations[operation_id]
        # Atomic assignment - no lock needed
        operation.progress = progress

        # For lists, replace entire list instead of extending (atomic)
        if warnings:
            operation.warnings = operation.warnings + warnings
        if errors:
            operation.errors = operation.errors + errors

        # 🔧 TEMP DEBUG: Log ALL progress updates at INFO level
        logger.info(
            f"📊 Operation {operation_id} progress: {progress.percentage:.1f}% - {progress.current_step or 'Loading'}"
        )

    async def complete_operation(
        self,
        operation_id: str,
        result_summary: Optional[dict[str, Any]] = None,
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
    ) -> dict[str, Any]:
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

            # Use unified cancellation coordinator
            cancellation_reason = reason or f"Operation {operation_id} cancelled"
            self._cancellation_coordinator.cancel_operation(
                operation_id, cancellation_reason
            )

            # Cancel the asyncio task if it exists
            cancelled_task = False
            if operation_id in self._operation_tasks:
                task = self._operation_tasks[operation_id]
                if not task.done():
                    task.cancel()
                    cancelled_task = True
                del self._operation_tasks[operation_id]

            # For training operations, also cancel the host service session
            training_session_cancelled = False
            if operation.operation_type == OperationType.TRAINING:
                logger.info(
                    f"Training cancellation requested for operation {operation_id} - reason: {reason or 'No reason provided'}"
                )

                session_id = None
                if (
                    hasattr(operation.metadata, "parameters")
                    and operation.metadata.parameters
                ):
                    session_id = operation.metadata.parameters.get("session_id")

                if session_id:
                    try:
                        logger.info(
                            f"Sending cancellation request to training host service for session {session_id}"
                        )
                        # Get training service to cancel the session
                        from ktrdr.api.services.training_service import (
                            get_training_service,
                        )

                        training_service = get_training_service()
                        await training_service.cancel_training_session(
                            session_id, reason
                        )
                        training_session_cancelled = True
                        logger.info(
                            f"Successfully sent cancellation to training host service for session {session_id}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to cancel training session {session_id}: {e}"
                        )
                else:
                    logger.warning(
                        f"No session_id found for training operation {operation_id} - cannot cancel host service"
                    )

            # Update operation status
            operation.status = OperationStatus.CANCELLED
            operation.completed_at = datetime.now(timezone.utc)
            operation.error_message = reason or "Operation cancelled by user"

            logger.info(
                f"Cancelled operation: {operation_id} (task_cancelled: {cancelled_task}, training_session_cancelled: {training_session_cancelled})"
            )

            return {
                "success": True,
                "operation_id": operation_id,
                "status": "cancelled",
                "cancelled_at": operation.completed_at.isoformat(),
                "cancellation_reason": reason,
                "task_cancelled": cancelled_task,
                "training_session_cancelled": training_session_cancelled,
            }

    async def get_operation(self, operation_id: str) -> Optional[OperationInfo]:
        """
        Get operation information with live status updates for training operations.

        Args:
            operation_id: Operation identifier

        Returns:
            Operation info or None if not found
        """
        async with self._lock:
            operation = self._operations.get(operation_id)
            if not operation:
                return None

            # For training operations, query host service for live status
            if (
                operation.operation_type == OperationType.TRAINING
                and operation.status == OperationStatus.RUNNING
            ):
                try:
                    # Get training host service status
                    updated_operation = (
                        await self._update_training_operation_from_host_service(
                            operation
                        )
                    )
                    if updated_operation:
                        # Update the stored operation with live data
                        self._operations[operation_id] = updated_operation
                        return updated_operation
                except Exception as e:
                    logger.debug(
                        f"Failed to get live training status for {operation_id}: {e}"
                    )
                    # Fall through to return stored operation

            return operation

    async def list_operations(
        self,
        status: Optional[OperationStatus] = None,
        operation_type: Optional[OperationType] = None,
        limit: int = 100,
        offset: int = 0,
        active_only: bool = False,
    ) -> tuple[list[OperationInfo], int, int]:
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
                started_at=None,
                completed_at=None,
                error_message=None,
                result_summary=None,
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

    async def _update_training_operation_from_host_service(
        self, operation: OperationInfo
    ) -> Optional[OperationInfo]:
        """
        Update training operation with live status from host service.

        Args:
            operation: Current operation info

        Returns:
            Updated operation info or None if update failed
        """
        try:
            # Extract session ID from operation metadata or results
            session_id = None
            if (
                hasattr(operation.metadata, "parameters")
                and operation.metadata.parameters
            ):
                session_id = operation.metadata.parameters.get("session_id")

            if (
                not session_id
                and hasattr(operation, "result_summary")
                and operation.result_summary
            ):
                session_id = operation.result_summary.get("session_id")

            if not session_id:
                logger.debug(
                    f"No session_id found for training operation {operation.operation_id}"
                )
                return None

            # Get training adapter from TrainingService (singleton, already configured)
            from ktrdr.api.services.training_service import get_training_service

            training_service = get_training_service()
            adapter = training_service.adapter

            # Verify we're in host service mode
            if not adapter.use_host_service:
                logger.warning(
                    f"Training operation {operation.operation_id} expected host service but adapter is in local mode"
                )
                return None

            # Query host service status
            status_data = await adapter.get_training_status(session_id)

            host_status = status_data.get("status", "unknown")
            host_progress = status_data.get("progress", {})
            host_metrics = status_data.get("metrics", {})

            logger.debug(
                f"Training operation {operation.operation_id}: host_status={host_status}, progress={host_progress}"
            )

            # Convert host service status to operation format
            if host_status == "running":
                # Extract progress information
                current_epoch = host_progress.get("epoch", 0)
                total_epochs = host_progress.get("total_epochs", 100)
                current_batch = host_progress.get("batch", 0)
                total_batches = host_progress.get("total_batches", 0)

                # Calculate percentage (20% to 90% range for training phase)
                if total_epochs > 0:
                    epoch_progress = current_epoch / total_epochs
                    if total_batches > 0 and current_batch > 0:
                        # Add batch-level granularity within the epoch
                        batch_progress = (current_batch / total_batches) / total_epochs
                        epoch_progress += batch_progress

                    percentage = 20.0 + (epoch_progress * 70.0)  # 20% to 90%
                else:
                    percentage = host_progress.get("progress_percent", 0.0)

                percentage = min(percentage, 90.0)  # Cap at 90%

                # Format current step with epoch and batch info
                current_step = f"Epoch: {current_epoch}"
                if total_epochs > 0:
                    current_step += f"/{total_epochs}"
                if total_batches > 0:
                    current_step += f", Batch: {current_batch}/{total_batches}"

                # Add metrics if available
                if host_metrics and host_metrics.get("current"):
                    metrics = host_metrics["current"]
                    if isinstance(metrics, dict):
                        accuracy = metrics.get("accuracy", 0)
                        loss = metrics.get("loss", 0)
                        if accuracy and len(str(accuracy)) > 0:
                            current_step += f" (Acc: {accuracy:.3f})"
                        if loss and len(str(loss)) > 0:
                            current_step += f" (Loss: {loss:.4f})"

                # Update operation progress
                updated_operation = operation
                updated_operation.progress = OperationProgress(
                    percentage=percentage,
                    current_step=current_step,
                    steps_completed=current_epoch,
                    steps_total=total_epochs,
                    items_processed=current_epoch,
                    items_total=total_epochs,
                    current_item=None,
                )

                return updated_operation

            elif host_status == "completed":
                # Training completed - mark operation as completed
                from datetime import datetime, timezone

                updated_operation = operation
                updated_operation.status = OperationStatus.COMPLETED
                updated_operation.completed_at = datetime.now(timezone.utc)
                updated_operation.progress = OperationProgress(
                    percentage=100.0,
                    current_step="Training completed successfully",
                    steps_completed=100,
                    steps_total=100,
                    items_processed=100,
                    items_total=100,
                    current_item=None,
                )
                # Store host metrics in result summary
                if not updated_operation.result_summary:
                    updated_operation.result_summary = {}
                updated_operation.result_summary.update(
                    {
                        "session_id": session_id,
                        "host_metrics": host_metrics,
                        "training_completed": True,
                        "host_service_used": True,
                    }
                )

                return updated_operation

            elif host_status == "failed":
                # Training failed - mark operation as failed
                from datetime import datetime, timezone

                error_msg = status_data.get("error", "Training failed on host service")

                updated_operation = operation
                updated_operation.status = OperationStatus.FAILED
                updated_operation.completed_at = datetime.now(timezone.utc)
                updated_operation.error_message = error_msg

                return updated_operation

            # For other statuses (stopped, etc.), return original operation
            return None

        except Exception as e:
            logger.warning(
                f"Failed to update training operation from host service: {e}"
            )
            return None

    def get_cancellation_token(
        self, operation_id: str
    ) -> Optional[AsyncCancellationToken]:
        """
        Get unified cancellation token for an operation.

        This method integrates with the global cancellation coordinator to provide
        cancellation tokens that work with the unified protocol.

        Args:
            operation_id: Operation identifier

        Returns:
            AsyncCancellationToken for the operation, or None if operation doesn't exist
        """
        # Check if operation exists
        if operation_id not in self._operations:
            logger.warning(
                f"Cannot get cancellation token - operation not found: {operation_id}"
            )
            return None

        # Create or get existing token from coordinator
        return self._cancellation_coordinator.create_token(operation_id)


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
