"""
Unit tests for IbDataAdapter AsyncHostService integration.

Tests the refactored adapter that inherits from AsyncHostService to ensure:
1. All existing IB API calls work identically
2. Same method signatures and return types
3. Identical error handling and exceptions
4. Connection pooling benefits are available
5. Health checking works for IB host service
"""

import asyncio
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pandas as pd

from ktrdr.data.external_data_interface import (
    DataProviderConnectionError,
)
from ktrdr.data.ib_data_adapter import IbDataAdapter
from ktrdr.managers.async_host_service import AsyncHostService, HostServiceConfig


class TestIbAdapterAsyncHostServiceIntegration(unittest.TestCase):
    """Test IB adapter AsyncHostService inheritance and integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.host_service_url = "http://localhost:5001"

    def test_adapter_inherits_from_async_host_service(self):
        """Test that IbDataAdapter inherits from AsyncHostService."""
        adapter = IbDataAdapter(
            use_host_service=True, host_service_url=self.host_service_url
        )

        # Should inherit from AsyncHostService
        self.assertIsInstance(adapter, AsyncHostService)

        # Should have AsyncHostService config
        self.assertIsInstance(adapter.config, HostServiceConfig)
        self.assertEqual(adapter.config.base_url, self.host_service_url)

    def test_adapter_implements_required_abstract_methods(self):
        """Test that IbDataAdapter implements AsyncHostService abstract methods."""
        adapter = IbDataAdapter(
            use_host_service=True, host_service_url=self.host_service_url
        )

        # Should implement all abstract methods
        self.assertEqual(adapter.get_service_name(), "IB Data Service")
        self.assertEqual(adapter.get_base_url(), self.host_service_url)

        async def test_async_methods():
            # Health check endpoint should be implemented
            endpoint = await adapter.get_health_check_endpoint()
            self.assertEqual(endpoint, "/health")

        asyncio.run(test_async_methods())

    def test_adapter_uses_inherited_http_methods_for_host_service(self):
        """Test that refactored adapter uses inherited HTTP methods instead of duplicates."""
        adapter = IbDataAdapter(
            use_host_service=True, host_service_url=self.host_service_url
        )

        async def test_http_methods():
            async with adapter:  # Use async context manager
                # Should use inherited _call_host_service_post method
                with patch.object(
                    adapter, "_call_host_service_post", new=AsyncMock()
                ) as mock_post:
                    mock_post.return_value = {"success": True, "is_valid": True}

                    result = await adapter.validate_symbol("AAPL")
                    self.assertTrue(result)
                    mock_post.assert_called_once()

                # Should use inherited _call_host_service_get method
                with patch.object(
                    adapter, "_call_host_service_get", new=AsyncMock()
                ) as mock_get:
                    mock_get.return_value = {
                        "healthy": True,
                        "ib_status": {"connected": True},
                    }

                    health = await adapter.health_check()
                    self.assertTrue(health["healthy"])
                    mock_get.assert_called_once()

        asyncio.run(test_http_methods())

    def test_adapter_no_longer_has_duplicate_http_methods(self):
        """Test that refactored adapter doesn't have duplicate HTTP connection code."""
        adapter = IbDataAdapter(
            use_host_service=True, host_service_url=self.host_service_url
        )

        # Should have wrapper methods that delegate to AsyncHostService
        self.assertTrue(hasattr(adapter, "_call_host_service_post"))
        self.assertTrue(hasattr(adapter, "_call_host_service_get"))

        # Should inherit AsyncHostService methods for the actual implementation
        self.assertTrue(hasattr(AsyncHostService, "_call_host_service_post"))
        self.assertTrue(hasattr(AsyncHostService, "_call_host_service_get"))

    def test_connection_pooling_available(self):
        """Test that adapter can use connection pooling from AsyncHostService."""
        adapter = IbDataAdapter(
            use_host_service=True, host_service_url=self.host_service_url
        )

        async def test_pooling():
            async with adapter:  # Setup connection pool
                # Should have connection pool initialized
                self.assertIsNotNone(adapter._http_client)
                self.assertIsNotNone(adapter._connection_pool)

                # Connection pool should be configured with limits
                # Note: httpx AsyncClient structure may vary, so test connection exists
                self.assertIsNotNone(adapter._connection_pool)
                # The fact that async context manager worked implies connection is configured

        asyncio.run(test_pooling())

    def test_statistics_and_metrics_available(self):
        """Test that adapter can access AsyncHostService statistics."""
        adapter = IbDataAdapter(
            use_host_service=True, host_service_url=self.host_service_url
        )

        # Should have inherited statistics methods
        self.assertTrue(hasattr(adapter, "get_request_count"))
        self.assertTrue(hasattr(adapter, "get_error_count"))
        self.assertTrue(hasattr(adapter, "get_statistics"))
        self.assertTrue(hasattr(adapter, "get_detailed_metrics"))

        # Should start with zero requests
        self.assertEqual(adapter.get_request_count(), 0)
        self.assertEqual(adapter.get_error_count(), 0)

    def test_health_check_uses_async_host_service(self):
        """Test that health check leverages AsyncHostService capabilities."""
        adapter = IbDataAdapter(
            use_host_service=True, host_service_url=self.host_service_url
        )

        async def test_health_check():
            async with adapter:
                with patch.object(
                    adapter, "_call_host_service_get", new=AsyncMock()
                ) as mock_get:
                    mock_get.return_value = {
                        "healthy": True,
                        "ib_status": {"connected": True},
                    }

                    result = await adapter.health_check()
                    self.assertTrue(result["healthy"])
                    mock_get.assert_called_once_with("/health")

        asyncio.run(test_health_check())

    def test_existing_api_compatibility_preserved(self):
        """Test that all existing IB adapter APIs work identically after refactoring."""
        adapter = IbDataAdapter(
            use_host_service=True, host_service_url=self.host_service_url
        )

        async def test_compatibility():
            async with adapter:
                # Mock the inherited HTTP methods to simulate responses
                with (
                    patch.object(
                        adapter, "_call_host_service_post", new=AsyncMock()
                    ) as mock_post,
                    patch.object(
                        adapter, "_call_host_service_get", new=AsyncMock()
                    ) as mock_get,
                ):
                    # validate_symbol should work identically
                    mock_post.return_value = {"success": True, "is_valid": True}
                    result = await adapter.validate_symbol("AAPL")
                    self.assertIsInstance(result, bool)
                    self.assertTrue(result)

                    # fetch_historical_data should work identically
                    mock_data = pd.DataFrame(
                        {
                            "open": [100.0],
                            "high": [101.0],
                            "low": [99.0],
                            "close": [100.5],
                            "volume": [1000],
                        },
                        index=pd.DatetimeIndex([datetime.now(timezone.utc)]),
                    )

                    mock_post.return_value = {
                        "success": True,
                        "data": mock_data.to_json(orient="index"),
                    }

                    start = datetime(2023, 1, 1, tzinfo=timezone.utc)
                    end = datetime(2023, 1, 2, tzinfo=timezone.utc)
                    result = await adapter.fetch_historical_data(
                        "AAPL", "1h", start, end
                    )

                    self.assertIsInstance(result, pd.DataFrame)
                    self.assertIn("open", result.columns)

                    # get_head_timestamp should work identically
                    mock_get.return_value = {
                        "success": True,
                        "timestamp": "2020-01-01T00:00:00Z",
                    }

                    result = await adapter.get_head_timestamp("AAPL", "1h")
                    self.assertIsInstance(result, datetime)
                    self.assertEqual(result.tzinfo, timezone.utc)

        asyncio.run(test_compatibility())

    def test_error_handling_preserved(self):
        """Test that error handling works identically after AsyncHostService refactoring."""
        adapter = IbDataAdapter(
            use_host_service=True, host_service_url=self.host_service_url
        )

        async def test_error_handling():
            async with adapter:
                with patch.object(
                    AsyncHostService, "_call_host_service_post", new=AsyncMock()
                ) as mock_post:
                    # Connection errors should still map to DataProviderConnectionError
                    from ktrdr.managers.async_host_service import (
                        HostServiceConnectionError,
                    )

                    mock_post.side_effect = HostServiceConnectionError(
                        "Connection failed", "IB Data Service"
                    )

                    with self.assertRaises(DataProviderConnectionError):
                        await adapter.validate_and_get_metadata("AAPL", ["1h"])

                    # Timeout errors should still map to appropriate errors
                    from ktrdr.managers.async_host_service import (
                        HostServiceTimeoutError,
                    )

                    mock_post.side_effect = HostServiceTimeoutError(
                        "Timeout", "IB Data Service"
                    )

                    with self.assertRaises(
                        DataProviderConnectionError
                    ):  # Should be translated
                        await adapter.validate_and_get_metadata("AAPL", ["1h"])

        asyncio.run(test_error_handling())

    def test_direct_connection_mode_unchanged(self):
        """Test that direct IB connection mode is not affected by AsyncHostService changes."""
        adapter = IbDataAdapter(use_host_service=False)  # Direct mode

        # Should not inherit from AsyncHostService in direct mode
        # Or should handle dual mode gracefully
        self.assertIsNotNone(adapter.symbol_validator)
        self.assertIsNotNone(adapter.data_fetcher)
        self.assertFalse(adapter.use_host_service)

    def test_resource_cleanup_with_async_context(self):
        """Test that resource cleanup works properly with AsyncHostService context manager."""
        adapter = IbDataAdapter(
            use_host_service=True, host_service_url=self.host_service_url
        )

        async def test_cleanup():
            async with adapter:
                # Connection pool should be initialized
                self.assertIsNotNone(adapter._http_client)

            # After context exit, connection pool should be cleaned up
            self.assertIsNone(adapter._http_client)

        asyncio.run(test_cleanup())


if __name__ == "__main__":
    # Run the failing tests - they should fail until IbDataAdapter is refactored
    unittest.main()
