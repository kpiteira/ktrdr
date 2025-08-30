"""
IB (Interactive Brokers) endpoints for the KTRDR API.

This module implements the API endpoints for IB status, health monitoring,
and connection management.
"""

import asyncio
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from ktrdr import get_logger
from ktrdr.api.models.base import ApiResponse, ErrorResponse
from ktrdr.api.models.ib import (
    DiscoveredSymbolsApiResponse,
    DiscoveredSymbolsResponse,
    IbConfigApiResponse,
    IbConfigUpdateApiResponse,
    IbConfigUpdateRequest,
    IbDataRangesApiResponse,
    IbHealthApiResponse,
    IbStatusApiResponse,
    SymbolDiscoveryApiResponse,
    SymbolDiscoveryRequest,
    SymbolDiscoveryResponse,
    SymbolInfo,
)
from ktrdr.api.services.ib_service import IbService

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
        status = await ib_service.get_status()
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
        health = await ib_service.get_health()

        # Return appropriate HTTP status based on health
        if not health.healthy:
            # Use HTTPException for proper FastAPI error handling
            from fastapi import HTTPException
            raise HTTPException(
                status_code=503,
                detail=f"IB connection is unhealthy: {health.error_message}"
            )

        return ApiResponse(success=True, data=health, error=None)

    except Exception as e:
        logger.error(f"Error checking IB health: {e}")
        from fastapi import HTTPException
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check IB health: {str(e)}"
        )


@router.get(
    "/resilience",
    response_model=ApiResponse[dict[str, Any]],
    summary="Get IB Connection Resilience Status",
    description="Get detailed status of connection resilience features including validation, garbage collection, and Client ID preference",
)
async def get_ib_resilience_status(
    ib_service: IbService = Depends(get_ib_service),
) -> ApiResponse[dict[str, Any]]:
    """
    Get comprehensive connection resilience status.

    Tests and reports on all connection resilience phases:
    - Phase 1: Systematic connection validation before handoff
    - Phase 2: Garbage collection with 5-minute idle timeout
    - Phase 3: Client ID 1 preference with incremental fallback

    Returns detailed metrics and an overall resilience score (0-100).
    """
    logger.info("🔍 PHASE 4: IB resilience status endpoint accessed")

    try:
        resilience_status = await ib_service.get_connection_resilience_status()

        # Return success response
        return ApiResponse(success=True, data=resilience_status, error=None)

    except Exception as e:
        logger.error(f"Error getting IB resilience status: {e}")
        from fastapi import HTTPException
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get IB resilience status: {str(e)}"
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
        config = await ib_service.get_config()
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


@router.get(
    "/circuit-breakers",
    response_model=ApiResponse[dict[str, Any]],
    tags=["IB", "Monitoring"],
    summary="Get circuit breaker status",
    description="Returns the status of all IB operation circuit breakers for monitoring silent connection issues.",
)
async def get_circuit_breaker_status() -> ApiResponse[dict[str, Any]]:
    """
    Get status of all IB circuit breakers.

    This endpoint provides visibility into circuit breaker states,
    helping diagnose IB connectivity issues and silent connections.

    Returns:
        ApiResponse with circuit breaker status information
    """
    try:
        from ktrdr.api.utils.circuit_breaker import get_all_circuit_breakers

        breakers = get_all_circuit_breakers()
        breaker_status = {
            name: breaker.get_status() for name, breaker in breakers.items()
        }

        return ApiResponse(
            success=True,
            data={
                "circuit_breakers": breaker_status,
                "summary": {
                    "total_breakers": len(breakers),
                    "open_breakers": len(
                        [b for b in breakers.values() if b.state.value == "open"]
                    ),
                    "half_open_breakers": len(
                        [b for b in breakers.values() if b.state.value == "half_open"]
                    ),
                },
            },
            error=None,
        )
    except Exception as e:
        logger.error(f"Error getting circuit breaker status: {e}")
        return ApiResponse(
            success=False,
            data=None,
            error=ErrorResponse(
                code="CIRCUIT-BREAKER-STATUS-ERROR",
                message="Failed to get circuit breaker status",
                details={"error": str(e)},
            ),
        )


@router.post(
    "/cleanup",
    response_model=ApiResponse[dict[str, Any]],
    tags=["IB"],
    summary="Clean up IB connections",
    description="Forcefully disconnects all active IB connections. Useful for troubleshooting connection issues.",
)
async def cleanup_ib_connections(
    ib_service: IbService = Depends(get_ib_service),
) -> ApiResponse[dict[str, Any]]:
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
        ranges_response = await ib_service.get_data_ranges(symbol_list, timeframe_list)

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


@router.post(
    "/symbols/discover",
    response_model=SymbolDiscoveryApiResponse,
    tags=["IB", "Symbols"],
    summary="Discover symbol information",
    description="Discovers and caches symbol information including instrument type, exchange, and contract details from Interactive Brokers.",
)
async def discover_symbol(
    request: SymbolDiscoveryRequest,
    ib_service: IbService = Depends(get_ib_service),
) -> SymbolDiscoveryApiResponse:
    """
    Discover symbol information from Interactive Brokers.

    This endpoint validates a symbol against IB's contract database and returns
    detailed information including instrument type, exchange, and description.
    Results are cached to improve performance on subsequent requests.

    Args:
        request: Symbol discovery request with symbol and optional force_refresh

    Returns:
        SymbolDiscoveryApiResponse with symbol information or null if not found

    Raises:
        HTTPException: If discovery operation fails
    """
    import time

    start_time = time.time()

    try:
        logger.info(f"Discovering symbol: {request.symbol}")

        # Discover symbol using IB service with circuit breaker for resilience
        try:
            from ktrdr.api.utils.circuit_breaker import (
                CircuitBreakerOpenError,
                with_circuit_breaker,
            )

            symbol_info_dict = await with_circuit_breaker(
                "ib_symbol_discovery",
                ib_service.discover_symbol,
                symbol=request.symbol,
                force_refresh=request.force_refresh,
            )
        except CircuitBreakerOpenError as e:
            logger.error(
                f"Symbol discovery circuit breaker OPEN for {request.symbol}: {e}"
            )

            # Perform rapid diagnosis to give clear error message
            # Old diagnosis utility removed - using basic error handling

            # Use simplified error handling without old diagnosis utility
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "IB-CIRCUIT-BREAKER",
                    "message": f"Symbol discovery circuit breaker OPEN for {request.symbol}",
                    "details": {"symbol": request.symbol, "reason": str(e)},
                },
            ) from None
        except asyncio.TimeoutError:
            logger.error(
                f"Symbol discovery TIMEOUT for {request.symbol} - possible silent IB connection!"
            )
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "IB-TIMEOUT",
                    "message": f"Symbol discovery timed out for {request.symbol}",
                    "details": {
                        "symbol": request.symbol,
                        "timeout_seconds": 30,
                        "possible_cause": "IB connection appears connected but operations timeout - check IB Gateway connectivity",
                    },
                },
            ) from None

        discovery_time_ms = (time.time() - start_time) * 1000

        if symbol_info_dict is None:
            # Symbol not found
            return SymbolDiscoveryApiResponse(
                success=True,
                data=SymbolDiscoveryResponse(
                    symbol_info=None, cached=False, discovery_time_ms=discovery_time_ms
                ),
                error=None
            )

        # Convert dict to SymbolInfo model
        symbol_info = SymbolInfo(**symbol_info_dict)

        # Determine if result was cached (heuristic based on discovery time)
        cached = discovery_time_ms < 50  # Fast response usually indicates cache hit

        return SymbolDiscoveryApiResponse(
            success=True,
            data=SymbolDiscoveryResponse(
                symbol_info=symbol_info,
                cached=cached,
                discovery_time_ms=discovery_time_ms,
            ),
            error=None
        )

    except Exception as e:
        logger.error(f"Symbol discovery failed for {request.symbol}: {e}")
        return SymbolDiscoveryApiResponse(
            success=False,
            data=None,
            error=ErrorResponse(
                code="IB-SYMBOL-DISCOVERY-ERROR",
                message=f"Failed to discover symbol '{request.symbol}'",
                details={"symbol": request.symbol, "error": str(e)},
            ),
        )


@router.get(
    "/symbols/discovered",
    response_model=DiscoveredSymbolsApiResponse,
    tags=["IB", "Symbols"],
    summary="Get discovered symbols",
    description="Returns all symbols that have been discovered and cached, with optional filtering by instrument type.",
)
async def get_discovered_symbols(
    instrument_type: Optional[str] = Query(
        None,
        description="Filter by instrument type (e.g., 'stock', 'forex', 'futures')",
    ),
    ib_service: IbService = Depends(get_ib_service),
) -> DiscoveredSymbolsApiResponse:
    """
    Get all discovered symbols from the cache.

    This endpoint returns symbols that have been previously discovered and cached
    by the symbol discovery system. Results can be filtered by instrument type.

    Args:
        instrument_type: Optional filter by instrument type

    Returns:
        DiscoveredSymbolsApiResponse with list of cached symbols and statistics

    Raises:
        HTTPException: If operation fails
    """
    try:
        logger.info(f"Getting discovered symbols (filter: {instrument_type})")

        # Get discovered symbols from IB service
        symbols_data = ib_service.get_discovered_symbols(
            instrument_type=instrument_type
        )

        # Convert to SymbolInfo models
        symbols = [SymbolInfo(**symbol_dict) for symbol_dict in symbols_data]

        # Count by instrument type
        instrument_type_counts = {}
        for symbol in symbols:
            instrument_type_counts[symbol.instrument_type] = (
                instrument_type_counts.get(symbol.instrument_type, 0) + 1
            )

        # Get cache statistics
        cache_stats = ib_service.get_symbol_discovery_stats()

        return DiscoveredSymbolsApiResponse(
            success=True,
            data=DiscoveredSymbolsResponse(
                symbols=symbols,
                total_count=len(symbols),
                instrument_types=instrument_type_counts,
                cache_stats=cache_stats,
            ),
            error=None
        )

    except Exception as e:
        logger.error(f"Failed to get discovered symbols: {e}")
        return DiscoveredSymbolsApiResponse(
            success=False,
            data=None,
            error=ErrorResponse(
                code="IB-DISCOVERED-SYMBOLS-ERROR",
                message="Failed to get discovered symbols",
                details={"instrument_type": instrument_type, "error": str(e)},
            ),
        )
