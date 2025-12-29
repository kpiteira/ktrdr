"""Startup reconciliation service for backend restart recovery.

On backend startup, this service processes all RUNNING operations to ensure
the system can recover from restarts:

- Worker-based operations: Marked with reconciliation_status='PENDING_RECONCILIATION'
  so the orphan detector can track them until workers re-register.
- Backend-local operations: Marked FAILED immediately since the backend process
  that was executing them has died.

This is part of Task 1.8 in Milestone 1 (Operations Persistence + Worker Re-Registration).
"""

from dataclasses import dataclass

from ktrdr.api.models.operations import OperationInfo
from ktrdr.api.repositories.operations_repository import OperationsRepository
from ktrdr.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ReconciliationResult:
    """Result of startup reconciliation.

    Attributes:
        total_processed: Total number of RUNNING operations processed.
        worker_ops_reconciled: Operations marked PENDING_RECONCILIATION.
        backend_ops_failed: Operations marked FAILED (backend-local).
    """

    total_processed: int
    worker_ops_reconciled: int
    backend_ops_failed: int


class StartupReconciliation:
    """Handles backend startup reconciliation of operations.

    On backend startup, this service ensures:
    1. Worker-based RUNNING operations are marked PENDING_RECONCILIATION
       so the orphan detector can track them until workers re-register.
    2. Backend-local RUNNING operations are marked FAILED since the
       backend process that was executing them has died.

    Example:
        reconciliation = StartupReconciliation(repository)
        result = await reconciliation.reconcile()
        logger.info(f"Reconciled {result.total_processed} operations")
    """

    def __init__(self, repository: OperationsRepository):
        """Initialize startup reconciliation service.

        Args:
            repository: Operations repository for database access.
        """
        self._repository = repository

    async def reconcile(self) -> ReconciliationResult:
        """Reconcile all RUNNING operations on backend startup.

        Queries all RUNNING operations and:
        - Marks worker-based ops as PENDING_RECONCILIATION
        - Marks backend-local ops as FAILED

        Returns:
            ReconciliationResult with counts of processed operations.
        """
        # Get all RUNNING operations from database
        running_ops = await self._repository.list(status="RUNNING")

        if not running_ops:
            logger.info("Startup reconciliation: No RUNNING operations to process")
            return ReconciliationResult(
                total_processed=0,
                worker_ops_reconciled=0,
                backend_ops_failed=0,
            )

        worker_ops_count = 0
        backend_ops_count = 0

        for op in running_ops:
            is_backend_local = self._is_backend_local(op)

            if is_backend_local:
                # Backend-local: process died, mark failed
                await self._repository.update(
                    op.operation_id,
                    status="FAILED",
                    error_message="Backend restarted - operation was running in backend process",
                )
                backend_ops_count += 1
                logger.debug(
                    f"Marked backend-local operation FAILED: {op.operation_id}"
                )
            else:
                # Worker-based: wait for re-registration
                await self._repository.update(
                    op.operation_id,
                    reconciliation_status="PENDING_RECONCILIATION",
                )
                worker_ops_count += 1
                logger.debug(
                    f"Marked worker operation PENDING_RECONCILIATION: {op.operation_id}"
                )

        total = len(running_ops)
        logger.info(
            f"Startup reconciliation complete: {total} operations processed "
            f"({worker_ops_count} worker-based → PENDING_RECONCILIATION, "
            f"{backend_ops_count} backend-local → FAILED)"
        )

        return ReconciliationResult(
            total_processed=total,
            worker_ops_reconciled=worker_ops_count,
            backend_ops_failed=backend_ops_count,
        )

    def _is_backend_local(self, operation: OperationInfo) -> bool:
        """Determine if an operation is backend-local.

        Args:
            operation: The operation to check.

        Returns:
            True if the operation runs in the backend process (not on a worker).
        """
        # Use the proper is_backend_local field from OperationInfo
        return operation.is_backend_local
