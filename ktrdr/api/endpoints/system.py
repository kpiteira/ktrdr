"""
System status endpoints for monitoring background services.

Provides endpoints to monitor:
- IB connection status
- Overall system health
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ktrdr.api.models.base import ApiResponse
from ktrdr.api.services.ib_service import IbService
from ktrdr.logging import get_logger
from ktrdr.version import __version__

logger = get_logger(__name__)

# Create router for system endpoints
router = APIRouter()


def get_ib_service() -> IbService:
    """Dependency to get IB service instance."""
    return IbService()


@router.get("/ib-status")
async def get_ib_status(
    ib_service: IbService = Depends(get_ib_service),
) -> dict[str, Any]:
    """
    Get Interactive Brokers connection status.

    Returns detailed information about the connection pool status,
    active connections, and pool metrics.
    """
    try:
        # Get real IB status via IbService (which queries the IB host service)
        status = await ib_service.get_status()

        # Extract connection info
        connection = status.connection
        metrics = status.connection_metrics

        return {
            "success": True,
            "connection_pool": {
                "available_connections": 1 if connection.connected else 0,
                "total_connections": metrics.total_connections,
                "failed_connections": metrics.failed_connections,
                "host": connection.host,
                "port": connection.port,
                "uptime_seconds": metrics.uptime_seconds or 0,
                "created_at": (
                    connection.connection_time.isoformat()
                    if connection.connection_time
                    else ""
                ),
            },
            "status": "available" if connection.connected else "disconnected",
            "ib_available": status.ib_available,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting IB status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting IB status: {str(e)}"
        ) from e


@router.get("/system-status")
async def get_system_status(
    ib_service: IbService = Depends(get_ib_service),
) -> dict[str, Any]:
    """
    Get overall system status.

    Returns a comprehensive view of all background services
    and their current state.
    """
    try:
        # Get real IB status via IbService
        status = await ib_service.get_status()
        ib_connected = status.connection.connected
        ib_available = status.ib_available

        # Determine overall health
        # System is healthy if IB is available, degraded otherwise
        overall_health = "healthy" if ib_available else "degraded"

        return {
            "status": "ok",
            "health": overall_health,
            "services": {
                "ib_connection": {
                    "status": "connected" if ib_connected else "disconnected",
                    "healthy": ib_available,
                    "host": status.connection.host,
                },
            },
            "summary": {
                "ib_connected": ib_connected,
                "ib_available": ib_available,
            },
        }

    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting system status: {str(e)}"
        ) from e


@router.get("/status")
async def get_system_status_standardized(
    ib_service: IbService = Depends(get_ib_service),
) -> ApiResponse:
    """
    Get overall system status in standardized API format.

    This endpoint provides the same information as /system-status
    but in the standardized API response format expected by tests.
    """
    try:
        # Get real IB status via IbService
        status = await ib_service.get_status()
        ib_connected = status.connection.connected
        ib_available = status.ib_available

        # Calculate uptime from connection metrics
        uptime_seconds = status.connection_metrics.uptime_seconds or 0

        return ApiResponse(
            success=True,
            data={
                "version": __version__,
                "environment": "development",  # Could be made configurable
                "uptime_seconds": uptime_seconds,
                "health": "healthy" if ib_available else "degraded",
                "services": {
                    "ib_connection": {
                        "status": "connected" if ib_connected else "disconnected",
                        "healthy": ib_available,
                        "host": status.connection.host,
                    },
                },
                "summary": {
                    "ib_connected": ib_connected,
                    "ib_available": ib_available,
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
        from ktrdr.config.settings import get_api_settings

        api_config = get_api_settings()

        return ApiResponse(
            success=True,
            data={
                "version": __version__,
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
