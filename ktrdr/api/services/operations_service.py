"""
Operations service for managing long-running operations.

This service provides a central registry for tracking and managing
async operations across the KTRDR system.
"""

import asyncio
import math
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from opentelemetry import trace

from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationProgress,
    OperationStatus,
    OperationType,
)
from ktrdr.api.repositories.operations_repository import OperationsRepository
from ktrdr.async_infrastructure.cancellation import (
    AsyncCancellationToken,
    get_global_coordinator,
)
from ktrdr.errors import DataError
from ktrdr.logging import get_logger
from ktrdr.monitoring.metrics import (
    increment_operations_total,
    operations_active,
    record_operation_duration,
)
from ktrdr.monitoring.service_telemetry import create_service_span, trace_service_method

logger = get_logger(__name__)

# Phase weight constants for parent operation progress aggregation (Task 1.15)
# These determine how child operation progress maps to parent progress
# Design: 0-5%, Training: 5-80%, Backtest: 80-100%
PHASE_WEIGHT_DESIGN_START = 0.0
PHASE_WEIGHT_DESIGN_END = 5.0
PHASE_WEIGHT_TRAINING_START = 5.0
PHASE_WEIGHT_TRAINING_END = 80.0
PHASE_WEIGHT_BACKTEST_START = 80.0
PHASE_WEIGHT_BACKTEST_END = 100.0


def _sanitize_for_json(obj: Any) -> Any:
    """Recursively sanitize a dict/list for JSON serialization.

    Replaces NaN and Inf float values with None, which is valid JSON.
    PostgreSQL JSONB columns reject NaN/Inf as invalid JSON tokens.

    Args:
        obj: Object to sanitize (dict, list, or scalar)

    Returns:
        Sanitized object safe for JSON serialization
    """
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_json(item) for item in obj]
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    return obj


class OperationsService:
    """
    Service for managing long-running operations.

    Provides a central registry for tracking operations, their status,
    progress, and cancellation capabilities.
    """

    def __init__(self, repository: Optional[OperationsRepository] = None):
        """Initialize the operations service.

        Args:
            repository: Optional repository for database persistence.
                       If provided, operations are persisted to DB.
                       If None, operations are stored in-memory only (backward compatible).
        """
        # Repository for database persistence (optional, for backward compatibility)
        self._repository: Optional[OperationsRepository] = repository

        # In-memory cache (read-through when repository is available)
        self._cache: dict[str, OperationInfo] = {}

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
        parent_operation_id: Optional[str] = None,
        is_backend_local: bool = False,
    ) -> OperationInfo:
        """
        Create a new operation in the registry.

        Args:
            operation_type: Type of operation
            metadata: Operation metadata
            operation_id: Optional custom operation ID
            parent_operation_id: Optional parent operation ID for child operations
            is_backend_local: True if operation runs in backend process (e.g., agent
                sessions), False if runs via distributed worker (default)

        Returns:
            Created operation info
        """
        async with self._lock:
            if operation_id is None:
                operation_id = self.generate_operation_id(operation_type)

            # Ensure operation ID is unique (check cache and DB)
            if operation_id in self._cache:
                raise DataError(
                    message=f"Operation ID already exists: {operation_id}",
                    error_code="OPERATIONS-DuplicateID",
                    details={"operation_id": operation_id},
                )

            # Also check repository if available
            if self._repository:
                existing = await self._repository.get(operation_id)
                if existing:
                    raise DataError(
                        message=f"Operation ID already exists: {operation_id}",
                        error_code="OPERATIONS-DuplicateID",
                        details={"operation_id": operation_id},
                    )

            # Validate parent operation exists if specified (check cache and DB)
            if parent_operation_id:
                parent_found = parent_operation_id in self._cache
                if not parent_found and self._repository:
                    parent_found = (
                        await self._repository.get(parent_operation_id) is not None
                    )
                if not parent_found:
                    raise DataError(
                        message=f"Parent operation not found: {parent_operation_id}",
                        error_code="OPERATIONS-ParentNotFound",
                        details={"parent_operation_id": parent_operation_id},
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
                span.set_attribute("operation.is_backend_local", is_backend_local)
                if parent_operation_id:
                    span.set_attribute("operation.parent_id", parent_operation_id)

                # Create operation
                operation = OperationInfo(
                    operation_id=operation_id,
                    parent_operation_id=parent_operation_id,
                    operation_type=operation_type,
                    status=OperationStatus.PENDING,
                    created_at=datetime.now(timezone.utc),
                    metadata=metadata,
                    started_at=None,
                    completed_at=None,
                    error_message=None,
                    result_summary=None,
                    metrics=None,  # NEW: M1 - initialize as None
                    is_backend_local=is_backend_local,
                )

                # Persist to repository first (if available)
                if self._repository:
                    await self._repository.create(operation)

                # Then add to cache
                self._cache[operation_id] = operation

                # Update Prometheus metrics
                operations_active.inc()

                logger.info(
                    f"Created operation: {operation_id} (type: {operation_type})"
                    + (
                        f", parent: {parent_operation_id}"
                        if parent_operation_id
                        else ""
                    )
                )
                return operation

    async def adopt_operation(self, operation_id: str) -> OperationInfo:
        """
        Adopt an existing operation for execution (used during resume).

        When a worker resumes an operation it didn't originally create,
        the operation exists in the database but not in the worker's local cache.
        This method loads the operation from the database into the cache so that
        subsequent calls to start_operation() and other methods work correctly.

        This is the correct pattern for resume-to-different-worker scenarios:
        1. Backend dispatches resume to any available worker
        2. Worker calls adopt_operation() to load from DB into cache
        3. Worker calls start_operation() to transition to RUNNING

        Args:
            operation_id: Operation identifier to adopt

        Returns:
            The adopted operation info

        Raises:
            DataError: If operation not found in database or no repository configured
        """
        async with self._lock:
            # If already in cache, just return it
            if operation_id in self._cache:
                logger.debug(
                    f"Operation {operation_id} already in cache, no adoption needed"
                )
                return self._cache[operation_id]

            # Must have a repository to adopt from database
            if not self._repository:
                raise DataError(
                    message=f"Cannot adopt operation without database repository: {operation_id}",
                    error_code="OPERATIONS-NoRepository",
                    details={"operation_id": operation_id},
                )

            # Load from database
            operation = await self._repository.get(operation_id)
            if not operation:
                raise DataError(
                    message=f"Operation not found in database: {operation_id}",
                    error_code="OPERATIONS-NotFound",
                    details={"operation_id": operation_id},
                )

            # Add to local cache
            self._cache[operation_id] = operation
            logger.info(f"Adopted operation {operation_id} from database for resume")

            return operation

    async def start_operation(
        self, operation_id: str, task: Optional[asyncio.Task] = None
    ) -> None:
        """
        Mark an operation as started and optionally register its task.

        Args:
            operation_id: Operation identifier
            task: Asyncio task for the operation (optional for distributed ops
                  where cancellation goes via remote proxy)

        Note:
            For resume scenarios, call adopt_operation() first to ensure
            the operation is in the local cache.
        """
        async with self._lock:
            if operation_id not in self._cache:
                raise DataError(
                    message=f"Operation not found: {operation_id}",
                    error_code="OPERATIONS-NotFound",
                    details={"operation_id": operation_id},
                )

            # Update operation status with telemetry
            operation = self._cache[operation_id]
            with create_service_span(
                "operation.state_transition", operation_id=operation_id
            ) as span:
                span.set_attribute("operation.from_status", operation.status.value)
                span.set_attribute("operation.to_status", OperationStatus.RUNNING.value)

                operation.status = OperationStatus.RUNNING
                operation.started_at = datetime.now(timezone.utc)

            # Persist to repository (if available)
            if self._repository:
                await self._repository.update(
                    operation_id,
                    status=OperationStatus.RUNNING.value,
                    started_at=operation.started_at,
                )

            # Register task for cancellation (only if provided - distributed ops use proxy)
            if task is not None:
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
        if operation_id not in self._cache:
            logger.warning(
                f"Cannot update progress - operation not found: {operation_id}"
            )
            return

        operation = self._cache[operation_id]
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

        # Task 3.10: Do NOT persist progress updates to repository
        # Design principle: Workers must be fast. DB is only for:
        # - Create operation (once)
        # - Checkpoint (periodic, policy-driven)
        # - Complete/Fail (once)
        # Progress updates stay in-memory; clients pull via proxy for live progress.

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
            if operation_id not in self._cache:
                logger.warning(f"Cannot complete - operation not found: {operation_id}")
                return

            operation = self._cache[operation_id]

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

            # Persist to repository (if available)
            if self._repository:
                # Sanitize result to handle NaN/Inf values that PostgreSQL JSONB rejects
                sanitized_result = _sanitize_for_json(result_summary)
                await self._repository.update(
                    operation_id,
                    status=OperationStatus.COMPLETED.value,
                    completed_at=operation.completed_at,
                    result=sanitized_result,
                    progress_percent=100.0,
                )

            # Clean up task reference
            if operation_id in self._operation_tasks:
                del self._operation_tasks[operation_id]

            # Update Prometheus metrics
            operations_active.dec()
            increment_operations_total(operation.operation_type.value, "completed")
            if operation.started_at and operation.completed_at:
                duration = (
                    operation.completed_at - operation.started_at
                ).total_seconds()
                record_operation_duration(
                    operation.operation_type.value, "completed", duration
                )

            # Clean up cache after completion when repository is configured.
            # Workers always have a repository, so this keeps them stateless.
            # For cache-only deployments (tests), keep in cache so get_operation() still works.
            if self._repository:
                self._remove_from_cache_unlocked(operation_id)

            logger.info(f"Completed operation: {operation_id}")

    async def fail_operation(
        self,
        operation_id: str,
        error_message: str,
        fail_parent: bool = False,
    ) -> None:
        """
        Mark an operation as failed.

        Args:
            operation_id: Operation identifier
            error_message: Error description
            fail_parent: If True and operation has a parent, also fail the parent (Task 1.15)
        """
        async with self._lock:
            if operation_id not in self._cache:
                logger.warning(f"Cannot fail - operation not found: {operation_id}")
                return

            operation = self._cache[operation_id]

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

            # Persist to repository (if available)
            if self._repository:
                await self._repository.update(
                    operation_id,
                    status=OperationStatus.FAILED.value,
                    completed_at=operation.completed_at,
                    error_message=error_message,
                )

            # Clean up task reference
            if operation_id in self._operation_tasks:
                del self._operation_tasks[operation_id]

            # Update Prometheus metrics
            operations_active.dec()
            increment_operations_total(operation.operation_type.value, "failed")
            if operation.started_at and operation.completed_at:
                duration = (
                    operation.completed_at - operation.started_at
                ).total_seconds()
                record_operation_duration(
                    operation.operation_type.value, "failed", duration
                )

            # Clean up cache after failure when repository is configured.
            # Workers always have a repository, so this keeps them stateless.
            # For cache-only deployments (tests), keep in cache so get_operation() still works.
            if self._repository:
                self._remove_from_cache_unlocked(operation_id)

            logger.error(f"Failed operation: {operation_id} - {error_message}")

            # Task 1.15: Cascade failure to parent if requested
            if fail_parent and operation.parent_operation_id:
                parent = self._cache.get(operation.parent_operation_id)
                if parent and parent.status in [
                    OperationStatus.PENDING,
                    OperationStatus.RUNNING,
                ]:
                    parent.status = OperationStatus.FAILED
                    parent.completed_at = datetime.now(timezone.utc)
                    parent.error_message = f"Child operation failed: {error_message}"

                    # Persist parent failure to repository
                    if self._repository:
                        await self._repository.update(
                            parent.operation_id,
                            status=OperationStatus.FAILED.value,
                            completed_at=parent.completed_at,
                            error_message=parent.error_message,
                        )

                    # Clean up parent task if exists
                    if parent.operation_id in self._operation_tasks:
                        parent_task = self._operation_tasks[parent.operation_id]
                        if not parent_task.done():
                            parent_task.cancel()
                        del self._operation_tasks[parent.operation_id]

                    # Update metrics for parent
                    operations_active.dec()
                    increment_operations_total(parent.operation_type.value, "failed")

                    logger.error(
                        f"Cascade-failed parent operation: {parent.operation_id} "
                        f"(child: {operation_id})"
                    )

    async def cancel_operation(
        self,
        operation_id: str,
        reason: Optional[str] = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """
        Cancel a running operation.

        For parent operations (Task 1.15): Also cancels all running children.

        Args:
            operation_id: Operation identifier
            reason: Optional cancellation reason
            force: Force cancellation even if operation is in critical section

        Returns:
            Cancellation result dictionary
        """
        async with self._lock:
            if operation_id not in self._cache:
                return {
                    "success": False,
                    "error": f"Operation not found: {operation_id}",
                }

            operation = self._cache[operation_id]

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

            # Task 1.15: Cancel children first (cascade cancellation)
            children_cancelled = []
            children = [
                op
                for op in self._cache.values()
                if op.parent_operation_id == operation_id
            ]
            for child in children:
                if child.status in [OperationStatus.PENDING, OperationStatus.RUNNING]:
                    # Cancel child's task if exists
                    if child.operation_id in self._operation_tasks:
                        child_task = self._operation_tasks[child.operation_id]
                        if not child_task.done():
                            child_task.cancel()
                        del self._operation_tasks[child.operation_id]

                    # Update child status
                    child.status = OperationStatus.CANCELLED
                    child.completed_at = datetime.now(timezone.utc)
                    child.error_message = (
                        f"Parent operation cancelled: {reason or 'User cancelled'}"
                    )

                    # Persist child cancellation to repository
                    if self._repository:
                        await self._repository.update(
                            child.operation_id,
                            status=OperationStatus.CANCELLED.value,
                            completed_at=child.completed_at,
                            error_message=child.error_message,
                        )

                    # Cancel via cancellation coordinator
                    self._cancellation_coordinator.cancel_operation(
                        child.operation_id, f"Parent cancelled: {reason}"
                    )

                    # Update metrics for child
                    operations_active.dec()
                    increment_operations_total(child.operation_type.value, "cancelled")

                    children_cancelled.append(child.operation_id)
                    logger.info(
                        f"Cascade-cancelled child operation: {child.operation_id}"
                    )

            # Use unified cancellation coordinator for parent
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
                if children_cancelled:
                    span.set_attribute(
                        "operation.children_cancelled", len(children_cancelled)
                    )

                operation.status = OperationStatus.CANCELLED
                operation.completed_at = datetime.now(timezone.utc)
                operation.error_message = reason or "Operation cancelled by user"

            # Persist to repository (if available)
            if self._repository:
                await self._repository.update(
                    operation_id,
                    status=OperationStatus.CANCELLED.value,
                    completed_at=operation.completed_at,
                    error_message=operation.error_message,
                )

            # Update Prometheus metrics
            operations_active.dec()
            increment_operations_total(operation.operation_type.value, "cancelled")
            if operation.started_at and operation.completed_at:
                duration = (
                    operation.completed_at - operation.started_at
                ).total_seconds()
                record_operation_duration(
                    operation.operation_type.value, "cancelled", duration
                )

            # Clean up cache after cancellation when repository is configured.
            # Workers always have a repository, so this keeps them stateless.
            # For cache-only deployments (tests), keep in cache so get_operation() still works.
            if self._repository:
                self._remove_from_cache_unlocked(operation_id)

            logger.info(
                f"Cancelled operation: {operation_id} (task_cancelled: {cancelled_task}, "
                f"remote_cancelled: {remote_cancelled}, children_cancelled: {len(children_cancelled)})"
            )

            return {
                "success": True,
                "operation_id": operation_id,
                "status": "cancelled",
                "cancelled_at": operation.completed_at.isoformat(),
                "cancellation_reason": reason,
                "task_cancelled": cancelled_task,
                "remote_cancelled": remote_cancelled,
                "children_cancelled": children_cancelled,
            }

    async def try_resume(self, operation_id: str) -> bool:
        """
        Atomically update status to RUNNING if currently resumable.

        Uses optimistic locking at the database level: the repository performs
        an atomic UPDATE with a status check in the WHERE clause, ensuring that
        concurrent resume requests result in exactly one success.

        Args:
            operation_id: Operation identifier

        Returns:
            True if status was updated (operation is now RUNNING),
            False if operation not found or not in resumable state.
        """
        # First try atomic DB update via repository
        if self._repository:
            success = await self._repository.try_resume(operation_id)

            if not success:
                logger.warning(
                    f"Cannot resume - operation not found or not in resumable state: "
                    f"{operation_id}"
                )
                return False

            # Atomic update succeeded - now update cache
            old_status: OperationStatus = OperationStatus.FAILED  # Default

            async with self._lock:
                cached_op = self._cache.get(operation_id)
                if cached_op is not None:
                    old_status = cached_op.status
                    cached_op.status = OperationStatus.RESUMING
                    cached_op.started_at = datetime.now(timezone.utc)
                    cached_op.completed_at = None
                    cached_op.error_message = None
                else:
                    # Load from DB to populate cache
                    db_op = await self._repository.get(operation_id)
                    if db_op is not None:
                        self._cache[operation_id] = db_op
                        # DB state is already RESUMING after try_resume
                        old_status = OperationStatus.CANCELLED  # Assume from context

            # Tracing for state transition
            with create_service_span(
                "operation.state_transition", operation_id=operation_id
            ) as span:
                span.set_attribute("operation.from_status", old_status.value)
                span.set_attribute(
                    "operation.to_status", OperationStatus.RESUMING.value
                )
                span.set_attribute("operation.resumed", True)

            # Update Prometheus metrics
            operations_active.inc()

            logger.info(
                f"Resumed operation: {operation_id} (from {old_status.value} to resuming)"
            )

            return True

        # Fallback for cache-only mode (no repository)
        async with self._lock:
            operation = self._cache.get(operation_id)

            if operation is None:
                logger.warning(f"Cannot resume - operation not found: {operation_id}")
                return False

            if operation.status not in [
                OperationStatus.CANCELLED,
                OperationStatus.FAILED,
            ]:
                logger.warning(
                    f"Cannot resume - operation not in resumable state: {operation_id} "
                    f"(status: {operation.status})"
                )
                return False

            old_status = operation.status
            operation.status = OperationStatus.RESUMING
            operation.started_at = datetime.now(timezone.utc)
            operation.completed_at = None
            operation.error_message = None

            # Tracing
            with create_service_span(
                "operation.state_transition", operation_id=operation_id
            ) as span:
                span.set_attribute("operation.from_status", old_status.value)
                span.set_attribute(
                    "operation.to_status", OperationStatus.RESUMING.value
                )
                span.set_attribute("operation.resumed", True)

            operations_active.inc()

            logger.info(
                f"Resumed operation: {operation_id} (from {old_status.value} to resuming)"
            )

            return True

    async def update_status(self, operation_id: str, status: str) -> None:
        """
        Update operation status directly.

        Used for cases where we need to set a specific status (e.g., marking
        as FAILED when checkpoint is not available during resume).

        Args:
            operation_id: Operation identifier
            status: New status string (will be converted to OperationStatus)
        """
        async with self._lock:
            operation = self._cache.get(operation_id)

            if operation is None:
                logger.warning(
                    f"Cannot update status - operation not found: {operation_id}"
                )
                return

            new_status = OperationStatus(status.lower())
            old_status = operation.status

            # Update in-memory cache
            operation.status = new_status
            if new_status in [
                OperationStatus.COMPLETED,
                OperationStatus.FAILED,
                OperationStatus.CANCELLED,
            ]:
                operation.completed_at = datetime.now(timezone.utc)

            # Persist to repository
            if self._repository:
                await self._repository.update(
                    operation_id,
                    status=new_status.value,
                    completed_at=operation.completed_at,
                )

            logger.info(
                f"Updated operation status: {operation_id} "
                f"({old_status.value} -> {new_status.value})"
            )

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
            # Check cache first
            operation = self._cache.get(operation_id)

            # Cache miss - try repository (read-through cache)
            if not operation and self._repository:
                operation = await self._repository.get(operation_id)
                if operation:
                    # Populate cache for future reads
                    self._cache[operation_id] = operation

            if not operation:
                # Check if there's a remote proxy for this operation (distributed worker case)
                # The worker creates/owns the operation - backend just proxies
                remote_proxy_info = self._get_remote_proxy(operation_id)
                if remote_proxy_info:
                    # Query proxy to get operation from worker
                    operation = await self._fetch_operation_from_proxy(
                        operation_id, remote_proxy_info
                    )
                    if operation:
                        # Cache for future reads
                        self._cache[operation_id] = operation

                if not operation:
                    return None

            # TASK 1.3/1.4: Pull from local bridge if registered and operation is active
            # (RUNNING or RESUMING - need to sync status transitions)
            if (
                operation.status in (OperationStatus.RUNNING, OperationStatus.RESUMING)
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

            # TASK 2.5: Pull from remote proxy if registered and:
            # - Operation is pending/running/resuming (to get progress updates), OR
            # - Operation completed but result_summary is missing (to sync final result)
            # NOTE: PENDING operations with remote proxy need refresh because the backend
            # creates a local PENDING entry, but the worker owns the real operation state.
            # RESUMING operations need proxy refresh to sync status transitions
            # (RESUMING → RUNNING → COMPLETED) from the worker.
            needs_result_sync = (
                operation.status == OperationStatus.COMPLETED
                and operation.result_summary is None
            )
            is_active = operation.status in (
                OperationStatus.PENDING,
                OperationStatus.RUNNING,
                OperationStatus.RESUMING,
            )
            if self._get_remote_proxy(operation_id) and (
                is_active or needs_result_sync
            ):
                # Force refresh bypasses cache
                if force_refresh or needs_result_sync:
                    # Invalidate cache to force refresh (always refresh for result sync)
                    self._last_refresh[operation_id] = 0
                    if needs_result_sync:
                        logger.info(
                            f"Syncing result_summary for completed remote operation {operation_id}"
                        )
                    else:
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
            all_operations = list(self._cache.values())

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
            original_operation = self._cache.get(operation_id)

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
                parent_operation_id=original_operation.parent_operation_id,  # Preserve parent link
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
            self._cache[new_operation_id] = new_operation

            logger.info(
                f"Created retry operation: {new_operation_id} (original: {operation_id})"
            )
            return new_operation

    async def get_children(self, parent_operation_id: str) -> list[OperationInfo]:
        """
        Get all child operations for a parent operation (Task 1.15).

        Returns children in creation order (oldest first).

        Args:
            parent_operation_id: Parent operation identifier

        Returns:
            List of child operations in creation order
        """
        async with self._lock:
            children = [
                op
                for op in self._cache.values()
                if op.parent_operation_id == parent_operation_id
            ]
            # Sort by creation time (oldest first)
            children.sort(key=lambda op: op.created_at)
            return children

    async def get_aggregated_progress(
        self, parent_operation_id: str
    ) -> OperationProgress:
        """
        Get aggregated progress for a parent operation based on children (Task 1.15).

        Progress is weighted by phase:
        - Design (AGENT_DESIGN): 0-5%
        - Training (TRAINING): 5-80%
        - Backtest (BACKTESTING): 80-100%

        Args:
            parent_operation_id: Parent operation identifier

        Returns:
            Aggregated progress information
        """
        children = await self.get_children(parent_operation_id)

        if not children:
            return OperationProgress(
                percentage=0.0,
                current_step="No phases started",
                steps_completed=0,
                steps_total=3,  # design, train, backtest
                items_processed=0,
                items_total=None,
                current_item=None,
            )

        # Find the currently active child (or most recent)
        active_child = None
        for child in reversed(children):  # Check from newest first
            if child.status == OperationStatus.RUNNING:
                active_child = child
                break
            elif child.status == OperationStatus.PENDING:
                active_child = child
                break

        # If no running/pending, use most recent child
        if not active_child:
            active_child = children[-1]

        # Determine phase name and weight range based on operation type
        if active_child.operation_type == OperationType.AGENT_DESIGN:
            phase_name = "Design"
            start_weight = PHASE_WEIGHT_DESIGN_START
            end_weight = PHASE_WEIGHT_DESIGN_END
        elif active_child.operation_type == OperationType.TRAINING:
            phase_name = "Training"
            start_weight = PHASE_WEIGHT_TRAINING_START
            end_weight = PHASE_WEIGHT_TRAINING_END
        elif active_child.operation_type == OperationType.BACKTESTING:
            phase_name = "Backtest"
            start_weight = PHASE_WEIGHT_BACKTEST_START
            end_weight = PHASE_WEIGHT_BACKTEST_END
        else:
            # Unknown phase - use simple average
            phase_name = active_child.operation_type.value
            start_weight = 0.0
            end_weight = 100.0

        # Calculate weighted progress
        child_progress_pct = active_child.progress.percentage / 100.0
        weight_range = end_weight - start_weight
        aggregated_percentage = start_weight + (weight_range * child_progress_pct)

        # If child is completed, use the end weight
        if active_child.status == OperationStatus.COMPLETED:
            aggregated_percentage = end_weight

        # Count completed phases
        completed_phases = sum(
            1 for c in children if c.status == OperationStatus.COMPLETED
        )

        return OperationProgress(
            percentage=min(aggregated_percentage, 100.0),
            current_step=f"{phase_name} ({active_child.progress.percentage:.0f}%)",
            steps_completed=completed_phases,
            steps_total=3,  # design, train, backtest
            items_processed=0,
            items_total=None,
            current_item=None,
            context={
                "current_phase": phase_name,
                "phase_progress": active_child.progress.percentage,
                "child_operation_id": active_child.operation_id,
            },
        )

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
            for operation_id, operation in self._cache.items():
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
                del self._cache[operation_id]
                # Clean up any remaining task references
                if operation_id in self._operation_tasks:
                    del self._operation_tasks[operation_id]

            if operations_to_remove:
                logger.info(f"Cleaned up {len(operations_to_remove)} old operations")

            return len(operations_to_remove)

    def _remove_from_cache_unlocked(self, operation_id: str) -> bool:
        """
        Remove an operation from the cache (internal, caller must hold lock).

        This method is called after operations finish (complete/fail/cancel) to ensure
        workers remain stateless and don't accumulate finished operations in memory.

        IMPORTANT: This method does NOT acquire the lock. Callers must already hold
        self._lock before calling this method to avoid race conditions.

        Args:
            operation_id: Operation identifier to remove

        Returns:
            True if operation was removed, False if it wasn't found
        """
        if operation_id not in self._cache:
            logger.debug(f"Operation {operation_id} not in cache, nothing to remove")
            return False

        # Remove from cache
        del self._cache[operation_id]

        # Clean up any remaining references
        if operation_id in self._operation_tasks:
            del self._operation_tasks[operation_id]

        if operation_id in self._local_bridges:
            del self._local_bridges[operation_id]

        if operation_id in self._metrics_cursors:
            del self._metrics_cursors[operation_id]

        if operation_id in self._remote_proxies:
            del self._remote_proxies[operation_id]

        if operation_id in self._last_refresh:
            del self._last_refresh[operation_id]

        logger.debug(
            f"Removed operation {operation_id} from cache and cleaned up references"
        )
        return True

    async def remove_from_cache(self, operation_id: str) -> bool:
        """
        Remove an operation from the cache (public, acquires lock).

        This is the public API for external callers who need to remove an operation
        from cache. For internal use within methods that already hold the lock,
        use _remove_from_cache_unlocked() instead.

        Args:
            operation_id: Operation identifier to remove

        Returns:
            True if operation was removed, False if it wasn't found
        """
        async with self._lock:
            return self._remove_from_cache_unlocked(operation_id)

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
        operation = self._cache.get(operation_id)
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

    async def _fetch_operation_from_proxy(
        self, operation_id: str, remote_proxy_info: tuple[Any, str]
    ) -> Optional[OperationInfo]:
        """
        Fetch operation from remote worker via proxy (for distributed worker case).

        This is called when the backend doesn't have the operation locally but has
        a proxy registered. The worker creates and owns the operation - backend
        just proxies queries to it.

        Args:
            operation_id: Backend operation identifier
            remote_proxy_info: Tuple of (proxy, host_operation_id)

        Returns:
            OperationInfo constructed from proxy response, or None on error
        """
        proxy, host_operation_id = remote_proxy_info

        try:
            # Query host service for operation
            host_data = await proxy.get_operation(host_operation_id)

            if not host_data:
                logger.warning(
                    f"Proxy returned no data for operation {host_operation_id}"
                )
                return None

            # Parse timestamps
            created_at = None
            started_at = None
            completed_at = None

            if "created_at" in host_data and host_data["created_at"]:
                if isinstance(host_data["created_at"], str):
                    created_at = datetime.fromisoformat(
                        host_data["created_at"].replace("Z", "+00:00")
                    )
                else:
                    created_at = host_data["created_at"]

            if "started_at" in host_data and host_data["started_at"]:
                if isinstance(host_data["started_at"], str):
                    started_at = datetime.fromisoformat(
                        host_data["started_at"].replace("Z", "+00:00")
                    )
                else:
                    started_at = host_data["started_at"]

            if "completed_at" in host_data and host_data["completed_at"]:
                if isinstance(host_data["completed_at"], str):
                    completed_at = datetime.fromisoformat(
                        host_data["completed_at"].replace("Z", "+00:00")
                    )
                else:
                    completed_at = host_data["completed_at"]

            # Parse progress
            progress = OperationProgress()
            if "progress" in host_data and host_data["progress"]:
                host_progress = host_data["progress"]
                progress = OperationProgress(
                    percentage=host_progress.get("percentage", 0.0),
                    current_step=host_progress.get("current_step", ""),
                    steps_completed=host_progress.get("steps_completed", 0),
                    steps_total=host_progress.get("steps_total", 0),
                    items_processed=host_progress.get("items_processed", 0),
                    items_total=host_progress.get("items_total"),
                    current_item=host_progress.get("current_item"),
                )

            # Parse metadata
            metadata = OperationMetadata()
            if "metadata" in host_data and host_data["metadata"]:
                host_meta = host_data["metadata"]
                metadata = OperationMetadata(
                    symbol=host_meta.get("symbol"),
                    timeframe=host_meta.get("timeframe"),
                    mode=host_meta.get("mode"),
                    parameters=host_meta.get("parameters", {}),
                )

            # Construct OperationInfo
            operation = OperationInfo(
                operation_id=operation_id,  # Use backend's ID
                parent_operation_id=host_data.get("parent_operation_id"),
                operation_type=OperationType(
                    host_data.get("operation_type", "training")
                ),
                status=OperationStatus(host_data.get("status", "pending")),
                created_at=created_at or datetime.now(timezone.utc),
                started_at=started_at,
                completed_at=completed_at,
                metadata=metadata,
                progress=progress,
                error_message=host_data.get("error_message"),
                result_summary=host_data.get("result_summary"),
                metrics=host_data.get("metrics"),
                is_backend_local=False,  # This is a distributed operation
            )

            # Update cache timestamp
            self._last_refresh[operation_id] = time.time()

            logger.info(
                f"Fetched operation {operation_id} from proxy "
                f"(status={operation.status.value}, progress={progress.percentage:.1f}%)"
            )

            return operation

        except Exception as e:
            logger.error(f"Failed to fetch operation {operation_id} from proxy: {e}")
            return None

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
            operation = self._cache.get(operation_id)
            if not operation:
                logger.warning(
                    f"Operation {operation_id} not found in backend registry"
                )
                return

            # Update status
            operation.status = OperationStatus(host_data["status"])

            # Sync result_summary when operation completes (critical for training gate!)
            if "result_summary" in host_data and host_data["result_summary"]:
                operation.result_summary = host_data["result_summary"]
                logger.debug(
                    f"Synced result_summary for {operation_id}: "
                    f"{list(host_data['result_summary'].keys())}"
                )

            # Sync completion timestamp
            if "completed_at" in host_data and host_data["completed_at"]:
                from datetime import datetime

                if isinstance(host_data["completed_at"], str):
                    operation.completed_at = datetime.fromisoformat(
                        host_data["completed_at"].replace("Z", "+00:00")
                    )
                else:
                    operation.completed_at = host_data["completed_at"]

            # Sync error_message for failed operations
            if "error_message" in host_data and host_data["error_message"]:
                operation.error_message = host_data["error_message"]

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
        if operation_id not in self._cache:
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
            if operation_id not in self._cache:
                raise KeyError(f"Operation not found: {operation_id}")

            operation = self._cache[operation_id]

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

    Creates and injects the database repository for persistence.

    Returns:
        OperationsService singleton instance
    """
    global _operations_service
    if _operations_service is None:
        # Create repository with database session factory
        from ktrdr.api.database import get_session_factory

        session_factory = get_session_factory()
        repository = OperationsRepository(session_factory)
        _operations_service = OperationsService(repository=repository)
        logger.info("Operations service initialized with database persistence")
    return _operations_service
