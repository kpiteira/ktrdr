"""
IB (Interactive Brokers) models for the KTRDR API.

This module defines the request and response models for IB-related endpoints.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
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
    connection_time: Optional[datetime] = Field(None, description="When connection was established")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "connected": True,
                "host": "127.0.0.1",
                "port": 4002,
                "client_id": 1234,
                "connection_time": "2025-05-29T10:30:00Z"
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
    failed_connections: int = Field(..., description="Number of failed connection attempts")
    last_connect_time: Optional[float] = Field(None, description="Timestamp of last successful connection")
    last_disconnect_time: Optional[float] = Field(None, description="Timestamp of last disconnect")
    uptime_seconds: Optional[float] = Field(None, description="Current connection uptime in seconds")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_connections": 5,
                "failed_connections": 1,
                "last_connect_time": 1735484400.0,
                "last_disconnect_time": 1735480800.0,
                "uptime_seconds": 3600.0
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
                "success_rate": 98.0
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
    connection: ConnectionInfo = Field(..., description="Current connection information")
    connection_metrics: ConnectionMetrics = Field(..., description="Connection performance metrics")
    data_metrics: DataFetchMetrics = Field(..., description="Data fetching performance metrics")
    ib_available: bool = Field(..., description="Whether IB integration is available")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "connection": {
                    "connected": True,
                    "host": "127.0.0.1",
                    "port": 4002,
                    "client_id": 1234,
                    "connection_time": "2025-05-29T10:30:00Z"
                },
                "connection_metrics": {
                    "total_connections": 5,
                    "failed_connections": 1,
                    "last_connect_time": 1735484400.0,
                    "last_disconnect_time": 1735480800.0,
                    "uptime_seconds": 3600.0
                },
                "data_metrics": {
                    "total_requests": 100,
                    "successful_requests": 98,
                    "failed_requests": 2,
                    "total_bars_fetched": 7500,
                    "success_rate": 98.0
                },
                "ib_available": True
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
    connection_ok: bool = Field(..., description="Whether connection is established and working")
    data_fetching_ok: bool = Field(..., description="Whether data fetching is working")
    last_successful_request: Optional[datetime] = Field(None, description="Time of last successful data request")
    error_message: Optional[str] = Field(None, description="Error message if unhealthy")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "healthy": True,
                "connection_ok": True,
                "data_fetching_ok": True,
                "last_successful_request": "2025-05-29T11:45:00Z",
                "error_message": None
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
                    "pacing_delay": 0.6
                }
            }
        }
    )

# Type aliases for API responses
IbStatusApiResponse = ApiResponse[IbStatusResponse]
IbHealthApiResponse = ApiResponse[IbHealthStatus]
IbConfigApiResponse = ApiResponse[IbConfigInfo]