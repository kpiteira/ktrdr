"""Worker registry for distributed execution.

This module provides the WorkerRegistry class which manages the lifecycle of
worker nodes in the distributed training and backtesting architecture.
"""

import logging
from datetime import datetime
from typing import Optional

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
