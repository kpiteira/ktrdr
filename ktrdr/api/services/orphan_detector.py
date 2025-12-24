"""Orphan operation detection service.

Detects and handles operations stuck in RUNNING or PENDING_RECONCILIATION state
with no worker claiming them. After a configurable timeout (default 60s), these
"orphan" operations are marked as FAILED.

This is part of Milestone 2 (Orphan Detection) in the Checkpoint & Resilience system.
"""

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from ktrdr.logging import get_logger

if TYPE_CHECKING:
    from ktrdr.api.services.operations_service import OperationsService
    from ktrdr.api.services.worker_registry import WorkerRegistry

logger = get_logger(__name__)


class OrphanOperationDetector:
    """Detects and marks FAILED operations with no worker claiming them.

    This service runs as a background task, periodically checking for operations
    that are in RUNNING or PENDING_RECONCILIATION status but have no worker
    assigned. After a configurable timeout, these "orphan" operations are marked
    as FAILED.

    The detector tracks potential orphans with a first-seen timestamp and only
    fails them after the timeout period. This gives workers time to re-register
    after a backend restart.

    Example:
        detector = OrphanOperationDetector(
            operations_service=ops_service,
            worker_registry=registry,
            orphan_timeout_seconds=60,
            check_interval_seconds=15,
        )
        await detector.start()
        # ... system runs ...
        await detector.stop()
    """

    def __init__(
        self,
        operations_service: "OperationsService",
        worker_registry: "WorkerRegistry",
        orphan_timeout_seconds: int = 60,
        check_interval_seconds: int = 15,
    ):
        """Initialize the orphan detector.

        Args:
            operations_service: Service for querying and updating operations.
            worker_registry: Registry for checking which workers claim operations.
            orphan_timeout_seconds: Time to wait before marking orphan as FAILED.
            check_interval_seconds: How often to check for orphans.
        """
        self._operations_service = operations_service
        self._worker_registry = worker_registry
        self._orphan_timeout = orphan_timeout_seconds
        self._check_interval = check_interval_seconds

        # Track when we first saw each potential orphan
        self._potential_orphans: dict[str, datetime] = {}

        # Background task for detection loop
        self._task: Optional[asyncio.Task] = None

        # Track last check time for health status
        self._last_check: Optional[datetime] = None

    async def start(self) -> None:
        """Start the background orphan detection loop.

        Creates an async task that runs the detection loop, checking
        for orphan operations at the configured interval.
        """
        if self._task is not None and not self._task.done():
            logger.warning("Orphan detector already running")
            return

        self._task = asyncio.create_task(self._detection_loop())
        logger.info(
            f"Orphan detector started "
            f"(timeout: {self._orphan_timeout}s, interval: {self._check_interval}s)"
        )

    async def stop(self) -> None:
        """Stop the background detection loop.

        Cancels the background task and waits for it to complete.
        Safe to call even if not started.
        """
        if self._task is None:
            return

        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            # Expected when cancelling the task - just proceed with cleanup
            pass

        self._task = None
        logger.info("Orphan detector stopped")

    async def _detection_loop(self) -> None:
        """Main detection loop that runs periodically.

        Checks for orphan operations at the configured interval.
        Runs until cancelled.
        """
        while True:
            try:
                await self._check_for_orphans()
                self._last_check = datetime.now(timezone.utc)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Error in orphan detection loop: {e}", exc_info=True)
                # Sleep inside exception handler to ensure consistent timing
                await asyncio.sleep(self._check_interval)
                continue

            await asyncio.sleep(self._check_interval)

    async def _check_for_orphans(self) -> None:
        """Check for and handle orphan operations.

        For each RUNNING operation:
        1. If claimed by a worker, remove from potential orphans
        2. If backend-local, skip (handled by StartupReconciliation)
        3. If not seen before, start tracking with current timestamp
        4. If timeout exceeded, mark as FAILED
        """
        from ktrdr.api.models.operations import OperationStatus

        now = datetime.now(timezone.utc)

        # Get all RUNNING operations (includes PENDING_RECONCILIATION via status check)
        running_ops, _, _ = await self._operations_service.list_operations(
            status=OperationStatus.RUNNING,
        )

        # Get operations claimed by workers
        workers = self._worker_registry.list_workers()
        claimed_operations: set[str] = {
            w.current_operation_id for w in workers if w.current_operation_id
        }

        for op in running_ops:
            op_id = op.operation_id

            # Check if worker claims this operation
            if op_id in claimed_operations:
                # Worker is running this - not an orphan
                self._potential_orphans.pop(op_id, None)
                continue

            # Check if backend-local (handled by StartupReconciliation)
            if self._is_backend_local(op):
                # Skip - already handled on startup
                continue

            # No worker claims this operation - potential orphan
            if op_id not in self._potential_orphans:
                # First time seeing this as potential orphan
                self._potential_orphans[op_id] = now
                logger.debug(f"Potential orphan detected: {op_id}")
                continue

            # Check if timeout exceeded
            first_seen = self._potential_orphans[op_id]
            elapsed = (now - first_seen).total_seconds()

            if elapsed >= self._orphan_timeout:
                # Timeout exceeded - mark as FAILED
                await self._mark_orphan_failed(op_id, elapsed)
                self._potential_orphans.pop(op_id, None)

        # Clean up stale entries: operations that transitioned to a terminal
        # state outside the orphan detector (e.g., completed or failed normally)
        running_op_ids = {op.operation_id for op in running_ops}
        stale_orphans = set(self._potential_orphans.keys()) - running_op_ids
        for op_id in stale_orphans:
            logger.debug(f"Removing {op_id} from orphan tracking (no longer RUNNING)")
            self._potential_orphans.pop(op_id, None)

    async def _mark_orphan_failed(self, operation_id: str, elapsed: float) -> None:
        """Mark an orphan operation as FAILED.

        Args:
            operation_id: The operation to mark as failed.
            elapsed: Time in seconds since first detected as orphan.
        """
        logger.warning(
            f"Orphan operation {operation_id} - no worker claimed it after "
            f"{elapsed:.0f}s, marking FAILED"
        )

        await self._operations_service.fail_operation(
            operation_id,
            error_message="Operation was RUNNING but no worker claimed it",
        )

    def _is_backend_local(self, operation) -> bool:
        """Check if an operation is backend-local.

        Backend-local operations run in the backend process itself (e.g., agent sessions)
        rather than on workers. These are handled by StartupReconciliation, not by
        the orphan detector.

        Args:
            operation: The operation to check.

        Returns:
            True if the operation is backend-local.
        """
        if operation.metadata and operation.metadata.parameters:
            return operation.metadata.parameters.get("is_backend_local", False)
        return False

    def get_status(self) -> dict:
        """Get current status of the orphan detector.

        Returns:
            Dictionary with running status, orphan count, and last check time.
        """
        return {
            "running": self._task is not None and not self._task.done(),
            "potential_orphans_count": len(self._potential_orphans),
            "last_check": self._last_check.isoformat() if self._last_check else None,
            "orphan_timeout_seconds": self._orphan_timeout,
            "check_interval_seconds": self._check_interval,
        }
