"""API Startup Configuration.

Simplified startup:
- No complex background services
- IB connections created on-demand via DataManager
- Agent system triggered on-demand via API/CLI
- Clean separation of concerns
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from ktrdr.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager for startup and shutdown.

    Services initialized:
    - TrainingService (logs training mode)
    - WorkerRegistry (background health checks)

    IB connections are created on-demand via DataManager.
    Agent system is triggered on-demand via POST /agent/trigger.
    """
    # Startup
    logger.info("Starting KTRDR API...")

    # Initialize training service to log training mode at startup
    from ktrdr.api.endpoints.training import get_training_service

    _ = await get_training_service()
    logger.info("TrainingService initialized")

    # Start worker registry background health checks
    from ktrdr.api.endpoints.workers import get_worker_registry

    registry = get_worker_registry()
    await registry.start()
    logger.info("Worker registry started")

    logger.info("API startup completed")

    yield

    # Shutdown
    logger.info("Shutting down KTRDR API...")

    # Stop worker registry background health checks
    await registry.stop()
    logger.info("Worker registry stopped")

    logger.info("API shutdown completed")
