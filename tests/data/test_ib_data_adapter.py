"""
Unit tests for IB Data Adapter

Tests the adapter that bridges the data layer to the IB module.
"""

import asyncio
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pandas as pd

from ktrdr.data.external_data_interface import (
    DataProviderConnectionError,
    DataProviderDataError,
    DataProviderError,
    DataProviderRateLimitError,
)
from ktrdr.data.ib_data_adapter import IbDataAdapter


class TestIbDataAdapter(unittest.TestCase):
    """Test IB data adapter functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.host = "localhost"
        self.port = 4002
        self.max_connections = 2

    def test_adapter_initialization(self):
        """Test adapter initialization."""
        adapter = IbDataAdapter(self.host, self.port, self.max_connections)

        self.assertEqual(adapter.host, self.host)
        self.assertEqual(adapter.port, self.port)
        self.assertEqual(adapter.requests_made, 0)
        self.assertEqual(adapter.errors_encountered, 0)
        self.assertIsNone(adapter.last_request_time)

        # Should have symbol validator and data fetcher components
        self.assertIsNotNone(adapter.symbol_validator)
        self.assertIsNotNone(adapter.data_fetcher)

    def test_validate_timeframe(self):
        """Test timeframe validation."""
        adapter = IbDataAdapter()

        # Valid timeframes should not raise
        adapter._validate_timeframe("1h")
        adapter._validate_timeframe("1d")
        adapter._validate_timeframe("5m")

        # Invalid timeframe should raise
        with self.assertRaises(ValueError) as context:
            adapter._validate_timeframe("invalid")

        self.assertIn("Unsupported timeframe", str(context.exception))

    def test_validate_datetime_range(self):
        """Test datetime range validation."""
        adapter = IbDataAdapter()

        start = datetime(2023, 1, 1, tzinfo=timezone.utc)
        end = datetime(2023, 1, 2, tzinfo=timezone.utc)

        # Valid range should not raise
        adapter._validate_datetime_range(start, end)

        # Start after end should raise
        with self.assertRaises(ValueError) as context:
            adapter._validate_datetime_range(end, start)

        self.assertIn("Start datetime must be before end", str(context.exception))

        # Non-timezone-aware should raise
        naive_start = datetime(2023, 1, 1)
        with self.assertRaises(ValueError) as context:
            adapter._validate_datetime_range(naive_start, end)

        self.assertIn("timezone-aware", str(context.exception))

    @unittest.skip("Timeframe conversion moved to internal IB module components")
    def test_convert_timeframe_to_ib(self):
        """Test timeframe conversion to IB format."""
        # This functionality has been moved to the IB module components
        # and is no longer exposed directly on the adapter
        pass

    @unittest.skip("Duration calculation moved to internal IB module components")
    def test_calculate_duration(self):
        """Test IB duration string calculation."""
        # This functionality has been moved to the IB module components
        # and is no longer exposed directly on the adapter
        pass

    def test_update_stats(self):
        """Test statistics updating."""
        adapter = IbDataAdapter()

        initial_requests = adapter.requests_made
        initial_time = adapter.last_request_time

        adapter._update_stats()

        self.assertEqual(adapter.requests_made, initial_requests + 1)
        self.assertIsNotNone(adapter.last_request_time)
        self.assertNotEqual(adapter.last_request_time, initial_time)

    def test_get_supported_timeframes(self):
        """Test getting supported timeframes."""
        adapter = IbDataAdapter()

        async def run_test():
            timeframes = await adapter.get_supported_timeframes()

            self.assertIsInstance(timeframes, list)
            self.assertIn("1m", timeframes)
            self.assertIn("1h", timeframes)
            self.assertIn("1d", timeframes)

        asyncio.run(run_test())

    def test_get_supported_instruments(self):
        """Test getting supported instruments."""
        adapter = IbDataAdapter()

        async def run_test():
            instruments = await adapter.get_supported_instruments()

            self.assertIsInstance(instruments, list)
            self.assertIn("STK", instruments)
            self.assertIn("FOREX", instruments)
            self.assertIn("CRYPTO", instruments)

        asyncio.run(run_test())

    def test_get_latest_timestamp(self):
        """Test getting latest timestamp."""
        adapter = IbDataAdapter()

        async def run_test():
            timestamp = await adapter.get_latest_timestamp("AAPL", "1h")

            self.assertIsInstance(timestamp, datetime)
            self.assertEqual(timestamp.tzinfo, timezone.utc)

        asyncio.run(run_test())

    def test_get_provider_info(self):
        """Test getting provider information."""
        adapter = IbDataAdapter()

        async def run_test():
            info = await adapter.get_provider_info()

            self.assertIsInstance(info, dict)
            self.assertEqual(info["name"], "Interactive Brokers")
            self.assertIn("capabilities", info)
            self.assertIn("rate_limits", info)
            self.assertIn("data_coverage", info)

        asyncio.run(run_test())

    @unittest.skip("Test relies on old IB architecture implementation details")
    @patch("ktrdr.data.ib_data_adapter.IbConnectionPool")
    @patch("ktrdr.data.ib_data_adapter.IbPaceManager")
    def test_fetch_historical_data_success(
        self, mock_pace_manager_class, mock_pool_class
    ):
        """Test successful historical data fetching."""
        # Mock components
        mock_pace_manager = Mock()
        mock_pace_manager.wait_if_needed = AsyncMock()
        mock_pace_manager_class.return_value = mock_pace_manager

        mock_pool = Mock()
        mock_pool.execute_with_connection = AsyncMock()
        mock_pool_class.return_value = mock_pool

        # Mock return data
        mock_data = pd.DataFrame(
            {
                "open": [100.0, 101.0],
                "high": [102.0, 103.0],
                "low": [99.0, 100.0],
                "close": [101.0, 102.0],
                "volume": [1000, 1100],
            },
            index=pd.date_range("2023-01-01", periods=2, freq="1h", tz="UTC"),
        )

        mock_pool.execute_with_connection.return_value = mock_data

        # Test the adapter
        adapter = IbDataAdapter()

        async def run_test():
            start = datetime(2023, 1, 1, tzinfo=timezone.utc)
            end = datetime(2023, 1, 2, tzinfo=timezone.utc)

            result = await adapter.fetch_historical_data("AAPL", "1h", start, end)

            self.assertIsInstance(result, pd.DataFrame)
            self.assertEqual(len(result), 2)
            self.assertIn("open", result.columns)

            # Verify pacing was applied
            mock_pace_manager.wait_if_needed.assert_called_once()

            # Verify stats were updated
            self.assertEqual(adapter.requests_made, 1)

        asyncio.run(run_test())

    @unittest.skip("Test relies on old IB architecture implementation details")
    @patch("ktrdr.data.ib_data_adapter.IbConnectionPool")
    @patch("ktrdr.data.ib_data_adapter.IbPaceManager")
    def test_validate_symbol_success(self, mock_pace_manager_class, mock_pool_class):
        """Test successful symbol validation."""
        # Mock components
        mock_pace_manager = Mock()
        mock_pace_manager.wait_if_needed = AsyncMock()
        mock_pace_manager_class.return_value = mock_pace_manager

        mock_pool = Mock()
        mock_pool.execute_with_connection = AsyncMock(return_value=True)
        mock_pool_class.return_value = mock_pool

        # Test the adapter
        adapter = IbDataAdapter()

        async def run_test():
            result = await adapter.validate_symbol("AAPL")

            self.assertTrue(result)
            mock_pace_manager.wait_if_needed.assert_called_once_with(
                is_historical=False
            )
            self.assertEqual(adapter.requests_made, 1)

        asyncio.run(run_test())

    @unittest.skip("Test relies on old IB architecture implementation details")
    @patch("ktrdr.data.ib_data_adapter.IbConnectionPool")
    @patch("ktrdr.data.ib_data_adapter.IbPaceManager")
    def test_validate_symbol_failure(self, mock_pace_manager_class, mock_pool_class):
        """Test symbol validation failure."""
        # Mock components
        mock_pace_manager = Mock()
        mock_pace_manager.wait_if_needed = AsyncMock()
        mock_pace_manager_class.return_value = mock_pace_manager

        mock_pool = Mock()
        mock_pool.execute_with_connection = AsyncMock(
            side_effect=Exception("Symbol not found")
        )
        mock_pool_class.return_value = mock_pool

        # Test the adapter
        adapter = IbDataAdapter()

        async def run_test():
            result = await adapter.validate_symbol("INVALID")

            self.assertFalse(result)
            self.assertEqual(adapter.errors_encountered, 1)

        asyncio.run(run_test())

    @unittest.skip("Test relies on old IB architecture implementation details")
    @patch("ktrdr.data.ib_data_adapter.IbConnectionPool")
    @patch("ktrdr.data.ib_data_adapter.IbPaceManager")
    def test_get_head_timestamp_success(self, mock_pace_manager_class, mock_pool_class):
        """Test successful head timestamp retrieval."""
        # Mock components
        mock_pace_manager = Mock()
        mock_pace_manager.wait_if_needed = AsyncMock()
        mock_pace_manager_class.return_value = mock_pace_manager

        mock_pool = Mock()
        expected_timestamp = datetime(2020, 1, 1, tzinfo=timezone.utc)
        mock_pool.execute_with_connection = AsyncMock(return_value=expected_timestamp)
        mock_pool_class.return_value = mock_pool

        # Test the adapter
        adapter = IbDataAdapter()

        async def run_test():
            result = await adapter.get_head_timestamp("AAPL", "1h")

            self.assertEqual(result, expected_timestamp)
            mock_pace_manager.wait_if_needed.assert_called_once()
            self.assertEqual(adapter.requests_made, 1)

        asyncio.run(run_test())

    @unittest.skip("Test relies on old IB architecture implementation details")
    @patch("ktrdr.data.ib_data_adapter.IbConnectionPool")
    def test_health_check_healthy(self, mock_pool_class):
        """Test health check when system is healthy."""
        mock_pool = Mock()
        mock_pool.health_check = AsyncMock(
            return_value={"healthy": True, "healthy_connections": 2}
        )
        mock_pool_class.return_value = mock_pool

        adapter = IbDataAdapter()
        adapter.pace_manager.get_stats = Mock(return_value={"test": "stats"})

        async def run_test():
            health = await adapter.health_check()

            self.assertTrue(health["healthy"])
            self.assertTrue(health["connected"])
            self.assertIn("rate_limit_status", health)
            self.assertIn("provider_info", health)

        asyncio.run(run_test())

    @unittest.skip("Test relies on old IB architecture implementation details")
    @patch("ktrdr.data.ib_data_adapter.IbConnectionPool")
    def test_health_check_unhealthy(self, mock_pool_class):
        """Test health check when system is unhealthy."""
        mock_pool = Mock()
        mock_pool.health_check = AsyncMock(side_effect=Exception("Health check failed"))
        mock_pool_class.return_value = mock_pool

        adapter = IbDataAdapter()

        async def run_test():
            health = await adapter.health_check()

            self.assertFalse(health["healthy"])
            self.assertFalse(health["connected"])
            self.assertIn("error", health["provider_info"])

        asyncio.run(run_test())

    def test_handle_ib_error_pacing_violation(self):
        """Test IB error handling for pacing violations."""
        adapter = IbDataAdapter()

        # Import the actual enum
        from ktrdr.ib.error_classifier import IbErrorType

        # Mock pacing violation
        with patch(
            "ktrdr.data.ib_data_adapter.IbErrorClassifier.classify"
        ) as mock_classify:
            mock_classify.return_value = (IbErrorType.PACING_VIOLATION, 60.0)

            with self.assertRaises(DataProviderRateLimitError) as context:
                adapter._handle_ib_error(
                    Exception("Rate limit exceeded"), "test_operation"
                )

            error = context.exception
            self.assertEqual(error.provider, "IB")
            self.assertEqual(error.retry_after, 60.0)

    def test_handle_ib_error_connection_error(self):
        """Test IB error handling for connection errors."""
        adapter = IbDataAdapter()

        # Import the actual enum
        from ktrdr.ib.error_classifier import IbErrorType

        # Mock connection error
        with patch(
            "ktrdr.data.ib_data_adapter.IbErrorClassifier.classify"
        ) as mock_classify:
            mock_classify.return_value = (IbErrorType.CONNECTION_ERROR, 5.0)

            with self.assertRaises(DataProviderConnectionError) as context:
                adapter._handle_ib_error(
                    Exception("Connection failed"), "test_operation"
                )

            error = context.exception
            self.assertEqual(error.provider, "IB")

    def test_handle_ib_error_data_unavailable(self):
        """Test IB error handling for data unavailable."""
        adapter = IbDataAdapter()

        # Import the actual enum
        from ktrdr.ib.error_classifier import IbErrorType

        # Mock data unavailable error
        with patch(
            "ktrdr.data.ib_data_adapter.IbErrorClassifier.classify"
        ) as mock_classify:
            mock_classify.return_value = (IbErrorType.DATA_UNAVAILABLE, 0.0)

            with self.assertRaises(DataProviderDataError) as context:
                adapter._handle_ib_error(
                    Exception("Data not available"), "test_operation"
                )

            error = context.exception
            self.assertEqual(error.provider, "IB")

    def test_handle_ib_error_fatal(self):
        """Test IB error handling for fatal errors."""
        adapter = IbDataAdapter()

        # Import the actual enum
        from ktrdr.ib.error_classifier import IbErrorType

        # Mock fatal error
        with patch(
            "ktrdr.data.ib_data_adapter.IbErrorClassifier.classify"
        ) as mock_classify:
            mock_classify.return_value = (IbErrorType.FATAL, 0.0)

            with self.assertRaises(DataProviderError) as context:
                adapter._handle_ib_error(Exception("Fatal error"), "test_operation")

            error = context.exception
            self.assertEqual(error.provider, "IB")

    def test_handle_ib_error_default(self):
        """Test IB error handling for default case."""
        adapter = IbDataAdapter()

        # Import the actual enum
        from ktrdr.ib.error_classifier import IbErrorType

        # Mock retryable error
        with patch(
            "ktrdr.data.ib_data_adapter.IbErrorClassifier.classify"
        ) as mock_classify:
            mock_classify.return_value = (IbErrorType.RETRYABLE, 5.0)

            with self.assertRaises(DataProviderError) as context:
                adapter._handle_ib_error(Exception("Unknown error"), "test_operation")

            error = context.exception
            self.assertEqual(error.provider, "IB")


if __name__ == "__main__":
    # Run the tests
    unittest.main()
