"""
IB (Interactive Brokers) service for the KTRDR API.

This module provides service layer functionality for IB operations.
"""

import time
import os
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path

from ktrdr import get_logger
from ktrdr.data.data_manager import DataManager
from ktrdr.data.ib_connection_manager import get_connection_manager
from ktrdr.data.ib_data_fetcher_sync import IbDataRangeDiscovery, IbDataFetcherSync
from ktrdr.data.ib_context_manager import create_context_aware_fetcher
from ktrdr.data.local_data_loader import LocalDataLoader
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

    def __init__(self, data_manager: Optional[DataManager] = None):
        """
        Initialize the IB service.

        Args:
            data_manager: Optional DataManager instance. If not provided,
                         a new instance will be created.
        """
        self.data_manager = data_manager or DataManager()
        self.connection_manager = get_connection_manager()
        self.data_dir = self._get_data_dir()
        self.data_loader = LocalDataLoader(data_dir=self.data_dir)
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
        # Check if IB connection is available via persistent connection manager
        connection = self.connection_manager.get_connection()
        ib_available = connection is not None and connection.is_connected()

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

        # Get connection info from persistent connection manager
        status = self.connection_manager.get_status()
        metrics = self.connection_manager.get_metrics()

        connection_info = ConnectionInfo(
            connected=status.connected,
            host=status.host or "",
            port=status.port or 0,
            client_id=status.client_id or 0,
            connection_time=status.last_connect_time,
        )

        # Get connection metrics from connection manager
        connection_metrics = ConnectionMetrics(
            total_connections=status.connection_attempts,
            failed_connections=status.failed_attempts,
            last_connect_time=(
                status.last_connect_time.timestamp()
                if status.last_connect_time
                else None
            ),
            last_disconnect_time=(
                status.last_disconnect_time.timestamp()
                if status.last_disconnect_time
                else None
            ),
            uptime_seconds=metrics.get("uptime_seconds"),
        )

        # For data fetching metrics, we'll use placeholder values since
        # the persistent connection manager doesn't track these yet
        data_metrics = DataFetchMetrics(
            total_requests=0,
            successful_requests=0,
            failed_requests=0,
            total_bars_fetched=0,
            success_rate=0.0,
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
        # Check if IB connection is available via persistent connection manager
        connection = self.connection_manager.get_connection()
        if not connection:
            return IbHealthStatus(
                healthy=False,
                connection_ok=False,
                data_fetching_ok=False,
                last_successful_request=None,
                error_message="IB connection not available",
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
        # Get connection from connection manager
        connection = self.connection_manager.get_connection()
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
        connection = self.connection_manager.get_connection()
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
        current_connection = self.connection_manager.get_connection()
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
        connection = self.connection_manager.get_connection()
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

        # Check if IB connection is available
        connection = self.connection_manager.get_connection()
        if not connection or not connection.is_connected():
            return IbLoadResponse(
                status="failed",
                fetched_bars=0,
                cached_before=False,
                merged_file="",
                start_time=None,
                end_time=None,
                requests_made=0,
                execution_time_seconds=time.time() - start_time,
                error_message="IB connection not available",
            )

        try:
            # Check if CSV exists before operation
            csv_path = Path(self.data_dir) / f"{request.symbol}_{request.timeframe}.csv"
            cached_before = csv_path.exists()

            # Load existing data to determine date ranges
            existing_data = None
            if cached_before:
                try:
                    existing_data = self.data_loader.load(
                        request.symbol, request.timeframe
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to load existing data for {request.symbol}_{request.timeframe}: {e}"
                    )
                    existing_data = None

            # Determine actual start and end dates based on mode
            actual_start, actual_end = self._determine_date_range(
                request, existing_data
            )

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
            gap_days = (actual_end - actual_start).days
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

            # Perform progressive loading for large gaps
            success, fetched_data, requests_made = self._load_data_progressive(
                request.symbol, request.timeframe, actual_start, actual_end
            )

            if not success or fetched_data is None:
                return IbLoadResponse(
                    status="failed",
                    fetched_bars=0,
                    cached_before=cached_before,
                    merged_file="",
                    start_time=actual_start,
                    end_time=actual_end,
                    requests_made=requests_made,
                    execution_time_seconds=time.time() - start_time,
                    error_message="Failed to fetch data from IB",
                )

            # Merge with existing data and save
            final_data = self._merge_and_save_data(
                request.symbol, request.timeframe, existing_data, fetched_data
            )

            return IbLoadResponse(
                status="success",
                fetched_bars=len(fetched_data) if fetched_data is not None else 0,
                cached_before=cached_before,
                merged_file=str(csv_path),
                start_time=actual_start,
                end_time=actual_end,
                requests_made=requests_made,
                execution_time_seconds=time.time() - start_time,
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
        self, request: IbLoadRequest, existing_data: Optional[pd.DataFrame]
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        """
        Determine the actual start and end dates for data loading based on mode.

        Args:
            request: Load request with mode and optional date overrides
            existing_data: Existing data from CSV (if any)

        Returns:
            Tuple of (start_time, end_time) or (None, None) if unable to determine
        """
        current_time = datetime.now(timezone.utc)

        # Use explicit date overrides if provided
        if request.start and request.end:
            start_time = request.start
            end_time = request.end

            # Ensure timezone-aware
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=timezone.utc)
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=timezone.utc)

            return start_time, end_time

        # Handle different modes
        if request.mode == "full":
            # Full mode: get maximum available history from IB
            max_limits = {
                "1m": 1,  # 1 day
                "5m": 7,  # 1 week
                "15m": 14,  # 2 weeks
                "30m": 30,  # 1 month
                "1h": 30,  # 1 month
                "4h": 30,  # 1 month
                "1d": 365,  # 1 year
                "1w": 730,  # 2 years
            }
            max_days = max_limits.get(request.timeframe, 30)
            start_time = current_time - timedelta(days=max_days)
            end_time = current_time

        elif request.mode == "tail":
            # Tail mode: from last data point to now
            if existing_data is None or existing_data.empty:
                # No existing data, treat as full mode
                max_limits = {
                    "1m": 1,
                    "5m": 7,
                    "15m": 14,
                    "30m": 30,
                    "1h": 30,
                    "4h": 30,
                    "1d": 365,
                    "1w": 730,
                }
                max_days = max_limits.get(request.timeframe, 30)
                start_time = current_time - timedelta(days=max_days)
                end_time = current_time
            else:
                # Get last timestamp from existing data
                last_timestamp = existing_data.index.max()
                if pd.isna(last_timestamp):
                    return None, None

                # Convert to timezone-aware if needed
                if last_timestamp.tz is None:
                    last_timestamp = last_timestamp.tz_localize(timezone.utc)
                else:
                    last_timestamp = last_timestamp.tz_convert(timezone.utc)

                # Calculate next expected timestamp
                timeframe_minutes = {
                    "1m": 1,
                    "5m": 5,
                    "15m": 15,
                    "30m": 30,
                    "1h": 60,
                    "4h": 240,
                    "1d": 1440,
                }
                minutes = timeframe_minutes.get(request.timeframe, 60)
                start_time = last_timestamp + timedelta(minutes=minutes)
                end_time = current_time

        elif request.mode == "backfill":
            # Backfill mode: before earliest data point
            if existing_data is None or existing_data.empty:
                # No existing data, treat as full mode
                max_limits = {
                    "1m": 1,
                    "5m": 7,
                    "15m": 14,
                    "30m": 30,
                    "1h": 30,
                    "4h": 30,
                    "1d": 365,
                    "1w": 730,
                }
                max_days = max_limits.get(request.timeframe, 30)
                start_time = current_time - timedelta(days=max_days)
                end_time = current_time
            else:
                # Get earliest timestamp from existing data
                earliest_timestamp = existing_data.index.min()
                if pd.isna(earliest_timestamp):
                    return None, None

                # Convert to timezone-aware if needed
                if earliest_timestamp.tz is None:
                    earliest_timestamp = earliest_timestamp.tz_localize(timezone.utc)
                else:
                    earliest_timestamp = earliest_timestamp.tz_convert(timezone.utc)

                # Calculate how far back we can go based on IB limits
                max_limits = {
                    "1m": 1,
                    "5m": 7,
                    "15m": 14,
                    "30m": 30,
                    "1h": 30,
                    "4h": 30,
                    "1d": 365,
                    "1w": 730,
                }
                max_days = max_limits.get(request.timeframe, 30)
                start_time = earliest_timestamp - timedelta(days=max_days)
                end_time = earliest_timestamp - timedelta(
                    minutes=1
                )  # Don't overlap with existing data

        else:
            logger.error(f"Unknown mode: {request.mode}")
            return None, None

        # Ensure start is before end
        if start_time >= end_time:
            return None, None

        return start_time, end_time

    def _load_data_progressive(
        self, symbol: str, timeframe: str, start_time: datetime, end_time: datetime
    ) -> Tuple[bool, Optional[pd.DataFrame], int]:
        """
        Load data progressively with multiple requests if needed for large gaps.

        Returns:
            Tuple of (success, fetched_data, requests_made)
        """
        try:
            # Get IB max duration limit for this timeframe
            max_limits = {
                "1m": 1,  # 1 day
                "5m": 7,  # 1 week
                "15m": 14,  # 2 weeks
                "30m": 30,  # 1 month
                "1h": 30,  # 1 month
                "4h": 30,  # 1 month
                "1d": 365,  # 1 year
                "1w": 730,  # 2 years
            }

            max_days = max_limits.get(timeframe, 30)
            total_gap_days = (end_time - start_time).days

            if total_gap_days <= max_days:
                # Small gap - use single request
                logger.info(f"Small gap ({total_gap_days} days) - using single request")
                success, data = self._fetch_data_chunk(
                    symbol, timeframe, start_time, end_time
                )
                return success, data, 1 if success else 0

            # Large gap - use progressive loading
            logger.info(
                f"Large gap ({total_gap_days} days) - using progressive loading (max {max_days} days per request)"
            )

            all_data = []
            current_end = end_time
            requests_made = 0
            max_requests = 5  # Limit to prevent excessive API calls

            while current_end > start_time and requests_made < max_requests:
                # Calculate start time for this chunk (work backwards)
                chunk_start = max(start_time, current_end - timedelta(days=max_days))

                logger.info(
                    f"Progressive load request {requests_made + 1}: {chunk_start.date()} to {current_end.date()}"
                )

                # Fetch this chunk
                chunk_success, chunk_data = self._fetch_data_chunk(
                    symbol, timeframe, chunk_start, current_end
                )
                requests_made += 1

                if chunk_success and chunk_data is not None and not chunk_data.empty:
                    all_data.append(chunk_data)
                    logger.info(
                        f"✅ Progressive chunk {requests_made} filled successfully ({len(chunk_data)} bars)"
                    )

                    # Move to previous chunk
                    current_end = chunk_start - timedelta(
                        hours=1
                    )  # Move back 1 hour to avoid overlap

                    # Add delay between requests to respect IB pacing
                    if current_end > start_time:
                        logger.debug("Pacing delay between progressive requests")
                        time.sleep(2.0)  # 2 second delay between requests
                else:
                    logger.warning(f"❌ Progressive chunk {requests_made} failed")
                    break

            if all_data:
                # Combine all chunks
                combined_data = pd.concat(all_data, ignore_index=False)
                combined_data = combined_data[
                    ~combined_data.index.duplicated(keep="last")
                ]
                combined_data = combined_data.sort_index()

                logger.info(
                    f"✅ Progressive loading completed: {len(combined_data)} total bars from {requests_made} requests"
                )
                return True, combined_data, requests_made
            else:
                logger.warning(
                    f"⚠️ Progressive loading failed after {requests_made} requests"
                )
                return False, None, requests_made

        except Exception as e:
            logger.error(
                f"Error in progressive data loading for {symbol}_{timeframe}: {e}"
            )
            return False, None, 0

    def _fetch_data_chunk(
        self, symbol: str, timeframe: str, start_time: datetime, end_time: datetime
    ) -> Tuple[bool, Optional[pd.DataFrame]]:
        """
        Fetch a single chunk of data from IB.

        Returns:
            Tuple of (success, data)
        """
        try:
            # Get IB connection
            connection = self.connection_manager.get_connection()
            if not connection:
                logger.warning("No IB connection available for data fetching")
                return False, None

            # Create context-aware data fetcher
            context_fetcher = create_context_aware_fetcher(connection)

            # Fetch data
            logger.debug(f"Fetching data for {symbol} from {start_time} to {end_time}")
            data = context_fetcher.fetch_historical_data(
                symbol, timeframe, start_time, end_time
            )

            if data is None or data.empty:
                logger.warning(f"No data received for {symbol}_{timeframe}")
                return False, None

            return True, data

        except Exception as e:
            logger.error(f"Error fetching data chunk for {symbol}_{timeframe}: {e}")
            return False, None

    def _merge_and_save_data(
        self,
        symbol: str,
        timeframe: str,
        existing_data: Optional[pd.DataFrame],
        new_data: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Merge new data with existing data and save to CSV.

        Returns:
            Final merged data
        """
        try:
            # Combine data if we have existing data
            if existing_data is not None and not existing_data.empty:
                # Ensure timezone consistency before combining
                if existing_data.index.tz is None and new_data.index.tz is not None:  # type: ignore
                    existing_data.index = existing_data.index.tz_localize(timezone.utc)  # type: ignore
                elif existing_data.index.tz is not None and new_data.index.tz is None:  # type: ignore
                    new_data.index = new_data.index.tz_localize(timezone.utc)  # type: ignore
                elif (
                    existing_data.index.tz is not None and new_data.index.tz is not None  # type: ignore
                ):
                    existing_data.index = existing_data.index.tz_convert(timezone.utc)  # type: ignore
                    new_data.index = new_data.index.tz_convert(timezone.utc)  # type: ignore

                # Combine data, removing duplicates
                combined = pd.concat([existing_data, new_data])
                combined = combined[~combined.index.duplicated(keep="last")]
                combined = combined.sort_index()
            else:
                combined = new_data

            # Save to CSV
            self._save_data_to_csv(symbol, timeframe, combined)

            logger.info(
                f"Merged and saved {len(combined)} total bars to {symbol}_{timeframe}.csv"
            )
            return combined

        except Exception as e:
            logger.error(f"Error merging and saving data for {symbol}_{timeframe}: {e}")
            raise

    def _save_data_to_csv(
        self, symbol: str, timeframe: str, data: pd.DataFrame
    ) -> None:
        """Save data to CSV file."""
        try:
            # Ensure data directory exists
            os.makedirs(self.data_dir, exist_ok=True)

            # Create filename
            filename = f"{symbol}_{timeframe}.csv"
            filepath = os.path.join(self.data_dir, filename)

            # Save to CSV
            data.to_csv(filepath)
            logger.debug(f"Saved {len(data)} bars to {filepath}")

        except Exception as e:
            logger.error(f"Error saving data to CSV: {e}")
            raise
