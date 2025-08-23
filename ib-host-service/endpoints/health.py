"""
Health check endpoints for IB Connector Host Service

Provides health monitoring and connection status information.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
import logging

# Import existing ktrdr modules
from ktrdr.ib import IbConnectionPool
from ktrdr.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/health", tags=["health"])

# Global connection pool instance
_connection_pool: Optional[IbConnectionPool] = None


async def get_connection_pool() -> IbConnectionPool:
    """Get or create IB connection pool instance."""
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = IbConnectionPool()
    return _connection_pool


# Response Models


class HealthResponse(BaseModel):
    """Health check response."""

    healthy: bool
    service: str = "ib-connector"
    timestamp: str
    ib_status: Dict[str, Any]
    connection_info: Dict[str, Any]
    error: Optional[str] = None


class DetailedHealthResponse(BaseModel):
    """Detailed health information."""

    healthy: bool
    service: str = "ib-connector"
    timestamp: str
    ib_gateway_connected: bool
    active_connections: int
    total_requests: int
    error_count: int
    last_error: Optional[str] = None
    uptime_seconds: float
    connection_pool_status: Dict[str, Any]


# Endpoints


@router.get("/", response_model=HealthResponse)
async def basic_health_check():
    """
    Basic health check endpoint.

    Returns overall service health and IB connection status.
    """
    try:
        current_time = datetime.utcnow()

        # Get connection pool for status
        pool = await get_connection_pool()

        # Check IB connection status (lightweight check)
        ib_connected = False
        connection_count = 0

        try:
            # Simple status check without heavy API calls
            connection_count = (
                len(pool._connections) if hasattr(pool, "_connections") else 0
            )
            # Consider healthy if we have at least one connection or can create one
            ib_connected = connection_count > 0
        except Exception as e:
            logger.warning(f"Error checking IB status: {str(e)}")
            ib_connected = False

        return HealthResponse(
            healthy=True,  # Service is running
            timestamp=current_time.isoformat(),
            ib_status={"connected": ib_connected, "connection_count": connection_count},
            connection_info={
                "service_running": True,
                "last_check": current_time.isoformat(),
            },
        )

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return HealthResponse(
            healthy=False,
            timestamp=datetime.utcnow().isoformat(),
            ib_status={"connected": False, "connection_count": 0},
            connection_info={"service_running": False},
            error=str(e),
        )


@router.get("/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check():
    """
    Detailed health check with comprehensive status information.

    Provides detailed information about IB connections, request counts,
    error rates, and service uptime.
    """
    try:
        current_time = datetime.utcnow()

        # Get connection pool
        pool = await get_connection_pool()

        # Gather detailed statistics
        connection_count = 0
        pool_status = {}

        try:
            if hasattr(pool, "_connections"):
                connection_count = len(pool._connections)
                pool_status = {
                    "total_connections": connection_count,
                    "max_connections": getattr(pool, "max_connections", "unknown"),
                    "pool_initialized": True,
                }
            else:
                pool_status = {"pool_initialized": False}
        except Exception as e:
            logger.warning(f"Error getting pool status: {str(e)}")
            pool_status = {"error": str(e)}

        return DetailedHealthResponse(
            healthy=True,
            timestamp=current_time.isoformat(),
            ib_gateway_connected=connection_count > 0,
            active_connections=connection_count,
            total_requests=0,  # TODO: Add request counter
            error_count=0,  # TODO: Add error counter
            uptime_seconds=0.0,  # TODO: Add uptime tracking
            connection_pool_status=pool_status,
        )

    except Exception as e:
        logger.error(f"Detailed health check failed: {str(e)}")
        return DetailedHealthResponse(
            healthy=False,
            timestamp=datetime.utcnow().isoformat(),
            ib_gateway_connected=False,
            active_connections=0,
            total_requests=0,
            error_count=1,
            last_error=str(e),
            uptime_seconds=0.0,
            connection_pool_status={"error": str(e)},
        )
