"""
Unit tests for Unified IB Data Fetcher

Tests comprehensive functionality including:
- Integration with IB connection pool
- IB pace manager integration
- Enhanced error handling and retries
- Connection reuse and proper cleanup
- Concurrent data fetching
- Metrics tracking and monitoring
- Backward compatibility
"""

import pytest
import asyncio
import time
import pandas as pd
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, MagicMock, patch, AsyncMock

from ktrdr.data.ib_data_fetcher_unified import (
    IbDataFetcherUnified,
    fetch_symbol_data_unified,
)
from ktrdr.data.ib_client_id_registry import ClientIdPurpose
from ktrdr.errors import DataError


class TestIbDataFetcherUnified:
    """Test the unified IB data fetcher."""

    @pytest.fixture
    def mock_connection_pool(self):
        """Mock connection pool."""
        pool_connection = Mock()
        pool_connection.client_id = 123
        pool_connection.ib = Mock()
        pool_connection.state = Mock()
        pool_connection.state.name = "CONNECTED"

        mock_pool = Mock()
        mock_pool.acquire_connection = AsyncMock()
        mock_pool.acquire_connection.return_value.__aenter__ = AsyncMock(
            return_value=pool_connection
        )
        mock_pool.acquire_connection.return_value.__aexit__ = AsyncMock(
            return_value=None
        )

        return mock_pool, pool_connection

    @pytest.fixture
    def mock_pace_manager(self):
        """Mock pace manager."""
        pace_manager = Mock()
        pace_manager.check_pace_limits_async = AsyncMock()
        pace_manager.handle_ib_error_async = AsyncMock(
            return_value=(False, 0.0)
        )  # No retry by default
        pace_manager.get_pace_statistics = Mock(
            return_value={"component_statistics": {}}
        )
        return pace_manager

    @pytest.fixture
    def mock_ib_bars(self):
        """Mock IB historical bars data."""
        bars = []
        base_time = datetime(2024, 1, 1, 9, 30)

        for i in range(10):
            bar = Mock()
            bar.date = base_time + timedelta(hours=i)
            bar.open = 100.0 + i
            bar.high = 105.0 + i
            bar.low = 95.0 + i
            bar.close = 102.0 + i
            bar.volume = 1000 + i * 100
            bars.append(bar)

        return bars

    @pytest.fixture
    def fetcher(self, mock_pace_manager):
        """Create a test fetcher with mocked dependencies."""
        with patch(
            "ktrdr.data.ib_data_fetcher_unified.get_pace_manager",
            return_value=mock_pace_manager,
        ):
            return IbDataFetcherUnified(component_name="test_fetcher")

    def test_initialization(self, fetcher):
        """Test fetcher initialization."""
        assert fetcher.component_name == "test_fetcher"
        assert fetcher.metrics["total_requests"] == 0
        assert fetcher.metrics["successful_requests"] == 0
        assert fetcher.metrics["failed_requests"] == 0

    def test_instrument_type_detection(self, fetcher):
        """Test automatic instrument type detection."""
        # Test forex detection
        assert fetcher._detect_instrument_type("EURUSD") == "forex"
        assert fetcher._detect_instrument_type("GBPJPY") == "forex"
        assert fetcher._detect_instrument_type("EUR.USD") == "forex"

        # Test stock detection
        assert fetcher._detect_instrument_type("AAPL") == "stock"
        assert fetcher._detect_instrument_type("MSFT") == "stock"
        assert fetcher._detect_instrument_type("GOOGL") == "stock"

    def test_bar_size_conversion(self, fetcher):
        """Test timeframe to IB bar size conversion."""
        assert fetcher._get_bar_size("1m") == "1 min"
        assert fetcher._get_bar_size("5m") == "5 mins"
        assert fetcher._get_bar_size("1h") == "1 hour"
        assert fetcher._get_bar_size("1d") == "1 day"

        with pytest.raises(ValueError):
            fetcher._get_bar_size("invalid")

    def test_duration_string_calculation(self, fetcher):
        """Test IB duration string calculation."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 8)  # 7 days

        duration = fetcher._calculate_duration_string("1d", start, end)
        assert duration == "1 W"

        # Test with limits
        start = datetime(2024, 1, 1)
        end = datetime(2024, 12, 31)  # Almost 1 year

        duration = fetcher._calculate_duration_string("1d", start, end)
        assert "Y" in duration or "M" in duration

    def test_datetime_formatting(self, fetcher):
        """Test IB datetime formatting."""
        dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        formatted = fetcher._format_ib_datetime(dt)
        assert formatted == "20240115 10:30:00 UTC"

        # Test with pandas timestamp
        pd_ts = pd.Timestamp(dt)
        formatted = fetcher._format_ib_datetime(pd_ts)
        assert formatted == "20240115 10:30:00 UTC"

    @pytest.mark.asyncio
    async def test_get_contract_stock(self, fetcher, mock_connection_pool):
        """Test contract creation for stocks."""
        _, pool_connection = mock_connection_pool

        # Mock the ib.qualifyContractsAsync call
        mock_contract = Mock()
        pool_connection.ib.qualifyContractsAsync = AsyncMock(
            return_value=[mock_contract]
        )

        contract = await fetcher._get_contract(pool_connection.ib, "AAPL", "stock")

        assert contract == mock_contract
        pool_connection.ib.qualifyContractsAsync.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_contract_forex(self, fetcher, mock_connection_pool):
        """Test contract creation for forex."""
        _, pool_connection = mock_connection_pool

        # Mock the ib.qualifyContractsAsync call
        mock_contract = Mock()
        pool_connection.ib.qualifyContractsAsync = AsyncMock(
            return_value=[mock_contract]
        )

        contract = await fetcher._get_contract(pool_connection.ib, "EURUSD", "forex")

        assert contract == mock_contract
        pool_connection.ib.qualifyContractsAsync.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_contract_auto_detect(self, fetcher, mock_connection_pool):
        """Test contract creation with auto-detection."""
        _, pool_connection = mock_connection_pool

        # Mock the ib.qualifyContractsAsync call
        mock_contract = Mock()
        pool_connection.ib.qualifyContractsAsync = AsyncMock(
            return_value=[mock_contract]
        )

        # Should auto-detect as forex
        contract = await fetcher._get_contract(pool_connection.ib, "EURUSD")
        assert contract == mock_contract

    @pytest.mark.asyncio
    async def test_get_contract_failure(self, fetcher, mock_connection_pool):
        """Test contract creation failure."""
        _, pool_connection = mock_connection_pool

        # Mock empty contract list
        pool_connection.ib.qualifyContractsAsync = AsyncMock(return_value=[])

        with pytest.raises(DataError):
            await fetcher._get_contract(pool_connection.ib, "INVALID")

    @pytest.mark.asyncio
    async def test_successful_data_fetch(
        self, fetcher, mock_connection_pool, mock_ib_bars
    ):
        """Test successful historical data fetch."""
        mock_pool, pool_connection = mock_connection_pool

        # Mock IB API calls
        mock_contract = Mock()
        pool_connection.ib.qualifyContractsAsync = AsyncMock(
            return_value=[mock_contract]
        )
        pool_connection.ib.reqHistoricalDataAsync = AsyncMock(return_value=mock_ib_bars)

        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 2, tzinfo=timezone.utc)

        with patch(
            "ktrdr.data.ib_data_fetcher_unified.acquire_ib_connection",
            return_value=mock_pool.acquire_connection.return_value,
        ):
            df = await fetcher.fetch_historical_data(
                symbol="AAPL",
                timeframe="1h",
                start=start_date,
                end=end_date,
                instrument_type="stock",
            )

        # Verify DataFrame
        assert not df.empty
        assert len(df) == 10
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]

        # Verify metrics
        metrics = fetcher.get_metrics()
        assert metrics["total_requests"] == 1
        assert metrics["successful_requests"] == 1
        assert metrics["total_bars_fetched"] == 10
        assert metrics["success_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_empty_data_response(self, fetcher, mock_connection_pool):
        """Test handling of empty data response."""
        mock_pool, pool_connection = mock_connection_pool

        # Mock IB API calls with empty response
        mock_contract = Mock()
        pool_connection.ib.qualifyContractsAsync = AsyncMock(
            return_value=[mock_contract]
        )
        pool_connection.ib.reqHistoricalDataAsync = AsyncMock(return_value=[])

        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 2, tzinfo=timezone.utc)

        with patch(
            "ktrdr.data.ib_data_fetcher_unified.acquire_ib_connection",
            return_value=mock_pool.acquire_connection.return_value,
        ):
            df = await fetcher.fetch_historical_data(
                symbol="AAPL", timeframe="1h", start=start_date, end=end_date
            )

        # Should return empty DataFrame
        assert df.empty
        assert fetcher.metrics["failed_requests"] == 1

    @pytest.mark.asyncio
    async def test_pace_manager_integration(
        self, fetcher, mock_connection_pool, mock_ib_bars
    ):
        """Test integration with pace manager."""
        mock_pool, pool_connection = mock_connection_pool

        # Mock IB API calls
        mock_contract = Mock()
        pool_connection.ib.qualifyContractsAsync = AsyncMock(
            return_value=[mock_contract]
        )
        pool_connection.ib.reqHistoricalDataAsync = AsyncMock(return_value=mock_ib_bars)

        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 2, tzinfo=timezone.utc)

        with patch(
            "ktrdr.data.ib_data_fetcher_unified.acquire_ib_connection",
            return_value=mock_pool.acquire_connection.return_value,
        ):
            await fetcher.fetch_historical_data(
                symbol="AAPL", timeframe="1h", start=start_date, end=end_date
            )

        # Verify pace manager was called
        fetcher.pace_manager.check_pace_limits_async.assert_called_once()
        call_args = fetcher.pace_manager.check_pace_limits_async.call_args[1]
        assert call_args["symbol"] == "AAPL"
        assert call_args["timeframe"] == "1h"
        assert call_args["component"] == "test_fetcher"
        assert call_args["start_date"] == start_date
        assert call_args["end_date"] == end_date

    @pytest.mark.asyncio
    async def test_error_handling_with_retries(self, fetcher, mock_connection_pool):
        """Test error handling with retry logic."""
        mock_pool, pool_connection = mock_connection_pool

        # Mock IB API to fail then succeed
        mock_contract = Mock()
        pool_connection.ib.qualifyContractsAsync = AsyncMock(
            return_value=[mock_contract]
        )

        call_count = 0

        async def failing_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                error = Exception("IB Error 162: pacing violation")
                error.errorCode = 162
                raise error
            else:
                # Return empty data on second call
                return []

        pool_connection.ib.reqHistoricalDataAsync = AsyncMock(
            side_effect=failing_request
        )

        # Mock pace manager to allow retry (but with 0 delay for fast tests)
        fetcher.pace_manager.handle_ib_error_async = AsyncMock(return_value=(True, 0.0))

        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 2, tzinfo=timezone.utc)

        # Mock sleep calls to make tests fast
        with (
            patch("asyncio.sleep", return_value=None),
            patch("time.sleep", return_value=None),
            patch(
                "ktrdr.data.ib_data_fetcher_unified.acquire_ib_connection",
                return_value=mock_pool.acquire_connection.return_value,
            ),
        ):
            df = await fetcher.fetch_historical_data(
                symbol="AAPL",
                timeframe="1h",
                start=start_date,
                end=end_date,
                max_retries=2,
            )

        # Should have retried and succeeded
        assert df.empty  # Empty because second call returned []
        assert call_count == 2
        assert fetcher.metrics["retries_performed"] == 1
        # Note: pace_violations_handled metric might be tracked differently
        
        # Verify pace manager error handling was called
        fetcher.pace_manager.handle_ib_error_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, fetcher, mock_connection_pool):
        """Test behavior when max retries are exceeded."""
        mock_pool, pool_connection = mock_connection_pool

        # Mock IB API to always fail
        mock_contract = Mock()
        pool_connection.ib.qualifyContractsAsync = AsyncMock(
            return_value=[mock_contract]
        )

        error = Exception("IB Error 162: pacing violation")
        error.errorCode = 162
        pool_connection.ib.reqHistoricalDataAsync = AsyncMock(side_effect=error)

        # Mock pace manager to allow retry (but with 0 delay for fast tests)
        fetcher.pace_manager.handle_ib_error_async = AsyncMock(return_value=(True, 0.0))

        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 2, tzinfo=timezone.utc)

        # Mock sleep calls to make tests fast
        with (
            patch("asyncio.sleep", return_value=None),
            patch("time.sleep", return_value=None),
            patch(
                "ktrdr.data.ib_data_fetcher_unified.acquire_ib_connection",
                return_value=mock_pool.acquire_connection.return_value,
            ),
        ):
            with pytest.raises(DataError):
                await fetcher.fetch_historical_data(
                    symbol="AAPL",
                    timeframe="1h",
                    start=start_date,
                    end=end_date,
                    max_retries=2,
                )

        # Should have retried max times
        assert fetcher.metrics["retries_performed"] == 2
        assert fetcher.metrics["failed_requests"] == 1

    @pytest.mark.asyncio
    async def test_future_date_validation(self, fetcher):
        """Test validation of future dates."""
        future_date = datetime.now(timezone.utc) + timedelta(days=1)
        now_date = datetime.now(timezone.utc)

        with pytest.raises(DataError, match="Start date .* is in the future"):
            await fetcher.fetch_historical_data(
                symbol="AAPL", timeframe="1h", start=future_date, end=now_date
            )

    @pytest.mark.asyncio
    async def test_concurrent_fetching(
        self, fetcher, mock_connection_pool, mock_ib_bars
    ):
        """Test concurrent symbol fetching."""
        mock_pool, pool_connection = mock_connection_pool

        # Mock IB API calls
        mock_contract = Mock()
        pool_connection.ib.qualifyContractsAsync = AsyncMock(
            return_value=[mock_contract]
        )
        pool_connection.ib.reqHistoricalDataAsync = AsyncMock(return_value=mock_ib_bars)

        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 2, tzinfo=timezone.utc)

        requests = [
            {
                "symbol": "AAPL",
                "timeframe": "1h",
                "start": start_date,
                "end": end_date,
                "instrument_type": "stock",
            },
            {
                "symbol": "MSFT",
                "timeframe": "1h",
                "start": start_date,
                "end": end_date,
                "instrument_type": "stock",
            },
        ]

        with patch(
            "ktrdr.data.ib_data_fetcher_unified.acquire_ib_connection",
            return_value=mock_pool.acquire_connection.return_value,
        ):
            results = await fetcher.fetch_multiple_symbols(requests, max_concurrent=2)

        # Should have results for both symbols
        assert "AAPL" in results
        assert "MSFT" in results
        assert not results["AAPL"].empty
        assert not results["MSFT"].empty

        # Should have made 2 requests
        assert fetcher.metrics["total_requests"] == 2
        assert fetcher.metrics["successful_requests"] == 2

    def test_metrics_calculation(self, fetcher):
        """Test metrics calculation including success rate."""
        # Simulate some requests
        fetcher.metrics["total_requests"] = 10
        fetcher.metrics["successful_requests"] = 8
        fetcher.metrics["failed_requests"] = 2
        fetcher.metrics["total_bars_fetched"] = 1000

        metrics = fetcher.get_metrics()

        assert metrics["success_rate"] == 0.8
        assert metrics["total_requests"] == 10
        assert metrics["successful_requests"] == 8
        assert metrics["component_name"] == "test_fetcher"

    def test_metrics_reset(self, fetcher):
        """Test metrics reset functionality."""
        # Set some metrics
        fetcher.metrics["total_requests"] = 5
        fetcher.metrics["successful_requests"] = 3

        # Reset
        fetcher.reset_metrics()

        # Should be back to zero
        assert fetcher.metrics["total_requests"] == 0
        assert fetcher.metrics["successful_requests"] == 0
        assert fetcher.metrics["failed_requests"] == 0


class TestConvenienceFunctions:
    """Test convenience functions."""

    @pytest.fixture
    def mock_ib_bars(self):
        """Mock IB historical bars data."""
        bars = []
        base_time = datetime(2024, 1, 1, 9, 30)

        for i in range(10):
            bar = Mock()
            bar.date = base_time + timedelta(hours=i)
            bar.open = 100.0 + i
            bar.high = 105.0 + i
            bar.low = 95.0 + i
            bar.close = 102.0 + i
            bar.volume = 1000 + i * 100
            bars.append(bar)

        return bars

    @pytest.mark.asyncio
    async def test_fetch_symbol_data_unified(self, mock_ib_bars):
        """Test convenience function for simple data fetching."""
        with patch(
            "ktrdr.data.ib_data_fetcher_unified.IbDataFetcherUnified"
        ) as mock_fetcher_class:
            mock_fetcher = Mock()
            mock_fetcher.fetch_historical_data = AsyncMock(
                return_value=pd.DataFrame({"close": [100, 101, 102]})
            )
            mock_fetcher_class.return_value = mock_fetcher

            start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
            end_date = datetime(2024, 1, 2, tzinfo=timezone.utc)

            df = await fetch_symbol_data_unified(
                symbol="AAPL",
                timeframe="1h",
                start=start_date,
                end=end_date,
                instrument_type="stock",
            )

            assert not df.empty
            mock_fetcher.fetch_historical_data.assert_called_once()


class TestBackwardCompatibility:
    """Test backward compatibility features."""

    @pytest.fixture
    def mock_connection_pool(self):
        """Mock connection pool."""
        pool_connection = Mock()
        pool_connection.client_id = 123
        pool_connection.ib = Mock()
        pool_connection.state = Mock()
        pool_connection.state.name = "CONNECTED"

        mock_pool = Mock()
        mock_pool.acquire_connection = AsyncMock()
        mock_pool.acquire_connection.return_value.__aenter__ = AsyncMock(
            return_value=pool_connection
        )
        mock_pool.acquire_connection.return_value.__aexit__ = AsyncMock(
            return_value=None
        )

        return mock_pool, pool_connection

    @pytest.fixture
    def mock_ib_bars(self):
        """Mock IB historical bars data."""
        bars = []
        base_time = datetime(2024, 1, 1, 9, 30)

        for i in range(10):
            bar = Mock()
            bar.date = base_time + timedelta(hours=i)
            bar.open = 100.0 + i
            bar.high = 105.0 + i
            bar.low = 95.0 + i
            bar.close = 102.0 + i
            bar.volume = 1000 + i * 100
            bars.append(bar)

        return bars

    def test_backward_compatibility_alias(self):
        """Test that IbDataFetcher is aliased to unified version."""
        from ktrdr.data.ib_data_fetcher_unified import IbDataFetcher

        # Should be the same class
        assert IbDataFetcher == IbDataFetcherUnified

    @pytest.mark.asyncio
    async def test_forex_what_to_show_adjustment(
        self, mock_connection_pool, mock_ib_bars
    ):
        """Test that what_to_show is adjusted for forex instruments."""
        mock_pool, pool_connection = mock_connection_pool
        mock_pace_manager = Mock()
        mock_pace_manager.check_pace_limits_async = AsyncMock()
        mock_pace_manager.handle_ib_error_async = AsyncMock(return_value=(False, 0.0))
        mock_pace_manager.get_pace_statistics = Mock(
            return_value={"component_statistics": {}}
        )

        with patch(
            "ktrdr.data.ib_data_fetcher_unified.get_pace_manager",
            return_value=mock_pace_manager,
        ):
            fetcher = IbDataFetcherUnified()

        # Mock IB API calls
        mock_contract = Mock()
        pool_connection.ib.qualifyContractsAsync = AsyncMock(
            return_value=[mock_contract]
        )
        pool_connection.ib.reqHistoricalDataAsync = AsyncMock(return_value=mock_ib_bars)

        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 2, tzinfo=timezone.utc)

        with patch(
            "ktrdr.data.ib_data_fetcher_unified.acquire_ib_connection",
            return_value=mock_pool.acquire_connection.return_value,
        ):
            await fetcher.fetch_historical_data(
                symbol="EURUSD",
                timeframe="1h",
                start=start_date,
                end=end_date,
                instrument_type="forex",
                what_to_show="TRADES",  # Should be converted to BID for forex
            )

        # Verify the call was made with BID instead of TRADES
        call_args = pool_connection.ib.reqHistoricalDataAsync.call_args[1]
        assert call_args["whatToShow"] == "BID"


if __name__ == "__main__":
    pytest.main([__file__])
