"""API Startup Configuration.

Simplified startup:
- No complex background services
- IB connections created on-demand via DataManager
- Agent system triggered on-demand via API/CLI
- Startup reconciliation for operation persistence (M1)
- Orphan detection for worker crash recovery (M2)
- Clean separation of concerns
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ktrdr.api.services.orphan_detector import OrphanOperationDetector
from ktrdr.config.settings import get_orphan_detector_settings
from ktrdr.logging import get_logger

logger = get_logger(__name__)

# Module-level singleton for orphan detector (M2)
_orphan_detector: OrphanOperationDetector | None = None


def get_orphan_detector() -> OrphanOperationDetector:
    """Get the global OrphanOperationDetector instance.

    Returns:
        OrphanOperationDetector: The global orphan detector singleton.

    Raises:
        RuntimeError: If called before the detector is initialized in lifespan.
    """
    if _orphan_detector is None:
        raise RuntimeError(
            "OrphanOperationDetector not initialized. "
            "This should only be called after API startup."
        )
    return _orphan_detector


async def _run_startup_reconciliation() -> None:
    """Run startup reconciliation to sync operation status after backend restart.

    This is part of M1 (Operations Persistence + Worker Re-Registration).
    On startup:
    - Worker-based RUNNING operations → PENDING_RECONCILIATION
    - Backend-local RUNNING operations → FAILED

    Gracefully handles database unavailability (skips reconciliation).
    """
    # Check if database is configured
    db_host = os.getenv("DB_HOST")
    if not db_host:
        logger.info("Startup reconciliation skipped: DB_HOST not configured")
        return

    try:
        from ktrdr.api.database import get_session_factory
        from ktrdr.api.repositories.operations_repository import OperationsRepository
        from ktrdr.api.services.startup_reconciliation import StartupReconciliation
        from ktrdr.checkpoint.checkpoint_service import CheckpointService

        session_factory = get_session_factory()
        repository = OperationsRepository(session_factory)

        # M7: Create checkpoint service for checking checkpoint availability
        checkpoint_service = CheckpointService(session_factory)

        reconciliation = StartupReconciliation(
            repository=repository,
            checkpoint_service=checkpoint_service,
        )
        result = await reconciliation.reconcile()

        if result.total_processed > 0:
            logger.info(
                f"Startup reconciliation: {result.total_processed} operations "
                f"({result.worker_ops_reconciled} worker-based, "
                f"{result.backend_ops_failed} backend-local)"
            )
    except Exception as e:
        # Don't fail startup if reconciliation fails (database might not be available)
        logger.warning(f"Startup reconciliation skipped due to error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager for startup and shutdown.

    Services initialized:
    - StartupReconciliation (M1: syncs operations after restart)
    - OrphanOperationDetector (M2: detects orphaned operations)
    - TrainingService (logs training mode)
    - WorkerRegistry (background health checks)

    IB connections are created on-demand via DataManager.
    Agent system is triggered on-demand via POST /agent/trigger.
    """
    global _orphan_detector

    # Startup
    logger.info("Starting KTRDR API...")

    # Run startup reconciliation (M1: Operations Persistence)
    await _run_startup_reconciliation()

    # Start orphan detector (M2: Orphan Detection)
    # Must be after reconciliation so we don't mark reconciling ops as orphans
    from ktrdr.api.endpoints.workers import get_worker_registry
    from ktrdr.api.services.operations_service import get_operations_service

    operations_service = get_operations_service()
    registry = get_worker_registry()

    # M2 Task 2.4: Use configurable settings for orphan detection
    orphan_settings = get_orphan_detector_settings()
    _orphan_detector = OrphanOperationDetector(
        operations_service=operations_service,
        worker_registry=registry,
        orphan_timeout_seconds=orphan_settings.timeout_seconds,
        check_interval_seconds=orphan_settings.check_interval_seconds,
    )
    await _orphan_detector.start()
    logger.info(
        "Orphan detector started (timeout=%ds, interval=%ds)",
        orphan_settings.timeout_seconds,
        orphan_settings.check_interval_seconds,
    )

    # Initialize training service to log training mode at startup
    from ktrdr.api.endpoints.training import get_training_service

    _ = await get_training_service()
    logger.info("TrainingService initialized")

    # Start worker registry background health checks
    # CRITICAL: Inject OperationsService for reconciliation to work (M1)
    registry.set_operations_service(operations_service)
    await registry.start()
    logger.info("Worker registry started")

    logger.info("API startup completed")

    yield

    # Shutdown
    logger.info("Shutting down KTRDR API...")

    # Stop orphan detector first (M2)
    if _orphan_detector:
        await _orphan_detector.stop()
        logger.info("Orphan detector stopped")

    # Stop worker registry background health checks
    await registry.stop()
    logger.info("Worker registry stopped")

    # Close database connections
    try:
        from ktrdr.api.database import close_database

        await close_database()
    except Exception as e:
        logger.warning(f"Error closing database: {e}")

    logger.info("API shutdown completed")
