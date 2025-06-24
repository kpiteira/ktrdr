"""
IB Data Fetcher

Simple, focused data fetcher that uses the connection pool to fetch historical data
from Interactive Brokers. This component is "dumb" - it just fetches what it's asked
to fetch without validation, metadata lookup, or complex orchestration.

Key Features:
- Uses shared connection pool for connection management
- Thread-safe execution using execute_with_connection_sync()
- Simple historical data fetching
- No validation, no caching, no metadata - just data fetching
- Proper error handling and timeout management
"""

import time
from typing import Optional
from datetime import datetime
import pandas as pd
from ib_insync import Stock, Forex, Contract

from ktrdr.logging import get_logger
from ktrdr.ib.pool_manager import get_shared_ib_pool

logger = get_logger(__name__)


class IbDataFetcher:
    """
    Simple data fetcher for historical data from Interactive Brokers.

    This component is focused solely on fetching historical OHLCV data
    using the connection pool. It doesn't do validation, caching, or
    metadata handling - that's handled by other components.
    """

    def __init__(self):
        """Initialize the data fetcher with connection pool."""
        self.connection_pool = get_shared_ib_pool()

        # Statistics
        self.requests_made = 0
        self.successful_requests = 0
        self.failed_requests = 0

        logger.info("IbDataFetcher initialized")

    async def fetch_historical_data(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        instrument_type: str = "STK",
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV data from IB.

        Args:
            symbol: Trading symbol (e.g., 'AAPL', 'EUR.USD')
            timeframe: Timeframe string (e.g., '1m', '1h', '1d')
            start: Start datetime (timezone-aware)
            end: End datetime (timezone-aware)
            instrument_type: Instrument type ('STK', 'CASH', 'FUT')

        Returns:
            DataFrame with OHLCV data

        Raises:
            Exception: If data fetching fails
        """
        self.requests_made += 1

        try:
            # Use connection pool with synchronous execution to avoid async issues
            result = await self.connection_pool.execute_with_connection_sync(
                self._fetch_historical_data_impl,
                symbol,
                timeframe,
                start,
                end,
                instrument_type,
            )

            self.successful_requests += 1
            logger.debug(
                f"Successfully fetched {len(result)} bars for {symbol} {timeframe}"
            )
            return result

        except Exception as e:
            self.failed_requests += 1
            logger.error(
                f"Failed to fetch historical data for {symbol} {timeframe}: {e}"
            )
            raise

    def _fetch_historical_data_impl(
        self,
        ib,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        instrument_type: str,
    ) -> pd.DataFrame:
        """
        Implementation of historical data fetching using IB connection.

        This method runs in the connection's dedicated thread to avoid async conflicts.
        """
        logger.debug(f"Starting data fetch for {symbol} ({timeframe})")

        # Give IB a moment to settle before making requests
        time.sleep(0.5)

        # Create contract based on instrument type
        try:
            contract = self._create_contract(symbol, instrument_type)
            logger.debug(f"Created contract: {contract.symbol} ({contract.secType})")
        except Exception as e:
            logger.error(f"Failed to create contract for {symbol}: {e}")
            raise

        # Convert timeframe to IB format
        try:
            ib_bar_size = self._convert_timeframe_to_ib(timeframe)
            duration = self._calculate_duration(start, end)
            logger.debug(f"IB parameters: duration={duration}, bar_size={ib_bar_size}")
        except Exception as e:
            logger.error(f"Failed to convert parameters: {e}")
            raise

        # Determine what data to show based on instrument type
        what_to_show = self._get_what_to_show(instrument_type, symbol)

        # Request historical data (synchronous call)
        try:
            logger.info(f"🔍 IB REQUEST: {contract.symbol} ({contract.secType}) {start.date()} to {end.date()}")
            logger.info(f"   ├─ Contract: {contract}")
            logger.info(f"   ├─ Duration: {duration}, Bar Size: {ib_bar_size}")
            logger.info(f"   ├─ What to Show: {what_to_show}, Use RTH: True")
            logger.info(f"   └─ End DateTime: {end}")

            bars = ib.reqHistoricalData(
                contract=contract,
                endDateTime=end,
                durationStr=duration,
                barSizeSetting=ib_bar_size,
                whatToShow=what_to_show,
                useRTH=True,
                formatDate=1,
            )

            logger.info(f"📊 IB RESPONSE: {len(bars) if bars else 0} bars returned")
            if bars:
                logger.info(f"   ├─ First bar: {bars[0].date} ({bars[0].open}-{bars[0].close})")
                logger.info(f"   └─ Last bar: {bars[-1].date} ({bars[-1].open}-{bars[-1].close})")
            else:
                logger.warning(f"❌ IB RESPONSE: No data available for requested period")

        except Exception as e:
            logger.error(f"IB reqHistoricalData failed: {e}")
            raise

        if not bars:
            logger.warning(f"No data returned for {symbol} {timeframe}")
            raise Exception(f"No data returned for {symbol} {timeframe}")

        # Convert to DataFrame
        try:
            logger.debug(f"Converting {len(bars)} bars to DataFrame")
            df = pd.DataFrame(
                [
                    {
                        "open": bar.open,
                        "high": bar.high,
                        "low": bar.low,
                        "close": bar.close,
                        "volume": bar.volume,
                    }
                    for bar in bars
                ]
            )

            # Set datetime index
            df.index = pd.to_datetime([bar.date for bar in bars])
            df.index = (
                df.index.tz_localize("UTC")
                if df.index.tz is None
                else df.index.tz_convert("UTC")
            )

            # Filter by date range
            df = df[(df.index >= start) & (df.index <= end)]

            logger.info(
                f"Successfully processed {len(df)} bars for {symbol} {timeframe}"
            )
            return df

        except Exception as e:
            logger.error(f"Failed to process bars to DataFrame: {e}")
            raise

    def _create_contract(self, symbol: str, instrument_type: str) -> Contract:
        """
        Create appropriate contract for the symbol and instrument type.

        Args:
            symbol: Trading symbol
            instrument_type: Type of instrument ('STK', 'CASH', 'FUT')

        Returns:
            IB Contract object
        """
        logger.debug(
            f"Creating contract for symbol='{symbol}', instrument_type='{instrument_type}'"
        )

        if instrument_type == "CASH" or "." in symbol:
            # Handle forex pairs
            if "." in symbol:
                base, quote = symbol.split(".")
                forex_symbol = base + quote
                logger.debug(f"Dot-separated forex: {symbol} → {forex_symbol}")
                contract = Forex(forex_symbol)
            else:
                logger.debug(f"Direct forex symbol: {symbol}")
                contract = Forex(symbol)
            logger.debug(f"Created forex contract: {contract}")
            return contract
        elif instrument_type == "STK":
            # Stock contract
            logger.debug(f"Creating stock contract for {symbol}")
            contract = Stock(symbol, "SMART", "USD")
            logger.debug(f"Created stock contract: {contract}")
            return contract
        else:
            # Default to stock for unknown types
            logger.warning(
                f"Unknown instrument type '{instrument_type}', defaulting to stock"
            )
            contract = Stock(symbol, "SMART", "USD")
            logger.debug(f"Created default stock contract: {contract}")
            return contract

    def _convert_timeframe_to_ib(self, timeframe: str) -> str:
        """Convert our timeframe format to IB bar size format."""
        mapping = {
            "1m": "1 min",
            "5m": "5 mins",
            "15m": "15 mins",
            "30m": "30 mins",
            "1h": "1 hour",
            "2h": "2 hours",
            "3h": "3 hours",
            "4h": "4 hours",
            "1d": "1 day",
            "1w": "1 week",
            "1M": "1 month",
        }
        return mapping.get(timeframe, "1 day")

    def _get_what_to_show(self, instrument_type: str, symbol: str) -> str:
        """
        Determine the appropriate 'whatToShow' parameter for IB API based on instrument type.

        Args:
            instrument_type: Type of instrument ('STK', 'CASH', 'FUT', 'OPT')
            symbol: Trading symbol (for additional context)

        Returns:
            String indicating what data to request from IB
        """
        if instrument_type == "CASH" or "." in symbol:
            # Forex instruments - IB doesn't support TRADES for forex
            return "BID"
        elif instrument_type in ["STK", "FUT", "OPT"]:
            # Stocks, futures, options - use TRADES data
            return "TRADES"
        else:
            # Default fallback
            logger.warning(
                f"Unknown instrument type '{instrument_type}' for {symbol}, defaulting to TRADES"
            )
            return "TRADES"

    def _calculate_duration(self, start: datetime, end: datetime) -> str:
        """Calculate IB duration string from datetime range."""
        delta = end - start
        total_seconds = delta.total_seconds()
        days = delta.days

        # Handle very small time ranges (less than 1 day)
        if total_seconds < 86400:  # Less than 1 day
            hours = int(total_seconds // 3600)
            if hours > 0:
                return f"{hours} H"
            else:
                return "1 H"  # Minimum 1 hour

        # Ensure minimum 1 day for day-based durations
        if days == 0:
            days = 1

        if days <= 7:
            return f"{days} D"
        elif days <= 365:
            weeks = days // 7
            return f"{max(1, weeks)} W"  # Ensure minimum 1 week
        else:
            years = days // 365
            return f"{max(1, years)} Y"  # Ensure minimum 1 year

    def get_stats(self) -> dict:
        """
        Get data fetcher statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            "requests_made": self.requests_made,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": (
                self.successful_requests / self.requests_made
                if self.requests_made > 0
                else 0.0
            ),
        }
