"""
Unified IB Data Fetcher

Enhanced data fetcher that uses the new IB connection pool and pace manager.

This unified fetcher provides:
- Integration with IbConnectionPool for connection management
- IbPaceManager for pace violation prevention and handling
- Enhanced error handling with intelligent retry strategies
- Support for both sync and async operations
- Comprehensive metrics and monitoring
- Connection reuse and proper resource cleanup

Key Features:
- Uses connection pool for efficient connection management
- Proactive pace limiting to prevent violations
- Enhanced error classification and handling
- Automatic retry with intelligent backoff
- Component-specific metrics tracking
- Clean async context managers
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Union
import pandas as pd
from ib_insync import Stock, Forex, Contract

from ktrdr.logging import get_logger
from ktrdr.errors import DataError
from ktrdr.data.ib_connection_pool import acquire_ib_connection, PooledConnection
from ktrdr.data.ib_client_id_registry import ClientIdPurpose
from ktrdr.data.ib_pace_manager import get_pace_manager
from ktrdr.utils.timezone_utils import TimestampManager
from ktrdr.config.ib_limits import IbLimitsRegistry

logger = get_logger(__name__)


class IbDataFetcherUnified:
    """
    Unified IB data fetcher using connection pool and pace manager.

    This fetcher provides enhanced functionality while maintaining
    compatibility with existing async patterns.
    """

    def __init__(self, component_name: str = "data_fetcher"):
        """
        Initialize the unified data fetcher.

        Args:
            component_name: Name for this component (used in metrics and logging)
        """
        self.component_name = component_name
        self.pace_manager = get_pace_manager()

        # Metrics tracking
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_bars_fetched": 0,
            "pace_violations_handled": 0,
            "retries_performed": 0,
            "total_fetch_time": 0.0,
            "avg_fetch_time": 0.0,
        }

        logger.info(f"IbDataFetcherUnified initialized (component: {component_name})")

    def _detect_instrument_type(self, symbol: str) -> str:
        """
        Auto-detect instrument type (forex vs stock) based on symbol patterns.

        Args:
            symbol: Symbol to analyze

        Returns:
            "forex" for forex pairs, "stock" for stocks
        """
        normalized = symbol.upper().replace("/", "").replace(".", "")

        # Forex detection heuristics
        # 6-character currency pairs like USDJPY, EURUSD
        if len(normalized) == 6 and normalized.isalpha():
            # Common forex pairs
            common_forex = {
                "EURUSD",
                "GBPUSD",
                "USDJPY",
                "USDCHF",
                "AUDUSD",
                "USDCAD",
                "NZDUSD",
                "EURJPY",
                "GBPJPY",
                "AUDJPY",
                "CADJPY",
                "CHFJPY",
                "NZDJPY",
                "EURGBP",
                "EURAUD",
                "EURCAD",
                "EURCHF",
                "EURNZD",
                "GBPAUD",
                "GBPCAD",
                "GBPCHF",
                "GBPNZD",
                "AUDCAD",
                "AUDCHF",
                "AUDNZD",
                "CADCHF",
                "NZDCAD",
                "NZDCHF",
            }
            if normalized in common_forex:
                return "forex"

            # Additional pattern: if it looks like XXXYYY where both XXX and YYY are currency codes
            major_currencies = {
                "USD",
                "EUR",
                "GBP",
                "JPY",
                "CHF",
                "AUD",
                "CAD",
                "NZD",
                "SEK",
                "NOK",
                "DKK",
            }
            base = normalized[:3]
            quote = normalized[3:]
            if base in major_currencies and quote in major_currencies:
                return "forex"

        # Symbol with dot notation like EUR.USD
        if "." in symbol and len(symbol.replace(".", "")) == 6:
            return "forex"

        # Default to stock for everything else
        return "stock"

    async def _get_contract(
        self, ib, symbol: str, instrument_type: str = None
    ) -> Contract:
        """
        Get IB contract for a symbol with auto-detection.

        Args:
            ib: Connected IB instance
            symbol: Symbol to look up
            instrument_type: Type of instrument (stock, forex). If None, auto-detects.

        Returns:
            Qualified IB contract
        """
        try:
            # Auto-detect instrument type if not provided
            if instrument_type is None:
                instrument_type = self._detect_instrument_type(symbol)
                logger.debug(
                    f"🔍 Auto-detected instrument type for {symbol}: {instrument_type}"
                )

            logger.debug(f"🔍 Getting contract for {symbol} ({instrument_type})")

            # Create contract based on type
            if instrument_type == "stock":
                contract = Stock(symbol, "SMART", "USD")
            elif instrument_type == "forex":
                contract = Forex(symbol)
            else:
                raise ValueError(f"Unsupported instrument type: {instrument_type}")

            logger.debug(f"📝 Created contract: {contract}")

            # Qualify contract asynchronously
            contracts = await ib.qualifyContractsAsync(contract)

            if not contracts:
                raise DataError(f"Could not qualify contract for {symbol}")

            qualified_contract = contracts[0]
            logger.debug(f"✅ Contract qualified: {qualified_contract}")
            return qualified_contract

        except Exception as e:
            logger.error(f"❌ Error getting contract for {symbol}: {e}")
            raise

    def _get_bar_size(self, timeframe: str) -> str:
        """Convert timeframe to IB bar size format."""
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

    def _calculate_duration_string(
        self, timeframe: str, start: datetime, end: datetime
    ) -> str:
        """Calculate IB duration string for the request."""
        days_diff = (end - start).days
        if days_diff < 1:
            days_diff = 1

        # Use IB limits to ensure we don't exceed maximum duration
        max_duration = IbLimitsRegistry.get_duration_limit(timeframe)
        max_days = max_duration.days

        if days_diff > max_days:
            logger.warning(
                f"Request for {days_diff} days exceeds IB limit of {max_days} days for {timeframe}"
            )
            days_diff = max_days

        # Convert to IB duration format
        if days_diff >= 365:
            years = (days_diff + 364) // 365  # Round up
            return f"{years} Y"
        elif days_diff >= 30:
            months = (days_diff + 29) // 30  # Round up
            return f"{months} M"
        elif days_diff >= 7:
            weeks = (days_diff + 6) // 7  # Round up
            return f"{weeks} W"
        else:
            return f"{days_diff} D"

    def _format_ib_datetime(self, dt: datetime) -> str:
        """Format datetime for IB API."""
        if isinstance(dt, pd.Timestamp):
            dt = dt.to_pydatetime()

        dt_utc = TimestampManager.to_utc(dt)
        return dt_utc.strftime("%Y%m%d %H:%M:%S UTC")

    async def fetch_historical_data(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        instrument_type: str = None,
        what_to_show: str = "TRADES",
        max_retries: int = 3,
        preferred_client_id: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Fetch historical data with enhanced connection management and pace handling.

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe (1h, 1d, etc.)
            start: Start datetime
            end: End datetime
            instrument_type: Type of instrument (stock, forex)
            what_to_show: IB data type to request
            max_retries: Maximum number of retry attempts
            preferred_client_id: Preferred client ID for connection

        Returns:
            DataFrame with OHLCV data
        """
        start_time = time.time()
        retry_count = 0
        last_error = None

        # Auto-detect instrument type if not provided
        if instrument_type is None:
            instrument_type = self._detect_instrument_type(symbol)

        try:
            logger.info(
                f"🚀 UNIFIED FETCH: {symbol} {timeframe} from {start} to {end} (component: {self.component_name})"
            )

            # Validate dates
            now_utc = TimestampManager.now_utc()
            if start > now_utc:
                raise DataError(f"Start date {start} is in the future")
            if end > now_utc:
                logger.warning(f"End date {end} is in the future, adjusting to now")
                end = now_utc

            # Prepare IB parameters
            bar_size = self._get_bar_size(timeframe)
            duration_str = self._calculate_duration_string(timeframe, start, end)
            end_dt_str = self._format_ib_datetime(end)

            # Adjust what_to_show for forex
            if instrument_type == "forex" and what_to_show == "TRADES":
                what_to_show = "BID"

            logger.info(f"📡 IB Request Parameters:")
            logger.info(f"   Symbol: {symbol}")
            logger.info(f"   Bar Size: {bar_size}")
            logger.info(f"   Duration: {duration_str}")
            logger.info(f"   End DateTime: {end_dt_str}")
            logger.info(f"   What to Show: {what_to_show}")

            # Retry loop with exponential backoff
            while retry_count <= max_retries:
                try:
                    # Check pace limits before making request
                    await self.pace_manager.check_pace_limits_async(
                        symbol=symbol,
                        timeframe=timeframe,
                        component=self.component_name,
                        operation="fetch_historical_data",
                        start_date=start,
                        end_date=end,
                    )

                    # Use connection pool for connection management
                    async with await acquire_ib_connection(
                        purpose=ClientIdPurpose.DATA_MANAGER,
                        requested_by=self.component_name,
                        preferred_client_id=preferred_client_id,
                    ) as connection:

                        ib = connection.ib

                        # Get contract
                        contract = await self._get_contract(ib, symbol, instrument_type)

                        # Make IB API call
                        self.metrics["total_requests"] += 1

                        logger.info(
                            f"🔗 Making IB API call (client_id: {connection.client_id})..."
                        )
                        bars = await ib.reqHistoricalDataAsync(
                            contract,
                            endDateTime=end_dt_str,
                            durationStr=duration_str,
                            barSizeSetting=bar_size,
                            whatToShow=what_to_show,
                            useRTH=False,
                            formatDate=1,
                        )

                        logger.info(
                            f"📊 Received {len(bars) if bars else 0} bars from IB"
                        )

                        if not bars:
                            logger.warning(f"❌ No data returned for {symbol}")
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

                        # Convert to UTC
                        df.index = TimestampManager.to_utc_series(df.index)

                        # Update metrics
                        elapsed = time.time() - start_time
                        self.metrics["successful_requests"] += 1
                        self.metrics["total_bars_fetched"] += len(df)
                        self.metrics["total_fetch_time"] += elapsed
                        if self.metrics["successful_requests"] > 0:
                            self.metrics["avg_fetch_time"] = (
                                self.metrics["total_fetch_time"]
                                / self.metrics["successful_requests"]
                            )

                        logger.info(
                            f"✅ UNIFIED FETCH SUCCESS: {len(df)} bars for {symbol} in {elapsed:.1f}s"
                        )
                        logger.info(
                            f"   Date range: {df.index.min()} to {df.index.max()}"
                        )
                        logger.info(
                            f"   Connection: client_id={connection.client_id}, reused={not connection.state.name.endswith('CONNECTING')}"
                        )

                        return df

                except Exception as e:
                    retry_count += 1
                    last_error = e

                    # Handle IB errors with pace manager
                    request_key = f"{symbol}:{timeframe}:fetch_historical_data"
                    should_retry, wait_time = (
                        await self.pace_manager.handle_ib_error_async(
                            error_code=getattr(e, "errorCode", 0),
                            error_message=str(e),
                            component=self.component_name,
                            request_key=request_key,
                        )
                    )

                    if not should_retry or retry_count > max_retries:
                        logger.error(
                            f"❌ Giving up after {retry_count} retries for {symbol}"
                        )
                        break

                    # Wait before retry
                    if wait_time > 0:
                        logger.info(
                            f"⏳ Waiting {wait_time}s before retry {retry_count}/{max_retries}"
                        )
                        await asyncio.sleep(wait_time)
                        self.metrics["pace_violations_handled"] += 1

                    # Exponential backoff for additional delay
                    backoff_delay = min(2 ** (retry_count - 1), 30)  # Cap at 30 seconds
                    if backoff_delay > 0:
                        logger.info(f"⏳ Additional backoff delay: {backoff_delay}s")
                        await asyncio.sleep(backoff_delay)

                    self.metrics["retries_performed"] += 1
                    logger.warning(
                        f"🔄 Retrying {symbol} (attempt {retry_count}/{max_retries}): {e}"
                    )

            # If we get here, all retries failed
            elapsed = time.time() - start_time
            self.metrics["failed_requests"] += 1
            logger.error(
                f"❌ UNIFIED FETCH FAILED: {symbol} after {elapsed:.1f}s and {retry_count} retries"
            )
            logger.error(f"   Final error: {last_error}")
            raise DataError(
                f"Failed to fetch historical data after {retry_count} retries: {last_error}"
            )

        except Exception as e:
            if "Failed to fetch historical data" not in str(e):
                # Update metrics for unexpected errors
                elapsed = time.time() - start_time
                self.metrics["failed_requests"] += 1
                logger.error(f"❌ UNIFIED FETCH ERROR: {symbol} after {elapsed:.1f}s")
                logger.error(f"   Error: {e}")
                raise DataError(f"Failed to fetch historical data: {e}")
            else:
                # Re-raise DataError from retry loop
                raise

    async def fetch_multiple_symbols(
        self, requests: List[Dict[str, Any]], max_concurrent: int = 3
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch data for multiple symbols concurrently with connection pool management.

        Args:
            requests: List of request dicts with keys: symbol, timeframe, start, end
            max_concurrent: Maximum concurrent requests

        Returns:
            Dictionary mapping symbol to DataFrame
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def fetch_with_limit(req):
            async with semaphore:
                try:
                    df = await self.fetch_historical_data(
                        req["symbol"],
                        req["timeframe"],
                        req["start"],
                        req["end"],
                        req.get("instrument_type"),
                        req.get("what_to_show", "TRADES"),
                        req.get("max_retries", 3),
                        req.get("preferred_client_id"),
                    )
                    return req["symbol"], df
                except Exception as e:
                    logger.error(f"Failed to fetch {req['symbol']}: {e}")
                    return req["symbol"], pd.DataFrame()

        # Execute all requests concurrently
        logger.info(
            f"🚀 Starting concurrent fetch for {len(requests)} symbols (max_concurrent={max_concurrent})"
        )
        tasks = [fetch_with_limit(req) for req in requests]
        results = await asyncio.gather(*tasks)

        successful_count = sum(1 for _, df in results if not df.empty)
        logger.info(
            f"✅ Concurrent fetch completed: {successful_count}/{len(requests)} successful"
        )

        return dict(results)

    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive fetcher metrics."""
        metrics = self.metrics.copy()

        # Calculate success rate
        total = metrics["total_requests"]
        if total > 0:
            metrics["success_rate"] = metrics["successful_requests"] / total
        else:
            metrics["success_rate"] = 0.0

        # Get pace manager statistics for this component
        pace_stats = self.pace_manager.get_pace_statistics()
        component_pace_stats = pace_stats.get("component_statistics", {}).get(
            self.component_name, {}
        )

        # Merge pace statistics
        metrics.update(
            {
                "pace_requests": component_pace_stats.get("total_requests", 0),
                "pace_violations": component_pace_stats.get("pace_violations", 0),
                "pace_wait_time": component_pace_stats.get("total_wait_time", 0.0),
                "component_name": self.component_name,
            }
        )

        return metrics

    def reset_metrics(self):
        """Reset fetcher metrics."""
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_bars_fetched": 0,
            "pace_violations_handled": 0,
            "retries_performed": 0,
            "total_fetch_time": 0.0,
            "avg_fetch_time": 0.0,
        }
        logger.info(f"Reset metrics for {self.component_name}")


# Convenience function for simple usage
async def fetch_symbol_data_unified(
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    instrument_type: str = None,
    component_name: str = "simple_fetch",
) -> pd.DataFrame:
    """
    Simple function to fetch data for a single symbol using unified architecture.

    Usage:
        df = await fetch_symbol_data_unified("AAPL", "1h", start_date, end_date)
    """
    fetcher = IbDataFetcherUnified(component_name=component_name)
    return await fetcher.fetch_historical_data(
        symbol, timeframe, start, end, instrument_type
    )


# Backward compatibility alias
IbDataFetcher = IbDataFetcherUnified
