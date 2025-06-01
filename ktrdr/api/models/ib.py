"""
IB (Interactive Brokers) models for the KTRDR API.

This module defines the request and response models for IB-related endpoints.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from ktrdr.api.models.base import ApiResponse


class ConnectionInfo(BaseModel):
    """
    IB connection information.

    Attributes:
        connected: Whether currently connected to IB
        host: IB Gateway/TWS host
        port: IB Gateway/TWS port
        client_id: Client ID used for connection
        connection_time: When the connection was established (if connected)
    """

    connected: bool = Field(..., description="Whether currently connected to IB")
    host: str = Field(..., description="IB Gateway/TWS host")
    port: int = Field(..., description="IB Gateway/TWS port")
    client_id: int = Field(..., description="Client ID used for connection")
    connection_time: Optional[datetime] = Field(
        None, description="When connection was established"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "connected": True,
                "host": "127.0.0.1",
                "port": 4002,
                "client_id": 1234,
                "connection_time": "2025-05-29T10:30:00Z",
            }
        }
    )


class ConnectionMetrics(BaseModel):
    """
    IB connection metrics.

    Attributes:
        total_connections: Total connection attempts
        failed_connections: Number of failed connection attempts
        last_connect_time: Timestamp of last successful connection
        last_disconnect_time: Timestamp of last disconnect
        uptime_seconds: Current connection uptime in seconds
    """

    total_connections: int = Field(..., description="Total connection attempts")
    failed_connections: int = Field(
        ..., description="Number of failed connection attempts"
    )
    last_connect_time: Optional[float] = Field(
        None, description="Timestamp of last successful connection"
    )
    last_disconnect_time: Optional[float] = Field(
        None, description="Timestamp of last disconnect"
    )
    uptime_seconds: Optional[float] = Field(
        None, description="Current connection uptime in seconds"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_connections": 5,
                "failed_connections": 1,
                "last_connect_time": 1735484400.0,
                "last_disconnect_time": 1735480800.0,
                "uptime_seconds": 3600.0,
            }
        }
    )


class DataFetchMetrics(BaseModel):
    """
    IB data fetching metrics.

    Attributes:
        total_requests: Total data requests made
        successful_requests: Number of successful requests
        failed_requests: Number of failed requests
        total_bars_fetched: Total number of bars fetched
        success_rate: Success rate as a percentage
    """

    total_requests: int = Field(..., description="Total data requests made")
    successful_requests: int = Field(..., description="Number of successful requests")
    failed_requests: int = Field(..., description="Number of failed requests")
    total_bars_fetched: int = Field(..., description="Total number of bars fetched")
    success_rate: float = Field(..., description="Success rate as a percentage")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_requests": 100,
                "successful_requests": 98,
                "failed_requests": 2,
                "total_bars_fetched": 7500,
                "success_rate": 98.0,
            }
        }
    )


class IbStatusResponse(BaseModel):
    """
    IB status response containing connection and metrics information.

    Attributes:
        connection: Current connection information
        connection_metrics: Connection performance metrics
        data_metrics: Data fetching performance metrics
        ib_available: Whether IB integration is available
    """

    connection: ConnectionInfo = Field(
        ..., description="Current connection information"
    )
    connection_metrics: ConnectionMetrics = Field(
        ..., description="Connection performance metrics"
    )
    data_metrics: DataFetchMetrics = Field(
        ..., description="Data fetching performance metrics"
    )
    ib_available: bool = Field(..., description="Whether IB integration is available")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "connection": {
                    "connected": True,
                    "host": "127.0.0.1",
                    "port": 4002,
                    "client_id": 1234,
                    "connection_time": "2025-05-29T10:30:00Z",
                },
                "connection_metrics": {
                    "total_connections": 5,
                    "failed_connections": 1,
                    "last_connect_time": 1735484400.0,
                    "last_disconnect_time": 1735480800.0,
                    "uptime_seconds": 3600.0,
                },
                "data_metrics": {
                    "total_requests": 100,
                    "successful_requests": 98,
                    "failed_requests": 2,
                    "total_bars_fetched": 7500,
                    "success_rate": 98.0,
                },
                "ib_available": True,
            }
        }
    )


class IbHealthStatus(BaseModel):
    """
    IB health check status.

    Attributes:
        healthy: Overall health status
        connection_ok: Whether connection is established and working
        data_fetching_ok: Whether data fetching is working
        last_successful_request: Time of last successful data request
        error_message: Error message if unhealthy
    """

    healthy: bool = Field(..., description="Overall health status")
    connection_ok: bool = Field(
        ..., description="Whether connection is established and working"
    )
    data_fetching_ok: bool = Field(..., description="Whether data fetching is working")
    last_successful_request: Optional[datetime] = Field(
        None, description="Time of last successful data request"
    )
    error_message: Optional[str] = Field(None, description="Error message if unhealthy")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "healthy": True,
                "connection_ok": True,
                "data_fetching_ok": True,
                "last_successful_request": "2025-05-29T11:45:00Z",
                "error_message": None,
            }
        }
    )


class IbConfigInfo(BaseModel):
    """
    IB configuration information.

    Attributes:
        host: Configured IB Gateway/TWS host
        port: Configured IB Gateway/TWS port
        client_id_range: Range of client IDs used (min, max)
        timeout: Connection timeout in seconds
        readonly: Whether connection is read-only
        rate_limit: Rate limit settings
    """

    host: str = Field(..., description="Configured IB Gateway/TWS host")
    port: int = Field(..., description="Configured IB Gateway/TWS port")
    client_id_range: Dict[str, int] = Field(..., description="Range of client IDs used")
    timeout: int = Field(..., description="Connection timeout in seconds")
    readonly: bool = Field(..., description="Whether connection is read-only")
    rate_limit: Dict[str, Any] = Field(..., description="Rate limit settings")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "host": "127.0.0.1",
                "port": 4002,
                "client_id_range": {"min": 1000, "max": 9999},
                "timeout": 15,
                "readonly": False,
                "rate_limit": {
                    "max_requests": 50,
                    "period_seconds": 60,
                    "pacing_delay": 0.6,
                },
            }
        }
    )


class IbConfigUpdateRequest(BaseModel):
    """
    Request to update IB configuration.

    Attributes:
        port: New port number (4002=IB Gateway Paper, 4001=IB Gateway Live, 7497=TWS Paper, 7496=TWS Live)
        host: New host address (optional)
        client_id: New client ID (optional)
    """

    port: Optional[int] = Field(None, ge=1, le=65535, description="New port number")
    host: Optional[str] = Field(None, description="New host address")
    client_id: Optional[int] = Field(None, ge=0, le=999999, description="New client ID")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"port": 4001, "host": "127.0.0.1", "client_id": 1}
        }
    )


class IbConfigUpdateResponse(BaseModel):
    """
    Response after updating IB configuration.

    Attributes:
        previous_config: Configuration before update
        new_config: Configuration after update
        reconnect_required: Whether reconnection is required for changes to take effect
    """

    previous_config: IbConfigInfo = Field(
        ..., description="Configuration before update"
    )
    new_config: IbConfigInfo = Field(..., description="Configuration after update")
    reconnect_required: bool = Field(
        ..., description="Whether reconnection is required"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "previous_config": {
                    "host": "127.0.0.1",
                    "port": 4002,
                    "client_id_range": {"min": 1000, "max": 9999},
                    "timeout": 15,
                    "readonly": False,
                    "rate_limit": {
                        "max_requests": 50,
                        "period_seconds": 60,
                        "pacing_delay": 0.6,
                    },
                },
                "new_config": {
                    "host": "127.0.0.1",
                    "port": 4001,
                    "client_id_range": {"min": 1000, "max": 9999},
                    "timeout": 15,
                    "readonly": False,
                    "rate_limit": {
                        "max_requests": 50,
                        "period_seconds": 60,
                        "pacing_delay": 0.6,
                    },
                },
                "reconnect_required": True,
            }
        }
    )


class DataRangeInfo(BaseModel):
    """
    Data range information for a symbol/timeframe combination.

    Attributes:
        earliest_date: Earliest available data date
        latest_date: Latest available data date (usually current)
        total_days: Total days of data coverage
        cached: Whether this result was from cache
    """

    earliest_date: Optional[datetime] = Field(
        None, description="Earliest available data date"
    )
    latest_date: Optional[datetime] = Field(
        None, description="Latest available data date"
    )
    total_days: Optional[int] = Field(None, description="Total days of data coverage")
    cached: bool = Field(..., description="Whether result was from cache")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "earliest_date": "1980-12-12T00:00:00Z",
                "latest_date": "2025-05-29T12:00:00Z",
                "total_days": 16204,
                "cached": True,
            }
        }
    )


class SymbolRangeResponse(BaseModel):
    """
    Data ranges for all requested timeframes of a symbol.

    Attributes:
        symbol: Symbol name
        ranges: Dictionary mapping timeframe to range info
    """

    symbol: str = Field(..., description="Symbol name")
    ranges: Dict[str, Optional[DataRangeInfo]] = Field(
        ..., description="Timeframe to range mapping"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "symbol": "AAPL",
                "ranges": {
                    "1d": {
                        "earliest_date": "1980-12-12T00:00:00Z",
                        "latest_date": "2025-05-29T12:00:00Z",
                        "total_days": 16204,
                        "cached": False,
                    },
                    "1h": {
                        "earliest_date": "2000-01-01T00:00:00Z",
                        "latest_date": "2025-05-29T12:00:00Z",
                        "total_days": 9279,
                        "cached": False,
                    },
                },
            }
        }
    )


class DataRangesResponse(BaseModel):
    """
    Data ranges for multiple symbols and timeframes.

    Attributes:
        symbols: List of symbol range information
        requested_timeframes: Timeframes that were requested
        cache_stats: Statistics about cache usage
    """

    symbols: List[SymbolRangeResponse] = Field(
        ..., description="Symbol range information"
    )
    requested_timeframes: List[str] = Field(..., description="Requested timeframes")
    cache_stats: Dict[str, Any] = Field(..., description="Cache usage statistics")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "symbols": [
                    {
                        "symbol": "AAPL",
                        "ranges": {
                            "1d": {
                                "earliest_date": "1980-12-12T00:00:00Z",
                                "latest_date": "2025-05-29T12:00:00Z",
                                "total_days": 16204,
                                "cached": False,
                            }
                        },
                    }
                ],
                "requested_timeframes": ["1d"],
                "cache_stats": {
                    "total_cached_ranges": 1,
                    "symbols_in_cache": 1,
                    "cache_ttl_hours": 24,
                },
            }
        }
    )


class IbLoadRequest(BaseModel):
    """
    Request to load data from IB.

    Attributes:
        symbol: Trading symbol to load
        timeframe: Data timeframe (e.g., '1d', '1h')
        mode: Loading mode ('tail', 'backfill', or 'full')
        start: Optional start date override (ISO 8601 format)
        end: Optional end date override (ISO 8601 format)
    """

    symbol: str = Field(..., description="Trading symbol")
    timeframe: str = Field(..., description="Data timeframe (e.g., '1d', '1h')")
    mode: str = Field(
        default="tail", description="Loading mode: 'tail', 'backfill', or 'full'"
    )
    start: Optional[datetime] = Field(None, description="Optional start date override")
    end: Optional[datetime] = Field(None, description="Optional end date override")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"symbol": "MSFT", "timeframe": "1h", "mode": "tail"},
                {
                    "symbol": "AAPL",
                    "timeframe": "1d",
                    "mode": "backfill",
                    "start": "2023-01-01T00:00:00Z",
                    "end": "2024-01-01T00:00:00Z",
                },
                {"symbol": "EURUSD", "timeframe": "1h", "mode": "full"},
            ]
        }
    )

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, v: str) -> str:
        """Validate that the timeframe is supported."""
        valid_timeframes = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]
        if v not in valid_timeframes:
            raise ValueError(f"Timeframe must be one of {valid_timeframes}")
        return v

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        """Validate that the mode is supported."""
        valid_modes = ["tail", "backfill", "full"]
        if v not in valid_modes:
            raise ValueError(f"Mode must be one of {valid_modes}")
        return v

    @model_validator(mode="after")
    def validate_dates(self) -> "IbLoadRequest":
        """Validate date constraints."""
        if self.start and self.end and self.start >= self.end:
            raise ValueError("start must be before end")
        return self


class IbLoadResponse(BaseModel):
    """
    Response from IB data loading operation.

    Attributes:
        status: Operation status ('success', 'partial', 'failed')
        fetched_bars: Number of bars fetched from IB
        cached_before: Whether data existed before the operation
        merged_file: Path to the merged CSV file
        start_time: Actual start time of loaded data
        end_time: Actual end time of loaded data
        requests_made: Number of IB API requests made
        execution_time_seconds: Time taken to complete the operation
        error_message: Error message if operation failed
    """

    status: str = Field(..., description="Operation status")
    fetched_bars: int = Field(..., description="Number of bars fetched from IB")
    cached_before: bool = Field(..., description="Whether data existed before")
    merged_file: str = Field(..., description="Path to the merged CSV file")
    start_time: Optional[datetime] = Field(
        None, description="Actual start time of loaded data"
    )
    end_time: Optional[datetime] = Field(
        None, description="Actual end time of loaded data"
    )
    requests_made: int = Field(default=0, description="Number of IB API requests made")
    execution_time_seconds: float = Field(
        ..., description="Time taken to complete operation"
    )
    error_message: Optional[str] = Field(None, description="Error message if failed")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "status": "success",
                    "fetched_bars": 2432,
                    "cached_before": True,
                    "merged_file": "data/MSFT_1h.csv",
                    "start_time": "2025-05-01T00:00:00Z",
                    "end_time": "2025-05-30T23:00:00Z",
                    "requests_made": 3,
                    "execution_time_seconds": 12.5,
                    "error_message": None,
                },
                {
                    "status": "failed",
                    "fetched_bars": 0,
                    "cached_before": False,
                    "merged_file": "",
                    "start_time": None,
                    "end_time": None,
                    "requests_made": 0,
                    "execution_time_seconds": 2.1,
                    "error_message": "Symbol INVALID not found",
                },
            ]
        }
    )


class SymbolInfo(BaseModel):
    """
    Information about a discovered symbol.
    
    Attributes:
        symbol: The normalized symbol
        instrument_type: Type of instrument (stock, forex, futures, etc.)
        exchange: Primary exchange
        currency: Contract currency
        description: Human-readable description
        discovered_at: Timestamp when first discovered
        last_validated: Timestamp of last successful validation
        validation_count: Number of times this symbol has been validated
        is_active: Whether this symbol is currently tradeable
    """
    
    symbol: str = Field(..., description="The normalized symbol")
    instrument_type: str = Field(..., description="Type of instrument")
    exchange: str = Field(..., description="Primary exchange")
    currency: str = Field(..., description="Contract currency")
    description: str = Field(..., description="Human-readable description")
    discovered_at: float = Field(..., description="Timestamp when first discovered")
    last_validated: float = Field(..., description="Timestamp of last validation")
    validation_count: int = Field(default=1, description="Number of validations")
    is_active: bool = Field(default=True, description="Whether symbol is tradeable")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "symbol": "AAPL",
                "instrument_type": "stock",
                "exchange": "NASDAQ",
                "currency": "USD",
                "description": "Apple Inc.",
                "discovered_at": 1735689600.0,
                "last_validated": 1735689600.0,
                "validation_count": 1,
                "is_active": True
            }
        }
    )


class SymbolDiscoveryRequest(BaseModel):
    """
    Request to discover symbol information.
    
    Attributes:
        symbol: Symbol to discover (e.g., 'AAPL', 'EURUSD')
        force_refresh: Force re-validation even if cached
    """
    
    symbol: str = Field(..., description="Symbol to discover")
    force_refresh: bool = Field(default=False, description="Force re-validation")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "symbol": "EURUSD",
                "force_refresh": False
            }
        }
    )


class SymbolDiscoveryResponse(BaseModel):
    """
    Response from symbol discovery operation.
    
    Attributes:
        symbol_info: Discovered symbol information (null if not found)
        cached: Whether result came from cache
        discovery_time_ms: Time taken to discover symbol
    """
    
    symbol_info: Optional[SymbolInfo] = Field(None, description="Discovered symbol info")
    cached: bool = Field(..., description="Whether result came from cache")
    discovery_time_ms: float = Field(..., description="Discovery time in milliseconds")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "symbol_info": {
                    "symbol": "EURUSD",
                    "instrument_type": "forex",
                    "exchange": "IDEALPRO",
                    "currency": "USD",
                    "description": "EUR.USD",
                    "discovered_at": 1735689600.0,
                    "last_validated": 1735689600.0,
                    "validation_count": 1,
                    "is_active": True
                },
                "cached": False,
                "discovery_time_ms": 125.5
            }
        }
    )


class DiscoveredSymbolsResponse(BaseModel):
    """
    Response containing list of discovered symbols.
    
    Attributes:
        symbols: List of discovered symbols
        total_count: Total number of discovered symbols
        instrument_types: Count by instrument type
        cache_stats: Symbol discovery cache statistics
    """
    
    symbols: List[SymbolInfo] = Field(..., description="List of discovered symbols")
    total_count: int = Field(..., description="Total number of symbols")
    instrument_types: Dict[str, int] = Field(..., description="Count by instrument type")
    cache_stats: Dict[str, Any] = Field(..., description="Cache statistics")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "symbols": [
                    {
                        "symbol": "AAPL",
                        "instrument_type": "stock",
                        "exchange": "NASDAQ",
                        "currency": "USD",
                        "description": "Apple Inc.",
                        "discovered_at": 1735689600.0,
                        "last_validated": 1735689600.0,
                        "validation_count": 5,
                        "is_active": True
                    }
                ],
                "total_count": 15,
                "instrument_types": {
                    "stock": 10,
                    "forex": 4,
                    "futures": 1
                },
                "cache_stats": {
                    "symbol_discoveries": 15,
                    "symbol_cache_hits": 45
                }
            }
        }
    )


# Type aliases for API responses
IbStatusApiResponse = ApiResponse[IbStatusResponse]
IbHealthApiResponse = ApiResponse[IbHealthStatus]
IbConfigApiResponse = ApiResponse[IbConfigInfo]
IbConfigUpdateApiResponse = ApiResponse[IbConfigUpdateResponse]
IbDataRangesApiResponse = ApiResponse[DataRangesResponse]
IbLoadApiResponse = ApiResponse[IbLoadResponse]
SymbolDiscoveryApiResponse = ApiResponse[SymbolDiscoveryResponse]
DiscoveredSymbolsApiResponse = ApiResponse[DiscoveredSymbolsResponse]
