"""
System status endpoints for monitoring background services.

Provides endpoints to monitor:
- IB connection status
- Overall system health
"""

from typing import Any

from fastapi import APIRouter, HTTPException

from ktrdr import metadata
from ktrdr.api.models.base import ApiResponse
from ktrdr.logging import get_logger

logger = get_logger(__name__)

# Create router for system endpoints
router = APIRouter()


@router.get("/ib-status")
async def get_ib_status() -> dict[str, Any]:
    """
    Get Interactive Brokers connection status.

    Returns detailed information about the connection pool status,
    active connections, and pool metrics.
    """
    try:
        # Get connection pool statistics
        # TODO: Implement with new IB architecture
        pool_stats = {"note": "New IB architecture - pool stats not yet implemented"}

        # Extract available connections once to ensure type consistency
        available_connections = pool_stats.get("available_connections", 0)

        return {
            "success": True,
            "connection_pool": {
                "available_connections": available_connections,
                "total_connections": pool_stats.get("total_connections", 0),
                "failed_connections": pool_stats.get("failed_connections", 0),
                "host": pool_stats.get("host", ""),
                "port": pool_stats.get("port", 0),
                "uptime_seconds": pool_stats.get("uptime_seconds", 0),
                "created_at": pool_stats.get("created_at", ""),
            },
            "status": (
                "available"
                if isinstance(available_connections, int) and available_connections > 0
                else "initializing"
            ),
            "timestamp": pool_stats.get("timestamp", ""),
        }

    except Exception as e:
        logger.error(f"Error getting IB status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting IB status: {str(e)}"
        ) from e


@router.get("/system-status")
async def get_system_status() -> dict[str, Any]:
    """
    Get overall system status.

    Returns a comprehensive view of all background services
    and their current state.
    """
    try:
        # Get IB connection status from pool
        # TODO: Implement with new IB architecture
        pool_stats = {"note": "New IB architecture - pool stats not yet implemented"}
        available_conns = pool_stats.get("available_connections", 0)
        ib_connected = isinstance(available_conns, int) and available_conns > 0

        # Determine overall health
        overall_health = "healthy" if ib_connected else "degraded"

        return {
            "status": "ok",
            "health": overall_health,
            "services": {
                "ib_connection": {
                    "status": "connected" if ib_connected else "disconnected",
                    "healthy": ib_connected,
                },
            },
            "summary": {
                "ib_connected": ib_connected,
            },
        }

    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting system status: {str(e)}"
        ) from e


@router.get("/status")
async def get_system_status_standardized() -> ApiResponse:
    """
    Get overall system status in standardized API format.

    This endpoint provides the same information as /system-status
    but in the standardized API response format expected by tests.
    """
    try:
        # Get IB connection status from pool
        # TODO: Implement with new IB architecture
        pool_stats = {"note": "New IB architecture - pool stats not yet implemented"}
        available_conns = pool_stats.get("available_connections", 0)
        ib_connected = isinstance(available_conns, int) and available_conns > 0

        # Calculate uptime
        uptime_seconds = pool_stats.get("pool_uptime_seconds", 0)

        return ApiResponse(
            success=True,
            data={
                "version": metadata.VERSION,
                "environment": "development",  # Could be made configurable
                "uptime_seconds": uptime_seconds,
                "health": "healthy" if ib_connected else "degraded",
                "services": {
                    "ib_connection": {
                        "status": "connected" if ib_connected else "disconnected",
                        "healthy": ib_connected,
                    },
                },
                "summary": {
                    "ib_connected": ib_connected,
                },
            },
            error=None,
        )

    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting system status: {str(e)}"
        ) from e


@router.get("/config")
async def get_system_config() -> ApiResponse:
    """
    Get system configuration information.

    Returns system-wide configuration details including version,
    environment, and feature settings.
    """
    try:
        # Get configuration details
        from ktrdr.api.config import APIConfig

        api_config = APIConfig()

        return ApiResponse(
            success=True,
            data={
                "version": metadata.VERSION,
                "environment": api_config.environment,
                "api_version": "v1",
                "api_prefix": api_config.api_prefix,
                "host": api_config.host,
                "port": api_config.port,
                "cors_origins": api_config.cors_origins,
                "features_enabled": [
                    "ib_integration",
                    "symbol_validation",
                    "data_loading",
                    "strategy_management",
                    "backtesting",
                    "neural_networks",
                    "fuzzy_logic",
                ],
                "services_available": [
                    "connection_pool",
                    "pace_manager",
                    "symbol_validator",
                    "data_fetcher",
                ],
            },
            error=None,
        )

    except Exception as e:
        logger.error(f"Error getting system config: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting system config: {str(e)}"
        ) from e
