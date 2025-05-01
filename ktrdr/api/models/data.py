"""
Data models for the KTRDR API.

This module defines the models related to OHLCV data, including request
and response models for data loading operations.
"""
from datetime import datetime
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator

from ktrdr.api.models.base import ApiResponse


class DataLoadRequest(BaseModel):
    """
    Request model for loading OHLCV data.
    
    Attributes:
        symbol (str): Trading symbol
        timeframe (str): Data timeframe (e.g., '1d', '1h')
        start_date (Optional[datetime]): Start date for data range
        end_date (Optional[datetime]): End date for data range
        include_metadata (bool): Whether to include metadata in response
    """
    symbol: str = Field(..., description="Trading symbol")
    timeframe: str = Field(..., description="Data timeframe (e.g., '1d', '1h')")
    start_date: Optional[datetime] = Field(None, description="Start date")
    end_date: Optional[datetime] = Field(None, description="End date")
    include_metadata: bool = Field(True, description="Whether to include metadata in response")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "symbol": "AAPL",
                    "timeframe": "1d",
                    "start_date": "2023-01-01T00:00:00",
                    "end_date": "2023-01-31T23:59:59",
                    "include_metadata": True
                }
            ]
        }
    }
    
    @field_validator('timeframe')
    @classmethod
    def validate_timeframe(cls, v: str) -> str:
        """Validate that the timeframe is in the correct format."""
        valid_timeframes = ['1m', '5m', '15m', '30m', '1h', '2h', '4h', '1d', '1w', '1M']
        if v not in valid_timeframes:
            raise ValueError(f"Timeframe must be one of {valid_timeframes}")
        return v
    
    @model_validator(mode='after')
    def validate_dates(self) -> 'DataLoadRequest':
        """Validate that start_date is before end_date if both are provided."""
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be before end_date")
        return self


class OHLCVPoint(BaseModel):
    """
    Single OHLCV data point.
    
    Attributes:
        timestamp (datetime): Timestamp for this data point
        open (float): Opening price
        high (float): Highest price
        low (float): Lowest price
        close (float): Closing price
        volume (float): Trading volume
    """
    timestamp: datetime = Field(..., description="Timestamp for this data point")
    open: float = Field(..., description="Opening price")
    high: float = Field(..., description="Highest price")
    low: float = Field(..., description="Lowest price")
    close: float = Field(..., description="Closing price")
    volume: float = Field(..., description="Trading volume")
    
    @model_validator(mode='after')
    def validate_ohlc(self) -> 'OHLCVPoint':
        """Validate price relationships (high >= open/close >= low)."""
        if self.high < self.open or self.high < self.close:
            raise ValueError("high price must be greater than or equal to open and close")
        if self.low > self.open or self.low > self.close:
            raise ValueError("low price must be less than or equal to open and close")
        if self.high < self.low:
            raise ValueError("high price must be greater than or equal to low price")
        return self


class OHLCVData(BaseModel):
    """
    OHLCV data response model.
    
    This model represents OHLCV data in both structured and array formats
    for flexibility in client consumption.
    
    Attributes:
        dates (List[str]): List of date strings
        ohlcv (List[List[float]]): Array of OHLCV data points
        points (Optional[List[OHLCVPoint]]): Structured OHLCV data points
        metadata (Dict[str, Any]): Metadata about the data
    """
    dates: List[str] = Field(..., description="List of date strings")
    ohlcv: List[List[float]] = Field(..., description="Array of OHLCV data [open, high, low, close, volume]")
    points: Optional[List[OHLCVPoint]] = Field(None, description="Structured OHLCV data points")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata about the data"
    )
    
    @field_validator('ohlcv')
    @classmethod
    def validate_ohlcv_format(cls, v: List[List[float]]) -> List[List[float]]:
        """Validate that OHLCV data has the correct format."""
        for point in v:
            if len(point) != 5:
                raise ValueError("Each OHLCV point must have 5 values [open, high, low, close, volume]")
            if point[1] < point[0] or point[1] < point[3]:  # high < open or high < close
                raise ValueError("high price must be greater than or equal to open and close")
            if point[2] > point[0] or point[2] > point[3]:  # low > open or low > close
                raise ValueError("low price must be less than or equal to open and close")
            if point[1] < point[2]:  # high < low
                raise ValueError("high price must be greater than or equal to low price")
        return v
    
    @model_validator(mode='after')
    def validate_matching_lengths(self) -> 'OHLCVData':
        """Validate that dates and OHLCV arrays have the same length."""
        if len(self.dates) != len(self.ohlcv):
            raise ValueError("dates and ohlcv arrays must have the same length")
        return self


class DataLoadResponse(ApiResponse[OHLCVData]):
    """
    Response model for data loading.
    
    This model encapsulates OHLCV data within the standard API response envelope.
    """
    pass


class SymbolInfo(BaseModel):
    """
    Information about a trading symbol.
    
    Attributes:
        symbol (str): Trading symbol identifier
        name (str): Full name of the instrument
        type (str): Instrument type (stock, forex, crypto, etc.)
        exchange (str): Exchange where the instrument is traded
        available_timeframes (List[str]): Available timeframes for this symbol
    """
    symbol: str = Field(..., description="Trading symbol identifier")
    name: str = Field(..., description="Full name of the instrument")
    type: str = Field(..., description="Instrument type (stock, forex, crypto, etc.)")
    exchange: str = Field(..., description="Exchange where the instrument is traded")
    available_timeframes: List[str] = Field(..., description="Available timeframes for this symbol")


class TimeframeInfo(BaseModel):
    """
    Information about a timeframe.
    
    Attributes:
        id (str): Timeframe identifier
        name (str): Display name
        description (str): Description of the timeframe
    """
    id: str = Field(..., description="Timeframe identifier")
    name: str = Field(..., description="Display name")
    description: str = Field(..., description="Description of the timeframe")


class SymbolsResponse(ApiResponse[List[SymbolInfo]]):
    """Response model for symbol list endpoint."""
    pass


class TimeframesResponse(ApiResponse[List[TimeframeInfo]]):
    """Response model for timeframes list endpoint."""
    pass


class DataRangeRequest(BaseModel):
    """
    Request model for retrieving available data range for a symbol.
    
    Attributes:
        symbol (str): Trading symbol
        timeframe (str): Data timeframe
    """
    symbol: str = Field(..., description="Trading symbol")
    timeframe: str = Field(..., description="Data timeframe")


class DataRangeInfo(BaseModel):
    """
    Information about available data range for a symbol.
    
    Attributes:
        symbol (str): Trading symbol
        timeframe (str): Data timeframe
        start_date (datetime): Earliest available date
        end_date (datetime): Latest available date
        point_count (int): Total number of data points available
    """
    symbol: str = Field(..., description="Trading symbol")
    timeframe: str = Field(..., description="Data timeframe")
    start_date: datetime = Field(..., description="Earliest available date")
    end_date: datetime = Field(..., description="Latest available date")
    point_count: int = Field(..., description="Total number of data points available")


class DataRangeResponse(ApiResponse[DataRangeInfo]):
    """Response model for data range endpoint."""
    pass