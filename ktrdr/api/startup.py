"""
API Startup Configuration - UPDATED FOR NEW IB ARCHITECTURE

Simplified startup for new IB architecture:
- No complex background services
- IB connections created on-demand via DataManager
- Clean separation of concerns

Note: Agent trigger loop temporarily disabled pending MVP implementation.
See docs/agentic/mvp/ for the new architecture design.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ktrdr.logging import get_logger

logger = get_logger(__name__)

# Global reference for background tasks (for graceful shutdown)
_agent_trigger_task: asyncio.Task | None = None


async def start_agent_trigger_loop() -> None:
    """Start the background agent trigger loop.

    NOTE: Temporarily disabled pending MVP implementation.
    The new agent architecture uses the worker pattern instead of
    a session database. See docs/agentic/mvp/ARCHITECTURE.md.

    Environment variables:
        AGENT_ENABLED: Must be "true" for this to do anything
    """
    logger.info(
        "Agent trigger loop disabled - pending MVP implementation. "
        "See docs/agentic/mvp/ for new architecture."
    )


async def stop_agent_trigger_loop() -> None:
    """Stop the background agent trigger loop gracefully.

    NOTE: Temporarily a no-op pending MVP implementation.
    """
    global _agent_trigger_task

    if _agent_trigger_task is not None:
        try:
            await asyncio.wait_for(_agent_trigger_task, timeout=5.0)
            logger.info("Agent trigger task completed")
        except asyncio.TimeoutError:
            logger.warning("Agent trigger task did not complete in time, cancelling")
            _agent_trigger_task.cancel()
            try:
                await _agent_trigger_task
            except asyncio.CancelledError:
                pass
        except asyncio.CancelledError:
            pass
        finally:
            _agent_trigger_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager for startup and shutdown.

    With the new simplified IB architecture:
    - No persistent background connection pools
    - Connections created on-demand via IbConnectionPool
    - DataManager uses IbDataAdapter when needed
    """
    global _agent_trigger_task

    # Startup
    logger.info("Starting KTRDR API with new IB architecture...")

    # New architecture doesn't require complex startup
    # IB connections are created on-demand when needed
    logger.info("New IB architecture: connections created on-demand")
    logger.info("DataManager uses IbDataAdapter when enable_ib=True")

    # Initialize training service to log training mode at startup
    from ktrdr.api.endpoints.training import get_training_service

    _ = await get_training_service()  # Initialize service (logs training mode)
    logger.info("TrainingService initialized")

    # Start worker registry background health checks
    from ktrdr.api.endpoints.workers import get_worker_registry

    registry = get_worker_registry()
    await registry.start()
    logger.info("Worker registry started with background health checks")

    # Agent trigger loop temporarily disabled pending MVP implementation
    agent_enabled = os.getenv("AGENT_ENABLED", "false").lower() in ("true", "1", "yes")
    if agent_enabled:
        logger.info(
            "AGENT_ENABLED=true but trigger loop disabled pending MVP. "
            "Use CLI to trigger agent operations manually."
        )

    logger.info("API startup completed")

    yield

    # Shutdown
    logger.info("Shutting down KTRDR API...")

    # Stop agent trigger loop if running
    if _agent_trigger_task is not None:
        logger.info("Stopping agent trigger loop...")
        await stop_agent_trigger_loop()
        logger.info("Agent trigger loop stopped")

    # Stop worker registry background health checks
    await registry.stop()
    logger.info("Worker registry stopped")

    # New architecture: connections are cleaned up automatically
    # via context managers and dedicated threads
    logger.info("IB connections cleaned up automatically")

    logger.info("API shutdown completed")


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
