"""
Data endpoints for IB Connector Host Service

These endpoints mirror the IbDataAdapter interface to provide
seamless integration with the existing backend.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import pandas as pd
import logging

# Import existing ktrdr modules
from ktrdr.ib import IbDataFetcher, IbSymbolValidator
from ktrdr.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/data", tags=["data"])

# Global instances (will be initialized on first use)
_data_fetcher: Optional[IbDataFetcher] = None
_symbol_validator: Optional[IbSymbolValidator] = None

async def get_data_fetcher() -> IbDataFetcher:
    """Get or create IB data fetcher instance."""
    global _data_fetcher
    if _data_fetcher is None:
        _data_fetcher = IbDataFetcher()
    return _data_fetcher

async def get_symbol_validator() -> IbSymbolValidator:
    """Get or create IB symbol validator instance."""
    global _symbol_validator
    if _symbol_validator is None:
        _symbol_validator = IbSymbolValidator()
    return _symbol_validator

# Request/Response Models

class HistoricalDataRequest(BaseModel):
    """Request for historical data."""
    symbol: str = Field(..., description="Trading symbol")
    timeframe: str = Field(..., description="Timeframe (e.g., '1h', '1d')")
    start: datetime = Field(..., description="Start datetime (UTC)")
    end: datetime = Field(..., description="End datetime (UTC)")
    instrument_type: Optional[str] = Field(None, description="Instrument type")

class HistoricalDataResponse(BaseModel):
    """Response for historical data."""
    success: bool
    data: Optional[str] = None  # JSON serialized DataFrame
    error: Optional[str] = None
    rows: Optional[int] = None

class ValidationRequest(BaseModel):
    """Request for symbol validation."""
    symbol: str = Field(..., description="Trading symbol")
    timeframes: Optional[List[str]] = Field(None, description="Timeframes for metadata")

class ValidationResponse(BaseModel):
    """Response for symbol validation."""
    success: bool
    is_valid: Optional[bool] = None
    error_message: Optional[str] = None
    contract_info: Optional[Dict[str, Any]] = None
    head_timestamps: Optional[Dict[str, Optional[str]]] = None
    error: Optional[str] = None

class HeadTimestampRequest(BaseModel):
    """Request for head timestamp."""
    symbol: str = Field(..., description="Trading symbol")
    timeframe: str = Field(..., description="Timeframe")
    instrument_type: Optional[str] = Field(None, description="Instrument type")

class HeadTimestampResponse(BaseModel):
    """Response for head timestamp."""
    success: bool
    timestamp: Optional[str] = None  # ISO format datetime
    error: Optional[str] = None

# Endpoints

@router.post("/historical", response_model=HistoricalDataResponse)
async def get_historical_data(request: HistoricalDataRequest):
    """
    Fetch historical OHLCV data for a symbol.
    
    This endpoint uses the existing IbDataFetcher to get data directly
    from IB Gateway, bypassing Docker networking issues.
    """
    try:
        logger.info(f"Fetching historical data: {request.symbol} {request.timeframe} "
                   f"{request.start} to {request.end}")
        
        fetcher = await get_data_fetcher()
        
        # Call existing IbDataFetcher method
        data = await fetcher.fetch_historical_data(
            symbol=request.symbol,
            timeframe=request.timeframe,
            start=request.start,
            end=request.end,
            instrument_type=request.instrument_type
        )
        
        if data.empty:
            return HistoricalDataResponse(
                success=True,
                data="{}",  # Empty DataFrame as JSON
                rows=0
            )
        
        # Convert DataFrame to JSON for HTTP transport
        data_json = data.to_json(orient="index", date_format="iso")
        
        return HistoricalDataResponse(
            success=True,
            data=data_json,
            rows=len(data)
        )
        
    except Exception as e:
        logger.error(f"Error fetching historical data: {str(e)}")
        return HistoricalDataResponse(
            success=False,
            error=str(e)
        )

@router.post("/validate", response_model=ValidationResponse)
async def validate_symbol(request: ValidationRequest):
    """
    Validate symbol and get metadata including head timestamps.
    
    This endpoint uses the existing IbSymbolValidator to check if a symbol
    is valid and get contract information.
    """
    try:
        logger.info(f"Validating symbol: {request.symbol} "
                   f"timeframes: {request.timeframes}")
        
        validator = await get_symbol_validator()
        
        # Call existing IbSymbolValidator method
        validation_result = await validator.validate_symbol_with_metadata(
            symbol=request.symbol,
            timeframes=request.timeframes or []
        )
        
        # Convert head timestamps to ISO format strings
        head_timestamps = {}
        if validation_result.head_timestamps:
            for tf, timestamp in validation_result.head_timestamps.items():
                head_timestamps[tf] = timestamp.isoformat() if timestamp else None
        
        return ValidationResponse(
            success=True,
            is_valid=validation_result.is_valid,
            error_message=validation_result.error_message,
            contract_info=validation_result.contract_info.__dict__ if validation_result.contract_info else None,
            head_timestamps=head_timestamps
        )
        
    except Exception as e:
        logger.error(f"Error validating symbol: {str(e)}")
        return ValidationResponse(
            success=False,
            error=str(e)
        )

@router.get("/head-timestamp", response_model=HeadTimestampResponse)
async def get_head_timestamp(
    symbol: str,
    timeframe: str,
    instrument_type: Optional[str] = None
):
    """
    Get the earliest available data timestamp for a symbol.
    
    This endpoint provides the head timestamp for a specific symbol/timeframe
    combination using the existing IB integration.
    """
    try:
        logger.info(f"Getting head timestamp: {symbol} {timeframe}")
        
        validator = await get_symbol_validator()
        
        # Get head timestamp using existing method
        head_timestamp = await validator.get_head_timestamp(
            symbol=symbol,
            timeframe=timeframe,
            instrument_type=instrument_type
        )
        
        return HeadTimestampResponse(
            success=True,
            timestamp=head_timestamp.isoformat() if head_timestamp else None
        )
        
    except Exception as e:
        logger.error(f"Error getting head timestamp: {str(e)}")
        return HeadTimestampResponse(
            success=False,
            error=str(e)
        )