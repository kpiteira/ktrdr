"""
IB Data Fetcher

Handles fetching historical OHLCV data from Interactive Brokers with
rate limiting, chunking, and data format conversion.
"""

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Tuple, Any
import pandas as pd
from ib_insync import Stock, Forex, Future, Contract, util

from ktrdr.logging import get_logger
from ktrdr.errors import DataError, DataNotFoundError, retry_with_backoff, RetryConfig
from ktrdr.config.ib_config import IbConfig, get_ib_config
from ktrdr.data.ib_connection import IbConnectionManager

logger = get_logger(__name__)


class RateLimiter:
    """Token bucket rate limiter for IB API requests."""
    
    def __init__(self, rate: int = 50, period: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            rate: Maximum requests per period
            period: Period in seconds
        """
        self.rate = rate
        self.period = period
        self.tokens = rate
        self.last_update = time.time()
        self._lock = asyncio.Lock()
        
    async def acquire(self):
        """Acquire a token, waiting if necessary."""
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_update
            
            # Refill tokens based on elapsed time
            new_tokens = elapsed * (self.rate / self.period)
            self.tokens = min(self.rate, self.tokens + new_tokens)
            self.last_update = now
            
            # Wait if no tokens available
            if self.tokens < 1:
                wait_time = (1 - self.tokens) * (self.period / self.rate)
                logger.debug(f"Rate limit reached, waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
                self.tokens = 1
                
            self.tokens -= 1


class IbDataFetcher:
    """
    Fetches historical data from Interactive Brokers.
    
    Features:
    - Rate limiting with token bucket algorithm
    - Automatic chunking based on IB limits
    - Data format conversion to standard OHLCV
    - Forex, stock, and futures support
    """
    
    # IB bar size to internal timeframe mapping
    TIMEFRAME_MAP = {
        "1m": "1 min",
        "2m": "2 mins",
        "3m": "3 mins",
        "5m": "5 mins",
        "10m": "10 mins",
        "15m": "15 mins",
        "20m": "20 mins",
        "30m": "30 mins",
        "1h": "1 hour",
        "2h": "2 hours",
        "3h": "3 hours",
        "4h": "4 hours",
        "1d": "1 day",
        "1w": "1 week",
        "1M": "1 month",
    }
    
    def __init__(
        self,
        connection: IbConnectionManager,
        config: Optional[IbConfig] = None
    ):
        """
        Initialize data fetcher.
        
        Args:
            connection: IB connection manager
            config: IB configuration (uses default if not provided)
        """
        self.connection = connection
        self.config = config or get_ib_config()
        self.rate_limiter = RateLimiter(
            rate=self.config.rate_limit,
            period=self.config.rate_period
        )
        
        # Metrics tracking
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_bars_fetched": 0,
            "total_response_time": 0.0,
        }
        
    def _get_bar_size(self, timeframe: str) -> str:
        """Convert internal timeframe to IB bar size."""
        bar_size = self.TIMEFRAME_MAP.get(timeframe)
        if not bar_size:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        return bar_size
        
    def _create_contract(self, symbol: str) -> Contract:
        """
        Create IB contract for symbol with priority: Forex, Stock, Future.
        
        Args:
            symbol: Symbol to create contract for
            
        Returns:
            IB Contract object
        """
        # Try Forex first (e.g., EUR.USD, EURUSD)
        if "." in symbol or (len(symbol) == 6 and symbol[:3].isalpha() and symbol[3:].isalpha()):
            # Handle both EUR.USD and EURUSD formats
            if "." in symbol:
                base, quote = symbol.split(".")
            else:
                base, quote = symbol[:3], symbol[3:]
            
            contract = Forex(base + quote)
            logger.debug(f"Created Forex contract for {symbol}")
            return contract
            
        # Try Stock
        contract = Stock(symbol, "SMART", "USD")
        logger.debug(f"Created Stock contract for {symbol}")
        return contract
        
    def _calculate_duration_string(self, bar_size: str, days: int) -> str:
        """
        Convert days to IB duration string format.
        
        Args:
            bar_size: IB bar size string
            days: Number of days to convert
            
        Returns:
            IB duration string (e.g., "1 W", "1 M", "1 Y")
        """
        # Convert days to appropriate IB duration format
        if days >= 365:
            years = days // 365
            return f"{years} Y"
        elif days >= 30:
            months = days // 30
            return f"{months} M"
        elif days >= 7:
            weeks = days // 7
            return f"{weeks} W"
        else:
            return f"{days} D"
    
    def _calculate_chunks(
        self,
        start: datetime,
        end: datetime,
        bar_size: str
    ) -> List[Tuple[datetime, datetime, str]]:
        """
        Calculate date chunks based on IB limits.
        
        Args:
            start: Start datetime
            end: End datetime
            bar_size: IB bar size string
            
        Returns:
            List of (chunk_start, chunk_end, duration_string) tuples
        """
        chunks = []
        chunk_days = self.config.get_chunk_size(bar_size)
        
        current = start
        while current < end:
            chunk_end = min(
                current + timedelta(days=chunk_days),
                end
            )
            # Calculate actual days for this chunk
            actual_days = (chunk_end - current).days
            if actual_days == 0:
                actual_days = 1  # Minimum 1 day
            
            # Convert to IB duration format
            duration_str = self._calculate_duration_string(bar_size, actual_days)
            
            chunks.append((current, chunk_end, duration_str))
            current = chunk_end
            
        logger.info(
            f"Split date range into {len(chunks)} chunks for {bar_size} bars"
        )
        
        return chunks
        
    async def fetch_historical_data(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV data from IB.
        
        Args:
            symbol: Symbol to fetch (e.g., "EUR.USD", "AAPL")
            timeframe: Timeframe (e.g., "1m", "1h", "1d")
            start: Start datetime (timezone-aware)
            end: End datetime (timezone-aware)
            
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
            
        Raises:
            DataError: If data fetch fails
            DataNotFoundError: If symbol not found
        """
        # Auto-connect if not already connected
        if not self.connection.is_connected_sync():
            logger.info("Connecting to IB for data fetch...")
            await self.connection.connect()
            
        # Convert timeframe to IB bar size
        bar_size = self._get_bar_size(timeframe)
        
        # Create contract
        contract = self._create_contract(symbol)
        
        # Calculate chunks
        chunks = self._calculate_chunks(start, end, bar_size)
        
        # Fetch all chunks
        all_data = []
        for i, (chunk_start, chunk_end, duration_str) in enumerate(chunks):
            logger.info(
                f"Fetching chunk {i+1}/{len(chunks)} for {symbol}: "
                f"{chunk_start} to {chunk_end} (duration: {duration_str})"
            )
            
            chunk_data = await self._fetch_chunk(
                contract, bar_size, chunk_start, chunk_end, duration_str
            )
            
            if not chunk_data.empty:
                all_data.append(chunk_data)
                
            # Add pacing delay between chunks
            if i < len(chunks) - 1:
                await asyncio.sleep(self.config.pacing_delay)
                
        if not all_data:
            raise DataNotFoundError(
                f"No data found for {symbol} from {start} to {end}"
            )
            
        # Combine all chunks
        result = pd.concat(all_data, ignore_index=True)
        
        # Remove duplicates and sort
        result = result.drop_duplicates(subset=['timestamp']).sort_values('timestamp')
        
        logger.info(
            f"Fetched {len(result)} bars for {symbol} "
            f"({self.metrics['successful_requests']} requests)"
        )
        
        return result
        
    @retry_with_backoff(
        retryable_exceptions=[DataError, asyncio.TimeoutError],
        config=RetryConfig(max_retries=3, base_delay=2.0)
    )
    async def _fetch_chunk(
        self,
        contract: Contract,
        bar_size: str,
        start: datetime,
        end: datetime,
        duration_str: str
    ) -> pd.DataFrame:
        """
        Fetch a single chunk of data with retry logic.
        
        Args:
            contract: IB contract
            bar_size: IB bar size string
            start: Chunk start datetime
            end: Chunk end datetime
            
        Returns:
            DataFrame with OHLCV data
        """
        # Acquire rate limit token
        await self.rate_limiter.acquire()
        
        # Track metrics
        self.metrics["total_requests"] += 1
        request_start = time.time()
        
        try:
            # Fetch data from IB
            bars = await asyncio.wait_for(
                self.connection.ib.reqHistoricalDataAsync(
                    contract,
                    endDateTime=end,
                    durationStr=duration_str,
                    barSizeSetting=bar_size,
                    whatToShow="TRADES",
                    useRTH=False,
                    formatDate=2  # UTC time
                ),
                timeout=15.0
            )
            
            # Track success
            self.metrics["successful_requests"] += 1
            self.metrics["total_response_time"] += time.time() - request_start
            
            if not bars:
                return pd.DataFrame()
                
            # Convert to DataFrame
            df = util.df(bars)
            
            # Rename columns to standard format
            df = df.rename(columns={
                'date': 'timestamp',
                'open': 'open',
                'high': 'high', 
                'low': 'low',
                'close': 'close',
                'volume': 'volume'
            })
            
            # Select only needed columns
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
            # Track bars fetched
            self.metrics["total_bars_fetched"] += len(df)
            
            return df
            
        except asyncio.TimeoutError:
            self.metrics["failed_requests"] += 1
            raise DataError(
                f"Timeout fetching data for {contract.symbol}",
                details={"bar_size": bar_size, "duration": duration_str}
            )
        except Exception as e:
            self.metrics["failed_requests"] += 1
            
            # Check for specific IB errors
            error_msg = str(e)
            if "No security definition" in error_msg:
                raise DataNotFoundError(f"Symbol not found: {contract.symbol}")
            elif "Invalid request" in error_msg:
                raise DataError(f"Invalid request: {error_msg}")
            else:
                raise DataError(
                    f"Failed to fetch data: {error_msg}",
                    details={"symbol": contract.symbol, "error_type": type(e).__name__}
                )
                
    def get_metrics(self) -> Dict[str, Any]:
        """Get fetcher metrics."""
        metrics = self.metrics.copy()
        
        # Calculate averages
        if metrics["successful_requests"] > 0:
            metrics["avg_response_time"] = (
                metrics["total_response_time"] / metrics["successful_requests"]
            )
            metrics["avg_bars_per_request"] = (
                metrics["total_bars_fetched"] / metrics["successful_requests"]
            )
        else:
            metrics["avg_response_time"] = 0
            metrics["avg_bars_per_request"] = 0
            
        # Calculate success rate
        total = metrics["total_requests"]
        if total > 0:
            metrics["success_rate"] = metrics["successful_requests"] / total
        else:
            metrics["success_rate"] = 0
            
        return metrics
        
    def fetch_historical_data_sync(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime
    ) -> pd.DataFrame:
        """Synchronous wrapper for fetch_historical_data."""
        return util.run(self.fetch_historical_data(symbol, timeframe, start, end))