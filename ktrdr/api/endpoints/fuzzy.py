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
    FuzzyConfigsResponse, FuzzyConfigResponse, FuzzyEvaluateRequest, FuzzyEvaluateResponse
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
    description="Returns a list of indicators available for fuzzy operations with their fuzzy sets."
)
async def list_fuzzy_indicators(
    fuzzy_service: FuzzyService = Depends(get_fuzzy_service)
) -> Dict[str, Any]:
    """
    List all indicators available for fuzzy operations.
    
    This endpoint returns information about indicators that have fuzzy set
    configurations, including their available fuzzy sets.
    
    Returns:
        Dict with success flag and list of fuzzy indicators
    """
    try:
        indicators = await fuzzy_service.get_available_indicators()
        return {
            "success": True,
            "data": indicators
        }
    except ProcessingError as e:
        logger.error(f"Error in list_fuzzy_indicators: {str(e)}")
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
        logger.error(f"Unexpected error in list_fuzzy_indicators: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred while retrieving fuzzy indicators",
                    "details": {"error": str(e)}
                }
            }
        )


@router.get(
    "/sets/{indicator}",
    response_model=Dict[str, Any],
    summary="Get fuzzy sets for indicator",
    description="Returns detailed information about fuzzy sets for a specific indicator."
)
async def get_fuzzy_sets(
    indicator: str,
    fuzzy_service: FuzzyService = Depends(get_fuzzy_service)
) -> Dict[str, Any]:
    """
    Get detailed information about fuzzy sets for a specific indicator.
    
    Args:
        indicator: Name of the indicator
        
    Returns:
        Dict with success flag and fuzzy sets information
    """
    try:
        fuzzy_sets = await fuzzy_service.get_fuzzy_sets(indicator)
        return {
            "success": True,
            "data": fuzzy_sets
        }
    except ConfigurationError as e:
        logger.error(f"Configuration error in get_fuzzy_sets: {str(e)}")
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
        logger.error(f"Processing error in get_fuzzy_sets: {str(e)}")
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
        logger.error(f"Unexpected error in get_fuzzy_sets: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred while retrieving fuzzy sets",
                    "details": {"error": str(e)}
                }
            }
        )


@router.post(
    "/evaluate",
    response_model=Dict[str, Any],
    summary="Fuzzify indicator values",
    description="Applies fuzzy membership functions to indicator values."
)
async def fuzzify_values(
    data: Dict[str, Any],
    fuzzy_service: FuzzyService = Depends(get_fuzzy_service)
) -> Dict[str, Any]:
    """
    Apply fuzzy membership functions to indicator values.
    
    Args:
        data: Dictionary containing indicator name and values to fuzzify
            
    Returns:
        Dict with success flag and fuzzified values
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
                        "details": {}
                    }
                }
            )
            
        if not values:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Missing required field: values",
                        "details": {}
                    }
                }
            )
        
        result = await fuzzy_service.fuzzify_indicator(indicator, values, dates)
        return {
            "success": True,
            "data": result
        }
    except ConfigurationError as e:
        logger.error(f"Configuration error in fuzzify_values: {str(e)}")
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
        logger.error(f"Processing error in fuzzify_values: {str(e)}")
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
        logger.error(f"Unexpected error in fuzzify_values: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred during fuzzification",
                    "details": {"error": str(e)}
                }
            }
        )


@router.post(
    "/data",
    response_model=Dict[str, Any],
    summary="Fuzzify indicator data",
    description="Loads data, calculates indicators, and applies fuzzy membership functions."
)
async def fuzzify_data(
    data: Dict[str, Any],
    fuzzy_service: FuzzyService = Depends(get_fuzzy_service)
) -> Dict[str, Any]:
    """
    Load data, calculate indicators, and apply fuzzy membership functions.
    
    Args:
        data: Dictionary containing symbol, timeframe, and indicators to fuzzify
            
    Returns:
        Dict with success flag and fuzzified data
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
                        "details": {}
                    }
                }
            )
            
        if not timeframe:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Missing required field: timeframe",
                        "details": {}
                    }
                }
            )
            
        if not indicator_configs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Missing required field: indicators",
                        "details": {}
                    }
                }
            )
        
        result = await fuzzy_service.fuzzify_data(
            symbol, timeframe, indicator_configs, start_date, end_date
        )
        return {
            "success": True,
            "data": result
        }
    except DataError as e:
        logger.error(f"Data error in fuzzify_data: {str(e)}")
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
        logger.error(f"Configuration error in fuzzify_data: {str(e)}")
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
        logger.error(f"Processing error in fuzzify_data: {str(e)}")
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
        logger.error(f"Unexpected error in fuzzify_data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred during data fuzzification",
                    "details": {"error": str(e)}
                }
            }
        )