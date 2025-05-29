"""
IB (Interactive Brokers) service for the KTRDR API.

This module provides service layer functionality for IB operations.
"""
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from ktrdr import get_logger
from ktrdr.data.data_manager import DataManager
from ktrdr.api.models.ib import (
    ConnectionInfo,
    ConnectionMetrics,
    DataFetchMetrics,
    IbStatusResponse,
    IbHealthStatus,
    IbConfigInfo
)

logger = get_logger(__name__)


class IbService:
    """
    Service for managing IB operations and status.
    
    This service provides methods for checking IB connection status,
    health monitoring, and configuration information.
    """
    
    def __init__(self, data_manager: Optional[DataManager] = None):
        """
        Initialize the IB service.
        
        Args:
            data_manager: Optional DataManager instance. If not provided,
                         a new instance will be created.
        """
        self.data_manager = data_manager or DataManager()
        logger.info("IbService initialized")
    
    def get_status(self) -> IbStatusResponse:
        """
        Get comprehensive IB status information.
        
        Returns:
            IbStatusResponse with connection info, metrics, and availability
        """
        # Check if IB components are available
        ib_available = (
            self.data_manager.ib_connection is not None and 
            self.data_manager.ib_fetcher is not None
        )
        
        if not ib_available:
            # Return minimal status when IB is not available
            return IbStatusResponse(
                connection=ConnectionInfo(
                    connected=False,
                    host="",
                    port=0,
                    client_id=0,
                    connection_time=None
                ),
                connection_metrics=ConnectionMetrics(
                    total_connections=0,
                    failed_connections=0,
                    last_connect_time=None,
                    last_disconnect_time=None,
                    uptime_seconds=None
                ),
                data_metrics=DataFetchMetrics(
                    total_requests=0,
                    successful_requests=0,
                    failed_requests=0,
                    total_bars_fetched=0,
                    success_rate=0.0
                ),
                ib_available=False
            )
        
        # Get connection info
        conn = self.data_manager.ib_connection
        is_connected = conn.is_connected()
        
        # Calculate connection time if connected
        connection_time = None
        uptime_seconds = None
        if is_connected and conn.metrics.get("last_connect_time"):
            connection_time = datetime.fromtimestamp(
                conn.metrics["last_connect_time"], 
                tz=timezone.utc
            )
            uptime_seconds = time.time() - conn.metrics["last_connect_time"]
        
        connection_info = ConnectionInfo(
            connected=is_connected,
            host=conn.config.host,
            port=conn.config.port,
            client_id=conn.config.client_id,
            connection_time=connection_time
        )
        
        # Get connection metrics
        connection_metrics = ConnectionMetrics(
            total_connections=conn.metrics.get("total_connections", 0),
            failed_connections=conn.metrics.get("failed_connections", 0),
            last_connect_time=conn.metrics.get("last_connect_time"),
            last_disconnect_time=conn.metrics.get("last_disconnect_time"),
            uptime_seconds=uptime_seconds
        )
        
        # Get data fetching metrics
        fetcher_metrics = self.data_manager.ib_fetcher.get_metrics()
        data_metrics = DataFetchMetrics(
            total_requests=fetcher_metrics.get("total_requests", 0),
            successful_requests=fetcher_metrics.get("successful_requests", 0),
            failed_requests=fetcher_metrics.get("failed_requests", 0),
            total_bars_fetched=fetcher_metrics.get("total_bars_fetched", 0),
            success_rate=fetcher_metrics.get("success_rate", 0.0) * 100  # Convert to percentage
        )
        
        return IbStatusResponse(
            connection=connection_info,
            connection_metrics=connection_metrics,
            data_metrics=data_metrics,
            ib_available=ib_available
        )
    
    def get_health(self) -> IbHealthStatus:
        """
        Perform health check on IB connection and functionality.
        
        Returns:
            IbHealthStatus indicating overall health
        """
        # Check if IB is available
        if not (self.data_manager.ib_connection and self.data_manager.ib_fetcher):
            return IbHealthStatus(
                healthy=False,
                connection_ok=False,
                data_fetching_ok=False,
                last_successful_request=None,
                error_message="IB integration not available"
            )
        
        # Check connection
        connection_ok = self.data_manager.ib_connection.is_connected()
        
        # Check data fetching (based on success rate)
        fetcher_metrics = self.data_manager.ib_fetcher.get_metrics()
        success_rate = fetcher_metrics.get("success_rate", 0.0)
        data_fetching_ok = success_rate > 0.9  # Consider healthy if >90% success rate
        
        # Get last successful request time
        last_successful_request = None
        if fetcher_metrics.get("successful_requests", 0) > 0:
            # This is a simplified approach - in production you might track this explicitly
            last_successful_request = datetime.now(timezone.utc)
        
        # Determine overall health
        healthy = connection_ok and data_fetching_ok
        
        # Build error message if unhealthy
        error_message = None
        if not healthy:
            errors = []
            if not connection_ok:
                errors.append("Connection is down")
            if not data_fetching_ok:
                errors.append(f"Data fetching success rate too low ({success_rate:.1%})")
            error_message = "; ".join(errors)
        
        return IbHealthStatus(
            healthy=healthy,
            connection_ok=connection_ok,
            data_fetching_ok=data_fetching_ok,
            last_successful_request=last_successful_request,
            error_message=error_message
        )
    
    def get_config(self) -> IbConfigInfo:
        """
        Get IB configuration information.
        
        Returns:
            IbConfigInfo with current configuration
        """
        # Default config if IB not available
        if not self.data_manager.ib_connection:
            return IbConfigInfo(
                host="",
                port=0,
                client_id_range={"min": 0, "max": 0},
                timeout=0,
                readonly=False,
                rate_limit={}
            )
        
        conn = self.data_manager.ib_connection
        config = conn.config
        
        return IbConfigInfo(
            host=config.host,
            port=config.port,
            client_id_range={"min": 1000, "max": 9999},  # Based on our implementation
            timeout=config.timeout,
            readonly=config.readonly,
            rate_limit={
                "max_requests": 60,  # IB limit
                "period_seconds": 600,  # 10 minutes
                "pacing_delay": 0.6
            }
        )
    
    async def cleanup_connections(self) -> Dict[str, Any]:
        """
        Clean up all IB connections.
        
        Returns:
            Dictionary with cleanup results
        """
        if not self.data_manager.ib_connection:
            return {
                "success": False,
                "message": "IB integration not available",
                "connections_closed": 0
            }
        
        try:
            # Disconnect current connection
            was_connected = self.data_manager.ib_connection.is_connected()
            if was_connected:
                self.data_manager.ib_connection.disconnect()
                logger.info("Disconnected IB connection")
            
            return {
                "success": True,
                "message": "IB connections cleaned up successfully",
                "connections_closed": 1 if was_connected else 0
            }
            
        except Exception as e:
            logger.error(f"Error cleaning up IB connections: {e}")
            return {
                "success": False,
                "message": f"Cleanup failed: {str(e)}",
                "connections_closed": 0
            }