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
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from ktrdr.checkpoint.service import CheckpointService

from opentelemetry import trace

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
from ktrdr.checkpoint.types import CheckpointType
from ktrdr.errors import DataError
from ktrdr.logging import get_logger
from ktrdr.monitoring.service_telemetry import create_service_span, trace_service_method

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

    @trace_service_method("operations.create")
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

            # Create operation with telemetry
            with create_service_span(
                "operation.register",
                operation_id=operation_id,
                symbol=metadata.symbol,
                timeframe=metadata.timeframe,
            ) as span:
                # Add operation-specific attributes
                span.set_attribute("operation.type", operation_type.value)
                span.set_attribute("operation.status", OperationStatus.PENDING.value)

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
                    checkpoint_id=None,
                    checkpoint_size_bytes=None,
                    checkpoint_created_at=None,
                )

                # Add to registry
                self._operations[operation_id] = operation

                # TASK 3.1: Persist to database
                await self.persist_operation(operation)

                logger.info(
                    f"Created operation: {operation_id} (type: {operation_type})"
                )
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

            # Update operation status with telemetry
            operation = self._operations[operation_id]
            with create_service_span(
                "operation.state_transition", operation_id=operation_id
            ) as span:
                span.set_attribute("operation.from_status", operation.status.value)
                span.set_attribute("operation.to_status", OperationStatus.RUNNING.value)

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

        This method updates the progress state and also integrates with OpenTelemetry
        by updating span attributes for real-time visibility in distributed traces.

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

        # Update OpenTelemetry span attributes with progress
        try:
            span = trace.get_current_span()
            if span.is_recording():
                # Update span attributes
                span.set_attribute("progress.percentage", progress.percentage)
                span.set_attribute("operation.id", operation_id)

                # Add phase/step information
                if progress.current_step:
                    span.set_attribute("progress.phase", progress.current_step)

                # Add timestamp for real-time tracking
                span.set_attribute("progress.updated_at", time.time())

                # Add items processed if available
                if progress.items_processed > 0:
                    span.set_attribute(
                        "progress.items_processed", progress.items_processed
                    )

                # Add steps completed if available
                if progress.steps_completed > 0:
                    span.set_attribute(
                        "progress.steps_completed", progress.steps_completed
                    )

                logger.debug(
                    f"Updated span attributes for operation {operation_id}: "
                    f"{progress.percentage:.1f}% - {progress.current_step or 'N/A'}"
                )
        except Exception as e:
            # Don't fail progress updates if telemetry fails
            logger.debug(f"Could not update span attributes: {e}")

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

            # CRITICAL: Pull final metrics from bridge before marking complete
            # This ensures all metrics captured during training are persisted
            if operation_id in self._local_bridges:
                logger.debug(f"Pulling final metrics from bridge for {operation_id}")
                # Force cache invalidation to ensure fresh metrics
                self._last_refresh[operation_id] = 0
                self._refresh_from_bridge(operation_id)

            # Update status with telemetry
            with create_service_span(
                "operation.state_transition", operation_id=operation_id
            ) as span:
                span.set_attribute("operation.from_status", operation.status.value)
                span.set_attribute(
                    "operation.to_status", OperationStatus.COMPLETED.value
                )

                operation.status = OperationStatus.COMPLETED
                operation.completed_at = datetime.now(timezone.utc)
                operation.result_summary = result_summary
                operation.progress.percentage = 100.0

            # TASK 3.1: Persist to database
            await self.persist_operation(operation)

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

            # Update status with telemetry
            with create_service_span(
                "operation.state_transition", operation_id=operation_id
            ) as span:
                span.set_attribute("operation.from_status", operation.status.value)
                span.set_attribute("operation.to_status", OperationStatus.FAILED.value)
                span.set_attribute("operation.error", error_message)

                operation.status = OperationStatus.FAILED
                operation.completed_at = datetime.now(timezone.utc)
                operation.error_message = error_message

            # TASK 3.1: Persist to database
            await self.persist_operation(operation)

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

            # M3: For operations with remote proxies, cancel via proxy (same pattern as refresh)
            remote_cancelled = False
            remote_proxy_info = self._get_remote_proxy(operation_id)
            if remote_proxy_info:
                try:
                    proxy, host_operation_id = remote_proxy_info

                    logger.info(
                        f"Cancelling remote operation via proxy: {host_operation_id} (backend: {operation_id})"
                    )

                    # Cancel on host service using the same proxy we use for get_operation
                    await proxy.cancel_operation(host_operation_id, reason)
                    remote_cancelled = True

                    logger.info(
                        f"Successfully cancelled remote operation: {host_operation_id}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to cancel remote operation {host_operation_id}: {e}"
                    )

            # Task 3.5: Create checkpoint before cancelling (if policy enables it)
            checkpoint_created = False
            try:
                from ktrdr.checkpoint.policy import load_checkpoint_policies

                # Load checkpoint policy for this operation type
                policies = load_checkpoint_policies()
                operation_type_key = operation.operation_type.value.lower()
                policy = policies.get(operation_type_key)

                if policy and policy.checkpoint_on_cancellation:
                    # Create cancellation checkpoint with metadata
                    checkpoint_created = await self.create_checkpoint(
                        operation_id=operation_id,
                        checkpoint_type=CheckpointType.CANCELLATION,
                        metadata={
                            "cancellation_reason": cancellation_reason,
                            "checkpoint_at_cancellation": True,
                        },
                    )
                    if checkpoint_created:
                        logger.info(
                            f"Created cancellation checkpoint for operation {operation_id}"
                        )
                    else:
                        logger.warning(
                            f"Failed to create cancellation checkpoint for {operation_id}, continuing with cancellation"
                        )
            except Exception as e:
                # Don't let checkpoint failure block cancellation
                logger.warning(
                    f"Checkpoint creation failed for {operation_id}: {e}, continuing with cancellation"
                )

            # Update operation status with telemetry
            with create_service_span(
                "operation.state_transition", operation_id=operation_id
            ) as span:
                span.set_attribute("operation.from_status", operation.status.value)
                span.set_attribute(
                    "operation.to_status", OperationStatus.CANCELLED.value
                )
                if reason:
                    span.set_attribute("operation.cancellation_reason", reason)

                operation.status = OperationStatus.CANCELLED
                operation.completed_at = datetime.now(timezone.utc)
                operation.error_message = reason or "Operation cancelled by user"

            logger.info(
                f"Cancelled operation: {operation_id} (task_cancelled: {cancelled_task}, remote_cancelled: {remote_cancelled})"
            )

            return {
                "success": True,
                "operation_id": operation_id,
                "status": "cancelled",
                "cancelled_at": operation.completed_at.isoformat(),
                "cancellation_reason": reason,
                "task_cancelled": cancelled_task,
                "remote_cancelled": remote_cancelled,
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
            if operation.status == OperationStatus.RUNNING and self._get_remote_proxy(
                operation_id
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

            return operation

    @trace_service_method("operations.list")
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
                checkpoint_id=None,
                checkpoint_size_bytes=None,
                checkpoint_created_at=None,
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

    def register_remote_proxy(
        self,
        backend_operation_id: str,
        proxy: Any,
        host_operation_id: str,
    ) -> None:
        """
        Register a remote proxy for pull-based progress updates from host service (TASK 3.1).

        This enables backend to act as transparent proxy for operations running on host
        services. Backend stores mapping between its operation ID and the host's operation ID,
        allowing clients to query using backend ID while backend translates to host ID.

        Architecture Pattern:
        - Backend creates operation with its own ID (e.g., "op_training_20250120_abc123")
        - Host service creates operation with its ID (e.g., "host_training_session_xyz789")
        - Backend stores mapping: backend_id → (proxy, host_id)
        - When clients query backend, backend uses proxy to query host with host_id

        Args:
            backend_operation_id: Operation ID in backend (client-facing)
            proxy: OperationServiceProxy instance for querying host service
            host_operation_id: Operation ID on host service
        """
        self._remote_proxies[backend_operation_id] = (proxy, host_operation_id)
        self._metrics_cursors[backend_operation_id] = 0  # Start cursor at 0
        logger.info(
            f"Registered remote proxy for operation {backend_operation_id} → "
            f"host {host_operation_id}"
        )

    def _get_remote_proxy(self, operation_id: str) -> Optional[tuple[Any, str]]:
        """
        Get proxy and host operation ID for a remote operation.

        This helper centralizes the mapping lookup logic to avoid duplication
        across cancel, refresh, and other remote operation methods.

        Args:
            operation_id: Backend operation identifier

        Returns:
            tuple: (proxy, host_operation_id) if found, None otherwise
        """
        if operation_id not in self._remote_proxies:
            return None
        return self._remote_proxies[operation_id]

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

            # Append new metrics to operation (if any) - TYPE-AWARE
            if new_metrics:
                if operation.metrics is None:
                    operation.metrics = {}

                # Type-aware metrics storage
                if operation.operation_type == OperationType.TRAINING:
                    if "epochs" not in operation.metrics:
                        operation.metrics["epochs"] = []
                    operation.metrics["epochs"].extend(new_metrics)

                elif operation.operation_type == OperationType.BACKTESTING:
                    if "bars" not in operation.metrics:
                        operation.metrics["bars"] = []
                    operation.metrics["bars"].extend(new_metrics)

                elif operation.operation_type == OperationType.DATA_LOAD:
                    if "segments" not in operation.metrics:
                        operation.metrics["segments"] = []
                    operation.metrics["segments"].extend(new_metrics)

                else:
                    # Generic fallback for other operation types
                    if "history" not in operation.metrics:
                        operation.metrics["history"] = []
                    operation.metrics["history"].extend(new_metrics)

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
        remote_proxy_info = self._get_remote_proxy(operation_id)
        if not remote_proxy_info:
            return

        proxy, host_operation_id = remote_proxy_info

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
        self, operation_id: str, cursor: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        """
        Get incremental metrics for an operation with cursor support (M2/M3).

        Supports cursor-based retrieval for efficient incremental reads.
        If operation has local bridge, pulls directly from bridge.
        Otherwise returns stored metrics with cursor slicing.

        Args:
            operation_id: Operation identifier
            cursor: Cursor for incremental metrics (0 = from beginning)

        Returns:
            tuple: (new_metrics, new_cursor)
                - new_metrics: List of metric dicts since cursor
                - new_cursor: New cursor position for next incremental read

        Raises:
            KeyError: If operation not found
        """
        # Trigger refresh from bridge/proxy if operation is running
        operation = await self.get_operation(operation_id)

        if not operation:
            raise KeyError(f"Operation not found: {operation_id}")

        # M2/M3: Pull directly from bridge if registered (enables incremental reads)
        if operation_id in self._local_bridges:
            bridge = self._local_bridges[operation_id]
            return bridge.get_metrics(cursor)

        # For operations without bridge (completed, or remote), return stored metrics
        if operation.metrics and "epochs" in operation.metrics:
            all_epochs = operation.metrics["epochs"]
            new_epochs = all_epochs[cursor:]
            new_cursor = len(all_epochs)
            return new_epochs, new_cursor

        # No metrics available
        return [], cursor

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

    # ========================================================================
    # DATABASE PERSISTENCE (TASK 3.1)
    # ========================================================================

    async def persist_operation(self, operation: OperationInfo) -> None:
        """
        Persist operation to PostgreSQL database.

        Uses UPSERT to insert new operations or update existing ones.
        Handles errors gracefully (logs and continues).

        Args:
            operation: Operation to persist
        """
        import json

        from ktrdr.database.connection import get_database_connection

        def _persist_sync():
            """Synchronous database operation (run in thread pool)."""
            try:
                db = get_database_connection()
                with db as conn:
                    with conn.cursor() as cursor:
                        # Serialize metadata and result_summary to JSON
                        # Use mode='json' to ensure datetime objects are serialized properly
                        metadata_json = json.dumps(
                            operation.metadata.model_dump(mode="json")
                        )
                        result_summary_json = (
                            json.dumps(operation.result_summary)
                            if operation.result_summary
                            else None
                        )

                        # UPSERT operation
                        cursor.execute(
                            """
                            INSERT INTO operations (
                                operation_id, operation_type, status,
                                created_at, started_at, completed_at, last_updated,
                                metadata_json, result_summary_json, error_message
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (operation_id) DO UPDATE
                            SET status = EXCLUDED.status,
                                started_at = EXCLUDED.started_at,
                                completed_at = EXCLUDED.completed_at,
                                last_updated = EXCLUDED.last_updated,
                                metadata_json = EXCLUDED.metadata_json,
                                result_summary_json = EXCLUDED.result_summary_json,
                                error_message = EXCLUDED.error_message
                            """,
                            (
                                operation.operation_id,
                                operation.operation_type.value,
                                operation.status.value,
                                operation.created_at,
                                operation.started_at,
                                operation.completed_at,
                                datetime.now(timezone.utc),  # last_updated
                                metadata_json,
                                result_summary_json,
                                operation.error_message,
                            ),
                        )
                        conn.commit()
                        logger.debug(
                            f"Persisted operation to database: {operation.operation_id}"
                        )
            except Exception as e:
                logger.error(
                    f"Failed to persist operation {operation.operation_id}: {e}"
                )
                # Rollback on error
                try:
                    if "conn" in locals():
                        conn.rollback()
                except Exception:
                    pass
                # Don't raise - graceful degradation

        # Run blocking database I/O in thread pool to avoid blocking event loop
        await asyncio.to_thread(_persist_sync)

    async def load_operations(
        self, status: Optional[OperationStatus] = None
    ) -> list[OperationInfo]:
        """
        Load operations from PostgreSQL database.

        Args:
            status: Optional status filter

        Returns:
            List of OperationInfo objects
        """
        import json

        from ktrdr.database.connection import get_database_connection

        try:
            db = get_database_connection()
            with db as conn:
                with conn.cursor() as cursor:
                    if status:
                        cursor.execute(
                            """
                            SELECT operation_id, operation_type, status,
                                   created_at, started_at, completed_at, last_updated,
                                   metadata_json, result_summary_json, error_message
                            FROM operations
                            WHERE status = %s
                            ORDER BY created_at DESC
                            """,
                            (status.value,),
                        )
                    else:
                        cursor.execute(
                            """
                            SELECT operation_id, operation_type, status,
                                   created_at, started_at, completed_at, last_updated,
                                   metadata_json, result_summary_json, error_message
                            FROM operations
                            ORDER BY created_at DESC
                            """
                        )

                    rows = cursor.fetchall()

                    operations = []
                    for row in rows:
                        metadata = json.loads(row[7]) if row[7] else {}  # metadata_json
                        result_summary = (
                            json.loads(row[8]) if row[8] else None
                        )  # result_summary_json

                        operation = OperationInfo(
                            operation_id=row[0],
                            operation_type=OperationType(row[1]),
                            status=OperationStatus(row[2]),
                            created_at=row[3],
                            started_at=row[4],
                            completed_at=row[5],
                            metadata=OperationMetadata(**metadata),
                            result_summary=result_summary,
                            error_message=row[9],
                            metrics=None,
                            checkpoint_id=None,
                            checkpoint_size_bytes=None,
                            checkpoint_created_at=None,
                        )
                        operations.append(operation)

                    logger.debug(f"Loaded {len(operations)} operations from database")
                    return operations

        except Exception as e:
            logger.error(f"Failed to load operations from database: {e}")
            return []

    async def load_operations_with_checkpoints(self) -> list[OperationInfo]:
        """
        Load operations with checkpoint metadata from database.

        Performs LEFT JOIN with operation_checkpoints to include checkpoint info.

        Returns:
            List of OperationInfo objects with checkpoint attributes added
        """
        import json

        from ktrdr.database.connection import get_database_connection

        try:
            db = get_database_connection()
            with db as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT
                            o.operation_id, o.operation_type, o.status,
                            o.created_at, o.started_at, o.completed_at, o.last_updated,
                            o.metadata_json, o.result_summary_json, o.error_message,
                            c.checkpoint_id, c.artifacts_size_bytes, c.created_at
                        FROM operations o
                        LEFT JOIN operation_checkpoints c ON o.operation_id = c.operation_id
                        ORDER BY o.created_at DESC
                        """
                    )

                    rows = cursor.fetchall()

                    operations = []
                    for row in rows:
                        metadata = json.loads(row[7]) if row[7] else {}
                        result_summary = json.loads(row[8]) if row[8] else None

                        operation = OperationInfo(
                            operation_id=row[0],
                            operation_type=OperationType(row[1]),
                            status=OperationStatus(row[2]),
                            created_at=row[3],
                            started_at=row[4],
                            completed_at=row[5],
                            metadata=OperationMetadata(**metadata),
                            result_summary=result_summary,
                            error_message=row[9],
                            metrics=None,
                            checkpoint_id=row[10],
                            checkpoint_size_bytes=row[11],
                            checkpoint_created_at=row[12],
                        )

                        operations.append(operation)

                    logger.debug(
                        f"Loaded {len(operations)} operations with checkpoint metadata"
                    )
                    return operations

        except Exception as e:
            logger.error(
                f"Failed to load operations with checkpoints from database: {e}"
            )
            return []

    async def recover_interrupted_operations(self) -> int:
        """
        Mark all RUNNING operations as FAILED on API startup.

        This handles the primary use case: API crashes/restarts.
        RUNNING operations are orphaned and cannot be resumed until marked FAILED.

        Returns:
            Number of operations recovered
        """
        from ktrdr.database.connection import get_database_connection

        try:
            db = get_database_connection()
            with db as conn:
                with conn.cursor() as cursor:
                    # Find all RUNNING operations
                    cursor.execute(
                        """
                        SELECT operation_id, operation_type, status,
                               created_at, started_at, completed_at, last_updated,
                               metadata_json, result_summary_json, error_message
                        FROM operations
                        WHERE status = %s
                        """,
                        ("running",),
                    )

                    rows = cursor.fetchall()
                    recovered_count = len(rows)

                    if recovered_count == 0:
                        logger.info("Startup recovery: No interrupted operations found")
                        return 0

                    # Mark each as FAILED
                    for row in rows:
                        operation_id = row[0]
                        cursor.execute(
                            """
                            UPDATE operations
                            SET status = %s,
                                error_message = %s,
                                completed_at = NOW(),
                                last_updated = NOW()
                            WHERE operation_id = %s
                            """,
                            (
                                "failed",
                                "Operation interrupted by API restart",
                                operation_id,
                            ),
                        )
                        logger.debug(f"Marked operation as FAILED: {operation_id}")

                    conn.commit()

                    logger.info(
                        f"Startup recovery: {recovered_count} operations marked as FAILED"
                    )
                    return recovered_count

        except Exception as e:
            logger.error(f"Failed to recover interrupted operations: {e}")
            try:
                conn.rollback()
            except Exception:
                pass
            return 0

    async def resume_operation(self, original_operation_id: str) -> dict[str, Any]:
        """
        Resume operation from checkpoint.

        REFACTORED for worker autonomy pattern:
        - Backend NO LONGER loads checkpoints
        - Backend NO LONGER extracts domain-specific params
        - Backend dispatches only operation IDs to services
        - Workers load checkpoints autonomously from database

        Algorithm:
        1. Validate original operation is resumable (FAILED/CANCELLED)
        2. Validate checkpoint exists (but don't load it)
        3. Create NEW operation with new operation_id
        4. Dispatch to appropriate service with operation IDs only
        5. Return new operation info

        Args:
            original_operation_id: ID of the original (failed/cancelled) operation

        Returns:
            dict with:
                - success: bool
                - original_operation_id: str
                - new_operation_id: str
                - message: str

        Raises:
            ValueError: If operation not found, not resumable, or no checkpoint exists
        """
        # Step 1: Validate operation exists and is resumable
        original_operation = await self.get_operation(original_operation_id)
        if original_operation is None:
            raise ValueError(f"Operation not found: {original_operation_id}")

        # Check status is FAILED or CANCELLED
        if original_operation.status not in [
            OperationStatus.FAILED,
            OperationStatus.CANCELLED,
        ]:
            raise ValueError(
                f"Cannot resume {original_operation.status.value} operation. "
                "Only FAILED or CANCELLED operations can be resumed."
            )

        # Step 2: Validate checkpoint exists (but don't load it - worker will handle)
        # Worker will load checkpoint autonomously from database using original_operation_id
        checkpoint_service = get_checkpoint_service()

        # Quick check: does checkpoint exist? (metadata only, no state loading)
        # NOTE: In future, add checkpoint_service.checkpoint_exists(operation_id) method
        # For now, we rely on worker to fail gracefully if checkpoint missing

        # Step 3: Create new operation with resumed_from link
        new_metadata = OperationMetadata(
            symbol=original_operation.metadata.symbol,
            timeframe=original_operation.metadata.timeframe,
            mode=original_operation.metadata.mode,
            start_date=original_operation.metadata.start_date,
            end_date=original_operation.metadata.end_date,
            parameters={
                **original_operation.metadata.parameters,
                "resumed_from": original_operation_id,
            },
        )

        new_operation = await self.create_operation(
            operation_type=original_operation.operation_type,
            metadata=new_metadata,
        )

        new_operation_id = new_operation.operation_id

        # Step 4: Dispatch to appropriate service based on operation type
        # Pass only operation IDs - NO checkpoint data sent over network
        try:
            if original_operation.operation_type == OperationType.TRAINING:
                # Dispatch to TrainingService (worker loads checkpoint autonomously)
                training_service = get_training_service()
                await training_service.resume_training_on_worker(
                    operation_id=new_operation_id,
                    original_operation_id=original_operation_id,
                )

            elif original_operation.operation_type == OperationType.BACKTESTING:
                # Dispatch to BacktestingService (worker loads checkpoint autonomously)
                backtesting_service = get_backtesting_service()
                await backtesting_service.resume_backtest_on_worker(
                    operation_id=new_operation_id,
                    original_operation_id=original_operation_id,
                )

            else:
                raise ValueError(
                    f"Resume not supported for operation type: {original_operation.operation_type.value}"
                )

        except Exception as e:
            # If resume dispatch fails, mark new operation as failed
            await self.fail_operation(
                new_operation_id, error_message=f"Resume failed: {str(e)}"
            )
            raise

        # Step 5: Return response (generic message - no domain-specific checkpoint info)
        return {
            "success": True,
            "original_operation_id": original_operation_id,
            "new_operation_id": new_operation_id,
            "message": "Operation resumed",
        }

    async def create_checkpoint(
        self,
        operation_id: str,
        checkpoint_type: "CheckpointType",
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        """
        Create a checkpoint for an operation.

        Centralized method for checkpoint creation, called from:
        - Progress tracking (TIMER checkpoints)
        - Forced checkpoints (FORCE checkpoints)
        - Operation cancellation (CANCELLATION checkpoints)
        - Worker shutdown (SHUTDOWN checkpoints)
        - Operation failure (FAILURE checkpoints)

        Args:
            operation_id: Operation identifier
            checkpoint_type: Type of checkpoint (from CheckpointType enum)
            metadata: Optional metadata to include in checkpoint

        Returns:
            True if checkpoint was created successfully, False otherwise

        Implementation note:
            This method coordinates with CheckpointService to persist checkpoints
            and retrieves current operation state from workers/progress bridges.
        """
        try:
            # Get current operation state
            current_state = await self._get_operation_state(operation_id)

            if current_state is None:
                logger.warning(
                    f"Cannot create checkpoint for {operation_id}: no state available"
                )
                return False

            # Ensure operation is persisted to database before creating checkpoint
            # This handles the case where persist_operation failed silently during
            # operation creation (graceful degradation) but we need database persistence
            # for checkpoint foreign key constraint
            # NOTE: We DON'T acquire the lock here because create_checkpoint may be called
            # from cancel_operation which already holds the lock. Accessing _operations
            # dict without lock is safe for reading if we just need to check existence.
            if operation_id in self._operations:
                operation = self._operations[operation_id]
                await self.persist_operation(operation)
                logger.debug(
                    f"Ensured operation {operation_id} is persisted to database before checkpoint"
                )

            # Get checkpoint service
            checkpoint_service = self._get_checkpoint_service()

            # Prepare metadata
            checkpoint_metadata = metadata or {}
            checkpoint_metadata["checkpoint_type"] = checkpoint_type.value
            checkpoint_metadata["created_at"] = datetime.now(timezone.utc).isoformat()

            # Save checkpoint (prepare data dict for CheckpointService)
            checkpoint_data = {
                "checkpoint_id": f"{operation_id}_{checkpoint_type.value}_{int(time.time())}",
                "checkpoint_type": checkpoint_type.value,
                "metadata": checkpoint_metadata,
                "state": current_state,
            }
            await asyncio.to_thread(
                checkpoint_service.save_checkpoint,
                operation_id,
                checkpoint_data,
            )

            logger.info(
                f"Created {checkpoint_type.value} checkpoint for operation {operation_id}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to create checkpoint for {operation_id}: {e}",
                exc_info=True,
            )
            return False

    def _get_checkpoint_service(self) -> "CheckpointService":
        """
        Get or create CheckpointService instance.

        Returns:
            CheckpointService singleton instance for this OperationsService

        Implementation note:
            Lazily initializes CheckpointService on first use.
            Uses lazy import to avoid circular dependencies.
        """
        if not hasattr(self, "_checkpoint_service"):
            from ktrdr.checkpoint.service import CheckpointService

            self._checkpoint_service = CheckpointService()

        return self._checkpoint_service

    async def _get_operation_state(self, operation_id: str) -> Optional[dict[str, Any]]:
        """
        Retrieve current state for an operation.

        Queries progress bridges and remote proxies to get the most recent
        operation state suitable for checkpoint creation.

        Args:
            operation_id: Operation identifier

        Returns:
            Dictionary containing operation state, or None if unavailable

        Implementation note:
            - For local operations: queries progress bridge
            - For remote operations: queries remote proxy
            - Returns state dict with epoch/bar_index, loss, model state, etc.
        """
        # Try to get state from local bridge first
        if operation_id in self._local_bridges:
            bridge = self._local_bridges[operation_id]
            if hasattr(bridge, "get_state"):
                state = await bridge.get_state()
                if state:
                    return state

        # Try to get state from remote proxy
        remote_proxy_info = self._get_remote_proxy(operation_id)
        if remote_proxy_info:
            proxy, remote_operation_id = remote_proxy_info
            try:
                if hasattr(proxy, "get_operation_state"):
                    state = await proxy.get_operation_state(remote_operation_id)
                    if state:
                        return state
            except Exception as e:
                logger.debug(
                    f"Could not get state from remote proxy for {operation_id}: {e}"
                )

        # Fallback: construct state from operation info
        if operation_id in self._operations:
            operation = self._operations[operation_id]
            return {
                "operation_id": operation_id,
                "operation_type": operation.operation_type.value,
                "status": operation.status.value,
                "progress": {
                    "percentage": operation.progress.percentage,
                    "current_step": operation.progress.current_step,
                    "steps_completed": operation.progress.steps_completed,
                    "steps_total": operation.progress.steps_total,
                },
                "started_at": (
                    operation.started_at.isoformat() if operation.started_at else None
                ),
            }

        return None


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


def get_checkpoint_service():
    """
    Get the CheckpointService instance.

    Returns:
        CheckpointService instance
    """
    from ktrdr.checkpoint import CheckpointService

    return CheckpointService()


def get_training_service():
    """
    Get the TrainingService instance.

    Returns:
        TrainingService instance
    """
    from ktrdr.api.services.training.training_service import (  # type: ignore[import-untyped]
        TrainingService,
    )

    return TrainingService()


def get_backtesting_service():
    """
    Get the BacktestingService instance.

    Returns:
        BacktestingService instance
    """
    from ktrdr.api.endpoints.workers import get_worker_registry
    from ktrdr.backtesting.backtesting_service import BacktestingService

    worker_registry = get_worker_registry()
    return BacktestingService(worker_registry=worker_registry)
