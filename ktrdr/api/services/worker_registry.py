"""Worker registry for distributed execution.

This module provides the WorkerRegistry class which manages the lifecycle of
worker nodes in the distributed training and backtesting architecture.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import httpx

from ktrdr.api.models.workers import (
    CompletedOperationReport,
    WorkerEndpoint,
    WorkerStatus,
    WorkerType,
)
from ktrdr.monitoring.metrics import update_worker_metrics
from ktrdr.monitoring.service_telemetry import trace_service_method

if TYPE_CHECKING:
    from ktrdr.api.services.operations_service import OperationsService

logger = logging.getLogger(__name__)


@dataclass
class RegistrationResult:
    """Result of worker registration including any signals for the worker."""

    worker: WorkerEndpoint
    stop_operations: list[str] = field(default_factory=list)
    """Operations that the worker should stop (e.g., already completed in DB)."""

    @property
    def worker_id(self) -> str:
        """Convenience property for backward compatibility."""
        return self.worker.worker_id


class WorkerRegistry:
    """
    Registry for managing worker nodes.

    The WorkerRegistry maintains a registry of all worker nodes that have
    registered with the backend. It provides methods to:
    - Register new workers (or update existing ones)
    - Retrieve workers by ID
    - List workers with optional filtering

    Workers are registered via push-based registration - they self-register
    on startup by calling POST /workers/register.
    """

    def __init__(self):
        """Initialize an empty worker registry."""
        self._workers: dict[str, WorkerEndpoint] = {}
        self._health_check_task: asyncio.Task | None = None
        self._health_check_interval: int = 10  # seconds
        self._removal_threshold_seconds: int = 300  # 5 minutes
        self._operations_service: OperationsService | None = None
        # Shutdown mode flag (M7.5 Task 7.5.3)
        # When True, registration requests are rejected with 503
        self._shutting_down: bool = False

    def set_operations_service(self, operations_service: OperationsService) -> None:
        """
        Set the operations service for reconciliation.

        This must be called after initialization to enable operation
        reconciliation during worker registration.

        Args:
            operations_service: The OperationsService instance
        """
        self._operations_service = operations_service

    def begin_shutdown(self) -> None:
        """
        Enter shutdown mode - reject new registrations.

        Called during backend shutdown to prevent workers from registering
        to a backend that's about to go away. Workers will receive 503
        responses and retry after the backend restarts.
        """
        self._shutting_down = True
        logger.info("Worker registry entering shutdown mode - rejecting registrations")

    def is_shutting_down(self) -> bool:
        """
        Check if registry is in shutdown mode.

        Returns:
            True if registry is shutting down and rejecting registrations
        """
        return self._shutting_down

    async def register_worker(
        self,
        worker_id: str,
        worker_type: WorkerType,
        endpoint_url: str,
        capabilities: dict | None = None,
        current_operation_id: str | None = None,
        completed_operations: list[CompletedOperationReport] | None = None,
    ) -> RegistrationResult:
        """
        Register or update a worker with optional operation reconciliation.

        This method is idempotent - if a worker with the same ID already exists,
        it will be updated instead of creating a duplicate.

        When workers re-register after a backend restart, they can report:
        - completed_operations: Operations that finished while backend was unavailable
        - current_operation_id: Operation the worker is currently running

        The backend reconciles these reports with its database state.

        Args:
            worker_id: Unique identifier for the worker
            worker_type: Type of worker (backtesting, training, etc.)
            endpoint_url: HTTP URL where the worker can be reached
            capabilities: Optional dict of worker capabilities (cores, memory, etc.)
            current_operation_id: ID of operation worker is currently running (if any)
            completed_operations: Operations that completed while backend was unavailable

        Returns:
            RegistrationResult containing the worker and any signals (e.g., stop_operations)

        Example:
            >>> registry = WorkerRegistry()
            >>> result = await registry.register_worker(
            ...     worker_id="backtest-1",
            ...     worker_type=WorkerType.BACKTESTING,
            ...     endpoint_url="http://192.168.1.201:5003",
            ...     capabilities={"cores": 4, "memory_gb": 8}
            ... )
        """
        if worker_id in self._workers:
            # Update existing worker (idempotent registration)
            worker = self._workers[worker_id]
            worker.endpoint_url = endpoint_url
            worker.capabilities = capabilities or {}
            worker.status = WorkerStatus.AVAILABLE
            worker.last_healthy_at = datetime.now(UTC)
            logger.info(f"Worker {worker_id} re-registered")
        else:
            # Check for stale workers with the same endpoint_url (worker restarted with new ID)
            stale_worker_ids = [
                wid
                for wid, w in self._workers.items()
                if w.endpoint_url == endpoint_url and wid != worker_id
            ]
            for stale_id in stale_worker_ids:
                logger.info(
                    f"Removing stale worker {stale_id} (same endpoint as {worker_id})"
                )
                del self._workers[stale_id]

            # Create new worker
            worker = WorkerEndpoint(
                worker_id=worker_id,
                worker_type=worker_type,
                endpoint_url=endpoint_url,
                status=WorkerStatus.AVAILABLE,
                capabilities=capabilities or {},
                last_healthy_at=datetime.now(UTC),
            )
            self._workers[worker_id] = worker
            logger.info(f"Worker {worker_id} registered ({worker_type})")

        # Update Prometheus metrics
        update_worker_metrics(self._workers)

        # Perform operation reconciliation if operations service is configured
        stop_operations: list[str] = []
        if self._operations_service is not None:
            # Process completed operations first (terminal state updates)
            if completed_operations:
                await self._reconcile_completed_operations(completed_operations)

            # Then process current operation (sync running status)
            if current_operation_id:
                should_stop = await self._reconcile_current_operation(
                    worker_id, current_operation_id
                )
                if should_stop:
                    stop_operations.append(current_operation_id)

        return RegistrationResult(worker=worker, stop_operations=stop_operations)

    def get_worker(self, worker_id: str) -> WorkerEndpoint | None:
        """
        Get a worker by ID.

        Args:
            worker_id: The worker ID to look up

        Returns:
            The WorkerEndpoint if found, None otherwise

        Example:
            >>> registry = WorkerRegistry()
            >>> worker = registry.get_worker("backtest-1")
        """
        return self._workers.get(worker_id)

    @trace_service_method("workers.list")
    def list_workers(
        self,
        worker_type: WorkerType | None = None,
        status: WorkerStatus | None = None,
    ) -> list[WorkerEndpoint]:
        """
        List workers with optional filtering.

        Args:
            worker_type: Optional filter by worker type
            status: Optional filter by worker status

        Returns:
            List of workers matching the filters

        Example:
            >>> registry = WorkerRegistry()
            >>> # Get all workers
            >>> all_workers = registry.list_workers()
            >>> # Get only backtest workers
            >>> backtest_workers = registry.list_workers(
            ...     worker_type=WorkerType.BACKTESTING
            ... )
            >>> # Get only available workers
            >>> available_workers = registry.list_workers(
            ...     status=WorkerStatus.AVAILABLE
            ... )
            >>> # Get available backtest workers
            >>> workers = registry.list_workers(
            ...     worker_type=WorkerType.BACKTESTING,
            ...     status=WorkerStatus.AVAILABLE
            ... )
        """
        workers = list(self._workers.values())

        # Apply filters
        if worker_type is not None:
            workers = [w for w in workers if w.worker_type == worker_type]

        if status is not None:
            workers = [w for w in workers if w.status == status]

        return workers

    def get_available_workers(self, worker_type: WorkerType) -> list[WorkerEndpoint]:
        """
        Get available workers of given type, sorted by last selection (LRU).

        Args:
            worker_type: Type of workers to retrieve

        Returns:
            List of available workers sorted by least recently used first

        Example:
            >>> registry = WorkerRegistry()
            >>> workers = registry.get_available_workers(WorkerType.BACKTESTING)
        """
        workers = [
            w
            for w in self._workers.values()
            if w.worker_type == worker_type and w.status == WorkerStatus.AVAILABLE
        ]

        # Sort by last_selected (least recently used first)
        # Workers without last_selected get 0.0 (will be selected first)
        workers.sort(key=lambda w: w.metadata.get("last_selected", 0.0))

        return workers

    @trace_service_method("workers.select")
    def select_worker(self, worker_type: WorkerType) -> WorkerEndpoint | None:
        """
        Select an available worker using round-robin (least recently used).

        This implements round-robin load balancing by selecting the worker
        that was least recently used.

        Args:
            worker_type: Type of worker to select

        Returns:
            Selected worker, or None if no workers available

        Example:
            >>> registry = WorkerRegistry()
            >>> worker = registry.select_worker(WorkerType.BACKTESTING)
            >>> if worker:
            ...     # Dispatch operation to this worker
            ...     registry.mark_busy(worker.worker_id, "op-123")
        """
        from opentelemetry import trace

        # Get tracer for adding attributes to the current span
        try:
            span = trace.get_current_span()
        except Exception:
            span = None

        # Gather worker selection metrics
        total_workers = len(self._workers)
        capable_workers = [
            w for w in self._workers.values() if w.worker_type == worker_type
        ]
        # Use get_available_workers to get properly sorted list (LRU first)
        available_workers = self.get_available_workers(worker_type)

        # Add telemetry attributes to current span
        if span and span.is_recording():
            span.set_attribute("worker.type", worker_type.value)
            span.set_attribute("worker.total_workers", str(total_workers))
            span.set_attribute("worker.capable_workers", str(len(capable_workers)))
            span.set_attribute("worker.available_workers", str(len(available_workers)))

        if not available_workers:
            if span and span.is_recording():
                span.set_attribute("worker.selection_status", "no_workers_available")
            return None

        # Select first worker (least recently used)
        worker = available_workers[0]

        # Update selection timestamp
        worker.metadata["last_selected"] = datetime.now(UTC).timestamp()

        # Add selection result to telemetry
        if span and span.is_recording():
            span.set_attribute("worker.selected_id", worker.worker_id)
            span.set_attribute("worker.selection_status", "success")

        logger.debug(f"Selected worker {worker.worker_id} for {worker_type}")
        return worker

    def mark_busy(self, worker_id: str, operation_id: str) -> None:
        """
        Mark a worker as busy with the given operation.

        Args:
            worker_id: ID of the worker to mark busy
            operation_id: ID of the operation the worker is executing

        Example:
            >>> registry = WorkerRegistry()
            >>> registry.mark_busy("backtest-1", "op-123")
        """
        if worker_id in self._workers:
            worker = self._workers[worker_id]
            worker.status = WorkerStatus.BUSY
            worker.current_operation_id = operation_id
            logger.info(
                f"Worker {worker_id} marked as BUSY (operation: {operation_id})"
            )
            # Update Prometheus metrics
            update_worker_metrics(self._workers)

    def mark_available(self, worker_id: str) -> None:
        """
        Mark a worker as available (operation completed).

        Args:
            worker_id: ID of the worker to mark available

        Example:
            >>> registry = WorkerRegistry()
            >>> registry.mark_available("backtest-1")
        """
        if worker_id in self._workers:
            worker = self._workers[worker_id]
            worker.status = WorkerStatus.AVAILABLE
            worker.current_operation_id = None
            logger.info(f"Worker {worker_id} marked as AVAILABLE")
            # Update Prometheus metrics
            update_worker_metrics(self._workers)

    async def _reconcile_completed_operations(
        self, completed_operations: list[CompletedOperationReport]
    ) -> None:
        """
        Reconcile completed operations reported by worker during re-registration.

        When a worker re-registers after backend restart, it reports operations
        that completed while the backend was unavailable. This method updates
        the database to reflect those terminal states.

        Args:
            completed_operations: List of operation completion reports from worker

        Reconciliation rules:
        - Unknown operation: Log warning, skip (no metadata to create record)
        - Already in terminal state: Skip (idempotent)
        - Not in terminal state: Update to reported terminal state
        """
        if not self._operations_service:
            return

        from ktrdr.api.models.operations import OperationStatus

        for report in completed_operations:
            operation = await self._operations_service.get_operation(
                report.operation_id
            )

            if operation is None:
                logger.warning(
                    f"Worker reported unknown completed operation: {report.operation_id}"
                )
                continue

            # Skip if already in terminal state
            if operation.status in [
                OperationStatus.COMPLETED,
                OperationStatus.FAILED,
                OperationStatus.CANCELLED,
            ]:
                logger.debug(
                    f"Operation {report.operation_id} already in terminal state "
                    f"({operation.status}), skipping reconciliation"
                )
                continue

            # Update to reported terminal state
            logger.info(
                f"Reconciling operation {report.operation_id}: "
                f"{operation.status} → {report.status}"
            )

            if report.status == "COMPLETED":
                await self._operations_service.complete_operation(
                    report.operation_id, result_summary=report.result
                )
            elif report.status == "FAILED":
                await self._operations_service.fail_operation(
                    report.operation_id,
                    error_message=report.error_message
                    or "Operation failed (no details)",
                )
            elif report.status == "CANCELLED":
                await self._operations_service.cancel_operation(report.operation_id)

    async def _reconcile_current_operation(
        self, worker_id: str, operation_id: str
    ) -> bool:
        """
        Reconcile a currently running operation reported by worker.

        When a worker re-registers and reports it's running an operation,
        we sync the database status based on reconciliation rules.

        Args:
            worker_id: ID of the worker claiming the operation
            operation_id: ID of the operation the worker claims is running

        Returns:
            True if the worker should stop this operation (e.g., DB says COMPLETED)

        Reconciliation rules:
        - Unknown operation: Log warning, return False (don't signal stop)
        - COMPLETED in DB: Return True (signal worker to stop)
        - RUNNING with same worker: No update needed
        - FAILED/CANCELLED/PENDING: Update to RUNNING
        """
        if not self._operations_service:
            return False

        from ktrdr.api.models.operations import OperationStatus

        operation = await self._operations_service.get_operation(operation_id)

        if operation is None:
            logger.warning(
                f"Worker {worker_id} claims unknown operation: {operation_id}"
            )
            return False

        # If DB says COMPLETED, trust DB - tell worker to stop
        if operation.status == OperationStatus.COMPLETED:
            logger.info(
                f"Operation {operation_id} is COMPLETED in DB, signaling worker to stop"
            )
            return True

        # If already RUNNING with same worker, no update needed
        if (
            operation.status == OperationStatus.RUNNING
            and getattr(operation, "worker_id", None) == worker_id
        ):
            logger.debug(
                f"Operation {operation_id} already RUNNING on worker {worker_id}"
            )
            return False

        # For other statuses (FAILED, CANCELLED, PENDING, etc.), sync to RUNNING
        # because the worker is actually running it
        if operation.status in [
            OperationStatus.FAILED,
            OperationStatus.CANCELLED,
            OperationStatus.PENDING,
        ]:
            logger.info(
                f"Syncing operation {operation_id}: {operation.status} → RUNNING "
                f"(worker {worker_id} is running it)"
            )

            # Use repository directly for field update (status + worker_id)
            if self._operations_service._repository:
                await self._operations_service._repository.update(
                    operation_id,
                    status="RUNNING",
                    worker_id=worker_id,
                )

        return False

    async def health_check_worker(self, worker_id: str) -> bool:
        """
        Perform health check on a worker.

        This method calls the worker's /health endpoint and updates the worker's
        status based on the response. It tracks consecutive failures and marks
        workers as temporarily unavailable after 3 failures.

        Args:
            worker_id: ID of the worker to health check

        Returns:
            True if health check successful, False otherwise

        Example:
            >>> registry = WorkerRegistry()
            >>> success = await registry.health_check_worker("backtest-1")
        """
        if worker_id not in self._workers:
            logger.warning(f"Cannot health check nonexistent worker: {worker_id}")
            return False

        worker = self._workers[worker_id]

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{worker.endpoint_url}/health")

                if response.status_code == 200:
                    data = response.json()

                    # Update status from health response
                    worker_status = data.get("worker_status", "idle")
                    if worker_status == "busy":
                        worker.status = WorkerStatus.BUSY
                        worker.current_operation_id = data.get("current_operation")
                    else:
                        worker.status = WorkerStatus.AVAILABLE
                        worker.current_operation_id = None

                    # Reset failure counter and update timestamps
                    worker.health_check_failures = 0
                    worker.last_health_check = datetime.now(UTC)
                    worker.last_healthy_at = datetime.now(UTC)

                    # Update Prometheus metrics
                    update_worker_metrics(self._workers)

                    logger.debug(f"Health check passed for {worker_id}")
                    return True
                else:
                    logger.warning(
                        f"Health check failed for {worker_id}: HTTP {response.status_code}"
                    )

        except Exception as e:
            logger.warning(f"Health check failed for {worker_id}: {e}")

        # Health check failed - increment failure counter
        worker.health_check_failures += 1
        worker.last_health_check = datetime.now(UTC)

        # Mark as unavailable if threshold exceeded
        if worker.health_check_failures >= 3:
            worker.status = WorkerStatus.TEMPORARILY_UNAVAILABLE
            logger.warning(
                f"Worker {worker_id} marked TEMPORARILY_UNAVAILABLE "
                f"after {worker.health_check_failures} failures"
            )
            # Update Prometheus metrics
            update_worker_metrics(self._workers)

        return False

    def _cleanup_dead_workers(self) -> None:
        """
        Remove workers that have been unavailable for too long.

        Workers marked as TEMPORARILY_UNAVAILABLE for longer than the removal
        threshold (default 5 minutes) are removed from the registry.

        This method is called periodically by the background health check loop.

        Example:
            >>> registry = WorkerRegistry()
            >>> # Worker becomes unavailable...
            >>> # After 5+ minutes of being unavailable...
            >>> registry._cleanup_dead_workers()  # Worker is removed
        """
        now = datetime.now(UTC)
        to_remove = []

        for worker_id, worker in self._workers.items():
            # Only consider workers that are temporarily unavailable
            if worker.status == WorkerStatus.TEMPORARILY_UNAVAILABLE:
                if worker.last_healthy_at:
                    time_unavailable = (now - worker.last_healthy_at).total_seconds()
                    if time_unavailable > self._removal_threshold_seconds:
                        to_remove.append(worker_id)

        # Remove dead workers
        for worker_id in to_remove:
            del self._workers[worker_id]
            logger.info(f"Removed dead worker: {worker_id}")

        # Update Prometheus metrics if any workers were removed
        if to_remove:
            update_worker_metrics(self._workers)

    async def start(self) -> None:
        """
        Start background health check task.

        Creates an asyncio task that continuously health checks all registered
        workers at regular intervals.

        Example:
            >>> registry = WorkerRegistry()
            >>> await registry.start()  # Starts background task
        """
        if self._health_check_task is None:
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            logger.info("Worker registry started - background health checks enabled")

    async def stop(self) -> None:
        """
        Stop background health check task.

        Cancels the background task and waits for it to finish cleanup.

        Example:
            >>> registry = WorkerRegistry()
            >>> await registry.start()
            >>> await registry.stop()  # Stops background task
        """
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
            logger.info("Worker registry stopped - background health checks disabled")

    async def _health_check_loop(self) -> None:
        """
        Background task to continuously health check all workers.

        This loop runs indefinitely until cancelled. It health checks all
        registered workers, then sleeps for the configured interval.

        The loop handles exceptions gracefully to ensure it continues running
        even if individual health checks fail.
        """
        logger.info(
            f"Background health check loop started (interval: {self._health_check_interval}s)"
        )

        while True:
            try:
                # Health check all workers
                for worker_id in list(self._workers.keys()):
                    await self.health_check_worker(worker_id)

                # Cleanup dead workers after health checks
                self._cleanup_dead_workers()

                # Wait before next round
                await asyncio.sleep(self._health_check_interval)

            except asyncio.CancelledError:
                logger.info("Background health check loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}", exc_info=True)
                # Continue after error
                await asyncio.sleep(self._health_check_interval)
