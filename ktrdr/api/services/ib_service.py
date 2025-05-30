"""
IB (Interactive Brokers) service for the KTRDR API.

This module provides service layer functionality for IB operations.
"""
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from ktrdr import get_logger
from ktrdr.data.data_manager import DataManager
from ktrdr.data.ib_connection_manager import get_connection_manager
from ktrdr.data.ib_data_fetcher_sync import IbDataRangeDiscovery
from ktrdr.api.models.ib import (
    ConnectionInfo,
    ConnectionMetrics,
    DataFetchMetrics,
    IbStatusResponse,
    IbHealthStatus,
    IbConfigInfo,
    IbConfigUpdateRequest,
    IbConfigUpdateResponse,
    DataRangeInfo,
    SymbolRangeResponse,
    DataRangesResponse
)
from ktrdr.config.ib_config import reset_ib_config, IbConfig

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
        self.connection_manager = get_connection_manager()
        logger.info("IbService initialized")
    
    def get_status(self) -> IbStatusResponse:
        """
        Get comprehensive IB status information.
        
        Returns:
            IbStatusResponse with connection info, metrics, and availability
        """
        # Check if IB connection is available via persistent connection manager
        connection = self.connection_manager.get_connection()
        ib_available = connection is not None and connection.is_connected()
        
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
        
        # Get connection info from persistent connection manager
        status = self.connection_manager.get_status()
        metrics = self.connection_manager.get_metrics()
        
        connection_info = ConnectionInfo(
            connected=status.connected,
            host=status.host,
            port=status.port,
            client_id=status.client_id,
            connection_time=status.last_connect_time
        )
        
        # Get connection metrics from connection manager
        connection_metrics = ConnectionMetrics(
            total_connections=status.connection_attempts,
            failed_connections=status.failed_attempts,
            last_connect_time=status.last_connect_time.timestamp() if status.last_connect_time else None,
            last_disconnect_time=status.last_disconnect_time.timestamp() if status.last_disconnect_time else None,
            uptime_seconds=metrics.get("uptime_seconds")
        )
        
        # For data fetching metrics, we'll use placeholder values since
        # the persistent connection manager doesn't track these yet
        data_metrics = DataFetchMetrics(
            total_requests=0,
            successful_requests=0,
            failed_requests=0,
            total_bars_fetched=0,
            success_rate=0.0
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
        # Check if IB connection is available via persistent connection manager
        connection = self.connection_manager.get_connection()
        if not connection:
            return IbHealthStatus(
                healthy=False,
                connection_ok=False,
                data_fetching_ok=False,
                last_successful_request=None,
                error_message="IB connection not available"
            )
        
        # Check connection using both manager state and actual IB connection
        manager_connected = self.connection_manager.is_connected()
        actual_connected = connection.is_connected()
        
        # REAL IB API TEST: Actually try to make an API call to verify connection works
        api_test_ok = False
        try:
            # Try to get account information - this is a simple API call that will fail if transport is broken
            if actual_connected:
                ib = connection.ib
                # Test 1: Try to get managed accounts (simple and fast)
                accounts = ib.managedAccounts()
                if accounts is not None:  # Even empty list is OK
                    api_test_ok = True
                    logger.debug(f"✅ IB API test successful: {len(accounts)} accounts found")
                else:
                    logger.warning("❌ IB API test failed: managedAccounts() returned None")
        except Exception as e:
            logger.warning(f"❌ IB API test failed: {e}")
            api_test_ok = False
        
        # Connection is only OK if all checks pass
        connection_ok = manager_connected and actual_connected and api_test_ok
        
        # Data fetching is OK if we can successfully make API calls
        data_fetching_ok = api_test_ok
        
        # Get last successful request time from connection status
        status = self.connection_manager.get_status()
        last_successful_request = status.last_connect_time
        
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
    
    async def update_config(self, request: IbConfigUpdateRequest) -> IbConfigUpdateResponse:
        """
        Update IB configuration dynamically.
        
        This method updates the IB configuration and determines if reconnection
        is required for the changes to take effect.
        
        Args:
            request: Configuration update request
            
        Returns:
            IbConfigUpdateResponse with previous and new configuration
        """
        # Get current configuration
        previous_config = self.get_config()
        
        # Create new configuration based on current + updates
        current_ib_config = self.data_manager.ib_connection.config if self.data_manager.ib_connection else IbConfig()
        
        # Track if we need to reconnect
        reconnect_required = False
        
        # Update configuration values
        if request.port is not None and request.port != current_ib_config.port:
            # Port change requires reconnection
            reconnect_required = True
            # Update port in environment variable so it persists
            import os
            os.environ["IB_PORT"] = str(request.port)
            
        if request.host is not None and request.host != current_ib_config.host:
            # Host change requires reconnection
            reconnect_required = True
            os.environ["IB_HOST"] = request.host
            
        if request.client_id is not None:
            # Client ID change requires reconnection if we're connected
            if self.data_manager.ib_connection and self.data_manager.ib_connection.is_connected():
                reconnect_required = True
            os.environ["IB_CLIENT_ID"] = str(request.client_id)
        
        # Reset the configuration to pick up new environment variables
        reset_ib_config()
        
        # Recreate data manager with new configuration
        if reconnect_required:
            # Disconnect existing connection if any
            if self.data_manager.ib_connection and self.data_manager.ib_connection.is_connected():
                self.data_manager.ib_connection.disconnect()
                logger.info("Disconnected existing IB connection for reconfiguration")
            
            # Create new data manager with updated configuration
            self.data_manager = DataManager()
            logger.info("Created new DataManager with updated IB configuration")
        
        # Get new configuration
        new_config = self.get_config()
        
        return IbConfigUpdateResponse(
            previous_config=previous_config,
            new_config=new_config,
            reconnect_required=reconnect_required
        )
    
    def get_data_ranges(self, symbols: List[str], timeframes: List[str]) -> DataRangesResponse:
        """
        Get historical data ranges for multiple symbols and timeframes.
        
        Args:
            symbols: List of symbols to check
            timeframes: List of timeframes to check (e.g., ['1d', '1h'])
            
        Returns:
            DataRangesResponse with range information
        """
        # Check if IB is available
        if not (self.data_manager.ib_connection and self.data_manager.ib_fetcher):
            raise ValueError("IB integration not available")
        
        # Create range discovery instance
        range_discovery = IbDataRangeDiscovery(self.data_manager.ib_fetcher)
        
        # Track which results were cached
        cached_ranges = set()
        for symbol in symbols:
            for timeframe in timeframes:
                if range_discovery._get_cached_range(symbol, timeframe):
                    cached_ranges.add(f"{symbol}:{timeframe}")
        
        # Get ranges for all symbols/timeframes
        multiple_ranges = range_discovery.get_multiple_ranges(symbols, timeframes)
        
        # Convert to API response format
        symbol_responses = []
        for symbol in symbols:
            ranges = {}
            for timeframe in timeframes:
                data_range = multiple_ranges.get(symbol, {}).get(timeframe)
                
                if data_range:
                    start_date, end_date = data_range
                    
                    # Handle timezone-aware datetime objects
                    if hasattr(start_date, 'to_pydatetime'):
                        start_date = start_date.to_pydatetime()
                    if hasattr(end_date, 'to_pydatetime'):
                        end_date = end_date.to_pydatetime()
                    
                    # Calculate total days, handling timezone differences
                    if start_date.tzinfo and not end_date.tzinfo:
                        end_date = end_date.replace(tzinfo=start_date.tzinfo)
                    elif end_date.tzinfo and not start_date.tzinfo:
                        start_date = start_date.replace(tzinfo=end_date.tzinfo)
                    
                    total_days = (end_date - start_date).days
                    was_cached = f"{symbol}:{timeframe}" in cached_ranges
                    
                    ranges[timeframe] = DataRangeInfo(
                        earliest_date=start_date,
                        latest_date=end_date,
                        total_days=total_days,
                        cached=was_cached
                    )
                else:
                    ranges[timeframe] = None
            
            symbol_responses.append(SymbolRangeResponse(
                symbol=symbol,
                ranges=ranges
            ))
        
        # Get cache statistics
        cache_stats = range_discovery.get_cache_stats()
        
        return DataRangesResponse(
            symbols=symbol_responses,
            requested_timeframes=timeframes,
            cache_stats=cache_stats
        )