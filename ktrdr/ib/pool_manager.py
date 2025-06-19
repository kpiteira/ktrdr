"""
Centralized IB Connection Pool Manager

Provides a single, shared connection pool for all IB operations
to ensure consistent timeouts and avoid connection conflicts.
"""

from typing import Optional
from ktrdr.ib.pool import IbConnectionPool
from ktrdr.config.ib_config import get_ib_config
from ktrdr.logging import get_logger

logger = get_logger(__name__)

# Global shared connection pool instance
_shared_pool: Optional[IbConnectionPool] = None


def get_shared_ib_pool() -> IbConnectionPool:
    """
    Get the shared IB connection pool instance.

    Creates the pool on first access using centralized configuration.
    All IB operations should use this shared pool to ensure consistency.

    Returns:
        The shared IbConnectionPool instance
    """
    global _shared_pool

    if _shared_pool is None:
        logger.info("Creating shared IB connection pool")
        config = get_ib_config()

        # Use consistent settings for all IB operations
        _shared_pool = IbConnectionPool(
            host=config.host, port=config.port, max_connections=5  # Conservative limit
        )

        logger.info(f"Shared IB pool created for {config.host}:{config.port}")

    return _shared_pool


def shutdown_shared_pool():
    """
    Shutdown the shared connection pool.

    Should be called during application shutdown to clean up connections.
    """
    global _shared_pool

    if _shared_pool is not None:
        logger.info("Shutting down shared IB connection pool")
        # The pool will clean up connections when it's destroyed
        _shared_pool = None
        logger.info("Shared IB pool shutdown complete")


def get_pool_stats() -> dict:
    """
    Get statistics from the shared pool.

    Returns:
        Dictionary with pool statistics, or empty dict if no pool exists
    """
    if _shared_pool is not None:
        return _shared_pool.get_pool_stats()
    return {"note": "Shared pool not yet created"}
