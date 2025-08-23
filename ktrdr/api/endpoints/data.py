"""
Data endpoints for the KTRDR API.

This module implements the API endpoints for accessing market data, symbols, and timeframes.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from ktrdr import get_logger
from ktrdr.api.dependencies import get_data_service
from ktrdr.api.models.base import ApiResponse
from ktrdr.api.models.data import (
    DataLoadApiResponse,
    DataLoadOperationResponse,
    DataLoadRequest,
    DataLoadResponse,
    DataRangeInfo,
    DataRangeRequest,
    DataRangeResponse,
    OHLCVData,
    SymbolInfo,
    SymbolsResponse,
    TimeframeInfo,
    TimeframesResponse,
)
from ktrdr.api.services.data_service import DataService
from ktrdr.errors import DataError, DataNotFoundError

# Setup module-level logger
logger = get_logger(__name__)

# Create router for data endpoints
router = APIRouter()


@router.get(
    "/data/info",
    response_model=ApiResponse,
    tags=["Data"],
    summary="Get data directory information",
    description="Returns information about the data directory, available symbols, and data statistics.",
)
async def get_data_info(
    data_service: DataService = Depends(get_data_service),
) -> ApiResponse:
    """
    Get comprehensive data directory information.

    Returns statistics about available symbols, data directory location,
    and data availability across different timeframes.
    """
    try:
        # Get available symbols directly from service
        available_symbols = await data_service.get_available_symbols()

        # Get available timeframes directly from service
        available_timeframes = await data_service.get_available_timeframes()

        # Get data directory from configuration
        data_directory = "data"  # Default
        try:
            from ktrdr.config.loader import ConfigLoader

            config_loader = ConfigLoader()
            config = config_loader.load_from_env(default_path="config/settings.yaml")
            if hasattr(config, "data") and hasattr(config.data, "directory"):
                data_directory = config.data.directory
        except Exception:
            pass

        # Calculate statistics
        total_symbols = len(available_symbols)
        symbol_types = {}
        symbol_names = []

        for symbol in available_symbols:
            # Handle both string and object types
            if hasattr(symbol, "symbol"):
                symbol_name = symbol.symbol
                instrument_type = getattr(symbol, "instrument_type", "unknown")
            else:
                symbol_name = str(symbol)
                instrument_type = "unknown"

            symbol_names.append(symbol_name)
            symbol_types[instrument_type] = symbol_types.get(instrument_type, 0) + 1

        # Handle timeframes
        timeframe_names = []
        for tf in available_timeframes:
            if hasattr(tf, "timeframe"):
                timeframe_names.append(tf.timeframe)
            else:
                timeframe_names.append(str(tf))

        return ApiResponse(
            success=True,
            data={
                "data_directory": data_directory,
                "total_symbols": total_symbols,
                "available_symbols": symbol_names,
                "symbol_types": symbol_types,
                "timeframes_available": timeframe_names,
                "total_timeframes": len(timeframe_names),
                "data_sources": ["local_files", "ib_gateway"],
                "features": [
                    "symbol_discovery",
                    "data_validation",
                    "gap_filling",
                    "real_time_updates",
                ],
            },
        )

    except Exception as e:
        logger.error(f"Error getting data info: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error getting data information: {str(e)}"
        )


@router.get(
    "/symbols",
    response_model=SymbolsResponse,
    tags=["Data"],
    summary="Get available trading symbols",
    description="Returns a list of all available trading symbols with metadata that can be used with the data loading endpoints.",
)
async def get_symbols(
    data_service: DataService = Depends(get_data_service),
) -> SymbolsResponse:
    """
    Get list of available trading symbols.

    Returns a list of symbols that can be used with the data loading endpoint,
    including metadata about each symbol.

    Returns:
        SymbolsResponse: Response containing list of available symbols

    Example response:
        ```json
        {
          "success": true,
          "data": [
            {
              "symbol": "AAPL",
              "name": "Apple Inc.",
              "exchange": "NASDAQ",
              "type": "stock",
              "currency": "USD"
            },
            {
              "symbol": "MSFT",
              "name": "Microsoft Corporation",
              "exchange": "NASDAQ",
              "type": "stock",
              "currency": "USD"
            }
          ]
        }
        ```
    """
    try:
        symbols_data = await data_service.get_available_symbols()

        # Convert to proper model
        symbols = [SymbolInfo(**s) for s in symbols_data]

        logger.info(f"Retrieved {len(symbols)} symbols")
        return SymbolsResponse(success=True, data=symbols)
    except Exception as e:
        logger.error(f"Error retrieving symbols: {str(e)}")
        raise DataError(
            message="Failed to retrieve symbols",
            error_code="DATA-SymbolListError",
            details={"error": str(e)},
        ) from e


@router.get(
    "/timeframes",
    response_model=TimeframesResponse,
    tags=["Data"],
    summary="Get available timeframes",
    description="Returns a list of all available timeframes that can be used with the data loading endpoints.",
)
async def get_timeframes(
    data_service: DataService = Depends(get_data_service),
) -> TimeframesResponse:
    """
    Get list of available timeframes.

    Returns a list of timeframes that can be used with the data loading endpoint,
    including metadata about each timeframe.

    Returns:
        TimeframesResponse: Response containing list of available timeframes

    Example response:
        ```json
        {
          "success": true,
          "data": [
            {
              "id": "1m",
              "name": "1 Minute",
              "seconds": 60,
              "description": "One-minute data"
            },
            {
              "id": "1h",
              "name": "1 Hour",
              "seconds": 3600,
              "description": "One-hour data"
            },
            {
              "id": "1d",
              "name": "1 Day",
              "seconds": 86400,
              "description": "Daily data"
            }
          ]
        }
        ```
    """
    try:
        timeframes_data = await data_service.get_available_timeframes()

        # Convert to proper model
        timeframes = [TimeframeInfo(**t) for t in timeframes_data]

        logger.info(f"Retrieved {len(timeframes)} timeframes")
        return TimeframesResponse(success=True, data=timeframes)
    except Exception as e:
        logger.error(f"Error retrieving timeframes: {str(e)}")
        raise DataError(
            message="Failed to retrieve timeframes",
            error_code="DATA-TimeframeListError",
            details={"error": str(e)},
        ) from e


@router.get(
    "/data/{symbol}/{timeframe}",
    response_model=DataLoadResponse,
    tags=["Data"],
    summary="Get cached OHLCV data (Frontend)",
    description="""
    Retrieves cached OHLCV data for visualization. This endpoint is optimized for frontend use:
    
    **Features:**
    - Fast response (local data only, no external API calls)
    - Returns actual OHLCV data arrays for charting
    - Optional date filtering with query parameters
    - Returns empty data if not cached locally (no errors)
    
    **Perfect for:** Frontend charts, data visualization, dashboards
    """,
)
async def get_cached_data(
    symbol: str = Path(..., description="Trading symbol (e.g. AAPL, MSFT)"),
    timeframe: str = Path(..., description="Data timeframe (e.g. 1d, 1h)"),
    start_date: Optional[str] = Query(
        None, description="Optional start date filter (YYYY-MM-DD)"
    ),
    end_date: Optional[str] = Query(
        None, description="Optional end date filter (YYYY-MM-DD)"
    ),
    trading_hours_only: Optional[bool] = Query(
        False, description="Filter to trading hours only"
    ),
    include_extended: Optional[bool] = Query(
        False, description="Include extended trading hours when filtering"
    ),
    data_service: DataService = Depends(get_data_service),
) -> DataLoadResponse:
    """
    Get cached OHLCV data from local storage for frontend visualization.

    This endpoint retrieves data that has already been fetched and cached locally.
    It does NOT trigger any external operations, making it perfect for frontend
    applications that need fast data display.

    Args:
        symbol: Trading symbol (e.g., 'AAPL', 'MSFT')
        timeframe: Data timeframe (e.g., '1d', '1h')
        start_date: Optional start date for filtering (YYYY-MM-DD format)
        end_date: Optional end date for filtering (YYYY-MM-DD format)
        trading_hours_only: Filter data to trading hours only
        include_extended: Include extended trading hours (pre-market, after-hours)

    Returns:
        DataLoadResponse containing OHLCV data in array format

    Example:
        GET /api/v1/data/AAPL/1d
        GET /api/v1/data/MSFT/1h?start_date=2023-01-01&end_date=2023-06-01
    """
    try:
        logger.info(
            f"Getting cached data for {symbol} ({timeframe}) - frontend request, trading_hours_only={trading_hours_only}, include_extended={include_extended}"
        )

        # Validate symbol
        if not symbol or not symbol.strip():
            raise DataError(
                message="Symbol is required and cannot be empty",
                error_code="DATA-InvalidSymbol",
                details={"symbol": symbol},
            )

        # Clean symbol
        clean_symbol = symbol.strip().upper()

        # Convert string dates to datetime if provided
        start_dt = None
        end_dt = None
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            except ValueError:
                raise DataError(
                    message="Invalid start_date format. Use YYYY-MM-DD",
                    error_code="DATA-InvalidDate",
                    details={"start_date": start_date},
                )
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            except ValueError:
                raise DataError(
                    message="Invalid end_date format. Use YYYY-MM-DD",
                    error_code="DATA-InvalidDate",
                    details={"end_date": end_date},
                )

        # Load data using DataManager with local mode only
        df = data_service.data_manager.load_data(
            symbol=clean_symbol,
            timeframe=timeframe,
            start_date=start_dt,
            end_date=end_dt,
            mode="local",  # Force local only - no external operations
            validate=True,
            repair=False,
        )

        # Apply trading hours filtering if requested
        if trading_hours_only and df is not None and not df.empty:
            try:
                # Get symbol info to access trading hours
                symbols_data = await data_service.get_available_symbols()
                symbol_info = next(
                    (s for s in symbols_data if s.get("symbol") == clean_symbol), None
                )

                if symbol_info and symbol_info.get("trading_hours"):
                    trading_hours = symbol_info["trading_hours"]
                    original_count = len(df)

                    # Apply trading hours filter using the data service helper
                    df = data_service._filter_trading_hours(
                        df, trading_hours, include_extended
                    )

                    filtered_count = len(df) if df is not None else 0
                    logger.info(
                        f"Trading hours filter applied: {original_count} -> {filtered_count} data points (include_extended={include_extended})"
                    )
                else:
                    logger.warning(
                        f"No trading hours info found for {clean_symbol}, skipping trading hours filter"
                    )
            except Exception as e:
                logger.warning(
                    f"Failed to apply trading hours filter for {clean_symbol}: {str(e)}"
                )
                # Continue without filtering on error

        # Convert to API format
        if df is None or df.empty:
            # Return empty data structure
            data = OHLCVData(
                dates=[],
                ohlcv=[],
                metadata={
                    "symbol": clean_symbol,
                    "timeframe": timeframe,
                    "start": "",
                    "end": "",
                    "points": 0,
                },
            )
        else:
            # Convert DataFrame to API format
            api_data = data_service._convert_df_to_api_format(
                df, clean_symbol, timeframe, include_metadata=True
            )
            data = OHLCVData(**api_data)

        logger.info(
            f"Retrieved {len(data.dates)} cached data points for {clean_symbol}"
        )
        return DataLoadResponse(success=True, data=data)

    except DataNotFoundError as e:
        logger.warning(
            f"No cached data found for {clean_symbol} ({timeframe}): {str(e)}"
        )
        # Return empty data instead of error for cached-only endpoint
        data = OHLCVData(
            dates=[],
            ohlcv=[],
            metadata={
                "symbol": clean_symbol,
                "timeframe": timeframe,
                "start": "",
                "end": "",
                "points": 0,
            },
        )
        return DataLoadResponse(success=True, data=data)

    except DataError as e:
        logger.error(f"Data error getting cached data for {clean_symbol}: {str(e)}")
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error getting cached data for {clean_symbol}: {str(e)}"
        )
        raise DataError(
            message=f"Failed to get cached data for {clean_symbol} ({timeframe})",
            error_code="DATA-GetError",
            details={
                "symbol": clean_symbol,
                "timeframe": timeframe,
                "error": str(e),
            },
        ) from e


@router.post(
    "/data/load",
    response_model=DataLoadApiResponse,
    tags=["Data"],
    summary="Load data via DataManager (CLI/Operations)",
    description="""
    Data loading operations endpoint for CLI and background processes.
    
    This endpoint performs actual data loading operations and returns operational
    metrics about what was fetched, from where, and how long it took.
    
    **Loading Modes:**
    - `tail`: Load recent data from last available timestamp to now
    - `backfill`: Load historical data before earliest available timestamp  
    - `full`: Load both historical (backfill) and recent (tail) data
    
    **Features:**
    - Intelligent gap analysis with trading calendar awareness
    - Progressive loading for large date ranges
    - Partial failure resilience (continues with successful segments)
    - Detailed operation metrics and timing
    
    **Perfect for:** CLI commands, background jobs, data management operations
    """,
)
async def load_data(
    request: DataLoadRequest,
    async_mode: bool = Query(False, description="Use async operation tracking"),
    data_service: DataService = Depends(get_data_service),
) -> DataLoadApiResponse:
    """
    Load data using enhanced DataManager with IB integration.

    This endpoint uses the enhanced DataManager which provides:
    - Intelligent gap analysis
    - Smart segmentation for large ranges
    - Trading calendar awareness
    - IB rate limit compliance
    - Partial failure resilience

    **Modes:**
    - Sync mode (async_mode=false): Returns results immediately (default)
    - Async mode (async_mode=true): Returns operation ID for tracking

    Args:
        request: Enhanced data loading request with mode support
        async_mode: Use async operation tracking for cancellable operations

    Returns:
        Detailed response with operation metrics/status or operation ID

    Example request (sync):
        ```json
        {
          "symbol": "AAPL",
          "timeframe": "1h",
          "mode": "tail"
        }
        ```

    Example request (async):
        ```
        POST /api/v1/data/load?async_mode=true
        {
          "symbol": "AAPL",
          "timeframe": "1h",
          "mode": "tail"
        }
        ```

    Example response (sync):
        ```json
        {
          "success": true,
          "data": {
            "status": "success",
            "fetched_bars": 168,
            "execution_time_seconds": 2.456
          }
        }
        ```

    Example response (async):
        ```json
        {
          "success": true,
          "data": {
            "operation_id": "op_data_load_20241201_abc123",
            "status": "started"
          }
        }
        ```
    """
    try:
        # Log user-initiated operation clearly for CLI visibility
        logger.info(
            f"📥 USER OPERATION: Data loading initiated for {request.symbol} ({request.timeframe})"
        )
        logger.info(
            f"Enhanced data loading for {request.symbol} ({request.timeframe}) - mode: {request.mode}, async: {async_mode}"
        )

        # Validate request
        if not request.symbol or not request.symbol.strip():
            raise DataError(
                message="Symbol is required and cannot be empty",
                error_code="DATA-InvalidSymbol",
                details={"symbol": request.symbol},
            )

        # Clean symbol
        clean_symbol = request.symbol.strip().upper()

        # Extract filters from request
        filters_dict = None
        if request.filters:
            filters_dict = {
                "trading_hours_only": request.filters.trading_hours_only,
                "include_extended": request.filters.include_extended,
            }

        if async_mode:
            # Async mode - start operation and return operation ID
            operation_id = await data_service.start_data_loading_operation(
                symbol=clean_symbol,
                timeframe=request.timeframe,
                start_date=request.start_date,
                end_date=request.end_date,
                mode=request.mode,
                filters=filters_dict,
                periodic_save_minutes=request.periodic_save_minutes,
            )

            # Return operation ID for tracking
            response_data = DataLoadOperationResponse(
                operation_id=operation_id,
                status="started",
                fetched_bars=0,
                cached_before=False,
                merged_file="",
                gaps_analyzed=0,
                segments_fetched=0,
                ib_requests_made=0,
                execution_time_seconds=0.0,
                error_message=None,
            )

            logger.info(f"Started async data loading operation: {operation_id}")
            return DataLoadApiResponse(success=True, data=response_data, error=None)

        else:
            # Sync mode - execute immediately and return results
            result = await data_service.load_data(
                symbol=clean_symbol,
                timeframe=request.timeframe,
                start_date=request.start_date,
                end_date=request.end_date,
                mode=request.mode,
                include_metadata=True,
                filters=filters_dict,
                periodic_save_minutes=request.periodic_save_minutes,
            )

        # Convert to response model
        response_data = DataLoadOperationResponse(**result)

        # Determine success based on status
        if result["status"] == "success":
            logger.info(
                f"Successfully loaded {result['fetched_bars']} bars for {clean_symbol}"
            )
            return DataLoadApiResponse(success=True, data=response_data, error=None)
        elif result["status"] == "partial":
            logger.warning(
                f"Partially loaded data for {clean_symbol}: {result.get('error_message', 'Unknown error')}"
            )
            return DataLoadApiResponse(
                success=True,  # Still considered success for partial data
                data=response_data,
                error={
                    "code": "DATA-PartialLoad",
                    "message": "Data loading partially successful",
                    "details": {"error_message": result.get("error_message")},
                },
            )
        else:
            logger.error(
                f"Failed to load data for {clean_symbol}: {result.get('error_message', 'Unknown error')}"
            )
            return DataLoadApiResponse(
                success=False,
                data=response_data,
                error={
                    "code": "DATA-LoadFailed",
                    "message": result.get("error_message", "Data loading failed"),
                    "details": {
                        "symbol": clean_symbol,
                        "timeframe": request.timeframe,
                        "mode": request.mode,
                    },
                },
            )

    except DataError as e:
        logger.error(f"Data error loading {request.symbol}: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error loading {request.symbol}: {str(e)}")
        raise DataError(
            message=f"Failed to load data for {request.symbol} ({request.timeframe})",
            error_code="DATA-LoadError",
            details={
                "symbol": request.symbol,
                "timeframe": request.timeframe,
                "mode": request.mode,
                "error": str(e),
            },
        ) from e


@router.post(
    "/data/range",
    response_model=DataRangeResponse,
    tags=["Data"],
    summary="Get available date range for data",
    description="""
    Retrieves the earliest and latest available dates for the specified symbol and timeframe, 
    along with the total number of data points. Useful for determining what time range is available 
    before loading full data.
    """,
)
async def get_data_range(
    request: DataRangeRequest, data_service: DataService = Depends(get_data_service)
) -> DataRangeResponse:
    """
    Get available date range for a symbol and timeframe.

    Retrieves the earliest and latest available dates for the specified
    symbol and timeframe, along with the total number of data points.

    Args:
        request (DataRangeRequest): Request parameters including symbol and timeframe

    Returns:
        DataRangeResponse: Response containing date range information

    Example request:
        ```json
        {
          "symbol": "AAPL",
          "timeframe": "1d"
        }
        ```

    Example response:
        ```json
        {
          "success": true,
          "data": {
            "symbol": "AAPL",
            "timeframe": "1d",
            "start_date": "2020-01-02T00:00:00",
            "end_date": "2023-04-28T00:00:00",
            "point_count": 840
          }
        }
        ```

    Errors:
        - 404: Data not found for the specified symbol and timeframe
        - 400: Invalid request parameters
        - 500: Server error while retrieving date range
    """
    try:
        logger.info(f"Getting date range for {request.symbol} ({request.timeframe})")

        range_data = await data_service.get_data_range(
            symbol=request.symbol, timeframe=request.timeframe
        )

        # Convert to DataRangeInfo model
        range_info = DataRangeInfo(**range_data)

        logger.info(f"Successfully retrieved date range for {request.symbol}")
        return DataRangeResponse(success=True, data=range_info)
    except DataNotFoundError as e:
        logger.error(f"Data not found: {str(e)}")
        raise HTTPException(
            status_code=404,
            detail=f"Data not found for {request.symbol} ({request.timeframe})",
        )
    except Exception as e:
        logger.error(f"Error retrieving date range: {str(e)}")
        raise DataError(
            message=f"Failed to get date range for {request.symbol} ({request.timeframe})",
            error_code="DATA-RangeError",
            details={
                "symbol": request.symbol,
                "timeframe": request.timeframe,
                "error": str(e),
            },
        ) from e
