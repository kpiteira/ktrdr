"""
Data endpoints for the KTRDR API.

This module implements the API endpoints for accessing market data, symbols, and timeframes.
"""
import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query, Path, HTTPException

from ktrdr import get_logger
from ktrdr.errors import DataNotFoundError, DataError
from ktrdr.api.services.data_service import DataService
from ktrdr.api.models.data import (
    SymbolInfo, 
    SymbolsResponse, 
    TimeframeInfo, 
    TimeframesResponse,
    DataLoadRequest,
    DataLoadResponse,
    OHLCVData,
    DataRangeRequest,
    DataRangeResponse,
    DataRangeInfo
)
from ktrdr.api.dependencies import get_data_service

# Setup module-level logger
logger = get_logger(__name__)

# Create router for data endpoints
router = APIRouter()

@router.get("/symbols", response_model=SymbolsResponse, tags=["Data"])
async def get_symbols(
    data_service: DataService = Depends(get_data_service)
) -> SymbolsResponse:
    """
    Get list of available trading symbols.
    
    Returns a list of symbols that can be used with the data loading endpoint,
    including metadata about each symbol.
    
    Returns:
        SymbolsResponse: Response containing list of available symbols
    """
    try:
        symbols_data = data_service.get_available_symbols()
        
        # Convert to proper model
        symbols = [SymbolInfo(**s) for s in symbols_data]
        
        logger.info(f"Retrieved {len(symbols)} symbols")
        return SymbolsResponse(success=True, data=symbols)
    except Exception as e:
        logger.error(f"Error retrieving symbols: {str(e)}")
        raise DataError(
            message="Failed to retrieve symbols",
            error_code="DATA-SymbolListError",
            details={"error": str(e)}
        ) from e

@router.get("/timeframes", response_model=TimeframesResponse, tags=["Data"])
async def get_timeframes(
    data_service: DataService = Depends(get_data_service)
) -> TimeframesResponse:
    """
    Get list of available timeframes.
    
    Returns a list of timeframes that can be used with the data loading endpoint,
    including metadata about each timeframe.
    
    Returns:
        TimeframesResponse: Response containing list of available timeframes
    """
    try:
        timeframes_data = data_service.get_available_timeframes()
        
        # Convert to proper model
        timeframes = [TimeframeInfo(**t) for t in timeframes_data]
        
        logger.info(f"Retrieved {len(timeframes)} timeframes")
        return TimeframesResponse(success=True, data=timeframes)
    except Exception as e:
        logger.error(f"Error retrieving timeframes: {str(e)}")
        raise DataError(
            message="Failed to retrieve timeframes",
            error_code="DATA-TimeframeListError",
            details={"error": str(e)}
        ) from e

@router.post("/data/load", response_model=DataLoadResponse, tags=["Data"])
async def load_data(
    request: DataLoadRequest,
    data_service: DataService = Depends(get_data_service)
) -> DataLoadResponse:
    """
    Load OHLCV data for a symbol and timeframe.
    
    Loads price and volume data for the specified symbol and timeframe,
    with optional date range filtering.
    
    Args:
        request (DataLoadRequest): Request parameters including symbol, timeframe, and date range
        
    Returns:
        DataLoadResponse: Response containing OHLCV data
        
    Example:
        ```json
        {
          "symbol": "AAPL",
          "timeframe": "1d",
          "start_date": "2023-01-01T00:00:00",
          "end_date": "2023-01-31T23:59:59",
          "include_metadata": true
        }
        ```
    """
    try:
        logger.info(f"Loading data for {request.symbol} ({request.timeframe})")
        
        data = data_service.load_data(
            symbol=request.symbol,
            timeframe=request.timeframe,
            start_date=request.start_date,
            end_date=request.end_date,
            include_metadata=request.include_metadata
        )
        
        # Convert to OHLCVData model
        ohlcv_data = OHLCVData(**data)
        
        logger.info(f"Successfully loaded {len(data['dates'])} data points for {request.symbol}")
        return DataLoadResponse(success=True, data=ohlcv_data)
    except DataNotFoundError as e:
        logger.error(f"Data not found: {str(e)}")
        raise HTTPException(
            status_code=404, 
            detail=f"Data not found for {request.symbol} ({request.timeframe})"
        )
    except DataError as e:
        # Let the global exception handler deal with this
        logger.error(f"Data error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error loading data: {str(e)}")
        raise DataError(
            message=f"Failed to load data for {request.symbol} ({request.timeframe})",
            error_code="DATA-LoadError",
            details={"symbol": request.symbol, "timeframe": request.timeframe, "error": str(e)}
        ) from e

@router.post("/data/range", response_model=DataRangeResponse, tags=["Data"])
async def get_data_range(
    request: DataRangeRequest,
    data_service: DataService = Depends(get_data_service)
) -> DataRangeResponse:
    """
    Get available date range for a symbol and timeframe.
    
    Retrieves the earliest and latest available dates for the specified
    symbol and timeframe, along with the total number of data points.
    
    Args:
        request (DataRangeRequest): Request parameters including symbol and timeframe
        
    Returns:
        DataRangeResponse: Response containing date range information
    """
    try:
        logger.info(f"Getting date range for {request.symbol} ({request.timeframe})")
        
        range_data = data_service.get_data_range(
            symbol=request.symbol,
            timeframe=request.timeframe
        )
        
        # Convert to DataRangeInfo model
        range_info = DataRangeInfo(**range_data)
        
        logger.info(f"Successfully retrieved date range for {request.symbol}")
        return DataRangeResponse(success=True, data=range_info)
    except DataNotFoundError as e:
        logger.error(f"Data not found: {str(e)}")
        raise HTTPException(
            status_code=404, 
            detail=f"Data not found for {request.symbol} ({request.timeframe})"
        )
    except Exception as e:
        logger.error(f"Error retrieving date range: {str(e)}")
        raise DataError(
            message=f"Failed to get date range for {request.symbol} ({request.timeframe})",
            error_code="DATA-RangeError",
            details={"symbol": request.symbol, "timeframe": request.timeframe, "error": str(e)}
        ) from e