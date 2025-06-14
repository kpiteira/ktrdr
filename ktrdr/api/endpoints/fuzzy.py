"""
Fuzzy logic endpoints for the KTRDR API.

This module provides endpoints for accessing fuzzy logic functionality,
including listing available fuzzy sets and fuzzifying indicator values.
"""

from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from ktrdr import get_logger
from ktrdr.errors import DataError, ConfigurationError, ProcessingError
from ktrdr.api.services.fuzzy_service import FuzzyService
from ktrdr.api.models.fuzzy import (
    FuzzyConfigsResponse,
    FuzzyConfigResponse,
    FuzzyEvaluateRequest,
    FuzzyEvaluateResponse,
    FuzzyOverlayResponse,
)
from ktrdr.api.dependencies import get_fuzzy_service

# Create module-level logger
logger = get_logger(__name__)

# Create router with consistent capitalization for the tag
router = APIRouter(prefix="/fuzzy", tags=["Fuzzy"])


@router.get(
    "/indicators",
    response_model=Dict[str, Any],
    summary="List available fuzzy indicators",
    description="""
    Returns a list of indicators that have fuzzy set configurations available, along with their 
    fuzzy sets and membership functions. These indicators can be used with the fuzzy evaluation endpoints.
    """,
)
async def list_fuzzy_indicators(
    fuzzy_service: FuzzyService = Depends(get_fuzzy_service),
) -> Dict[str, Any]:
    """
    List all indicators available for fuzzy operations.

    This endpoint returns information about indicators that have fuzzy set
    configurations, including their available fuzzy sets.

    Returns:
        Dict with success flag and list of fuzzy indicators

    Example response:
        ```json
        {
          "success": true,
          "data": [
            {
              "id": "rsi",
              "name": "RSI",
              "fuzzy_sets": ["low", "medium", "high"],
              "output_columns": ["rsi_low", "rsi_medium", "rsi_high"]
            },
            {
              "id": "macd",
              "name": "MACD",
              "fuzzy_sets": ["negative", "neutral", "positive"],
              "output_columns": ["macd_negative", "macd_neutral", "macd_positive"]
            }
          ]
        }
        ```

    Errors:
        - 500: Server error while retrieving fuzzy indicator information
    """
    try:
        indicators = await fuzzy_service.get_available_indicators()
        return {"success": True, "data": indicators}
    except ProcessingError as e:
        logger.error(f"Error in list_fuzzy_indicators: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": e.error_code,
                    "message": str(e),
                    "details": e.details,
                },
            },
        )
    except Exception as e:
        logger.error(f"Unexpected error in list_fuzzy_indicators: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred while retrieving fuzzy indicators",
                    "details": {"error": str(e)},
                },
            },
        )


@router.get(
    "/sets/{indicator}",
    response_model=Dict[str, Any],
    summary="Get fuzzy sets for indicator",
    description="""
    Returns detailed information about the fuzzy sets configured for a specific indicator,
    including membership function types and parameters. This provides insight into how
    indicator values are converted to fuzzy membership degrees.
    """,
)
async def get_fuzzy_sets(
    indicator: str, fuzzy_service: FuzzyService = Depends(get_fuzzy_service)
) -> Dict[str, Any]:
    """
    Get detailed information about fuzzy sets for a specific indicator.

    Args:
        indicator: Name of the indicator

    Returns:
        Dict with success flag and fuzzy sets information

    Example response:
        ```json
        {
          "success": true,
          "data": {
            "low": {
              "type": "triangular",
              "parameters": [0, 0, 30]
            },
            "medium": {
              "type": "triangular",
              "parameters": [20, 50, 80]
            },
            "high": {
              "type": "triangular",
              "parameters": [70, 100, 100]
            }
          }
        }
        ```

    Errors:
        - 400: Invalid indicator name or configuration error
        - 500: Server error while retrieving fuzzy set information
    """
    try:
        fuzzy_sets = await fuzzy_service.get_fuzzy_sets(indicator)
        return {"success": True, "data": fuzzy_sets}
    except ConfigurationError as e:
        logger.error(f"Configuration error in get_fuzzy_sets: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": {
                    "code": e.error_code,
                    "message": str(e),
                    "details": e.details,
                },
            },
        )
    except ProcessingError as e:
        logger.error(f"Processing error in get_fuzzy_sets: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": e.error_code,
                    "message": str(e),
                    "details": e.details,
                },
            },
        )
    except Exception as e:
        logger.error(f"Unexpected error in get_fuzzy_sets: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred while retrieving fuzzy sets",
                    "details": {"error": str(e)},
                },
            },
        )


@router.get(
    "/data",
    response_model=FuzzyOverlayResponse,
    summary="Get fuzzy membership overlays for chart display",
    description="""
    Returns time series fuzzy membership values for indicators over a given period.
    This endpoint is designed for frontend chart overlays, providing fuzzy membership
    data in a format optimized for visualization.
    
    The endpoint loads OHLCV data, calculates requested indicators, and computes
    fuzzy membership values using the configured membership functions. Results
    are returned as time series data suitable for chart overlays.
    """,
)
async def get_fuzzy_overlay_data(
    symbol: str = Query(..., description="Trading symbol (e.g., AAPL)"),
    timeframe: str = Query(..., description="Data timeframe (e.g., 1h, 1d)"),
    indicators: Optional[List[str]] = Query(
        None,
        description="List of indicators (if omitted, returns all configured indicators)",
    ),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    fuzzy_service: FuzzyService = Depends(get_fuzzy_service),
) -> FuzzyOverlayResponse:
    """
    Get fuzzy membership overlays for indicators over time.

    This endpoint provides time series fuzzy membership values that can be used
    to create chart overlays showing fuzzy regions (e.g., RSI "low", "neutral", "high").

    Args:
        symbol: Trading symbol to load data for
        timeframe: Data timeframe (e.g., "1h", "1d", "5m")
        indicators: Optional list of specific indicators to include
        start_date: Optional start date for data filtering
        end_date: Optional end date for data filtering

    Returns:
        FuzzyOverlayResponse with time series membership data

    Example response:
        ```json
        {
          "symbol": "AAPL",
          "timeframe": "1h",
          "data": {
            "rsi": [
              {
                "set": "low",
                "membership": [
                  {"timestamp": "2023-01-01T09:00:00", "value": 0.8},
                  {"timestamp": "2023-01-01T10:00:00", "value": 0.6}
                ]
              },
              {
                "set": "high",
                "membership": [
                  {"timestamp": "2023-01-01T09:00:00", "value": 0.2},
                  {"timestamp": "2023-01-01T10:00:00", "value": 0.4}
                ]
              }
            ]
          },
          "warnings": ["Unknown indicator 'invalid' - skipping"]
        }
        ```

    Errors:
        - 400: Invalid request parameters or configuration error
        - 404: No data available for the specified symbol and timeframe
        - 500: Server error during processing
    """
    try:
        logger.info(f"Getting fuzzy overlay data for {symbol} {timeframe}")

        # Call the service to get fuzzy overlays
        result = await fuzzy_service.get_fuzzy_overlays(
            symbol=symbol,
            timeframe=timeframe,
            indicators=indicators,
            start_date=start_date,
            end_date=end_date,
        )

        # Convert service response to Pydantic model
        return FuzzyOverlayResponse(**result)

    except DataError as e:
        logger.error(f"Data error in get_fuzzy_overlay_data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": e.error_code,
                    "message": str(e),
                    "details": e.details,
                },
            },
        )
    except ConfigurationError as e:
        logger.error(f"Configuration error in get_fuzzy_overlay_data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": e.error_code,
                    "message": str(e),
                    "details": e.details,
                },
            },
        )
    except ProcessingError as e:
        logger.error(f"Processing error in get_fuzzy_overlay_data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": e.error_code,
                    "message": str(e),
                    "details": e.details,
                },
            },
        )
    except Exception as e:
        logger.error(f"Unexpected error in get_fuzzy_overlay_data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred during fuzzy overlay generation",
                    "details": {"error": str(e)},
                },
            },
        )


@router.post(
    "/evaluate",
    response_model=Dict[str, Any],
    summary="Fuzzify indicator values",
    description="""
    Applies fuzzy membership functions to convert numeric indicator values into fuzzy membership degrees.
    This endpoint is useful for converting raw indicator values into fuzzy logic inputs that represent
    linguistic variables like "low", "medium", or "high".
    """,
)
async def fuzzify_values(
    data: Dict[str, Any], fuzzy_service: FuzzyService = Depends(get_fuzzy_service)
) -> Dict[str, Any]:
    """
    Apply fuzzy membership functions to indicator values.

    Args:
        data: Dictionary containing indicator name and values to fuzzify

    Returns:
        Dict with success flag and fuzzified values

    Example request:
        ```json
        {
          "indicator": "rsi",
          "values": [30.5, 45.2, 68.7, 82.1],
          "dates": ["2023-01-01", "2023-01-02", "2023-01-03", "2023-01-04"]
        }
        ```

    Example response:
        ```json
        {
          "success": true,
          "data": {
            "indicator": "rsi",
            "fuzzy_sets": ["low", "medium", "high"],
            "values": {
              "rsi_low": [0.78, 0.24, 0.05, 0.0],
              "rsi_medium": [0.22, 0.76, 0.56, 0.12],
              "rsi_high": [0.0, 0.0, 0.39, 0.88]
            },
            "points": 4
          }
        }
        ```

    Errors:
        - 400: Invalid indicator or missing required fields
        - 500: Server error during fuzzification
    """
    try:
        indicator = data.get("indicator")
        values = data.get("values", [])
        dates = data.get("dates")

        if not indicator:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Missing required field: indicator",
                        "details": {},
                    },
                },
            )

        if not values:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Missing required field: values",
                        "details": {},
                    },
                },
            )

        result = await fuzzy_service.fuzzify_indicator(indicator, values, dates)
        return {"success": True, "data": result}
    except ConfigurationError as e:
        logger.error(f"Configuration error in fuzzify_values: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": {
                    "code": e.error_code,
                    "message": str(e),
                    "details": e.details,
                },
            },
        )
    except ProcessingError as e:
        logger.error(f"Processing error in fuzzify_values: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": e.error_code,
                    "message": str(e),
                    "details": e.details,
                },
            },
        )
    except Exception as e:
        logger.error(f"Unexpected error in fuzzify_values: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred during fuzzification",
                    "details": {"error": str(e)},
                },
            },
        )


@router.post(
    "/data",
    response_model=Dict[str, Any],
    summary="Fuzzify indicator data",
    description="""
    Loads market data, calculates indicators, and applies fuzzy membership functions in a single operation.
    This is a convenience endpoint that combines data loading, indicator calculation, and fuzzy evaluation
    in one request, making it ideal for applications that need to process OHLCV data through fuzzy logic.
    """,
)
async def fuzzify_data(
    data: Dict[str, Any], fuzzy_service: FuzzyService = Depends(get_fuzzy_service)
) -> Dict[str, Any]:
    """
    Load data, calculate indicators, and apply fuzzy membership functions.

    Args:
        data: Dictionary containing symbol, timeframe, and indicators to fuzzify

    Returns:
        Dict with success flag and fuzzified data

    Example request:
        ```json
        {
          "symbol": "AAPL",
          "timeframe": "1d",
          "indicators": [
            {
              "name": "rsi",
              "source_column": "close"
            },
            {
              "name": "macd",
              "source_column": "macd_line"
            }
          ],
          "start_date": "2023-01-01T00:00:00",
          "end_date": "2023-01-31T23:59:59"
        }
        ```

    Example response:
        ```json
        {
          "success": true,
          "data": {
            "symbol": "AAPL",
            "timeframe": "1d",
            "dates": ["2023-01-03", "2023-01-04", "2023-01-05"],
            "indicators": {
              "rsi": {
                "rsi_low": [0.78, 0.24, 0.05],
                "rsi_medium": [0.22, 0.76, 0.56],
                "rsi_high": [0.0, 0.0, 0.39]
              },
              "macd": {
                "macd_negative": [0.85, 0.62, 0.31],
                "macd_neutral": [0.15, 0.38, 0.69],
                "macd_positive": [0.0, 0.0, 0.0]
              }
            },
            "metadata": {
              "start_date": "2023-01-03",
              "end_date": "2023-01-05",
              "points": 3
            }
          }
        }
        ```

    Errors:
        - 400: Invalid request parameters or configuration error
        - 404: Data not found for the specified symbol and timeframe
        - 500: Server error during processing
    """
    try:
        symbol = data.get("symbol")
        timeframe = data.get("timeframe")
        indicator_configs = data.get("indicators", [])
        start_date = data.get("start_date")
        end_date = data.get("end_date")

        if not symbol:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Missing required field: symbol",
                        "details": {},
                    },
                },
            )

        if not timeframe:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Missing required field: timeframe",
                        "details": {},
                    },
                },
            )

        if not indicator_configs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Missing required field: indicators",
                        "details": {},
                    },
                },
            )

        result = await fuzzy_service.fuzzify_data(
            symbol, timeframe, indicator_configs, start_date, end_date
        )
        return {"success": True, "data": result}
    except DataError as e:
        logger.error(f"Data error in fuzzify_data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "success": False,
                "error": {
                    "code": e.error_code,
                    "message": str(e),
                    "details": e.details,
                },
            },
        )
    except ConfigurationError as e:
        logger.error(f"Configuration error in fuzzify_data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": {
                    "code": e.error_code,
                    "message": str(e),
                    "details": e.details,
                },
            },
        )
    except ProcessingError as e:
        logger.error(f"Processing error in fuzzify_data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": e.error_code,
                    "message": str(e),
                    "details": e.details,
                },
            },
        )
    except Exception as e:
        logger.error(f"Unexpected error in fuzzify_data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred during data fuzzification",
                    "details": {"error": str(e)},
                },
            },
        )
