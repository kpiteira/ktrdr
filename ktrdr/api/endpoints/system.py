"""
System status endpoints for monitoring background services.

Provides endpoints to monitor:
- IB connection status
- Gap filling service status
- Overall system health
"""

from typing import Any

from fastapi import APIRouter, HTTPException

from ktrdr import metadata
from ktrdr.api.models.base import ApiResponse

# Old architecture removed - using new ktrdr.ib module
from ktrdr.data.ib_gap_filler import get_gap_filler
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

        return {
            "success": True,
            "connection_pool": {
                "available_connections": pool_stats.get("available_connections", 0),
                "total_connections": pool_stats.get("total_connections", 0),
                "failed_connections": pool_stats.get("failed_connections", 0),
                "host": pool_stats.get("host", ""),
                "port": pool_stats.get("port", 0),
                "uptime_seconds": pool_stats.get("uptime_seconds", 0),
                "created_at": pool_stats.get("created_at", ""),
            },
            "status": (
                "available"
                if pool_stats.get("available_connections", 0) > 0
                else "initializing"
            ),
            "timestamp": pool_stats.get("timestamp", ""),
        }

    except Exception as e:
        logger.error(f"Error getting IB status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting IB status: {str(e)}"
        )


@router.get("/gap-filler-status")
async def get_gap_filler_status() -> dict[str, Any]:
    """
    Get gap filling service status.

    Returns information about the automatic gap filling service
    including statistics on gaps detected and filled.
    """
    try:
        gap_filler = get_gap_filler()
        stats = gap_filler.get_stats()

        return {
            "status": "ok",
            "gap_filler": {
                "running": stats["running"],
                "check_interval": stats["check_interval"],
                "supported_timeframes": stats["supported_timeframes"],
                "last_scan_time": (
                    stats["last_scan_time"].isoformat()
                    if stats["last_scan_time"]
                    else None
                ),
            },
            "statistics": {
                "gaps_detected": stats["gaps_detected"],
                "gaps_filled": stats["gaps_filled"],
                "gaps_failed": stats["gaps_failed"],
                "symbols_processed": stats["symbols_processed"],
                "recent_errors": [
                    {"time": error["time"].isoformat(), "error": error["error"]}
                    for error in stats.get("errors", [])
                ],
            },
        }

    except Exception as e:
        logger.error(f"Error getting gap filler status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting gap filler status: {str(e)}"
        )


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
        ib_connected = pool_stats.get("available_connections", 0) > 0

        # Get gap filler status
        gap_filler = get_gap_filler()
        gap_filler_stats = gap_filler.get_stats()
        gap_filler_running = gap_filler_stats["running"]

        # Determine overall health
        overall_health = "healthy"
        if not ib_connected and not gap_filler_running:
            overall_health = "critical"
        elif not ib_connected or not gap_filler_running:
            overall_health = "degraded"

        return {
            "status": "ok",
            "health": overall_health,
            "services": {
                "ib_connection": {
                    "status": "connected" if ib_connected else "disconnected",
                    "healthy": ib_connected,
                },
                "gap_filler": {
                    "status": "running" if gap_filler_running else "stopped",
                    "healthy": gap_filler_running,
                },
            },
            "summary": {
                "ib_connected": ib_connected,
                "gap_filler_running": gap_filler_running,
                "gaps_filled_today": gap_filler_stats.get("gaps_filled", 0),
                "symbols_processed": len(gap_filler_stats.get("symbols_processed", [])),
            },
        }

    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting system status: {str(e)}"
        )


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
        ib_connected = pool_stats.get("available_connections", 0) > 0

        # Get gap filler status
        gap_filler = get_gap_filler()
        gap_filler_stats = gap_filler.get_stats()
        gap_filler_running = gap_filler_stats["running"]

        # Calculate uptime
        uptime_seconds = pool_stats.get("pool_uptime_seconds", 0)

        return ApiResponse(
            success=True,
            data={
                "version": metadata.VERSION,
                "environment": "development",  # Could be made configurable
                "uptime_seconds": uptime_seconds,
                "health": (
                    "healthy" if ib_connected and gap_filler_running else "degraded"
                ),
                "services": {
                    "ib_connection": {
                        "status": "connected" if ib_connected else "disconnected",
                        "healthy": ib_connected,
                    },
                    "gap_filler": {
                        "status": "running" if gap_filler_running else "stopped",
                        "healthy": gap_filler_running,
                    },
                },
                "summary": {
                    "ib_connected": ib_connected,
                    "gap_filler_running": gap_filler_running,
                    "gaps_filled_today": gap_filler_stats.get("gaps_filled", 0),
                    "symbols_processed": len(
                        gap_filler_stats.get("symbols_processed", [])
                    ),
                },
            },
        )

    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting system status: {str(e)}"
        )


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
                    "gap_filling",
                    "symbol_validation",
                    "data_loading",
                    "strategy_management",
                    "backtesting",
                    "neural_networks",
                    "fuzzy_logic",
                ],
                "services_available": [
                    "connection_pool",
                    "gap_filler",
                    "pace_manager",
                    "symbol_validator",
                    "data_fetcher",
                ],
            },
        )

    except Exception as e:
        logger.error(f"Error getting system config: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting system config: {str(e)}"
        )


@router.post("/gap-filler/force-scan")
async def force_gap_scan() -> dict[str, Any]:
    """
    Force an immediate gap scan.

    Triggers the gap filling service to immediately scan for
    and attempt to fill data gaps. Useful for testing or
    when immediate gap filling is needed.
    """
    try:
        gap_filler = get_gap_filler()
        result = gap_filler.force_scan()

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return {"status": "ok", "message": "Gap scan completed", "result": result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error forcing gap scan: {e}")
        raise HTTPException(status_code=500, detail=f"Error forcing gap scan: {str(e)}")
