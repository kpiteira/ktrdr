"""
Data models for the KTRDR API.

This module defines the models related to OHLCV data, including request
and response models for data loading operations.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from ktrdr.api.models.base import ApiResponse


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

    @model_validator(mode="after")
    def validate_ohlc(self) -> "OHLCVPoint":
        """Validate price relationships (high >= open/close >= low)."""
        if self.high < self.open or self.high < self.close:
            raise ValueError(
                "high price must be greater than or equal to open and close"
            )
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

    dates: list[str] = Field(..., description="List of date strings")
    ohlcv: list[list[float]] = Field(
        ..., description="Array of OHLCV data [open, high, low, close, volume]"
    )
    points: Optional[list[OHLCVPoint]] = Field(
        None, description="Structured OHLCV data points"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Metadata about the data"
    )

    @field_validator("ohlcv")
    @classmethod
    def validate_ohlcv_format(cls, v: list[list[float]]) -> list[list[float]]:
        """Validate that OHLCV data has the correct format."""
        for point in v:
            if len(point) != 5:
                raise ValueError(
                    "Each OHLCV point must have 5 values [open, high, low, close, volume]"
                )
            if (
                point[1] < point[0] or point[1] < point[3]
            ):  # high < open or high < close
                raise ValueError(
                    "high price must be greater than or equal to open and close"
                )
            if point[2] > point[0] or point[2] > point[3]:  # low > open or low > close
                raise ValueError(
                    "low price must be less than or equal to open and close"
                )
            if point[1] < point[2]:  # high < low
                raise ValueError(
                    "high price must be greater than or equal to low price"
                )
        return v

    @model_validator(mode="after")
    def validate_matching_lengths(self) -> "OHLCVData":
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


class TradingHoursInfo(BaseModel):
    """
    Trading hours information for a symbol.

    Attributes:
        timezone (str): Exchange timezone (e.g., 'America/New_York')
        regular_hours (Dict): Regular trading session info
        extended_hours (List[Dict]): Extended trading sessions
        trading_days (List[int]): Days of week when trading occurs
    """

    timezone: str = Field(..., description="Exchange timezone")
    regular_hours: dict[str, Any] = Field(..., description="Regular trading session")
    extended_hours: list[dict[str, Any]] = Field(
        ..., description="Extended trading sessions"
    )
    trading_days: list[int] = Field(
        ..., description="Days of week when trading occurs (0=Monday)"
    )


class SymbolInfo(BaseModel):
    """
    Information about a trading symbol.

    Attributes:
        symbol (str): Trading symbol identifier
        name (str): Full name of the instrument
        type (str): Instrument type (stock, forex, crypto, etc.)
        exchange (str): Exchange where the instrument is traded
        currency (str): Currency denomination
        available_timeframes (List[str]): Available timeframes for this symbol
        trading_hours (Optional[TradingHoursInfo]): Trading hours metadata
    """

    symbol: str = Field(..., description="Trading symbol identifier")
    name: str = Field(..., description="Full name of the instrument")
    type: str = Field(..., description="Instrument type (stock, forex, crypto, etc.)")
    exchange: str = Field(..., description="Exchange where the instrument is traded")
    currency: str = Field(..., description="Currency denomination")
    available_timeframes: list[str] = Field(
        ..., description="Available timeframes for this symbol"
    )
    trading_hours: Optional[TradingHoursInfo] = Field(
        None, description="Trading hours metadata for this symbol"
    )


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


class SymbolsResponse(ApiResponse[list[SymbolInfo]]):
    """Response model for symbol list endpoint."""

    pass


class TimeframesResponse(ApiResponse[list[TimeframeInfo]]):
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


class DataFilters(BaseModel):
    """
    Data filtering options.

    Attributes:
        trading_hours_only (bool): Only include data during trading hours
        include_extended (bool): Include extended hours if trading_hours_only is True
    """

    trading_hours_only: bool = Field(
        False, description="Only include data during trading hours"
    )
    include_extended: bool = Field(
        False, description="Include extended hours (pre-market, after-hours)"
    )


class DataLoadRequest(BaseModel):
    """
    Request model for loading data via DataManager.

    This model supports intelligent gap analysis, mode-based loading,
    and leverages the enhanced DataManager capabilities.

    Attributes:
        symbol (str): Trading symbol
        timeframe (str): Data timeframe (e.g., '1d', '1h')
        mode (str): Loading mode - 'local' (cached only), 'tail' (recent gaps), 'backfill' (historical), 'full' (backfill + tail)
        start_date (Optional[datetime]): Optional start date override
        end_date (Optional[datetime]): Optional end date override
    """

    symbol: str = Field(..., description="Trading symbol")
    timeframe: str = Field(..., description="Data timeframe (e.g., '1d', '1h')")
    mode: Literal["local", "tail", "backfill", "full"] = Field(
        default="local",
        description="Loading mode: 'local' for cached data only, 'tail' for recent gaps, 'backfill' for historical, 'full' for backfill + tail",
    )
    start_date: Optional[datetime] = Field(
        None, description="Optional start date override"
    )
    end_date: Optional[datetime] = Field(None, description="Optional end date override")
    filters: Optional[DataFilters] = Field(None, description="Data filtering options")
    periodic_save_minutes: float = Field(
        default=2.0,
        description="Save progress every N minutes during long downloads (default: 2.0)",
        gt=0.1,  # Must be at least 6 seconds
        le=60.0,  # Max 1 hour between saves
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"symbol": "AAPL", "timeframe": "1h", "mode": "tail"},
                {
                    "symbol": "MSFT",
                    "timeframe": "1d",
                    "mode": "backfill",
                    "start_date": "2023-01-01T00:00:00Z",
                    "end_date": "2023-06-01T00:00:00Z",
                },
            ]
        }
    }

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, v: str) -> str:
        """Validate that the timeframe is in the correct format."""
        valid_timeframes = [
            "1m",
            "5m",
            "15m",
            "30m",
            "1h",
            "2h",
            "4h",
            "1d",
            "1w",
            "1M",
        ]
        if v not in valid_timeframes:
            raise ValueError(f"Timeframe must be one of {valid_timeframes}")
        return v

    @model_validator(mode="after")
    def validate_dates(self) -> "DataLoadRequest":
        """Validate that start_date is before end_date if both are provided."""
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be before end_date")
        return self


class DataLoadOperationResponse(BaseModel):
    """
    Response model for data loading operations with enhanced metrics.

    Provides detailed information about the loading operation including
    gap analysis results and data source metrics.

    Attributes:
        status (str): Operation status - 'success', 'partial', 'failed', or 'started'
        operation_id (Optional[str]): Operation ID for async operations
        fetched_bars (int): Number of bars fetched
        cached_before (bool): Whether data existed before operation
        merged_file (str): Path to the merged CSV file
        gaps_analyzed (int): Number of gaps identified by DataManager
        segments_fetched (int): Number of segments successfully fetched
        ib_requests_made (int): Number of IB API calls made
        execution_time_seconds (float): Total execution time
        error_message (Optional[str]): Error message if operation failed
    """

    status: Literal["success", "partial", "failed", "started"] = Field(
        ..., description="Operation status"
    )
    operation_id: Optional[str] = Field(
        None, description="Operation ID for async operations"
    )
    fetched_bars: int = Field(..., description="Number of bars fetched")
    cached_before: bool = Field(
        ..., description="Whether data existed before operation"
    )
    merged_file: str = Field(..., description="Path to the merged CSV file")
    gaps_analyzed: int = Field(
        ..., description="Number of gaps identified by DataManager"
    )
    segments_fetched: int = Field(
        ..., description="Number of segments successfully fetched"
    )
    ib_requests_made: int = Field(..., description="Number of IB API calls made")
    execution_time_seconds: float = Field(..., description="Total execution time")
    error_message: Optional[str] = Field(
        None, description="Error message if operation failed"
    )


class DataLoadApiResponse(ApiResponse[DataLoadOperationResponse]):
    """API response wrapper for data loading operations."""

    pass
