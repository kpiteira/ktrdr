"""
API Startup Configuration

Handles initialization of background services when the API starts:
- Persistent IB connection manager
- Automatic gap filling service
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI

from ktrdr.logging import get_logger
from ktrdr.data.ib_gap_filler import start_gap_filler, stop_gap_filler
from ktrdr.data.ib_connection_pool import get_connection_pool

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager for startup and shutdown.

    This handles:
    - Starting persistent IB connection manager on startup
    - Starting gap filling service on startup
    - Stopping both services on shutdown
    """
    # Startup
    logger.info("🚀 Starting KTRDR API services...")

    # Check IB connection pool availability
    try:
        pool = await get_connection_pool()
        pool_stats = pool.get_pool_status()
        if pool_stats.get("available_connections", 0) > 0:
            logger.info("✅ IB connection pool is available")
        else:
            logger.info(
                "ℹ️ IB connection pool initialized (connections created on demand)"
            )
    except Exception as e:
        logger.error(f"❌ Error checking IB connection pool: {e}")

    # Give a moment for initialization
    await asyncio.sleep(1)

    # Start gap filling service
    try:
        if start_gap_filler():
            logger.info("✅ Automatic gap filling service started")
        else:
            logger.warning("⚠️ Failed to start gap filling service")
    except Exception as e:
        logger.error(f"❌ Error starting gap filling service: {e}")

    logger.info("🎉 API startup completed")

    yield

    # Shutdown
    logger.info("🛑 Shutting down KTRDR API services...")

    # Stop gap filling service first
    try:
        stop_gap_filler()
        logger.info("✅ Gap filling service stopped")
    except Exception as e:
        logger.error(f"❌ Error stopping gap filling service: {e}")

    # Clean up IB connection pool
    try:
        from ktrdr.data.ib_connection_pool import get_connection_pool

        pool = get_connection_pool()
        await pool.cleanup_all_connections()
        logger.info("✅ IB connection pool cleaned up")
    except Exception as e:
        logger.error(f"❌ Error cleaning up IB connection pool: {e}")

    logger.info("👋 API shutdown completed")


def init_background_services():
    """
    Alternative initialization for non-FastAPI contexts.

    This can be called directly in non-web contexts to start
    the background services manually.
    """
    logger.info("Initializing background services...")

    # Check IB connection pool
    try:
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            pool = loop.run_until_complete(get_connection_pool())
            pool_stats = pool.get_pool_status()
            logger.info("✅ IB connection pool available")
            pool_available = True
        finally:
            loop.close()
    except Exception as e:
        logger.warning(f"⚠️ IB connection pool not available: {e}")
        pool_available = False

    # Start gap filler service
    gap_filler_started = start_gap_filler()

    if gap_filler_started:
        logger.info("✅ Background services started successfully")
        return True
    else:
        logger.warning("⚠️ Gap filler service failed to start")
        return False


def stop_background_services():
    """
    Stop all background services.

    This can be called to manually stop services.
    """
    logger.info("Stopping background services...")

    stop_gap_filler()

    # Note: Connection pool cleanup should be done asynchronously
    # For sync context, we just log that cleanup is needed
    logger.info("ℹ️ Note: IB connection pool cleanup should be done asynchronously")

    logger.info("✅ Background services stopped")
