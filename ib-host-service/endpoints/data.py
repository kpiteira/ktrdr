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
        
        # Determine instrument type if not provided by validating with IB
        instrument_type = request.instrument_type
        if instrument_type is None:
            logger.info(f"Auto-validating {request.symbol} to determine contract type")
            validator = await get_symbol_validator()
            validation_result = await validator.validate_symbol_with_metadata(
                symbol=request.symbol,
                timeframes=[]  # No need for head timestamps in data fetch
            )
            
            if not validation_result.is_valid:
                return HistoricalDataResponse(
                    success=False,
                    error=f"Symbol validation failed: {validation_result.error_message or 'Unknown error'}"
                )
            
            # Use the validated contract type and check head timestamp
            if validation_result.contract_info:
                instrument_type = validation_result.contract_info.asset_type
                logger.info(f"Validated {request.symbol} as {instrument_type}")
                
                # Check if request start is before head timestamp (like backend used to do)
                if hasattr(validation_result.contract_info, 'head_timestamp') and validation_result.contract_info.head_timestamp:
                    from datetime import datetime
                    head_timestamp = datetime.fromisoformat(validation_result.contract_info.head_timestamp.replace('Z', '+00:00'))
                    
                    if request.start < head_timestamp:
                        return HistoricalDataResponse(
                            success=False,
                            error=f"Data not available before {head_timestamp.isoformat()}. Requested start: {request.start.isoformat()}. Head timestamp: {head_timestamp.isoformat()}"
                        )
                
            else:
                logger.warning(f"No contract info returned for {request.symbol}, defaulting to STK")
                instrument_type = "STK"
        
        fetcher = await get_data_fetcher()
        
        # Ensure IB connection is properly synchronized before making requests
        # This prevents race conditions where we make calls before sync is complete
        import asyncio
        await asyncio.sleep(0.5)  # Give IB time to settle after connection
        
        # Call existing IbDataFetcher method with validated instrument type
        data = await fetcher.fetch_historical_data(
            symbol=request.symbol,
            timeframe=request.timeframe,
            start=request.start,
            end=request.end,
            instrument_type=instrument_type
        )
        
        if data.empty:
            return HistoricalDataResponse(
                success=True,
                data="{}",  # Empty DataFrame as JSON
                rows=0
            )
        
        # Convert DataFrame to JSON for HTTP transport
        # Debug: Check precision in host service
        logger.info(f"🔍 DEBUG: Host service DataFrame precision:")
        for col in ['open', 'high', 'low', 'close']:
            if col in data.columns and len(data) > 0:
                sample_val = data[col].iloc[0]
                logger.info(f"   {col}[0]: {sample_val:.16f}")
        
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
                if timestamp is None:
                    head_timestamps[tf] = None
                elif hasattr(timestamp, 'isoformat'):
                    # It's a datetime object
                    head_timestamps[tf] = timestamp.isoformat()
                else:
                    # It's already a string or other type
                    head_timestamps[tf] = str(timestamp)
        
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

@router.get("/symbol-info/{symbol}", response_model=ValidationResponse)
async def get_symbol_info(symbol: str):
    """
    Get comprehensive symbol information including contract details, head timestamp,
    trading hours, and all cached metadata.
    
    This endpoint exposes the same symbol validation and caching that the backend
    used to have, allowing the Data Manager to make intelligent segment decisions.
    """
    try:
        logger.info(f"Getting symbol info: {symbol}")
        
        validator = await get_symbol_validator()
        
        # Get full symbol validation with metadata (same as backend used to do)
        # Include a default timeframe to trigger head timestamp fetching
        validation_result = await validator.validate_symbol_with_metadata(
            symbol=symbol,
            timeframes=["1h"]  # Default timeframe to get head timestamp
        )
        
        # Convert head timestamps to ISO format strings
        head_timestamps = {}
        if validation_result.head_timestamps:
            for tf, timestamp in validation_result.head_timestamps.items():
                if timestamp is None:
                    head_timestamps[tf] = None
                elif hasattr(timestamp, 'isoformat'):
                    head_timestamps[tf] = timestamp.isoformat()
                else:
                    head_timestamps[tf] = str(timestamp)
        
        return ValidationResponse(
            success=True,
            is_valid=validation_result.is_valid,
            error_message=validation_result.error_message,
            contract_info=validation_result.contract_info.__dict__ if validation_result.contract_info else None,
            head_timestamps=head_timestamps
        )
        
    except Exception as e:
        logger.error(f"Error getting symbol info: {str(e)}")
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
        head_timestamp = await validator.fetch_head_timestamp_async(
            symbol=symbol,
            timeframe=timeframe
        )
        
        return HeadTimestampResponse(
            success=True,
            timestamp=head_timestamp if head_timestamp else None
        )
        
    except Exception as e:
        logger.error(f"Error getting head timestamp: {str(e)}")
        return HeadTimestampResponse(
            success=False,
            error=str(e)
        )