"""
Unit tests for IbDataProvider (HTTP-Only).

Tests the new HTTP-only IB data provider that:
1. Only communicates with IB via host service (HTTP)
2. Never imports from ktrdr.ib
3. Implements ExternalDataProvider interface
4. Inherits from AsyncServiceAdapter for connection pooling
"""

import asyncio
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pandas as pd

from ktrdr.async_infrastructure.service_adapter import (
    AsyncServiceAdapter,
    HostServiceConfig,
)
from ktrdr.data.acquisition.external_data_interface import (
    DataProviderConnectionError,
    DataProviderDataError,
    DataProviderError,
    ExternalDataProvider,
)
from ktrdr.data.acquisition.ib_data_provider import IbDataProvider


class TestIbDataProviderInitialization(unittest.TestCase):
    """Test IbDataProvider initialization and configuration."""

    def test_provider_inherits_from_required_classes(self):
        """Test that IbDataProvider inherits from ExternalDataProvider and AsyncServiceAdapter."""
        provider = IbDataProvider(host_service_url="http://localhost:5001")

        # Should inherit from both required classes
        self.assertIsInstance(provider, ExternalDataProvider)
        self.assertIsInstance(provider, AsyncServiceAdapter)

    def test_provider_initializes_with_default_url(self):
        """Test that provider can initialize with default host service URL."""
        provider = IbDataProvider()

        # Should have default URL
        self.assertEqual(provider.host_service_url, "http://localhost:5001")
        self.assertEqual(provider.config.base_url, "http://localhost:5001")

    def test_provider_initializes_with_custom_url(self):
        """Test that provider can initialize with custom host service URL."""
        custom_url = "http://custom-host:8080"
        provider = IbDataProvider(host_service_url=custom_url)

        self.assertEqual(provider.host_service_url, custom_url)
        self.assertEqual(provider.config.base_url, custom_url)

    def test_provider_has_async_service_adapter_config(self):
        """Test that provider has proper AsyncServiceAdapter configuration."""
        provider = IbDataProvider(host_service_url="http://localhost:5001")

        # Should have config from AsyncServiceAdapter
        self.assertIsInstance(provider.config, HostServiceConfig)
        self.assertEqual(provider.config.base_url, "http://localhost:5001")
        # IB-specific connection pool limit
        self.assertEqual(provider.config.connection_pool_limit, 10)

    def test_provider_initializes_statistics(self):
        """Test that provider initializes request/error statistics."""
        provider = IbDataProvider()

        # Should start with zero statistics
        self.assertEqual(provider.requests_made, 0)
        self.assertEqual(provider.errors_encountered, 0)
        self.assertIsNone(provider.last_request_time)

    def test_provider_does_not_have_direct_ib_components(self):
        """Test that provider does NOT initialize direct IB components."""
        provider = IbDataProvider()

        # Should NOT have direct IB connection components
        self.assertFalse(hasattr(provider, "symbol_validator"))
        self.assertFalse(hasattr(provider, "data_fetcher"))
        self.assertFalse(hasattr(provider, "use_host_service"))  # Always HTTP


class TestIbDataProviderAsyncServiceAdapterMethods(unittest.TestCase):
    """Test IbDataProvider AsyncServiceAdapter abstract method implementations."""

    def test_get_service_name(self):
        """Test get_service_name returns IB Data Service."""
        provider = IbDataProvider()
        self.assertEqual(provider.get_service_name(), "IB Data Service")

    def test_get_service_type(self):
        """Test get_service_type returns ib_data."""
        provider = IbDataProvider()
        self.assertEqual(provider.get_service_type(), "ib_data")

    def test_get_base_url(self):
        """Test get_base_url returns host service URL."""
        provider = IbDataProvider(host_service_url="http://test:5001")
        self.assertEqual(provider.get_base_url(), "http://test:5001")

    def test_get_health_check_endpoint(self):
        """Test get_health_check_endpoint returns /health."""
        provider = IbDataProvider()

        async def test_async():
            endpoint = await provider.get_health_check_endpoint()
            self.assertEqual(endpoint, "/health")

        asyncio.run(test_async())


class TestIbDataProviderFetchHistoricalData(unittest.TestCase):
    """Test IbDataProvider fetch_historical_data method."""

    def test_fetch_historical_data_success(self):
        """Test successful historical data fetch via HTTP."""
        provider = IbDataProvider(host_service_url="http://localhost:5001")

        async def test_async():
            async with provider:
                # Mock HTTP response
                mock_data = pd.DataFrame(
                    {
                        "open": [100.0, 101.0],
                        "high": [102.0, 103.0],
                        "low": [99.0, 100.0],
                        "close": [101.0, 102.0],
                        "volume": [1000, 1100],
                    },
                    index=pd.DatetimeIndex(
                        [
                            datetime(2023, 1, 1, tzinfo=timezone.utc),
                            datetime(2023, 1, 2, tzinfo=timezone.utc),
                        ]
                    ),
                )

                with patch.object(
                    provider, "_call_host_service_post", new=AsyncMock()
                ) as mock_post:
                    mock_post.return_value = {
                        "success": True,
                        "data": mock_data.to_json(orient="index"),
                    }

                    start = datetime(2023, 1, 1, tzinfo=timezone.utc)
                    end = datetime(2023, 1, 2, tzinfo=timezone.utc)

                    result = await provider.fetch_historical_data(
                        "AAPL", "1h", start, end
                    )

                    # Should call host service with correct parameters
                    mock_post.assert_called_once_with(
                        "/data/historical",
                        {
                            "symbol": "AAPL",
                            "timeframe": "1h",
                            "start": start.isoformat(),
                            "end": end.isoformat(),
                            "instrument_type": None,
                        },
                    )

                    # Should return DataFrame
                    self.assertIsInstance(result, pd.DataFrame)
                    self.assertEqual(len(result), 2)
                    self.assertIn("open", result.columns)
                    self.assertIn("close", result.columns)

                    # Should update statistics
                    self.assertEqual(provider.requests_made, 1)
                    self.assertIsNotNone(provider.last_request_time)

        asyncio.run(test_async())

    def test_fetch_historical_data_failure(self):
        """Test historical data fetch failure raises DataProviderDataError."""
        provider = IbDataProvider()

        async def test_async():
            async with provider:
                with patch.object(
                    provider, "_call_host_service_post", new=AsyncMock()
                ) as mock_post:
                    mock_post.return_value = {
                        "success": False,
                        "error": "Symbol not found",
                    }

                    start = datetime(2023, 1, 1, tzinfo=timezone.utc)
                    end = datetime(2023, 1, 2, tzinfo=timezone.utc)

                    with self.assertRaises(DataProviderDataError) as ctx:
                        await provider.fetch_historical_data(
                            "INVALID", "1h", start, end
                        )

                    self.assertIn("Symbol not found", str(ctx.exception))
                    self.assertEqual(provider.errors_encountered, 1)

        asyncio.run(test_async())

    def test_fetch_historical_data_validates_timeframe(self):
        """Test that invalid timeframe is rejected."""
        provider = IbDataProvider()

        async def test_async():
            async with provider:
                start = datetime(2023, 1, 1, tzinfo=timezone.utc)
                end = datetime(2023, 1, 2, tzinfo=timezone.utc)

                with self.assertRaises(ValueError) as ctx:
                    await provider.fetch_historical_data("AAPL", "invalid", start, end)

                self.assertIn("Unsupported timeframe", str(ctx.exception))

        asyncio.run(test_async())

    def test_fetch_historical_data_validates_datetime_range(self):
        """Test that invalid datetime range is rejected."""
        provider = IbDataProvider()

        async def test_async():
            async with provider:
                # Test timezone-naive datetimes
                start_naive = datetime(2023, 1, 1)
                end = datetime(2023, 1, 2, tzinfo=timezone.utc)

                with self.assertRaises(ValueError) as ctx:
                    await provider.fetch_historical_data("AAPL", "1h", start_naive, end)

                self.assertIn("timezone-aware", str(ctx.exception))

                # Test start >= end
                start = datetime(2023, 1, 2, tzinfo=timezone.utc)
                end = datetime(2023, 1, 1, tzinfo=timezone.utc)

                with self.assertRaises(ValueError) as ctx:
                    await provider.fetch_historical_data("AAPL", "1h", start, end)

                self.assertIn("before", str(ctx.exception))

        asyncio.run(test_async())


class TestIbDataProviderSymbolValidation(unittest.TestCase):
    """Test IbDataProvider symbol validation methods."""

    def test_validate_symbol_success(self):
        """Test successful symbol validation."""
        provider = IbDataProvider()

        async def test_async():
            async with provider:
                with patch.object(
                    provider, "_call_host_service_post", new=AsyncMock()
                ) as mock_post:
                    mock_post.return_value = {"success": True, "is_valid": True}

                    result = await provider.validate_symbol("AAPL")

                    self.assertTrue(result)
                    mock_post.assert_called_once_with(
                        "/data/validate", {"symbol": "AAPL", "timeframes": []}
                    )
                    self.assertEqual(provider.requests_made, 1)

        asyncio.run(test_async())

    def test_validate_symbol_invalid(self):
        """Test validation returns False for invalid symbol."""
        provider = IbDataProvider()

        async def test_async():
            async with provider:
                with patch.object(
                    provider, "_call_host_service_post", new=AsyncMock()
                ) as mock_post:
                    mock_post.return_value = {"success": False, "is_valid": False}

                    result = await provider.validate_symbol("INVALID")

                    self.assertFalse(result)

        asyncio.run(test_async())

    def test_validate_symbol_handles_exceptions(self):
        """Test that symbol validation handles exceptions gracefully."""
        provider = IbDataProvider()

        async def test_async():
            async with provider:
                with patch.object(
                    provider, "_call_host_service_post", new=AsyncMock()
                ) as mock_post:
                    mock_post.side_effect = Exception("Connection failed")

                    result = await provider.validate_symbol("AAPL")

                    # Should return False on exception, not raise
                    self.assertFalse(result)
                    self.assertEqual(provider.errors_encountered, 1)

        asyncio.run(test_async())

    def test_get_symbol_info_success(self):
        """Test get_symbol_info returns symbol metadata."""
        provider = IbDataProvider()

        async def test_async():
            async with provider:
                with patch.object(
                    provider, "_call_host_service_get", new=AsyncMock()
                ) as mock_get:
                    mock_get.return_value = {
                        "success": True,
                        "is_valid": True,
                        "contract_info": {
                            "symbol": "AAPL",
                            "exchange": "NASDAQ",
                            "currency": "USD",
                            "instrument_type": "STK",
                        },
                        "head_timestamps": {"1h": "2020-01-01T00:00:00Z"},
                    }

                    result = await provider.get_symbol_info("AAPL")

                    # Should return ValidationResult-like structure
                    self.assertTrue(result.is_valid)
                    self.assertEqual(result.symbol, "AAPL")
                    self.assertIsNotNone(result.contract_info)
                    mock_get.assert_called_once_with("/data/symbol-info/AAPL")

        asyncio.run(test_async())


class TestIbDataProviderTimestampMethods(unittest.TestCase):
    """Test IbDataProvider timestamp-related methods."""

    def test_get_head_timestamp_success(self):
        """Test get_head_timestamp returns earliest available timestamp."""
        provider = IbDataProvider()

        async def test_async():
            async with provider:
                with patch.object(
                    provider, "_call_host_service_get", new=AsyncMock()
                ) as mock_get:
                    mock_get.return_value = {
                        "success": True,
                        "timestamp": "2020-01-01T00:00:00Z",
                    }

                    result = await provider.get_head_timestamp("AAPL", "1h")

                    self.assertIsInstance(result, datetime)
                    self.assertEqual(result.tzinfo, timezone.utc)
                    self.assertEqual(result.year, 2020)
                    mock_get.assert_called_once()

        asyncio.run(test_async())

    def test_get_head_timestamp_not_available(self):
        """Test get_head_timestamp returns None when not available."""
        provider = IbDataProvider()

        async def test_async():
            async with provider:
                with patch.object(
                    provider, "_call_host_service_get", new=AsyncMock()
                ) as mock_get:
                    mock_get.return_value = {"success": False, "timestamp": None}

                    result = await provider.get_head_timestamp("INVALID", "1h")

                    self.assertIsNone(result)

        asyncio.run(test_async())

    def test_get_head_timestamp_handles_exceptions(self):
        """Test get_head_timestamp returns None on exception."""
        provider = IbDataProvider()

        async def test_async():
            async with provider:
                with patch.object(
                    provider, "_call_host_service_get", new=AsyncMock()
                ) as mock_get:
                    mock_get.side_effect = Exception("Connection failed")

                    result = await provider.get_head_timestamp("AAPL", "1h")

                    # Should return None on exception, not raise
                    self.assertIsNone(result)
                    self.assertEqual(provider.errors_encountered, 1)

        asyncio.run(test_async())

    def test_get_latest_timestamp_returns_current_time(self):
        """Test get_latest_timestamp returns current UTC time."""
        provider = IbDataProvider()

        async def test_async():
            before = datetime.now(timezone.utc)
            result = await provider.get_latest_timestamp("AAPL", "1h")
            after = datetime.now(timezone.utc)

            self.assertIsInstance(result, datetime)
            self.assertEqual(result.tzinfo, timezone.utc)
            self.assertGreaterEqual(result, before)
            self.assertLessEqual(result, after)

        asyncio.run(test_async())


class TestIbDataProviderSupportMethods(unittest.TestCase):
    """Test IbDataProvider support methods (timeframes, instruments, etc.)."""

    def test_get_supported_timeframes(self):
        """Test get_supported_timeframes returns list of timeframes."""
        provider = IbDataProvider()

        async def test_async():
            result = await provider.get_supported_timeframes()

            self.assertIsInstance(result, list)
            self.assertIn("1m", result)
            self.assertIn("1h", result)
            self.assertIn("1d", result)
            # Should have all standard IB timeframes
            expected = [
                "1m",
                "5m",
                "15m",
                "30m",
                "1h",
                "2h",
                "3h",
                "4h",
                "1d",
                "1w",
                "1M",
            ]
            self.assertEqual(set(result), set(expected))

        asyncio.run(test_async())

    def test_get_supported_instruments(self):
        """Test get_supported_instruments returns list of instrument types."""
        provider = IbDataProvider()

        async def test_async():
            result = await provider.get_supported_instruments()

            self.assertIsInstance(result, list)
            self.assertIn("STK", result)
            self.assertIn("FOREX", result)
            self.assertIn("CRYPTO", result)
            # Should have all standard IB instrument types
            expected = ["STK", "FOREX", "CRYPTO", "FUTURE", "OPTION", "INDEX"]
            self.assertEqual(set(result), set(expected))

        asyncio.run(test_async())


class TestIbDataProviderHealthCheck(unittest.TestCase):
    """Test IbDataProvider health check and provider info methods."""

    def test_health_check_success(self):
        """Test health check returns healthy status."""
        provider = IbDataProvider()

        async def test_async():
            async with provider:
                with patch.object(
                    provider, "_call_host_service_get", new=AsyncMock()
                ) as mock_get:
                    mock_get.return_value = {
                        "healthy": True,
                        "ib_status": {"connected": True},
                    }

                    result = await provider.health_check()

                    self.assertIsInstance(result, dict)
                    self.assertTrue(result["healthy"])
                    self.assertTrue(result["connected"])
                    self.assertIn("provider_info", result)
                    self.assertEqual(result["provider_info"]["mode"], "host_service")
                    mock_get.assert_called_once_with("/health")

        asyncio.run(test_async())

    def test_health_check_unhealthy(self):
        """Test health check handles unhealthy status."""
        provider = IbDataProvider()

        async def test_async():
            async with provider:
                with patch.object(
                    provider, "_call_host_service_get", new=AsyncMock()
                ) as mock_get:
                    mock_get.return_value = {
                        "healthy": False,
                        "ib_status": {"connected": False},
                    }

                    result = await provider.health_check()

                    self.assertFalse(result["healthy"])
                    self.assertFalse(result["connected"])

        asyncio.run(test_async())

    def test_health_check_handles_exceptions(self):
        """Test health check returns unhealthy on exception."""
        provider = IbDataProvider()

        async def test_async():
            async with provider:
                with patch.object(
                    provider, "_call_host_service_get", new=AsyncMock()
                ) as mock_get:
                    mock_get.side_effect = Exception("Connection failed")

                    result = await provider.health_check()

                    self.assertFalse(result["healthy"])
                    self.assertFalse(result["connected"])
                    self.assertIn("provider_info", result)
                    self.assertIn("error", result["provider_info"])

        asyncio.run(test_async())

    def test_get_provider_info(self):
        """Test get_provider_info returns IB provider metadata."""
        provider = IbDataProvider()

        async def test_async():
            result = await provider.get_provider_info()

            self.assertIsInstance(result, dict)
            self.assertEqual(result["name"], "Interactive Brokers")
            self.assertIn("capabilities", result)
            self.assertIn("rate_limits", result)
            self.assertIn("data_coverage", result)
            self.assertIn("historical_data", result["capabilities"])

        asyncio.run(test_async())


class TestIbDataProviderErrorHandling(unittest.TestCase):
    """Test IbDataProvider error handling and translation."""

    def test_connection_error_translation(self):
        """Test that host service connection errors are translated correctly."""
        provider = IbDataProvider()

        async def test_async():
            async with provider:
                from ktrdr.async_infrastructure.service_adapter import (
                    HostServiceConnectionError,
                )

                with patch.object(
                    AsyncServiceAdapter, "_call_host_service_post", new=AsyncMock()
                ) as mock_post:
                    mock_post.side_effect = HostServiceConnectionError(
                        "Connection failed", "IB Data Service"
                    )

                    with self.assertRaises(DataProviderConnectionError) as ctx:
                        await provider.fetch_historical_data(
                            "AAPL",
                            "1h",
                            datetime(2023, 1, 1, tzinfo=timezone.utc),
                            datetime(2023, 1, 2, tzinfo=timezone.utc),
                        )

                    self.assertIn("Connection failed", str(ctx.exception))
                    self.assertEqual(ctx.exception.provider, "IB")

        asyncio.run(test_async())

    def test_timeout_error_translation(self):
        """Test that timeout errors are translated to DataProviderConnectionError."""
        provider = IbDataProvider()

        async def test_async():
            async with provider:
                from ktrdr.async_infrastructure.service_adapter import (
                    HostServiceTimeoutError,
                )

                with patch.object(
                    AsyncServiceAdapter, "_call_host_service_post", new=AsyncMock()
                ) as mock_post:
                    mock_post.side_effect = HostServiceTimeoutError(
                        "Request timeout", "IB Data Service"
                    )

                    with self.assertRaises(DataProviderConnectionError) as ctx:
                        await provider.fetch_historical_data(
                            "AAPL",
                            "1h",
                            datetime(2023, 1, 1, tzinfo=timezone.utc),
                            datetime(2023, 1, 2, tzinfo=timezone.utc),
                        )

                    self.assertIn("timeout", str(ctx.exception).lower())

        asyncio.run(test_async())

    def test_generic_error_translation(self):
        """Test that generic errors are translated to DataProviderError."""
        provider = IbDataProvider()

        async def test_async():
            async with provider:
                from ktrdr.async_infrastructure.service_adapter import HostServiceError

                with patch.object(
                    AsyncServiceAdapter, "_call_host_service_post", new=AsyncMock()
                ) as mock_post:
                    mock_post.side_effect = HostServiceError(
                        "Generic error", "IB Data Service"
                    )

                    with self.assertRaises(DataProviderError) as ctx:
                        await provider.fetch_historical_data(
                            "AAPL",
                            "1h",
                            datetime(2023, 1, 1, tzinfo=timezone.utc),
                            datetime(2023, 1, 2, tzinfo=timezone.utc),
                        )

                    self.assertEqual(ctx.exception.provider, "IB")

        asyncio.run(test_async())


class TestIbDataProviderNoDirectIBImports(unittest.TestCase):
    """Test that IbDataProvider does NOT import from ktrdr.ib."""

    def test_no_ktrdr_ib_imports(self):
        """Test that IbDataProvider module does not import from ktrdr.ib."""
        import inspect

        from ktrdr.data.acquisition import ib_data_provider

        # Get the source code of the module
        source = inspect.getsource(ib_data_provider)

        # Should NOT contain imports from ktrdr.ib
        self.assertNotIn("from ktrdr.ib import", source)
        self.assertNotIn("import ktrdr.ib", source)

        # Should NOT contain references to IB-specific classes
        self.assertNotIn("IbDataFetcher", source)
        self.assertNotIn("IbSymbolValidator", source)
        self.assertNotIn("IbErrorClassifier", source)
        self.assertNotIn("IbErrorType", source)


if __name__ == "__main__":
    unittest.main()
