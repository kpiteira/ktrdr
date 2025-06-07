"""
Synchronous IB Data Fetcher based on proven working pattern.
"""

import time
import math
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple
import pandas as pd
from ib_insync import Stock, Forex, Contract
from ktrdr.logging import get_logger
from ktrdr.errors import DataError
from ktrdr.data.ib_connection_sync import IbConnectionSync, ConnectionConfig
from ktrdr.utils.timezone_utils import TimestampManager

logger = get_logger(__name__)


class IbDataFetcherSync:
    """
    Synchronous IB data fetcher that avoids event loop issues.

    Based on proven working pattern without async/await complexity.
    """

    def __init__(
        self,
        connection: Optional[IbConnectionSync] = None,
        config: Optional[ConnectionConfig] = None,
    ):
        """
        Initialize the data fetcher.

        Args:
            connection: IbConnectionSync instance (REQUIRED for persistent connection manager)
            config: Optional ConnectionConfig (only used if connection is None - DEPRECATED)
        """
        if connection:
            self.connection = connection
        else:
            # DANGEROUS: Creating own connection can cause garbage collection disconnects
            logger.warning(
                "⚠️ Creating IbDataFetcherSync without connection parameter - this may cause disconnects!"
            )
            logger.warning("⚠️ Consider using persistent connection manager instead")
            self.connection = IbConnectionSync(config)

        self.ib = self.connection.ib

        # Metrics
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_bars_fetched": 0,
        }

    def get_contract(self, symbol: str, instrument_type: str = "stock") -> Contract:
        """
        Get IB contract for a symbol.

        Args:
            symbol: Symbol to get contract for
            instrument_type: Type of instrument ('stock' or 'forex')

        Returns:
            Qualified IB contract
        """
        if not self.connection.ensure_connection():
            raise ConnectionError("Not connected to IB")

        try:
            # Use thread-safe contract qualification 
            if instrument_type == "stock":
                contract = Stock(symbol, "SMART", "USD")
            elif instrument_type == "forex":
                contract = Forex(symbol)
            else:
                raise ValueError(f"Unsupported instrument type: {instrument_type}")

            # Use the connection's event loop to run the async operation
            contracts = self._run_in_connection_loop(
                self.ib.qualifyContractsAsync(contract)
            )

            if not contracts:
                raise DataError(f"Could not qualify contract for {symbol}")

            return contracts[0]

        except Exception as e:
            logger.error(f"Error qualifying contract for {symbol}: {e}")
            raise

    def _run_in_connection_loop(self, coro):
        """Run an async coroutine using the connection's event loop."""
        import asyncio
        
        # Check if the connection has an event loop
        if hasattr(self.connection, '_event_loop') and self.connection._event_loop:
            try:
                # Use the connection's event loop via run_coroutine_threadsafe
                future = asyncio.run_coroutine_threadsafe(coro, self.connection._event_loop)
                return future.result(timeout=30)  # 30 second timeout
            except Exception as e:
                logger.warning(f"Failed to use connection event loop: {e}, falling back to temp loop")
                return self._run_in_temp_loop(coro)
        else:
            logger.debug("Connection has no event loop, using temporary loop")
            # Fallback: create a temporary event loop
            return self._run_in_temp_loop(coro)

    def _run_in_temp_loop(self, coro):
        """Run coroutine in a temporary event loop (fallback)."""
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    def determine_duration_str(self, timeframe: str, days: int) -> str:
        """
        Determine the appropriate duration string based on timeframe and days.

        This method respects IB maximum duration limits per timeframe and rounds UP
        to ensure complete gap coverage.

        Args:
            timeframe: Timeframe like '1h', '1d', etc.
            days: Number of days to fetch

        Returns:
            IB-compatible duration string like '1 W', '1 M', etc.
        """
        # Get max allowed duration for this timeframe from centralized registry
        from ktrdr.config.ib_limits import IbLimitsRegistry
        max_duration = IbLimitsRegistry.get_duration_limit(timeframe)
        max_days = max_duration.days

        # If request exceeds IB limits, cap it and warn
        if days > max_days:
            logger.warning(
                f"Request for {days} days exceeds IB limit of {max_days} days for {timeframe}"
            )
            logger.warning(
                f"Capping to {max_days} days - you may need multiple requests for full gap"
            )
            days = max_days

        # Round UP to ensure we cover the entire gap

        if days >= 365:
            years = math.ceil(days / 365)
            return f"{years} Y"
        elif days >= 30:
            months = math.ceil(days / 30)
            return f"{months} M"
        elif days >= 7:
            weeks = math.ceil(days / 7)
            return f"{weeks} W"
        else:
            return f"{days} D"

    def get_bar_size(self, timeframe: str) -> str:
        """
        Convert our timeframe format to IB bar size format.

        Args:
            timeframe: Our format like '1h', '1d'

        Returns:
            IB format like '1 hour', '1 day'
        """
        mappings = {
            "1m": "1 min",
            "5m": "5 mins",
            "15m": "15 mins",
            "30m": "30 mins",
            "1h": "1 hour",
            "4h": "4 hours",
            "1d": "1 day",
            "1w": "1 week",
        }

        bar_size = mappings.get(timeframe)
        if not bar_size:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        return bar_size

    def format_ib_datetime(self, dt: Optional[datetime]) -> str:
        """
        Format datetime for IB API.

        Args:
            dt: Datetime to format

        Returns:
            Formatted string 'YYYYMMDD HH:MM:SS' or empty string
        """
        if dt is None:
            return ""

        # Ensure it's a datetime object
        if isinstance(dt, pd.Timestamp):
            dt = dt.to_pydatetime()

        # Format as IB expects
        return dt.strftime("%Y%m%d %H:%M:%S")

    def fetch_historical_data(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        instrument_type: str = "stock",
        what_to_show: str = "TRADES",
        timeout_seconds: int = 120,
    ) -> pd.DataFrame:
        """
        Fetch historical data from IB with proper timeout and error handling.

        Args:
            symbol: Symbol to fetch
            timeframe: Timeframe like '1h', '1d'
            start: Start datetime
            end: End datetime
            instrument_type: Type of instrument
            what_to_show: IB data type (TRADES, BID, ASK, MIDPOINT)
            timeout_seconds: Request timeout in seconds

        Returns:
            DataFrame with OHLCV data
        """
        if not self.connection.ensure_connection():
            raise ConnectionError("Not connected to IB")

        start_time = time.time()

        try:
            # Get contract
            contract = self.get_contract(symbol, instrument_type)

            # Convert timeframe to IB bar size
            bar_size = self.get_bar_size(timeframe)

            # Calculate duration
            days_diff = (end - start).days
            if days_diff < 1:
                days_diff = 1
            duration_str = self.determine_duration_str(timeframe, days_diff)

            # Format end datetime for IB
            end_dt_str = self.format_ib_datetime(end)

            # Adjust what_to_show for forex
            if instrument_type == "forex" and what_to_show == "TRADES":
                what_to_show = "BID"
                logger.info(f"Adjusted whatToShow to 'BID' for forex instrument")

            logger.info(
                f"🌐 IB API CALL: Requesting historical data for {symbol} ({instrument_type})"
            )
            logger.info(
                f"🌐 IB API PARAMS: bar_size={bar_size}, duration={duration_str}, "
                f"end={end_dt_str}, whatToShow={what_to_show}, timeout={timeout_seconds}s"
            )

            # Make the request with proper error handling
            self.metrics["total_requests"] += 1

            # Clear any previous errors before request
            if (
                hasattr(self.connection, "metrics")
                and "last_error" in self.connection.metrics
            ):
                self.connection.metrics["last_error"] = None

            # Use thread-safe historical data request
            bars = self._run_in_connection_loop(
                self.ib.reqHistoricalDataAsync(
                    contract,
                    endDateTime=end_dt_str,
                    durationStr=duration_str,
                    barSizeSetting=bar_size,
                    whatToShow=what_to_show,
                    useRTH=False,  # Use all trading hours
                    formatDate=1,  # Return as datetime objects
                )
            )

            # Check for timeout
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                logger.error(f"Request timed out after {elapsed:.1f}s for {symbol}")
                self.metrics["failed_requests"] += 1
                raise DataError(
                    f"Request timed out after {elapsed:.1f}s",
                    details={"symbol": symbol},
                )

            # Check for errors that might have occurred during request
            if hasattr(self.connection, "metrics") and self.connection.metrics.get(
                "last_error"
            ):
                error_info = self.connection.metrics["last_error"]
                error_code = error_info.get("errorCode")
                error_msg = error_info.get("errorString")

                # Filter out informational messages that aren't actually errors
                informational_codes = [
                    2106,  # HMDS data farm connection is OK
                    2107,  # HMDS data farm connection is OK (historical data)
                    2108,  # HMDS data farm connection is inactive
                    2119,  # Market data farm connection is OK
                    2174,  # Time zone warning (not an error)
                ]

                # Check if error occurred during our request (within last few seconds)
                error_time = error_info.get("time", 0)
                if error_time > start_time and error_code not in informational_codes:
                    logger.error(
                        f"IB error during request for {symbol}: {error_code} - {error_msg}"
                    )
                    self.metrics["failed_requests"] += 1
                    raise DataError(
                        f"IB error {error_code}: {error_msg}",
                        details={"symbol": symbol},
                    )

            if not bars:
                logger.warning(f"No data returned for {symbol}")
                self.metrics["failed_requests"] += 1
                return pd.DataFrame()

            # Convert to DataFrame
            data = []
            for bar in bars:
                data.append(
                    {
                        "timestamp": bar.date,
                        "open": bar.open,
                        "high": bar.high,
                        "low": bar.low,
                        "close": bar.close,
                        "volume": bar.volume,
                    }
                )

            df = pd.DataFrame(data)
            df.set_index("timestamp", inplace=True)
            df.index = pd.to_datetime(df.index)

            # Convert to UTC using TimestampManager for consistent handling
            df.index = TimestampManager.to_utc_series(df.index)

            self.metrics["successful_requests"] += 1
            self.metrics["total_bars_fetched"] += len(df)

            elapsed = time.time() - start_time
            logger.info(
                f"🌐 IB API SUCCESS: Fetched {len(df)} bars for {symbol} in {elapsed:.1f}s"
            )

            return df

        except Exception as e:
            elapsed = time.time() - start_time
            self.metrics["failed_requests"] += 1
            logger.error(f"Error fetching data for {symbol} after {elapsed:.1f}s: {e}")
            raise DataError(
                f"Failed to fetch historical data: {e}",
                details={"symbol": symbol, "error": str(e), "elapsed_seconds": elapsed},
            )

    def get_metrics(self) -> Dict[str, Any]:
        """Get fetcher metrics."""
        metrics = self.metrics.copy()

        # Calculate success rate
        total = metrics["total_requests"]
        if total > 0:
            metrics["success_rate"] = metrics["successful_requests"] / total
        else:
            metrics["success_rate"] = 0

        return metrics


class IbDataRangeDiscovery:
    """
    Historical data range discovery for IB symbols.

    This class provides methods to discover the earliest available data
    for symbols using binary search algorithms.
    """

    def __init__(self, data_fetcher: IbDataFetcherSync):
        """
        Initialize range discovery.

        Args:
            data_fetcher: IbDataFetcherSync instance for data requests
        """
        self.data_fetcher = data_fetcher
        self.range_cache: Dict[str, Dict[str, Tuple[datetime, datetime]]] = {}
        self.cache_ttl = 86400  # 24 hours cache TTL
        self.cache_timestamps: Dict[str, float] = {}

        logger.info("IbDataRangeDiscovery initialized")

    def _cache_key(self, symbol: str, timeframe: str) -> str:
        """Generate cache key for symbol/timeframe combination."""
        return f"{symbol}:{timeframe}"

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is still valid."""
        if cache_key not in self.cache_timestamps:
            return False

        age = time.time() - self.cache_timestamps[cache_key]
        return age < self.cache_ttl

    def _get_cached_range(
        self, symbol: str, timeframe: str
    ) -> Optional[Tuple[datetime, datetime]]:
        """Get cached data range if available and valid."""
        cache_key = self._cache_key(symbol, timeframe)

        if not self._is_cache_valid(cache_key):
            return None

        symbol_cache = self.range_cache.get(symbol, {})
        return symbol_cache.get(timeframe)

    def _cache_range(self, symbol: str, timeframe: str, start: datetime, end: datetime):
        """Cache discovered data range."""
        cache_key = self._cache_key(symbol, timeframe)

        if symbol not in self.range_cache:
            self.range_cache[symbol] = {}

        self.range_cache[symbol][timeframe] = (start, end)
        self.cache_timestamps[cache_key] = time.time()

        logger.debug(f"Cached range for {symbol}:{timeframe}: {start} to {end}")

    def _has_data_at_date(self, symbol: str, timeframe: str, date: datetime) -> bool:
        """
        Check if data exists at a specific date.

        Args:
            symbol: Symbol to check
            timeframe: Timeframe string (e.g., "1 day", "1 hour")
            date: Date to check for data

        Returns:
            True if data exists at the date, False otherwise
        """
        try:
            # Request a small amount of data around this date
            end_date = date + timedelta(days=30)  # Look 30 days forward

            df = self.data_fetcher.fetch_historical_data(
                symbol=symbol, timeframe=timeframe, start=date, end=end_date
            )

            # Check if we got any data and if the earliest data is close to our target date
            if df.empty:
                return False

            earliest_data = df.index.min()
            # Allow up to 7 days difference for weekends/holidays
            date_diff = abs((earliest_data.date() - date.date()).days)

            return date_diff <= 7

        except Exception as e:
            logger.debug(f"Error checking data at {date} for {symbol}: {e}")
            return False

    def _get_head_timestamp_direct(
        self, symbol: str, timeframe: str
    ) -> Optional[datetime]:
        """
        Get earliest data point using IB's reqHeadTimeStamp API.

        This is much faster and more accurate than binary search.

        Args:
            symbol: Symbol to search for
            timeframe: Timeframe string (not used for head timestamp)

        Returns:
            Earliest available date or None if API fails
        """
        try:
            # Check if data fetcher and IB connection are available
            if not (
                self.data_fetcher
                and self.data_fetcher.connection
                and self.data_fetcher.connection.ib
            ):
                logger.debug("IB connection not available for head timestamp")
                return None

            if not self.data_fetcher.connection.is_connected():
                logger.debug("IB connection not active for head timestamp")
                return None

            # Get contract for the symbol
            contract = self.data_fetcher.get_contract(symbol)

            # Use reqHeadTimeStamp API - much faster than binary search!
            logger.debug(f"Requesting head timestamp for {symbol}")
            head_timestamp = self.data_fetcher._run_in_connection_loop(
                self.data_fetcher.connection.ib.reqHeadTimeStampAsync(
                    contract=contract,
                    whatToShow="TRADES",
                    useRTH=False,  # Include all trading hours
                    formatDate=1,  # Return as datetime
                )
            )

            if head_timestamp:
                # Ensure it's timezone-aware
                if hasattr(head_timestamp, "tzinfo") and head_timestamp.tzinfo is None:
                    head_timestamp = head_timestamp.replace(tzinfo=timezone.utc)

                logger.info(f"Head timestamp for {symbol}: {head_timestamp}")
                return head_timestamp
            else:
                logger.warning(f"No head timestamp returned for {symbol}")
                return None

        except Exception as e:
            logger.debug(f"Head timestamp request failed for {symbol}: {e}")
            return None

    def get_earliest_data_point(
        self, symbol: str, timeframe: str, max_lookback_years: int = 20
    ) -> Optional[datetime]:
        """
        Find the earliest available data point for a symbol.

        Uses IB's reqHeadTimeStamp API for fast, accurate results with
        binary search as fallback for older IB versions.

        Args:
            symbol: Symbol to search for
            timeframe: Timeframe string (e.g., "1 day", "1 hour")
            max_lookback_years: Maximum years to look back (used for binary search fallback)

        Returns:
            Earliest available date or None if no data found
        """
        logger.info(f"Discovering earliest data for {symbol} at {timeframe}")

        # Check cache first
        cached_range = self._get_cached_range(symbol, timeframe)
        if cached_range:
            logger.debug(f"Using cached range for {symbol}:{timeframe}")
            return cached_range[0]

        # Try IB's reqHeadTimeStamp API first (much faster!)
        head_timestamp = self._get_head_timestamp_direct(symbol, timeframe)
        if head_timestamp:
            # Cache the result with current time as end
            latest_date = datetime.now(timezone.utc)
            self._cache_range(symbol, timeframe, head_timestamp, latest_date)
            return head_timestamp

        # Fallback to binary search if reqHeadTimeStamp fails
        logger.info(
            f"Head timestamp failed for {symbol}, falling back to binary search"
        )
        return self._get_earliest_binary_search(symbol, timeframe, max_lookback_years)

    def _get_earliest_binary_search(
        self, symbol: str, timeframe: str, max_lookback_years: int = 20
    ) -> Optional[datetime]:
        """
        Find earliest data point using binary search (fallback method).

        Args:
            symbol: Symbol to search for
            timeframe: Timeframe string
            max_lookback_years: Maximum years to look back

        Returns:
            Earliest available date or None if no data found
        """
        logger.debug(f"Using binary search fallback for {symbol} at {timeframe}")

        # Set up binary search bounds
        end_date = TimestampManager.now_utc()
        start_date = end_date - timedelta(days=365 * max_lookback_years)

        logger.debug(f"Binary search range: {start_date.date()} to {end_date.date()}")

        # Check if there's any data at all in the maximum range
        if not self._has_data_at_date(symbol, timeframe, start_date):
            # Try to find any data by checking the most recent period first
            if not self._has_data_at_date(
                symbol, timeframe, end_date - timedelta(days=30)
            ):
                logger.warning(f"No data found for {symbol} in any timeframe")
                return None

        # Binary search for earliest date
        earliest_found = None
        left_date = start_date
        right_date = end_date

        search_iterations = 0
        max_iterations = 20  # Prevent infinite loops

        while (right_date - left_date).days > 7 and search_iterations < max_iterations:
            search_iterations += 1
            mid_date = left_date + (right_date - left_date) / 2

            logger.debug(
                f"Search iteration {search_iterations}: checking {mid_date.date()}"
            )

            if self._has_data_at_date(symbol, timeframe, mid_date):
                # Data exists at mid_date, search earlier
                earliest_found = mid_date
                right_date = mid_date
                logger.debug(f"Data found at {mid_date.date()}, searching earlier")
            else:
                # No data at mid_date, search later
                left_date = mid_date
                logger.debug(f"No data at {mid_date.date()}, searching later")

        if earliest_found:
            # Try to get the exact earliest date by fetching a small sample
            try:
                sample_end = earliest_found + timedelta(days=30)
                df = self.data_fetcher.fetch_historical_data(
                    symbol=symbol,
                    timeframe=timeframe,
                    start=earliest_found - timedelta(days=7),
                    end=sample_end,
                )

                if not df.empty:
                    actual_earliest = df.index.min()
                    logger.info(
                        f"Found earliest data for {symbol} at {actual_earliest}"
                    )

                    # Cache the result
                    latest_date = TimestampManager.now_utc()
                    self._cache_range(symbol, timeframe, actual_earliest, latest_date)

                    return actual_earliest

            except Exception as e:
                logger.warning(f"Error refining earliest date for {symbol}: {e}")

        logger.warning(f"Could not determine earliest data point for {symbol}")
        return earliest_found

    def get_data_range(
        self, symbol: str, timeframe: str
    ) -> Optional[Tuple[datetime, datetime]]:
        """
        Get the full available data range for a symbol.

        Args:
            symbol: Symbol to check
            timeframe: Timeframe string

        Returns:
            Tuple of (earliest_date, latest_date) or None if no data
        """
        # Check cache first
        cached_range = self._get_cached_range(symbol, timeframe)
        if cached_range:
            return cached_range

        # Discover earliest data point
        earliest = self.get_earliest_data_point(symbol, timeframe)
        if not earliest:
            return None

        # Latest date is essentially "now" for live data
        latest = TimestampManager.now_utc()

        # Cache and return
        self._cache_range(symbol, timeframe, earliest, latest)
        return (earliest, latest)

    def get_multiple_ranges(
        self, symbols: List[str], timeframes: List[str]
    ) -> Dict[str, Dict[str, Optional[Tuple[datetime, datetime]]]]:
        """
        Get data ranges for multiple symbols and timeframes.

        Args:
            symbols: List of symbols to check
            timeframes: List of timeframes to check

        Returns:
            Nested dictionary: {symbol: {timeframe: (start, end) or None}}
        """
        results = {}

        for symbol in symbols:
            results[symbol] = {}
            for timeframe in timeframes:
                try:
                    data_range = self.get_data_range(symbol, timeframe)
                    results[symbol][timeframe] = data_range

                    if data_range:
                        logger.info(
                            f"Range for {symbol}:{timeframe}: {data_range[0].date()} to {data_range[1].date()}"
                        )
                    else:
                        logger.warning(f"No data range found for {symbol}:{timeframe}")

                except Exception as e:
                    logger.error(f"Error getting range for {symbol}:{timeframe}: {e}")
                    results[symbol][timeframe] = None

        return results

    def clear_cache(self):
        """Clear all cached range data."""
        self.range_cache.clear()
        self.cache_timestamps.clear()
        logger.info("Data range cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_entries = sum(len(timeframes) for timeframes in self.range_cache.values())

        return {
            "total_cached_ranges": total_entries,
            "symbols_in_cache": len(self.range_cache),
            "cache_ttl_hours": self.cache_ttl / 3600,
        }
