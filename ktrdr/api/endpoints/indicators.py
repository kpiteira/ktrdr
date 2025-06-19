"""
Indicator endpoints for the KTRDR API.

This module provides endpoints for accessing indicator functionality,
including listing available indicators and calculating indicator values.
"""

from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from ktrdr import get_logger
from ktrdr.errors import DataError, ConfigurationError, ProcessingError
from ktrdr.api.services.indicator_service import IndicatorService
from ktrdr.indicators.categories import (
    get_category_summary,
    get_indicators_by_category,
    get_all_categories,
    get_category_info,
    IndicatorCategory,
)
from ktrdr.api.models.indicators import (
    IndicatorMetadata,
    IndicatorCalculateRequest,
    IndicatorCalculateResponse,
    IndicatorsListResponse,
)
from ktrdr.api.dependencies import get_indicator_service

# Create module-level logger
logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/indicators", tags=["indicators"])


@router.get(
    "/",
    response_model=IndicatorsListResponse,
    summary="List available technical indicators",
    description="""
    Returns a list of all available technical indicators with their metadata, including parameters,
    default values, allowed ranges, and descriptions. Use this endpoint to discover what indicators
    are available for calculation.
    """,
)
async def list_indicators(
    indicator_service: IndicatorService = Depends(get_indicator_service),
) -> IndicatorsListResponse:
    """
    List all available indicators with their metadata.

    This endpoint returns information about all available technical indicators,
    including their parameters, default values, and descriptions.

    Returns:
        IndicatorsListResponse: Response containing a list of indicator metadata.

    Example response:
        ```json
        {
          "success": true,
          "data": [
            {
              "id": "RSIIndicator",
              "name": "Relative Strength Index",
              "description": "Momentum oscillator that measures the speed and change of price movements",
              "type": "momentum",
              "parameters": [
                {
                  "name": "period",
                  "type": "int",
                  "description": "Lookback period",
                  "default": 14,
                  "min_value": 2,
                  "max_value": 100,
                  "options": null
                },
                {
                  "name": "source",
                  "type": "str",
                  "description": "Source price data to use",
                  "default": "close",
                  "min_value": null,
                  "max_value": null,
                  "options": ["close", "open", "high", "low"]
                }
              ]
            },
            {
              "id": "SimpleMovingAverage",
              "name": "Simple Moving Average",
              "description": "Average of prices over the specified period",
              "type": "trend",
              "parameters": [
                {
                  "name": "period",
                  "type": "int",
                  "description": "Lookback period",
                  "default": 20,
                  "min_value": 2,
                  "max_value": 500,
                  "options": null
                },
                {
                  "name": "source",
                  "type": "str",
                  "description": "Source price data to use",
                  "default": "close",
                  "min_value": null,
                  "max_value": null,
                  "options": ["close", "open", "high", "low"]
                }
              ]
            }
          ]
        }
        ```

    Errors:
        - 500: Server error while retrieving indicator metadata
    """
    try:
        indicators = await indicator_service.get_available_indicators()
        return IndicatorsListResponse(success=True, data=indicators)
    except ProcessingError as e:
        logger.error(f"Error in list_indicators: {str(e)}")
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
        logger.error(f"Unexpected error in list_indicators: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred while retrieving indicators",
                    "details": {"error": str(e)},
                },
            },
        )


@router.post(
    "/calculate",
    response_model=IndicatorCalculateResponse,
    summary="Calculate technical indicators",
    description="""
    Calculates indicator values for the given symbol and timeframe. You can request multiple indicators
    in a single call, each with custom parameters. Results are paginated to handle large datasets efficiently.
    """,
)
async def calculate_indicators(
    request: IndicatorCalculateRequest,
    page: int = Query(1, ge=1, description="Page number for pagination"),
    page_size: int = Query(
        1000, ge=1, le=10000, description="Number of data points per page"
    ),
    indicator_service: IndicatorService = Depends(get_indicator_service),
) -> IndicatorCalculateResponse:
    """
    Calculate indicators for the given symbol and timeframe.

    This endpoint loads OHLCV data for the specified symbol and timeframe,
    calculates the requested indicators, and returns the results with pagination support.

    Args:
        request: Request model containing the calculation parameters.
        page: Page number for pagination (default: 1).
        page_size: Number of data points per page (default: 1000, max: 10000).

    Returns:
        IndicatorCalculateResponse: Response containing the calculated indicator values.

    Example request:
        ```json
        {
          "symbol": "AAPL",
          "timeframe": "1d",
          "indicators": [
            {
              "id": "RSIIndicator",
              "parameters": {
                "period": 14,
                "source": "close"
              },
              "output_name": "RSI_14"
            },
            {
              "id": "SimpleMovingAverage",
              "parameters": {
                "period": 20,
                "source": "close"
              },
              "output_name": "SMA_20"
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
          "dates": ["2023-01-03", "2023-01-04", "2023-01-05"],
          "indicators": {
            "RSI_14": [48.35, 52.67, 46.89],
            "SMA_20": [126.25, 126.45, 126.32]
          },
          "metadata": {
            "symbol": "AAPL",
            "timeframe": "1d",
            "start_date": "2023-01-03",
            "end_date": "2023-01-05",
            "points": 3,
            "total_items": 3,
            "total_pages": 1,
            "current_page": 1,
            "page_size": 1000,
            "has_next": false,
            "has_prev": false
          }
        }
        ```

    Errors:
        - 400: Invalid indicator configuration
        - 404: Data not found for the specified symbol and timeframe
        - 422: Validation error in the request parameters
        - 500: Server error during calculation
    """
    try:
        # Call the service to calculate indicators
        dates, indicator_values, metadata = (
            await indicator_service.calculate_indicators(request)
        )

        # Apply pagination
        total_items = len(dates)
        total_pages = (total_items + page_size - 1) // page_size

        # Ensure page is within valid range
        if page > total_pages and total_pages > 0:
            page = total_pages

        # Calculate slice indices
        start_idx = (page - 1) * page_size
        end_idx = min(start_idx + page_size, total_items)

        # Slice the data
        paginated_dates = dates[start_idx:end_idx]
        paginated_indicators = {}
        for name, values in indicator_values.items():
            paginated_indicators[name] = values[start_idx:end_idx]

        # Add pagination metadata
        pagination_metadata = {
            "total_items": total_items,
            "total_pages": total_pages,
            "current_page": page,
            "page_size": page_size,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        }

        # Merge with existing metadata
        metadata.update(pagination_metadata)

        return IndicatorCalculateResponse(
            success=True,
            dates=paginated_dates,
            indicators=paginated_indicators,
            metadata=metadata,
        )

    except DataError as e:
        logger.error(f"Data error in calculate_indicators: {str(e)}")
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
        logger.error(f"Configuration error in calculate_indicators: {str(e)}")
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
        logger.error(f"Processing error in calculate_indicators: {str(e)}")
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
        logger.error(f"Unexpected error in calculate_indicators: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred during indicator calculation",
                    "details": {"error": str(e)},
                },
            },
        )


@router.get(
    "/categories",
    summary="Get indicators organized by categories",
    description="""
    Returns all available technical indicators organized by their categories.
    Each category includes metadata about its purpose, typical usage patterns,
    and a list of indicators that belong to it.
    """,
)
async def get_indicators_by_categories() -> Dict[str, Any]:
    """
    Get indicators organized by categories.

    This endpoint returns a comprehensive overview of all available indicators
    organized by their functional categories (Trend, Momentum, Volatility, etc.).

    Returns:
        Dict containing category information and indicator mappings.

    Example response:
        ```json
        {
          "success": true,
          "categories": {
            "trend": {
              "info": {
                "name": "Trend Indicators",
                "description": "Indicators that identify direction and strength of price trends",
                "purpose": "Determine if market is trending up, down, or sideways",
                "typical_usage": "Entry/exit signals, trend confirmation",
                "common_timeframes": ["1h", "4h", "1d", "1w"]
              },
              "indicators": ["SimpleMovingAverage", "ExponentialMovingAverage"],
              "count": 2
            }
          },
          "total_categories": 6,
          "total_indicators": 19
        }
        ```
    """
    try:
        # Get category summary from the categorization system
        category_summary = get_category_summary()

        # Calculate totals
        total_categories = len(category_summary)
        total_indicators = sum(
            cat_data["count"] for cat_data in category_summary.values()
        )

        return {
            "success": True,
            "categories": category_summary,
            "total_categories": total_categories,
            "total_indicators": total_indicators,
        }

    except Exception as e:
        logger.error(f"Error retrieving category information: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to retrieve category information",
                    "details": {"error": str(e)},
                },
            },
        )


@router.get(
    "/categories/{category}",
    summary="Get indicators by specific category",
    description="""
    Returns all indicators that belong to a specific category with detailed information
    about the category's purpose and usage patterns.
    """,
)
async def get_indicators_by_category_endpoint(
    category: str,
    indicator_service: IndicatorService = Depends(get_indicator_service),
) -> Dict[str, Any]:
    """
    Get all indicators in a specific category.

    Args:
        category: The category name (trend, momentum, volatility, volume, support_resistance, multi_purpose)

    Returns:
        Dict containing category information and its indicators.

    Example response:
        ```json
        {
          "success": true,
          "category": {
            "name": "trend",
            "info": {
              "name": "Trend Indicators",
              "description": "Indicators that identify direction and strength of price trends",
              "purpose": "Determine if market is trending up, down, or sideways",
              "typical_usage": "Entry/exit signals, trend confirmation",
              "common_timeframes": ["1h", "4h", "1d", "1w"]
            },
            "indicators": ["SimpleMovingAverage", "ExponentialMovingAverage", "ADX"],
            "count": 3
          }
        }
        ```

    Errors:
        - 404: Category not found
        - 500: Server error
    """
    try:
        # Validate category
        try:
            category_enum = IndicatorCategory(category.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "error": {
                        "code": "CATEGORY_NOT_FOUND",
                        "message": f"Category '{category}' not found",
                        "details": {
                            "available_categories": [
                                cat.value for cat in get_all_categories()
                            ]
                        },
                    },
                },
            )

        # Get category information
        category_info = get_category_info(category_enum)
        indicators = get_indicators_by_category(category_enum)

        return {
            "success": True,
            "category": {
                "name": category_enum.value,
                "info": {
                    "name": category_info.name,
                    "description": category_info.description,
                    "purpose": category_info.purpose,
                    "typical_usage": category_info.typical_usage,
                    "common_timeframes": category_info.common_timeframes,
                },
                "indicators": indicators,
                "count": len(indicators),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving category '{category}': {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": f"Failed to retrieve category '{category}'",
                    "details": {"error": str(e)},
                },
            },
        )


@router.get(
    "/category-names",
    summary="Get list of available category names",
    description="""
    Returns a simple list of all available indicator category names.
    Useful for frontend dropdowns and category selection interfaces.
    """,
)
async def get_category_names() -> Dict[str, Any]:
    """
    Get list of available category names.

    Returns:
        Dict containing list of category names.

    Example response:
        ```json
        {
          "success": true,
          "categories": [
            "trend",
            "momentum",
            "volatility",
            "volume",
            "support_resistance",
            "multi_purpose"
          ],
          "count": 6
        }
        ```
    """
    try:
        categories = get_all_categories()
        category_names = [cat.value for cat in categories]

        return {
            "success": True,
            "categories": category_names,
            "count": len(category_names),
        }

    except Exception as e:
        logger.error(f"Error retrieving category names: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to retrieve category names",
                    "details": {"error": str(e)},
                },
            },
        )
