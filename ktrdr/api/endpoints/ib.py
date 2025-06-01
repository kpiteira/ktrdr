"""
IB (Interactive Brokers) endpoints for the KTRDR API.

This module implements the API endpoints for IB status, health monitoring,
and connection management.
"""

from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from ktrdr import get_logger
from ktrdr.api.services.ib_service import IbService
from ktrdr.api.models.ib import (
    IbStatusApiResponse,
    IbHealthApiResponse,
    IbConfigApiResponse,
    IbConfigUpdateApiResponse,
    IbDataRangesApiResponse,
    IbStatusResponse,
    IbHealthStatus,
    IbConfigInfo,
    IbConfigUpdateRequest,
    IbConfigUpdateResponse,
    DataRangesResponse,
)
from ktrdr.api.models.base import ApiResponse, ErrorResponse

# Setup module-level logger
logger = get_logger(__name__)

# Create router for IB endpoints
router = APIRouter()


def get_ib_service() -> IbService:
    """Dependency to get IB service instance."""
    return IbService()


@router.get(
    "/status",
    response_model=IbStatusApiResponse,
    tags=["IB"],
    summary="Get IB connection status",
    description="Returns comprehensive status information about the IB connection including metrics and health indicators.",
)
async def get_ib_status(
    ib_service: IbService = Depends(get_ib_service),
) -> IbStatusApiResponse:
    """
    Get IB connection status and metrics.

    Returns detailed information about:
    - Current connection status
    - Connection performance metrics
    - Data fetching performance metrics
    - Overall IB availability

    Returns:
        IbStatusApiResponse with comprehensive status information
    """
    try:
        status = ib_service.get_status()
        return ApiResponse(success=True, data=status, error=None)
    except Exception as e:
        logger.error(f"Error getting IB status: {e}")
        return ApiResponse(
            success=False,
            data=None,
            error=ErrorResponse(
                code="IB-STATUS-ERROR",
                message="Failed to get IB status",
                details={"error": str(e)},
            ),
        )


@router.get(
    "/health",
    response_model=IbHealthApiResponse,
    tags=["IB"],
    summary="Check IB health",
    description="Performs a health check on the IB connection and returns the overall health status.",
)
async def check_ib_health(
    ib_service: IbService = Depends(get_ib_service),
) -> IbHealthApiResponse:
    """
    Check IB connection health.

    Performs health checks on:
    - Connection status
    - Data fetching capability
    - Recent request success rate

    Returns:
        IbHealthApiResponse with health status
    """
    try:
        health = ib_service.get_health()

        # Return appropriate HTTP status based on health
        if not health.healthy:
            return JSONResponse(
                status_code=503,  # Service Unavailable
                content=ApiResponse(
                    success=False,
                    data=health,
                    error=ErrorResponse(
                        code="IB-UNHEALTHY",
                        message="IB connection is unhealthy",
                        details={"error_message": health.error_message},
                    ),
                ).model_dump(),
            )

        return ApiResponse(success=True, data=health, error=None)

    except Exception as e:
        logger.error(f"Error checking IB health: {e}")
        return JSONResponse(
            status_code=500,
            content=ApiResponse(
                success=False,
                data=None,
                error=ErrorResponse(
                    code="IB-HEALTH-ERROR",
                    message="Failed to check IB health",
                    details={"error": str(e)},
                ),
            ).model_dump(),
        )


@router.get(
    "/config",
    response_model=IbConfigApiResponse,
    tags=["IB"],
    summary="Get IB configuration",
    description="Returns the current IB configuration settings.",
)
async def get_ib_config(
    ib_service: IbService = Depends(get_ib_service),
) -> IbConfigApiResponse:
    """
    Get IB configuration information.

    Returns configuration details including:
    - Connection settings (host, port)
    - Client ID range
    - Timeout settings
    - Rate limiting configuration

    Returns:
        IbConfigApiResponse with configuration information
    """
    try:
        config = ib_service.get_config()
        return ApiResponse(success=True, data=config, error=None)
    except Exception as e:
        logger.error(f"Error getting IB config: {e}")
        return ApiResponse(
            success=False,
            data=None,
            error=ErrorResponse(
                code="IB-CONFIG-ERROR",
                message="Failed to get IB configuration",
                details={"error": str(e)},
            ),
        )


@router.post(
    "/cleanup",
    response_model=ApiResponse[Dict[str, Any]],
    tags=["IB"],
    summary="Clean up IB connections",
    description="Forcefully disconnects all active IB connections. Useful for troubleshooting connection issues.",
)
async def cleanup_ib_connections(
    ib_service: IbService = Depends(get_ib_service),
) -> ApiResponse[Dict[str, Any]]:
    """
    Clean up all IB connections.

    This endpoint forcefully disconnects all active IB connections,
    which can be useful when:
    - Connections are stuck
    - Testing requires a clean state
    - Troubleshooting connection issues

    Returns:
        ApiResponse with cleanup results
    """
    try:
        result = await ib_service.cleanup_connections()

        if result["success"]:
            return ApiResponse(success=True, data=result, error=None)
        else:
            return ApiResponse(
                success=False,
                data=result,
                error=ErrorResponse(
                    code="IB-CLEANUP-FAILED", message=result["message"], details=result
                ),
            )

    except Exception as e:
        logger.error(f"Error cleaning up IB connections: {e}")
        return ApiResponse(
            success=False,
            data=None,
            error=ErrorResponse(
                code="IB-CLEANUP-ERROR",
                message="Failed to clean up IB connections",
                details={"error": str(e)},
            ),
        )


@router.put(
    "/config",
    response_model=IbConfigUpdateApiResponse,
    tags=["IB"],
    summary="Update IB configuration",
    description="Updates the IB connection configuration. May require reconnection for changes to take effect.",
)
async def update_ib_config(
    request: IbConfigUpdateRequest, ib_service: IbService = Depends(get_ib_service)
) -> IbConfigUpdateApiResponse:
    """
    Update IB configuration dynamically.

    Allows updating:
    - Port (4002=IB Gateway Paper, 4001=IB Gateway Live, 7497=TWS Paper, 7496=TWS Live)
    - Host address
    - Client ID

    The response indicates whether reconnection is required for the changes
    to take effect.

    Returns:
        IbConfigUpdateApiResponse with previous and new configuration
    """
    try:
        result = await ib_service.update_config(request)
        return ApiResponse(success=True, data=result, error=None)
    except Exception as e:
        logger.error(f"Error updating IB config: {e}")
        return ApiResponse(
            success=False,
            data=None,
            error=ErrorResponse(
                code="IB-CONFIG-UPDATE-ERROR",
                message="Failed to update IB configuration",
                details={"error": str(e)},
            ),
        )


@router.get(
    "/ranges",
    response_model=IbDataRangesApiResponse,
    tags=["IB"],
    summary="Get historical data ranges for symbols",
    description="Discovers the earliest and latest available data for symbols and timeframes using binary search.",
)
async def get_data_ranges(
    symbols: str = Query(
        ..., description="Comma-separated list of symbols (e.g., 'AAPL,MSFT')"
    ),
    timeframes: str = Query(
        default="1d", description="Comma-separated list of timeframes (e.g., '1d,1h')"
    ),
    ib_service: IbService = Depends(get_ib_service),
) -> IbDataRangesApiResponse:
    """
    Get historical data ranges for symbols and timeframes.

    This endpoint discovers the earliest available data for the specified symbols
    using a binary search algorithm. Results are cached for 24 hours to improve
    performance on subsequent requests.

    Supported timeframes: 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w

    Returns:
        IbDataRangesApiResponse with range information for each symbol/timeframe
    """
    try:
        # Parse comma-separated inputs
        symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
        timeframe_list = [t.strip().lower() for t in timeframes.split(",") if t.strip()]

        if not symbol_list:
            return ApiResponse(
                success=False,
                data=None,
                error=ErrorResponse(
                    code="IB-RANGES-INVALID-SYMBOLS",
                    message="No valid symbols provided",
                    details={"symbols": symbols},
                ),
            )

        if not timeframe_list:
            return ApiResponse(
                success=False,
                data=None,
                error=ErrorResponse(
                    code="IB-RANGES-INVALID-TIMEFRAMES",
                    message="No valid timeframes provided",
                    details={"timeframes": timeframes},
                ),
            )

        # Validate timeframes
        valid_timeframes = {"1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"}
        invalid_timeframes = [tf for tf in timeframe_list if tf not in valid_timeframes]
        if invalid_timeframes:
            return ApiResponse(
                success=False,
                data=None,
                error=ErrorResponse(
                    code="IB-RANGES-UNSUPPORTED-TIMEFRAMES",
                    message=f"Unsupported timeframes: {', '.join(invalid_timeframes)}",
                    details={
                        "invalid_timeframes": invalid_timeframes,
                        "valid_timeframes": list(valid_timeframes),
                    },
                ),
            )

        # Get data ranges
        ranges_response = ib_service.get_data_ranges(symbol_list, timeframe_list)

        return ApiResponse(success=True, data=ranges_response, error=None)

    except ValueError as e:
        logger.error(f"Error getting data ranges: {e}")
        return ApiResponse(
            success=False,
            data=None,
            error=ErrorResponse(
                code="IB-RANGES-UNAVAILABLE", message=str(e), details={"error": str(e)}
            ),
        )

    except Exception as e:
        logger.error(f"Error getting data ranges: {e}")
        return ApiResponse(
            success=False,
            data=None,
            error=ErrorResponse(
                code="IB-RANGES-ERROR",
                message="Failed to get data ranges",
                details={"error": str(e)},
            ),
        )


