"""
Operations service for managing long-running operations.

This service provides a central registry for tracking and managing
async operations across the KTRDR system.
"""

import asyncio
import os
import time
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

        # TASK 1.3: Bridge registry for pull-based progress updates (M1)
        self._local_bridges: dict[str, Any] = {}  # operation_id → ProgressBridge
        self._metrics_cursors: dict[str, int] = (
            {}
        )  # operation_id → cursor for incremental metrics
        self._remote_proxies: dict[str, Any] = (
            {}
        )  # operation_id → OperationServiceProxy (M2)

        # TASK 1.4: Cache infrastructure for preventing redundant bridge reads (M1)
        self._last_refresh: dict[str, float] = {}  # operation_id → timestamp
        self._cache_ttl: float = float(
            os.getenv("OPERATIONS_CACHE_TTL", "1.0")
        )  # Default: 1 second

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
                metrics=None,  # NEW: M1 - initialize as None
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

    async def get_operation(
        self, operation_id: str, force_refresh: bool = False
    ) -> Optional[OperationInfo]:
        """
        Get operation information with live status updates.

        TASK 1.3: Now includes pull-based refresh from local bridges.
        TASK 1.4: Added cache awareness and force_refresh parameter.

        Args:
            operation_id: Operation identifier
            force_refresh: If True, bypass cache and force refresh from bridge

        Returns:
            Operation info or None if not found
        """
        async with self._lock:
            operation = self._operations.get(operation_id)
            if not operation:
                return None

            # TASK 1.3/1.4: Pull from local bridge if registered and operation still running
            if (
                operation.status == OperationStatus.RUNNING
                and operation_id in self._local_bridges
            ):
                # TASK 1.4: Force refresh bypasses cache
                if force_refresh:
                    # Invalidate cache to force refresh
                    self._last_refresh[operation_id] = 0
                    logger.debug(
                        f"Force refresh requested for operation {operation_id}"
                    )

                # Refresh from bridge (synchronous, fast, cache-aware)
                self._refresh_from_bridge(operation_id)

            # TASK 2.5: Pull from remote proxy if registered and operation still running
            if (
                operation.status == OperationStatus.RUNNING
                and operation_id in self._remote_proxies
            ):
                # Force refresh bypasses cache
                if force_refresh:
                    # Invalidate cache to force refresh
                    self._last_refresh[operation_id] = 0
                    logger.debug(
                        f"Force refresh requested for remote operation {operation_id}"
                    )

                # Refresh from remote host service (async, cache-aware)
                await self._refresh_from_remote_proxy(operation_id)

            # For training operations, query host service for live status
            # (This legacy code remains for backward compatibility, will be removed in M3)
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
                metrics=None,  # NEW: M1 - initialize as None
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

    def register_local_bridge(self, operation_id: str, bridge: Any) -> None:
        """
        Register a local bridge for pull-based progress updates (TASK 1.3).

        Args:
            operation_id: Operation identifier
            bridge: ProgressBridge instance for this operation
        """
        self._local_bridges[operation_id] = bridge
        self._metrics_cursors[operation_id] = 0  # Start cursor at 0
        logger.info(f"Registered local bridge for operation {operation_id}")

    def _refresh_from_bridge(self, operation_id: str) -> None:
        """
        Pull state and metrics from registered bridge with cache awareness (TASK 1.4).

        This method checks cache freshness before reading from the bridge to prevent
        redundant reads when multiple clients poll within the TTL window.

        Args:
            operation_id: Operation identifier
        """
        bridge = self._local_bridges.get(operation_id)
        if not bridge:
            return

        # TASK 1.4: Check cache freshness
        last_refresh = self._last_refresh.get(operation_id, 0)
        age = time.time() - last_refresh

        if age < self._cache_ttl:
            # Cache is fresh - skip refresh
            logger.debug(
                f"Cache hit for operation {operation_id} (age={age:.3f}s, TTL={self._cache_ttl}s)"
            )
            return

        # Cache miss or stale - pull from bridge
        logger.debug(
            f"Cache miss for operation {operation_id} (age={age:.3f}s > TTL={self._cache_ttl}s) - refreshing"
        )

        # Pull current state from bridge
        state = bridge.get_status()

        # Pull incremental metrics from bridge
        cursor = self._metrics_cursors.get(operation_id, 0)
        new_metrics, new_cursor = bridge.get_metrics(cursor)

        # Update operation with fresh data
        operation = self._operations.get(operation_id)
        if operation:
            # Update progress from state
            operation.progress = OperationProgress(
                percentage=state.get("percentage", 0.0),
                current_step=state.get(
                    "message", ""
                ),  # message is the string description
                steps_completed=state.get("current_step", 0),  # numeric step counter
                steps_total=state.get(
                    "total_epochs", 0
                ),  # total number of steps/epochs
                items_processed=state.get("items_processed", 0),
                items_total=state.get("items_total"),
                current_item=state.get("current_item"),
            )

            # Append new metrics to operation (if any)
            if new_metrics:
                if operation.metrics is None:
                    operation.metrics = {}
                # For training operations, append to epochs list
                if operation.operation_type == OperationType.TRAINING:
                    if "epochs" not in operation.metrics:
                        operation.metrics["epochs"] = []
                    operation.metrics["epochs"].extend(new_metrics)

            # Update cursor for next incremental read
            self._metrics_cursors[operation_id] = new_cursor

            # TASK 1.4: Update cache timestamp
            self._last_refresh[operation_id] = time.time()

            logger.debug(
                f"Refreshed operation {operation_id} from bridge "
                f"(cursor {cursor} → {new_cursor}, {len(new_metrics)} new metrics)"
            )

    async def _refresh_from_remote_proxy(self, operation_id: str) -> None:
        """
        Pull state and metrics from host service via proxy with cache awareness (TASK 2.5).

        This method queries the host service for operation state and incremental metrics,
        updating the backend operation accordingly. Similar to _refresh_from_bridge() but
        for remote host services instead of local bridges.

        Architecture:
        - Backend tracks cursor per operation
        - Backend passes cursor to host when querying metrics
        - Host returns delta (metrics since cursor)
        - Backend updates cursor with new value
        - Two-level caching: backend cache → host service cache → bridge

        Args:
            operation_id: Backend operation identifier
        """
        # Check if proxy registered
        if operation_id not in self._remote_proxies:
            return

        proxy, host_operation_id = self._remote_proxies[operation_id]

        # Check cache freshness (same pattern as local bridges)
        last_refresh = self._last_refresh.get(operation_id, 0)
        age = time.time() - last_refresh

        if age < self._cache_ttl:
            # Cache is fresh - skip refresh
            logger.debug(
                f"Cache hit for remote operation {operation_id} "
                f"(age={age:.3f}s, TTL={self._cache_ttl}s)"
            )
            return

        # Cache miss or stale - pull from host service
        logger.debug(
            f"Cache miss for remote operation {operation_id} "
            f"(age={age:.3f}s > TTL={self._cache_ttl}s) - querying host service"
        )

        try:
            # (1) Query host service for operation state
            host_data = await proxy.get_operation(host_operation_id)

            # (2) Update backend operation with host's data
            operation = self._operations.get(operation_id)
            if not operation:
                logger.warning(
                    f"Operation {operation_id} not found in backend registry"
                )
                return

            # Update status
            operation.status = OperationStatus(host_data["status"])

            # Update progress from host data
            if "progress" in host_data:
                host_progress = host_data["progress"]
                operation.progress = OperationProgress(
                    percentage=host_progress.get("percentage", 0.0),
                    current_step=host_progress.get("current_step", ""),
                    steps_completed=host_progress.get("steps_completed", 0),
                    steps_total=host_progress.get("steps_total", 0),
                    items_processed=host_progress.get("items_processed", 0),
                    items_total=host_progress.get("items_total"),
                    current_item=host_progress.get("current_item"),
                )

            # (3) Get incremental metrics from host (backend tracks cursor)
            cursor = self._metrics_cursors.get(operation_id, 0)
            metrics_data = await proxy.get_metrics(host_operation_id, cursor)
            new_metrics, new_cursor = metrics_data

            # (4) Append new metrics to operation
            if new_metrics:
                if operation.metrics is None:
                    operation.metrics = {}

                # For training operations, append to epochs list
                if operation.operation_type == OperationType.TRAINING:
                    if "epochs" not in operation.metrics:
                        operation.metrics["epochs"] = []
                    operation.metrics["epochs"].extend(new_metrics)

            # (5) Update cursor to new value (always update, even if no new metrics)
            self._metrics_cursors[operation_id] = new_cursor

            # (6) Update cache timestamp
            self._last_refresh[operation_id] = time.time()

            logger.debug(
                f"Refreshed operation {operation_id} from host {host_operation_id} "
                f"(cursor {cursor} → {new_cursor}, {len(new_metrics)} new metrics)"
            )

        except Exception as e:
            logger.error(
                f"Failed to refresh operation {operation_id} from host service: {e}"
            )
            # Don't raise - allow operation to continue with stale data
            # Client will retry on next query

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
            if adapter is None or not adapter.use_host_service:
                logger.warning(
                    f"Training operation {operation.operation_id} expected host service but not in host service mode"
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

    async def get_operation_metrics(
        self, operation_id: str
    ) -> Optional[dict[str, Any]]:
        """
        Get domain-specific metrics for an operation (M1: API Contract).

        In M1, this returns empty structure. In M2, will return populated metrics.

        Args:
            operation_id: Operation identifier

        Returns:
            dict containing metrics, or None if operation doesn't exist

        Raises:
            KeyError: If operation not found
        """
        operation = await self.get_operation(operation_id)

        if not operation:
            raise KeyError(f"Operation not found: {operation_id}")

        # M1: Return empty metrics (will be populated in M2)
        return operation.metrics if operation.metrics is not None else {}

    async def add_operation_metrics(
        self, operation_id: str, metrics_data: dict[str, Any]
    ) -> None:
        """
        Add domain-specific metrics to an operation.

        For training operations: stores epoch metrics and computes trend analysis.
        For other operation types: stores metrics as-is.

        Args:
            operation_id: Operation identifier
            metrics_data: Metrics payload (structure varies by operation type)

        Raises:
            KeyError: If operation not found
            ValueError: If metrics_data is invalid
        """
        async with self._lock:
            if operation_id not in self._operations:
                raise KeyError(f"Operation not found: {operation_id}")

            operation = self._operations[operation_id]

            # Validate that metrics_data is a dict
            if not isinstance(metrics_data, dict):
                raise ValueError("metrics_data must be a dictionary")

            # Initialize metrics dict if needed
            if operation.metrics is None:
                operation.metrics = {}

            # Handle training-specific metrics
            if operation.operation_type == OperationType.TRAINING:
                await self._add_training_epoch_metrics(operation, metrics_data)
            else:
                # For other operation types, store as-is
                operation.metrics.update(metrics_data)

            logger.debug(
                f"Metrics added for operation {operation_id} "
                f"(type={operation.operation_type}, total_fields={len(operation.metrics)})"
            )

    async def _add_training_epoch_metrics(
        self, operation: OperationInfo, epoch_metrics: dict[str, Any]
    ) -> None:
        """
        Add epoch metrics to training operation and update trend analysis.

        Args:
            operation: The training operation
            epoch_metrics: Epoch metrics to add
        """
        # Ensure operation.metrics is initialized (should be from add_operation_metrics)
        assert operation.metrics is not None, "Metrics should be initialized"

        # Initialize training metrics structure if needed
        if "epochs" not in operation.metrics:
            operation.metrics["epochs"] = []
            operation.metrics["total_epochs_planned"] = 0
            operation.metrics["total_epochs_completed"] = 0

        # Add epoch metrics
        operation.metrics["epochs"].append(epoch_metrics)
        operation.metrics["total_epochs_completed"] = len(operation.metrics["epochs"])

        # Update trend analysis
        self._update_training_metrics_analysis(operation.metrics)

    def _update_training_metrics_analysis(self, metrics: dict[str, Any]) -> None:
        """
        Compute trend indicators from epoch history.

        Updates:
        - best_epoch: Index of epoch with lowest validation loss
        - best_val_loss: Lowest validation loss achieved
        - epochs_since_improvement: Epochs since last improvement
        - is_overfitting: Whether training shows overfitting pattern
        - is_plateaued: Whether training has plateaued (no improvement for 10+ epochs)

        Args:
            metrics: Training metrics dict to update
        """
        epochs = metrics.get("epochs", [])
        if not epochs:
            return

        # Find best epoch (lowest validation loss)
        val_losses = [
            (i, e["val_loss"])
            for i, e in enumerate(epochs)
            if e.get("val_loss") is not None
        ]

        if val_losses:
            best_idx, best_loss = min(val_losses, key=lambda x: x[1])
            metrics["best_epoch"] = best_idx
            metrics["best_val_loss"] = best_loss
            metrics["epochs_since_improvement"] = len(epochs) - 1 - best_idx
        else:
            # No validation data available
            metrics["best_epoch"] = None
            metrics["best_val_loss"] = None
            metrics["epochs_since_improvement"] = 0

        # Detect overfitting (train loss ↓ while val loss ↑)
        if len(epochs) >= 10:
            recent = epochs[-10:]
            train_losses = [e["train_loss"] for e in recent]
            val_losses_recent = [
                e.get("val_loss") for e in recent if e.get("val_loss") is not None
            ]

            if len(val_losses_recent) >= 10:
                # Simple linear trend: last < first means decreasing
                train_decreasing = train_losses[-1] < train_losses[0]
                val_increasing = val_losses_recent[-1] > val_losses_recent[0]

                # Additional check: significant divergence
                train_improvement = (
                    (train_losses[0] - train_losses[-1]) / train_losses[0]
                    if train_losses[0] > 0
                    else 0
                )
                val_degradation = (
                    (val_losses_recent[-1] - val_losses_recent[0])
                    / val_losses_recent[0]
                    if val_losses_recent[0] > 0
                    else 0
                )

                # Overfitting if train improving >5% while val degrading >5%
                metrics["is_overfitting"] = (
                    train_decreasing
                    and val_increasing
                    and train_improvement > 0.05
                    and val_degradation > 0.05
                )
            else:
                metrics["is_overfitting"] = False
        else:
            metrics["is_overfitting"] = False

        # Detect plateau (no improvement for 10+ epochs)
        metrics["is_plateaued"] = metrics.get("epochs_since_improvement", 0) >= 10

    async def add_metrics(
        self, operation_id: str, metrics_data: dict[str, Any]
    ) -> None:
        """
        Alias for add_operation_metrics for backwards compatibility.

        Args:
            operation_id: Operation identifier
            metrics_data: Metrics payload

        Raises:
            KeyError: If operation not found
            ValueError: If metrics_data is invalid
        """
        await self.add_operation_metrics(operation_id, metrics_data)


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
