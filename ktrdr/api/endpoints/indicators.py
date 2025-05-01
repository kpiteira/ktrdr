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
from ktrdr.api.models.indicators import (
    IndicatorMetadata, IndicatorCalculateRequest, IndicatorCalculateResponse,
    IndicatorsListResponse
)
from ktrdr.api.dependencies import get_indicator_service

# Create module-level logger
logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/indicators", tags=["indicators"])


@router.get(
    "/",
    response_model=IndicatorsListResponse,
    summary="List available indicators",
    description="Returns a list of all available indicators with their metadata."
)
async def list_indicators(
    indicator_service: IndicatorService = Depends(get_indicator_service)
) -> IndicatorsListResponse:
    """
    List all available indicators with their metadata.
    
    This endpoint returns information about all available technical indicators,
    including their parameters, default values, and descriptions.
    
    Returns:
        IndicatorsListResponse: Response containing a list of indicator metadata.
    """
    try:
        indicators = await indicator_service.get_available_indicators()
        return IndicatorsListResponse(
            success=True,
            data=indicators
        )
    except ProcessingError as e:
        logger.error(f"Error in list_indicators: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": e.error_code,
                    "message": str(e),
                    "details": e.details
                }
            }
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
                    "details": {"error": str(e)}
                }
            }
        )


@router.post(
    "/calculate",
    response_model=IndicatorCalculateResponse,
    summary="Calculate indicators",
    description="Calculates indicator values for the given symbol and timeframe."
)
async def calculate_indicators(
    request: IndicatorCalculateRequest,
    page: int = Query(1, ge=1, description="Page number for pagination"),
    page_size: int = Query(1000, ge=1, le=10000, description="Number of data points per page"),
    indicator_service: IndicatorService = Depends(get_indicator_service)
) -> IndicatorCalculateResponse:
    """
    Calculate indicators for the given symbol and timeframe.
    
    This endpoint loads OHLCV data for the specified symbol and timeframe,
    calculates the requested indicators, and returns the results.
    
    Args:
        request: Request model containing the calculation parameters.
        page: Page number for pagination (default: 1).
        page_size: Number of data points per page (default: 1000, max: 10000).
        
    Returns:
        IndicatorCalculateResponse: Response containing the calculated indicator values.
    """
    try:
        # Call the service to calculate indicators
        dates, indicator_values, metadata = await indicator_service.calculate_indicators(request)
        
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
            "has_prev": page > 1
        }
        
        # Merge with existing metadata
        metadata.update(pagination_metadata)
        
        return IndicatorCalculateResponse(
            success=True,
            dates=paginated_dates,
            indicators=paginated_indicators,
            metadata=metadata
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
                    "details": e.details
                }
            }
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
                    "details": e.details
                }
            }
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
                    "details": e.details
                }
            }
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
                    "details": {"error": str(e)}
                }
            }
        )