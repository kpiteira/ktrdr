"""
Unit tests for External Data Provider Interface

Tests the abstract interface for external data providers.
"""

import unittest
from abc import ABC
from datetime import datetime, timezone
import pandas as pd
from ktrdr.data.external_data_interface import (
    ExternalDataProvider,
    DataProviderError,
    DataProviderConnectionError,
    DataProviderRateLimitError,
    DataProviderDataError,
    DataProviderConfigError,
)


class MockExternalDataProvider(ExternalDataProvider):
    """Mock implementation for testing."""

    def __init__(self):
        self.fetch_calls = []
        self.validate_calls = []
        self.head_timestamp_calls = []

    async def fetch_historical_data(
        self, symbol, timeframe, start, end, instrument_type=None
    ):
        self.fetch_calls.append((symbol, timeframe, start, end, instrument_type))

        # Return mock data
        dates = pd.date_range(start=start, end=end, freq="1h")
        return pd.DataFrame(
            {
                "open": [100.0] * len(dates),
                "high": [101.0] * len(dates),
                "low": [99.0] * len(dates),
                "close": [100.5] * len(dates),
                "volume": [1000] * len(dates),
            },
            index=dates,
        )

    async def validate_symbol(self, symbol, instrument_type=None):
        self.validate_calls.append((symbol, instrument_type))
        return symbol != "INVALID"

    async def get_head_timestamp(self, symbol, timeframe, instrument_type=None):
        self.head_timestamp_calls.append((symbol, timeframe, instrument_type))
        return datetime(2020, 1, 1, tzinfo=timezone.utc)

    async def get_latest_timestamp(self, symbol, timeframe, instrument_type=None):
        return datetime.now(timezone.utc)

    async def get_supported_timeframes(self):
        return ["1m", "5m", "1h", "1d"]

    async def get_supported_instruments(self):
        return ["STK", "FOREX"]

    async def health_check(self):
        return {
            "healthy": True,
            "connected": True,
            "last_request_time": datetime.now(timezone.utc),
            "error_count": 0,
            "rate_limit_status": {},
            "provider_info": {"name": "Mock Provider"},
        }

    async def get_provider_info(self):
        return {
            "name": "Mock Provider",
            "version": "1.0.0",
            "capabilities": ["historical_data", "symbol_validation"],
            "rate_limits": {},
            "data_coverage": {},
        }


class TestExternalDataInterface(unittest.TestCase):
    """Test external data provider interface."""

    def test_interface_is_abstract(self):
        """Test that ExternalDataProvider is abstract."""
        self.assertTrue(issubclass(ExternalDataProvider, ABC))

        # Should not be able to instantiate directly
        with self.assertRaises(TypeError):
            ExternalDataProvider()

    async def test_mock_implementation(self):
        """Test mock implementation works correctly."""
        provider = MockExternalDataProvider()

        # Test fetch_historical_data
        start = datetime(2023, 1, 1, tzinfo=timezone.utc)
        end = datetime(2023, 1, 2, tzinfo=timezone.utc)

        data = await provider.fetch_historical_data("AAPL", "1h", start, end, "STK")

        self.assertIsInstance(data, pd.DataFrame)
        self.assertIn("open", data.columns)
        self.assertIn("high", data.columns)
        self.assertIn("low", data.columns)
        self.assertIn("close", data.columns)
        self.assertIn("volume", data.columns)
        self.assertEqual(len(provider.fetch_calls), 1)
        self.assertEqual(provider.fetch_calls[0], ("AAPL", "1h", start, end, "STK"))

    async def test_symbol_validation(self):
        """Test symbol validation."""
        provider = MockExternalDataProvider()

        # Valid symbol
        is_valid = await provider.validate_symbol("AAPL", "STK")
        self.assertTrue(is_valid)

        # Invalid symbol
        is_valid = await provider.validate_symbol("INVALID", "STK")
        self.assertFalse(is_valid)

        self.assertEqual(len(provider.validate_calls), 2)

    async def test_head_timestamp(self):
        """Test head timestamp retrieval."""
        provider = MockExternalDataProvider()

        timestamp = await provider.get_head_timestamp("AAPL", "1h", "STK")

        self.assertIsInstance(timestamp, datetime)
        self.assertEqual(timestamp.tzinfo, timezone.utc)
        self.assertEqual(len(provider.head_timestamp_calls), 1)

    async def test_latest_timestamp(self):
        """Test latest timestamp retrieval."""
        provider = MockExternalDataProvider()

        timestamp = await provider.get_latest_timestamp("AAPL", "1h", "STK")

        self.assertIsInstance(timestamp, datetime)
        self.assertEqual(timestamp.tzinfo, timezone.utc)

    async def test_supported_timeframes(self):
        """Test supported timeframes."""
        provider = MockExternalDataProvider()

        timeframes = await provider.get_supported_timeframes()

        self.assertIsInstance(timeframes, list)
        self.assertIn("1h", timeframes)
        self.assertIn("1d", timeframes)

    async def test_supported_instruments(self):
        """Test supported instruments."""
        provider = MockExternalDataProvider()

        instruments = await provider.get_supported_instruments()

        self.assertIsInstance(instruments, list)
        self.assertIn("STK", instruments)
        self.assertIn("FOREX", instruments)

    async def test_health_check(self):
        """Test health check."""
        provider = MockExternalDataProvider()

        health = await provider.health_check()

        self.assertIsInstance(health, dict)
        self.assertIn("healthy", health)
        self.assertIn("connected", health)
        self.assertTrue(health["healthy"])
        self.assertTrue(health["connected"])

    async def test_provider_info(self):
        """Test provider info."""
        provider = MockExternalDataProvider()

        info = await provider.get_provider_info()

        self.assertIsInstance(info, dict)
        self.assertIn("name", info)
        self.assertIn("version", info)
        self.assertIn("capabilities", info)
        self.assertEqual(info["name"], "Mock Provider")

    async def test_optional_methods_default_behavior(self):
        """Test optional methods have default implementations."""
        provider = MockExternalDataProvider()

        # These should not raise NotImplementedError
        market_hours = await provider.get_market_hours(
            "AAPL", datetime.now(timezone.utc)
        )
        self.assertIsNone(market_hours)

        contract_details = await provider.get_contract_details("AAPL")
        self.assertIsNone(contract_details)

        search_results = await provider.search_symbols("AAPL")
        self.assertEqual(search_results, [])


class TestDataProviderExceptions(unittest.TestCase):
    """Test data provider exception classes."""

    def test_base_exception(self):
        """Test base DataProviderError."""
        error = DataProviderError("Test message", "TestProvider", "ERR001")

        self.assertEqual(str(error), "Test message")
        self.assertEqual(error.provider, "TestProvider")
        self.assertEqual(error.error_code, "ERR001")

    def test_connection_error(self):
        """Test DataProviderConnectionError."""
        error = DataProviderConnectionError(
            "Connection failed", "TestProvider", "CONN001"
        )

        self.assertIsInstance(error, DataProviderError)
        self.assertEqual(error.provider, "TestProvider")
        self.assertEqual(error.error_code, "CONN001")

    def test_rate_limit_error(self):
        """Test DataProviderRateLimitError."""
        error = DataProviderRateLimitError(
            "Rate limit exceeded", "TestProvider", retry_after=60.0
        )

        self.assertIsInstance(error, DataProviderError)
        self.assertEqual(error.provider, "TestProvider")
        self.assertEqual(error.retry_after, 60.0)

    def test_data_error(self):
        """Test DataProviderDataError."""
        error = DataProviderDataError("Data not available", "TestProvider", "DATA001")

        self.assertIsInstance(error, DataProviderError)
        self.assertEqual(error.provider, "TestProvider")
        self.assertEqual(error.error_code, "DATA001")

    def test_config_error(self):
        """Test DataProviderConfigError."""
        error = DataProviderConfigError(
            "Invalid configuration", "TestProvider", "CONFIG001"
        )

        self.assertIsInstance(error, DataProviderError)
        self.assertEqual(error.provider, "TestProvider")
        self.assertEqual(error.error_code, "CONFIG001")


if __name__ == "__main__":
    # For async tests, we need to run them properly
    import asyncio

    class AsyncTestRunner:
        """Helper to run async tests."""

        def __init__(self, test_class):
            self.test_class = test_class

        async def run_async_tests(self):
            """Run all async test methods."""
            test_instance = self.test_class()

            # Find all async test methods
            async_methods = [
                method
                for method in dir(test_instance)
                if method.startswith("test_")
                and asyncio.iscoroutinefunction(getattr(test_instance, method))
            ]

            for method_name in async_methods:
                method = getattr(test_instance, method_name)
                try:
                    await method()
                    print(f"✓ {method_name}")
                except Exception as e:
                    print(f"✗ {method_name}: {e}")

    # Run sync tests
    unittest.main(exit=False, verbosity=2)

    # Run async tests
    print("\nRunning async tests...")
    runner = AsyncTestRunner(TestExternalDataInterface)
    asyncio.run(runner.run_async_tests())
