"""
System status endpoints for monitoring background services.

Provides endpoints to monitor:
- IB connection status
- Gap filling service status
- Overall system health
"""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException

from ktrdr.logging import get_logger
from ktrdr.data.ib_connection_manager import get_connection_manager
from ktrdr.data.ib_gap_filler import get_gap_filler

logger = get_logger(__name__)

# Create router for system endpoints
router = APIRouter()


@router.get("/ib-status")
async def get_ib_status() -> Dict[str, Any]:
    """
    Get Interactive Brokers connection status.

    Returns detailed information about the persistent IB connection
    including connection state, client ID, retry attempts, etc.
    """
    try:
        connection_manager = get_connection_manager()
        status = connection_manager.get_status()
        metrics = connection_manager.get_metrics()

        # Get actual IB connection state
        connection = connection_manager.get_connection()
        actual_connected = False
        ib_connection_details = None

        if connection:
            try:
                # Test actual IB connection using ib_insync's isConnected()
                actual_connected = connection.ib.isConnected()

                if actual_connected:
                    ib_connection_details = {
                        "connection_verified": True,
                        "transport_open": not hasattr(connection.ib.client, "conn")
                        or (
                            hasattr(connection.ib.client.conn, "is_closing")
                            and not connection.ib.client.conn.is_closing()
                        ),
                    }
            except Exception as e:
                logger.warning(f"Error testing actual IB connection: {e}")
                actual_connected = False

        return {
            "status": "ok",
            "ib_connection": {
                "manager_thinks_connected": status.connected,  # Our internal state
                "actually_connected": actual_connected,  # Real IB state
                "connection_mismatch": status.connected != actual_connected,
                "client_id": status.client_id,
                "host": status.host,
                "port": status.port,
                "last_connect_time": (
                    status.last_connect_time.isoformat()
                    if status.last_connect_time
                    else None
                ),
                "last_disconnect_time": (
                    status.last_disconnect_time.isoformat()
                    if status.last_disconnect_time
                    else None
                ),
                "connection_attempts": status.connection_attempts,
                "failed_attempts": status.failed_attempts,
                "current_attempt": status.current_attempt,
                "next_retry_time": (
                    status.next_retry_time.isoformat()
                    if status.next_retry_time
                    else None
                ),
                "ib_details": ib_connection_details,
            },
            "metrics": metrics,
        }

    except Exception as e:
        logger.error(f"Error getting IB status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting IB status: {str(e)}"
        )


@router.get("/gap-filler-status")
async def get_gap_filler_status() -> Dict[str, Any]:
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
async def get_system_status() -> Dict[str, Any]:
    """
    Get overall system status.

    Returns a comprehensive view of all background services
    and their current state.
    """
    try:
        # Get IB connection status
        connection_manager = get_connection_manager()
        ib_connected = connection_manager.is_connected()

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


@router.post("/gap-filler/force-scan")
async def force_gap_scan() -> Dict[str, Any]:
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
