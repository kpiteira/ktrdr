"""Worker registry for distributed execution.

This module provides the WorkerRegistry class which manages the lifecycle of
worker nodes in the distributed training and backtesting architecture.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

import httpx

from ktrdr.api.models.workers import WorkerEndpoint, WorkerStatus, WorkerType

logger = logging.getLogger(__name__)


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
        self._health_check_task: Optional[asyncio.Task] = None
        self._health_check_interval: int = 10  # seconds
        self._removal_threshold_seconds: int = 300  # 5 minutes

    def register_worker(
        self,
        worker_id: str,
        worker_type: WorkerType,
        endpoint_url: str,
        capabilities: Optional[dict] = None,
    ) -> WorkerEndpoint:
        """
        Register or update a worker.

        This method is idempotent - if a worker with the same ID already exists,
        it will be updated instead of creating a duplicate.

        Args:
            worker_id: Unique identifier for the worker
            worker_type: Type of worker (backtesting, training, etc.)
            endpoint_url: HTTP URL where the worker can be reached
            capabilities: Optional dict of worker capabilities (cores, memory, etc.)

        Returns:
            The registered WorkerEndpoint

        Example:
            >>> registry = WorkerRegistry()
            >>> worker = registry.register_worker(
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
            worker.last_healthy_at = datetime.utcnow()
            logger.info(f"Worker {worker_id} re-registered")
        else:
            # Create new worker
            worker = WorkerEndpoint(
                worker_id=worker_id,
                worker_type=worker_type,
                endpoint_url=endpoint_url,
                status=WorkerStatus.AVAILABLE,
                capabilities=capabilities or {},
                last_healthy_at=datetime.utcnow(),
            )
            self._workers[worker_id] = worker
            logger.info(f"Worker {worker_id} registered ({worker_type})")

        return worker

    def get_worker(self, worker_id: str) -> Optional[WorkerEndpoint]:
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
        worker_type: Optional[WorkerType] = None,
        status: Optional[WorkerStatus] = None,
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
    def select_worker(self, worker_type: WorkerType) -> Optional[WorkerEndpoint]:
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
        workers = self.get_available_workers(worker_type)
        if not workers:
            return None

        # Select first worker (least recently used)
        worker = workers[0]

        # Update selection timestamp
        worker.metadata["last_selected"] = datetime.utcnow().timestamp()

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
                    worker.last_health_check = datetime.utcnow()
                    worker.last_healthy_at = datetime.utcnow()

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
        worker.last_health_check = datetime.utcnow()

        # Mark as unavailable if threshold exceeded
        if worker.health_check_failures >= 3:
            worker.status = WorkerStatus.TEMPORARILY_UNAVAILABLE
            logger.warning(
                f"Worker {worker_id} marked TEMPORARILY_UNAVAILABLE "
                f"after {worker.health_check_failures} failures"
            )

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
        now = datetime.utcnow()
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
