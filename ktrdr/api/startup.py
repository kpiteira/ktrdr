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
from ktrdr.data.ib_connection_manager import start_connection_manager, stop_connection_manager
from ktrdr.data.ib_gap_filler import start_gap_filler, stop_gap_filler

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
    
    # Start persistent IB connection manager
    try:
        if start_connection_manager():
            logger.info("✅ Persistent IB connection manager started")
        else:
            logger.warning("⚠️ Failed to start IB connection manager")
    except Exception as e:
        logger.error(f"❌ Error starting IB connection manager: {e}")
    
    # Give connection manager a moment to attempt initial connection
    await asyncio.sleep(2)
    
    # Start gap filling service - TEMPORARILY DISABLED for connection debugging
    logger.info("🔧 Gap filling service temporarily disabled for debugging")
    # try:
    #     if start_gap_filler():
    #         logger.info("✅ Automatic gap filling service started")
    #     else:
    #         logger.warning("⚠️ Failed to start gap filling service")
    # except Exception as e:
    #     logger.error(f"❌ Error starting gap filling service: {e}")
    
    logger.info("🎉 API startup completed")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down KTRDR API services...")
    
    # Stop gap filling service first - TEMPORARILY DISABLED
    logger.info("🔧 Gap filling service was disabled, no need to stop")
    # try:
    #     stop_gap_filler()
    #     logger.info("✅ Gap filling service stopped")
    # except Exception as e:
    #     logger.error(f"❌ Error stopping gap filling service: {e}")
    
    # Stop connection manager
    try:
        stop_connection_manager()
        logger.info("✅ IB connection manager stopped")
    except Exception as e:
        logger.error(f"❌ Error stopping IB connection manager: {e}")
    
    logger.info("👋 API shutdown completed")


def init_background_services():
    """
    Alternative initialization for non-FastAPI contexts.
    
    This can be called directly in non-web contexts to start
    the background services manually.
    """
    logger.info("Initializing background services...")
    
    # Start services
    connection_started = start_connection_manager()
    gap_filler_started = start_gap_filler()
    
    if connection_started and gap_filler_started:
        logger.info("✅ All background services started successfully")
        return True
    else:
        logger.warning("⚠️ Some background services failed to start")
        return False


def stop_background_services():
    """
    Stop all background services.
    
    This can be called to manually stop services.
    """
    logger.info("Stopping background services...")
    
    stop_gap_filler()
    stop_connection_manager()
    
    logger.info("✅ All background services stopped")