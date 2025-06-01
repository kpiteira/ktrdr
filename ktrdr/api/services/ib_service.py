"""
IB (Interactive Brokers) service for the KTRDR API.

This module provides service layer functionality for IB operations.
"""

import time
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path

from ktrdr import get_logger
from ktrdr.data.data_manager import DataManager
from ktrdr.data.ib_data_loader import IbDataLoader
from ktrdr.data.ib_connection_strategy import get_connection_strategy
from ktrdr.data.ib_data_fetcher_sync import IbDataRangeDiscovery, IbDataFetcherSync
from ktrdr.config.ib_limits import IbLimitsRegistry
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
    DataRangesResponse,
    IbLoadRequest,
    IbLoadResponse,
)
from ktrdr.config.ib_config import reset_ib_config, IbConfig

logger = get_logger(__name__)


class IbService:
    """
    Service for managing IB operations and status.

    This service provides methods for checking IB connection status,
    health monitoring, and configuration information.
    """

    def __init__(self, data_manager: Optional[DataManager] = None, data_loader: Optional[IbDataLoader] = None):
        """
        Initialize the IB service.

        Args:
            data_manager: Optional DataManager instance. If not provided,
                         a new instance will be created.
            data_loader: Optional IbDataLoader instance for dependency injection.
        """
        self.data_manager = data_manager or DataManager()
        
        # Use injected data loader or create default
        if data_loader:
            self.data_loader = data_loader
        else:
            # Create default data loader with API connection strategy
            connection_strategy = get_connection_strategy()
            self.data_dir = self._get_data_dir()
            self.data_loader = IbDataLoader(
                connection_strategy=connection_strategy,
                data_dir=self.data_dir,
                validate_data=True
            )
        
        logger.info("IbService initialized")

    def _get_data_dir(self) -> str:
        """Get data directory from configuration."""
        try:
            from ktrdr.config.loader import ConfigLoader

            config_loader = ConfigLoader()
            config = config_loader.load_from_env(default_path="config/settings.yaml")
            if hasattr(config, "data") and hasattr(config.data, "directory"):
                return config.data.directory
            return "data"
        except Exception:
            return "data"

    def get_status(self) -> IbStatusResponse:
        """
        Get comprehensive IB status information.

        Returns:
            IbStatusResponse with connection info, metrics, and availability
        """
        # Check if IB connection is available via connection strategy
        try:
            connection_strategy = get_connection_strategy()
            connection = connection_strategy.get_connection_for_operation("api_call")
            ib_available = connection is not None and connection.is_connected()
        except Exception:
            ib_available = False
            connection = None

        if not ib_available:
            # Return minimal status when IB is not available
            return IbStatusResponse(
                connection=ConnectionInfo(
                    connected=False, host="", port=0, client_id=0, connection_time=None
                ),
                connection_metrics=ConnectionMetrics(
                    total_connections=0,
                    failed_connections=0,
                    last_connect_time=None,
                    last_disconnect_time=None,
                    uptime_seconds=None,
                ),
                data_metrics=DataFetchMetrics(
                    total_requests=0,
                    successful_requests=0,
                    failed_requests=0,
                    total_bars_fetched=0,
                    success_rate=0.0,
                ),
                ib_available=False,
            )

        # Get connection info from connection strategy
        connection_strategy = get_connection_strategy()
        connection_status = connection_strategy.get_connection_status()

        connection_info = ConnectionInfo(
            connected=ib_available,
            host=connection.config.host if connection else "",
            port=connection.config.port if connection else 0,
            client_id=connection.config.client_id if connection and connection.config.client_id is not None else 0,
            connection_time=datetime.now(timezone.utc) if ib_available else None,
        )

        # Get connection metrics from connection strategy
        connection_metrics = ConnectionMetrics(
            total_connections=connection_status.get("total_connections", 0),
            failed_connections=0,  # Connection strategy doesn't track failures yet
            last_connect_time=None,  # Will be enhanced in future
            last_disconnect_time=None,
            uptime_seconds=None,
        )

        # Get data fetching metrics from data loader
        data_loader_stats = self.data_loader.get_stats()
        data_metrics = DataFetchMetrics(
            total_requests=data_loader_stats.get("total_requests", 0),
            successful_requests=data_loader_stats.get("successful_requests", 0),
            failed_requests=data_loader_stats.get("failed_requests", 0),
            total_bars_fetched=data_loader_stats.get("total_bars_fetched", 0),
            success_rate=data_loader_stats.get("success_rate", 0.0),
        )

        return IbStatusResponse(
            connection=connection_info,
            connection_metrics=connection_metrics,
            data_metrics=data_metrics,
            ib_available=ib_available,
        )

    def get_health(self) -> IbHealthStatus:
        """
        Perform health check on IB connection and functionality.

        Returns:
            IbHealthStatus indicating overall health
        """
        # Check if IB connection is available via connection strategy
        try:
            connection_strategy = get_connection_strategy()
            connection = connection_strategy.get_connection_for_operation("api_call")
        except Exception:
            connection = None
            
        if not connection:
            return IbHealthStatus(
                healthy=False,
                connection_ok=False,
                data_fetching_ok=False,
                last_successful_request=None,
                error_message="IB connection not available",
            )

        # Check connection using connection strategy and actual IB connection
        actual_connected = connection.is_connected() if connection else False

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
                    logger.debug(
                        f"✅ IB API test successful: {len(accounts)} accounts found"
                    )
                else:
                    logger.warning(
                        "❌ IB API test failed: managedAccounts() returned None"
                    )
        except Exception as e:
            logger.warning(f"❌ IB API test failed: {e}")
            api_test_ok = False

        # Connection is only OK if all checks pass
        connection_ok = actual_connected and api_test_ok

        # Data fetching is OK if we can successfully make API calls
        data_fetching_ok = api_test_ok

        # Get last successful request time - for now we'll use current time if connected
        last_successful_request = datetime.now(timezone.utc) if connection_ok else None

        # Determine overall health
        healthy = connection_ok and data_fetching_ok

        # Build error message if unhealthy
        error_message = None
        if not healthy:
            errors = []
            if not connection_ok:
                errors.append("Connection is down")
            if not data_fetching_ok:
                errors.append("Data fetching is not working")
            error_message = "; ".join(errors)

        return IbHealthStatus(
            healthy=healthy,
            connection_ok=connection_ok,
            data_fetching_ok=data_fetching_ok,
            last_successful_request=last_successful_request,
            error_message=error_message,
        )

    def get_config(self) -> IbConfigInfo:
        """
        Get IB configuration information.

        Returns:
            IbConfigInfo with current configuration
        """
        # Get connection from connection strategy
        try:
            connection_strategy = get_connection_strategy()
            connection = connection_strategy.get_connection_for_operation("api_call")
        except Exception:
            connection = None
        if not connection:
            return IbConfigInfo(
                host="",
                port=0,
                client_id_range={"min": 0, "max": 0},
                timeout=0,
                readonly=False,
                rate_limit={},
            )

        config = connection.config

        return IbConfigInfo(
            host=config.host,
            port=config.port,
            client_id_range={"min": 1000, "max": 9999},  # Based on our implementation
            timeout=config.timeout,
            readonly=config.readonly,
            rate_limit={
                "max_requests": 60,  # IB limit
                "period_seconds": 600,  # 10 minutes
                "pacing_delay": 0.6,
            },
        )

    async def cleanup_connections(self) -> Dict[str, Any]:
        """
        Clean up all IB connections.

        Returns:
            Dictionary with cleanup results
        """
        try:
            connection_strategy = get_connection_strategy()
            connection = connection_strategy.get_connection_for_operation("api_call")
        except Exception:
            connection = None
            
        if not connection:
            return {
                "success": False,
                "message": "IB integration not available",
                "connections_closed": 0,
            }

        try:
            # Disconnect current connection
            was_connected = connection.is_connected()
            if was_connected:
                connection.disconnect()
                logger.info("Disconnected IB connection")

            return {
                "success": True,
                "message": "IB connections cleaned up successfully",
                "connections_closed": 1 if was_connected else 0,
            }

        except Exception as e:
            logger.error(f"Error cleaning up IB connections: {e}")
            return {
                "success": False,
                "message": f"Cleanup failed: {str(e)}",
                "connections_closed": 0,
            }

    async def update_config(
        self, request: IbConfigUpdateRequest
    ) -> IbConfigUpdateResponse:
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
        try:
            connection_strategy = get_connection_strategy()
            current_connection = connection_strategy.get_connection_for_operation("api_call")
        except Exception:
            current_connection = None
            
        current_ib_config = current_connection.config if current_connection else IbConfig()

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
            if current_connection and current_connection.is_connected():
                reconnect_required = True
            os.environ["IB_CLIENT_ID"] = str(request.client_id)

        # Reset the configuration to pick up new environment variables
        reset_ib_config()

        # Recreate data manager with new configuration
        if reconnect_required:
            # Disconnect existing connection if any
            if current_connection and current_connection.is_connected():
                current_connection.disconnect()
                logger.info("Disconnected existing IB connection for reconfiguration")

            # Create new data manager with updated configuration
            self.data_manager = DataManager()
            logger.info("Created new DataManager with updated IB configuration")

        # Get new configuration
        new_config = self.get_config()

        return IbConfigUpdateResponse(
            previous_config=previous_config,
            new_config=new_config,
            reconnect_required=reconnect_required,
        )

    def get_data_ranges(
        self, symbols: List[str], timeframes: List[str]
    ) -> DataRangesResponse:
        """
        Get historical data ranges for multiple symbols and timeframes.

        Args:
            symbols: List of symbols to check
            timeframes: List of timeframes to check (e.g., ['1d', '1h'])

        Returns:
            DataRangesResponse with range information
        """
        # Check if IB is available
        try:
            connection_strategy = get_connection_strategy()
            connection = connection_strategy.get_connection_for_operation("api_call")
        except Exception:
            connection = None
            
        if not connection:
            raise ValueError("IB integration not available")

        # Create range discovery instance  
        ib_fetcher = IbDataFetcherSync(connection)
        range_discovery = IbDataRangeDiscovery(ib_fetcher)

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
            ranges: Dict[str, Optional[DataRangeInfo]] = {}
            for timeframe in timeframes:
                data_range = multiple_ranges.get(symbol, {}).get(timeframe)

                if data_range:
                    start_date, end_date = data_range

                    # Handle timezone-aware datetime objects
                    if hasattr(start_date, "to_pydatetime"):
                        start_date = start_date.to_pydatetime()
                    if hasattr(end_date, "to_pydatetime"):
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
                        cached=was_cached,
                    )
                else:
                    ranges[timeframe] = None

            symbol_responses.append(SymbolRangeResponse(symbol=symbol, ranges=ranges))

        # Get cache statistics
        cache_stats = range_discovery.get_cache_stats()

        return DataRangesResponse(
            symbols=symbol_responses,
            requested_timeframes=timeframes,
            cache_stats=cache_stats,
        )

    def load_data(self, request: IbLoadRequest) -> IbLoadResponse:
        """
        Load data from IB with support for different modes.

        Args:
            request: Data loading request with symbol, timeframe, mode, and optional date range

        Returns:
            IbLoadResponse with operation results
        """
        start_time = time.time()

        try:
            # Check if CSV exists before operation  
            data_dir = getattr(self.data_loader, 'data_dir', self._get_data_dir())
            csv_path = Path(data_dir) / f"{request.symbol}_{request.timeframe}.csv"
            cached_before = csv_path.exists()

            # Determine start and end dates based on request mode
            actual_start, actual_end = self._determine_date_range(request)

            if actual_start is None or actual_end is None:
                return IbLoadResponse(
                    status="failed",
                    fetched_bars=0,
                    cached_before=cached_before,
                    merged_file="",
                    start_time=None,
                    end_time=None,
                    requests_made=0,
                    execution_time_seconds=time.time() - start_time,
                    error_message="Unable to determine valid date range for loading",
                )

            # Check if the date range is reasonable
            gap_days = (actual_end - actual_start).days if actual_start and actual_end else 0
            if gap_days <= 0:
                return IbLoadResponse(
                    status="success",
                    fetched_bars=0,
                    cached_before=cached_before,
                    merged_file=str(csv_path),
                    start_time=actual_start,
                    end_time=actual_end,
                    requests_made=0,
                    execution_time_seconds=time.time() - start_time,
                    error_message=None,
                )

            # Use unified data loader for all operations
            final_data, metadata = self.data_loader.load_with_existing_check(
                symbol=request.symbol,
                timeframe=request.timeframe,
                start=actual_start,
                end=actual_end,
                operation_type="api_call"
            )

            return IbLoadResponse(
                status="success" if metadata["fetched_bars"] >= 0 else "failed",
                fetched_bars=metadata["fetched_bars"],
                cached_before=metadata["cached_before"],
                merged_file=str(csv_path),
                start_time=actual_start,
                end_time=actual_end,
                requests_made=1,  # Data loader handles progressive requests internally
                execution_time_seconds=metadata["execution_time_seconds"],
                error_message=None,
            )

        except Exception as e:
            logger.error(
                f"Error loading data for {request.symbol}_{request.timeframe}: {e}"
            )
            return IbLoadResponse(
                status="failed",
                fetched_bars=0,
                cached_before=cached_before if "cached_before" in locals() else False,
                merged_file="",
                start_time=None,
                end_time=None,
                requests_made=0,
                execution_time_seconds=time.time() - start_time,
                error_message=str(e),
            )

    def _determine_date_range(
        self, request: IbLoadRequest
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        """
        Determine the actual start and end dates for data loading based on mode.

        As per specification: If no local CSV exists, treat ALL modes as "full initialization".

        Args:
            request: Load request with mode and optional date overrides

        Returns:
            Tuple of (start_time, end_time) or (None, None) if unable to determine
        """
        current_time = datetime.now(timezone.utc)
        
        # Use explicit date overrides if provided
        if request.start or request.end:
            start_time = request.start
            end_time = request.end or current_time  # Default end to now if not provided

            if start_time:
                # Ensure timezone-aware
                if start_time.tzinfo is None:
                    start_time = start_time.replace(tzinfo=timezone.utc)
            
            if end_time:
                # Ensure timezone-aware
                if end_time.tzinfo is None:
                    end_time = end_time.replace(tzinfo=timezone.utc)
                    
            # If only end date provided, use IB limits to calculate start
            if not start_time and end_time:
                max_duration = IbLimitsRegistry.get_duration_limit(request.timeframe)
                start_time = end_time - max_duration
                
            return start_time, end_time

        # Check if CSV exists for this symbol/timeframe
        data_dir = getattr(self.data_loader, 'data_dir', self._get_data_dir())
        csv_path = Path(data_dir) / f"{request.symbol}_{request.timeframe}.csv"
        csv_exists = csv_path.exists() and csv_path.stat().st_size > 100  # Must have content
        
        if not csv_exists:
            # SPECIFICATION: "CSV not found: treat all modes as full initialization"
            logger.info(f"No CSV found for {request.symbol}_{request.timeframe}, treating {request.mode} mode as full initialization")
            max_duration = IbLimitsRegistry.get_duration_limit(request.timeframe)
            start_time = current_time - max_duration
            end_time = current_time
            return start_time, end_time
            
        # CSV exists - handle modes based on existing data
        if request.mode == "full":
            # Full mode: get maximum available history based on IB limits
            max_duration = IbLimitsRegistry.get_duration_limit(request.timeframe)
            start_time = current_time - max_duration
            end_time = current_time
            
        elif request.mode == "tail":
            # Tail mode: load from end of existing CSV to now
            try:
                # Load existing data to find the latest timestamp
                from ktrdr.data.local_data_loader import LocalDataLoader
                local_loader = LocalDataLoader(data_dir=str(data_dir))
                existing_df = local_loader.load(request.symbol, request.timeframe)
                
                if not existing_df.empty:
                    latest_timestamp = existing_df.index.max()
                    # Start from next period after latest data
                    if request.timeframe == "1h":
                        start_time = latest_timestamp + pd.Timedelta(hours=1)
                    else:
                        start_time = latest_timestamp + pd.Timedelta(days=1)
                    end_time = current_time
                else:
                    # Empty CSV - treat as full initialization
                    max_duration = IbLimitsRegistry.get_duration_limit(request.timeframe)
                    start_time = current_time - max_duration
                    end_time = current_time
                    
            except Exception as e:
                logger.warning(f"Error reading existing CSV for tail mode: {e}, treating as full initialization")
                max_duration = IbLimitsRegistry.get_duration_limit(request.timeframe)
                start_time = current_time - max_duration
                end_time = current_time
                
        elif request.mode == "backfill":
            # Backfill mode: load before earliest existing data
            try:
                from ktrdr.data.local_data_loader import LocalDataLoader
                local_loader = LocalDataLoader(data_dir=str(data_dir))
                existing_df = local_loader.load(request.symbol, request.timeframe)
                
                if not existing_df.empty:
                    earliest_timestamp = existing_df.index.min()
                    # Backfill some reasonable amount based on timeframe
                    backfill_duration = IbLimitsRegistry.get_duration_limit(request.timeframe)
                    start_time = earliest_timestamp - backfill_duration
                    if request.timeframe == "1h":
                        end_time = earliest_timestamp - pd.Timedelta(hours=1)
                    else:
                        end_time = earliest_timestamp - pd.Timedelta(days=1)
                else:
                    # Empty CSV - treat as full initialization
                    max_duration = IbLimitsRegistry.get_duration_limit(request.timeframe)
                    start_time = current_time - max_duration
                    end_time = current_time
                    
            except Exception as e:
                logger.warning(f"Error reading existing CSV for backfill mode: {e}, treating as full initialization")
                max_duration = IbLimitsRegistry.get_duration_limit(request.timeframe)
                start_time = current_time - max_duration
                end_time = current_time
        else:
            logger.error(f"Unknown mode: {request.mode}")
            return None, None

        return start_time, end_time

