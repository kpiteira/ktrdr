"""
Tests for IB Data Fetcher
"""

import pytest

pytestmark = pytest.mark.skip(reason="IB integration tests disabled for unit test run")
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, AsyncMock, patch
import pandas as pd
from ib_insync import BarData

from ktrdr.data.ib_data_fetcher import IbDataFetcher, RateLimiter
from ktrdr.data.ib_connection import IbConnectionManager
from ktrdr.config.ib_config import IbConfig
from ktrdr.errors import DataError, DataNotFoundError


class TestRateLimiter:
    """Test rate limiter functionality."""

    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Test that rate limiter enforces limits."""
        limiter = RateLimiter(rate=5, period=1)  # 5 requests per second

        # Should be able to make 5 requests immediately
        start = asyncio.get_event_loop().time()
        for _ in range(5):
            await limiter.acquire()

        # 6th request should be delayed
        await limiter.acquire()
        elapsed = asyncio.get_event_loop().time() - start

        # Should have waited at least 0.2 seconds (1/5)
        assert elapsed >= 0.15  # Allow some tolerance

    @pytest.mark.asyncio
    async def test_token_refill(self):
        """Test that tokens refill over time."""
        limiter = RateLimiter(rate=10, period=1)

        # Use all tokens
        for _ in range(10):
            await limiter.acquire()

        # Wait for refill
        await asyncio.sleep(0.5)

        # Should be able to acquire more tokens
        start = asyncio.get_event_loop().time()
        for _ in range(5):
            await limiter.acquire()
        elapsed = asyncio.get_event_loop().time() - start

        # Should complete quickly since tokens refilled
        assert elapsed < 0.1


class TestIbDataFetcher:
    """Test IB data fetcher functionality."""

    @pytest.fixture
    def mock_connection(self):
        """Create mock connection manager."""
        connection = Mock(spec=IbConnectionManager)
        connection.is_connected_sync.return_value = True
        connection.ib = Mock()
        return connection

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return IbConfig(rate_limit=100, rate_period=60, pacing_delay=0.01)

    @pytest.fixture
    def fetcher(self, mock_connection, config):
        """Create data fetcher instance."""
        return IbDataFetcher(mock_connection, config)

    def test_timeframe_conversion(self, fetcher):
        """Test timeframe to bar size conversion."""
        assert fetcher._get_bar_size("1m") == "1 min"
        assert fetcher._get_bar_size("5m") == "5 mins"
        assert fetcher._get_bar_size("1h") == "1 hour"
        assert fetcher._get_bar_size("1d") == "1 day"

        with pytest.raises(ValueError):
            fetcher._get_bar_size("invalid")

    def test_create_forex_contract(self, fetcher):
        """Test Forex contract creation."""
        # IB Forex contracts set symbol to base currency, currency to quote
        contract = fetcher._create_contract("EUR.USD")
        assert contract.symbol == "EUR"  # Base currency
        assert contract.currency == "USD"  # Quote currency
        assert contract.secType == "CASH"
        assert contract.exchange == "IDEALPRO"

        # Test without dot
        contract = fetcher._create_contract("EURUSD")
        assert contract.symbol == "EUR"  # Base currency
        assert contract.currency == "USD"  # Quote currency
        assert contract.secType == "CASH"

    def test_create_stock_contract(self, fetcher):
        """Test Stock contract creation."""
        contract = fetcher._create_contract("AAPL")
        assert contract.symbol == "AAPL"
        assert contract.secType == "STK"
        assert contract.exchange == "SMART"
        assert contract.currency == "USD"

    def test_calculate_chunks(self, fetcher):
        """Test chunk calculation."""
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 15, tzinfo=timezone.utc)

        # For 1 day bar size, should create single chunk
        chunks = fetcher._calculate_chunks(start, end, "1 day")
        assert len(chunks) == 1
        assert chunks[0] == (start, end)

        # For 1 minute bar size, should create multiple chunks
        chunks = fetcher._calculate_chunks(start, end, "1 min")
        assert len(chunks) > 1
        assert chunks[0][0] == start
        assert chunks[-1][1] == end

    @pytest.mark.asyncio
    async def test_fetch_chunk_success(self, fetcher, mock_connection):
        """Test successful chunk fetch."""
        # Create mock bar data
        mock_bars = [
            Mock(
                spec=BarData,
                date=datetime(2024, 1, 1, 9, 30),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=1000,
            ),
            Mock(
                spec=BarData,
                date=datetime(2024, 1, 1, 9, 31),
                open=100.5,
                high=101.5,
                low=100.0,
                close=101.0,
                volume=1500,
            ),
        ]

        mock_connection.ib.reqHistoricalDataAsync = AsyncMock(return_value=mock_bars)

        # Mock util.df to return DataFrame
        with patch("ktrdr.data.ib_data_fetcher.util.df") as mock_df:
            mock_df.return_value = pd.DataFrame(
                {
                    "date": [b.date for b in mock_bars],
                    "open": [b.open for b in mock_bars],
                    "high": [b.high for b in mock_bars],
                    "low": [b.low for b in mock_bars],
                    "close": [b.close for b in mock_bars],
                    "volume": [b.volume for b in mock_bars],
                }
            )

            contract = fetcher._create_contract("AAPL")
            start = datetime(2024, 1, 1, tzinfo=timezone.utc)
            end = datetime(2024, 1, 2, tzinfo=timezone.utc)

            df = await fetcher._fetch_chunk(contract, "1 min", start, end)

            assert len(df) == 2
            assert list(df.columns) == [
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ]
            assert df["open"].iloc[0] == 100.0
            assert df["close"].iloc[1] == 101.0

    @pytest.mark.asyncio
    async def test_fetch_chunk_timeout(self, fetcher, mock_connection):
        """Test chunk fetch timeout handling."""
        mock_connection.ib.reqHistoricalDataAsync = AsyncMock(
            side_effect=asyncio.TimeoutError()
        )

        contract = fetcher._create_contract("AAPL")
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)

        with pytest.raises(DataError) as exc_info:
            await fetcher._fetch_chunk(contract, "1 min", start, end)

        assert "Timeout" in str(exc_info.value)
        assert fetcher.metrics["failed_requests"] == 1

    @pytest.mark.asyncio
    async def test_fetch_chunk_symbol_not_found(self, fetcher, mock_connection):
        """Test handling of symbol not found error."""
        mock_connection.ib.reqHistoricalDataAsync = AsyncMock(
            side_effect=Exception("No security definition has been found")
        )

        contract = fetcher._create_contract("INVALID")
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)

        with pytest.raises(DataNotFoundError) as exc_info:
            await fetcher._fetch_chunk(contract, "1 min", start, end)

        assert "Symbol not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_historical_data_integration(self, fetcher, mock_connection):
        """Test full historical data fetch with chunking."""

        # Create mock bars for multiple chunks
        def create_mock_bars(date):
            return [
                Mock(
                    spec=BarData,
                    date=date + timedelta(hours=i),
                    open=100.0 + i,
                    high=101.0 + i,
                    low=99.0 + i,
                    close=100.5 + i,
                    volume=1000 + i * 100,
                )
                for i in range(24)
            ]

        call_count = 0

        async def mock_req_historical(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # Return different data for each chunk
            return create_mock_bars(datetime(2024, 1, call_count))

        mock_connection.ib.reqHistoricalDataAsync = mock_req_historical

        with patch("ktrdr.data.ib_data_fetcher.util.df") as mock_df:

            def df_side_effect(bars):
                return pd.DataFrame(
                    {
                        "date": [b.date for b in bars],
                        "open": [b.open for b in bars],
                        "high": [b.high for b in bars],
                        "low": [b.low for b in bars],
                        "close": [b.close for b in bars],
                        "volume": [b.volume for b in bars],
                    }
                )

            mock_df.side_effect = df_side_effect

            start = datetime(2024, 1, 1, tzinfo=timezone.utc)
            end = datetime(
                2024, 3, 1, tzinfo=timezone.utc
            )  # 2 months = ~60 days, requires 2 chunks

            df = await fetcher.fetch_historical_data("AAPL", "1h", start, end)

            assert len(df) == 48  # 2 chunks * 24 hours each
            assert call_count == 2  # Should have made 2 chunk requests
            assert fetcher.metrics["successful_requests"] == 2
            assert fetcher.metrics["total_bars_fetched"] == 48

    def test_get_metrics(self, fetcher):
        """Test metrics calculation."""
        fetcher.metrics = {
            "total_requests": 10,
            "successful_requests": 8,
            "failed_requests": 2,
            "total_bars_fetched": 1000,
            "total_response_time": 16.0,
        }

        metrics = fetcher.get_metrics()

        assert metrics["success_rate"] == 0.8
        assert metrics["avg_response_time"] == 2.0
        assert metrics["avg_bars_per_request"] == 125

    @pytest.mark.asyncio
    async def test_not_connected_error(self, fetcher, mock_connection):
        """Test error when not connected to IB."""
        mock_connection.is_connected_sync.return_value = False

        with pytest.raises(ConnectionError):
            await fetcher.fetch_historical_data(
                "AAPL",
                "1m",
                datetime.now(timezone.utc) - timedelta(days=1),
                datetime.now(timezone.utc),
            )
