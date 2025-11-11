"""
API Startup Configuration - UPDATED FOR NEW IB ARCHITECTURE

Simplified startup for new IB architecture:
- No complex background services
- IB connections created on-demand via DataManager
- Clean separation of concerns
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from ktrdr.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager for startup and shutdown.

    With the new simplified IB architecture:
    - No persistent background connection pools
    - Connections created on-demand via IbConnectionPool
    - DataManager uses IbDataAdapter when needed
    """
    # Startup
    logger.info("🚀 Starting KTRDR API with new IB architecture...")

    # New architecture doesn't require complex startup
    # IB connections are created on-demand when needed
    logger.info("✅ New IB architecture: connections created on-demand")
    logger.info("✅ DataManager uses IbDataAdapter when enable_ib=True")

    # Initialize training service to log training mode at startup
    from ktrdr.api.endpoints.training import get_training_service

    _ = await get_training_service()  # Initialize service (logs training mode)
    logger.info("✅ TrainingService initialized")

    # Start worker registry background health checks
    from ktrdr.api.endpoints.workers import get_worker_registry

    registry = get_worker_registry()
    await registry.start()
    logger.info("✅ Worker registry started with background health checks")

    logger.info("🎉 API startup completed")

    yield

    # Shutdown
    logger.info("🛑 Shutting down KTRDR API...")

    # Stop worker registry background health checks
    await registry.stop()
    logger.info("✅ Worker registry stopped")

    # New architecture: connections are cleaned up automatically
    # via context managers and dedicated threads
    logger.info("✅ IB connections cleaned up automatically")

    logger.info("👋 API shutdown completed")


def init_background_services():
    """
    DEPRECATED: Background services not needed in new IB architecture.

    The new architecture creates IB connections on-demand via:
    - DataManager with IbDataAdapter when enable_ib=True
    - IbConnectionPool for dedicated thread connections

    No persistent background services required.
    """
    logger.info("New IB architecture: no background services needed")
    logger.info("IB connections created on-demand when required")
    return True


def stop_background_services():
    """
    DEPRECATED: Background services not used in new IB architecture.

    Connections are cleaned up automatically via context managers.
    """
    logger.info("New IB architecture: no background services to stop")
    logger.info("IB connections cleaned up automatically")
