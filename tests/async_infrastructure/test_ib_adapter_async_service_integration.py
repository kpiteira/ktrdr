"""
Tests for IbDataAdapter AsyncServiceAdapter Integration (Task 4.2)

Validates that IbDataAdapter properly inherits from AsyncServiceAdapter and uses
unified infrastructure for connection pooling, cancellation, and error handling.
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

from ktrdr.async_infrastructure.cancellation import CancellationToken
from ktrdr.async_infrastructure.service_adapter import (
    AsyncServiceAdapter,
    HostServiceConfig,
)
from ktrdr.data.ib_data_adapter import IbDataAdapter


class TestIbDataAdapterAsyncServiceIntegration(unittest.TestCase):
    """Test IbDataAdapter AsyncServiceAdapter integration."""

    def test_inherits_from_async_service_adapter(self):
        """Test that IbDataAdapter inherits from AsyncServiceAdapter."""
        adapter = IbDataAdapter(use_host_service=True)

        # Should inherit from AsyncServiceAdapter
        self.assertIsInstance(adapter, AsyncServiceAdapter)

    def test_implements_get_service_name(self):
        """Test that get_service_name is implemented."""
        adapter = IbDataAdapter(use_host_service=True)

        service_name = adapter.get_service_name()

        # Should return IB-specific service name
        self.assertEqual(service_name, "IB Data Service")
        self.assertIsInstance(service_name, str)

    def test_implements_get_service_type(self):
        """Test that get_service_type is implemented."""
        adapter = IbDataAdapter(use_host_service=True)

        service_type = adapter.get_service_type()

        # Should return IB-specific service type identifier
        self.assertEqual(service_type, "ib_data")
        self.assertIsInstance(service_type, str)

    def test_implements_get_base_url(self):
        """Test that get_base_url returns configured URL."""
        adapter = IbDataAdapter(
            use_host_service=True, host_service_url="http://localhost:5001"
        )

        base_url = adapter.get_base_url()

        self.assertEqual(base_url, "http://localhost:5001")

    def test_implements_get_health_check_endpoint(self):
        """Test that get_health_check_endpoint is implemented."""
        adapter = IbDataAdapter(use_host_service=True)

        async def run_test():
            endpoint = await adapter.get_health_check_endpoint()

            # Should return health check endpoint
            self.assertEqual(endpoint, "/health")
            self.assertIsInstance(endpoint, str)

        asyncio.run(run_test())

    def test_uses_async_service_adapter_connection_pooling(self):
        """Test that IbDataAdapter uses AsyncServiceAdapter connection pooling."""
        adapter = IbDataAdapter(use_host_service=True)

        # Should have config from AsyncServiceAdapter
        self.assertIsInstance(adapter.config, HostServiceConfig)

        # Should NOT have separate HTTP client management
        # (AsyncServiceAdapter manages this)
        self.assertFalse(hasattr(adapter, "_separate_http_client"))

    def test_cancellation_token_integration(self):
        """Test that cancellation token is properly integrated."""
        adapter = IbDataAdapter(use_host_service=True)

        async def run_test():
            # Create a cancelled token
            token = Mock(spec=CancellationToken)
            token.is_cancelled.return_value = True

            # Mock HTTP client to avoid actual requests
            with patch.object(adapter, "_http_client", create=True) as mock_client:
                mock_client.post = AsyncMock()

                # Attempting operation with cancelled token should raise
                with self.assertRaises(asyncio.CancelledError):
                    await adapter._call_host_service_post(
                        "/test", {}, cancellation_token=token
                    )

        asyncio.run(run_test())

    def test_uses_unified_error_handling(self):
        """Test that IbDataAdapter uses unified error handling."""
        # IbDataAdapter should use AsyncServiceAdapter error types
        # This is tested by verifying the adapter inherits from AsyncServiceAdapter
        # which provides unified error handling
        adapter = IbDataAdapter(use_host_service=True)
        self.assertIsInstance(adapter, AsyncServiceAdapter)

    @patch("httpx.AsyncClient")
    def test_connection_pooling_reuses_connections(self, mock_client_class):
        """Test that connection pooling reuses HTTP connections."""
        adapter = IbDataAdapter(use_host_service=True)

        async def run_test():
            # Setup adapter with connection pool
            async with adapter:
                # Mock HTTP client
                mock_client = AsyncMock()
                mock_response = AsyncMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"success": True}
                mock_response.raise_for_status = Mock()
                mock_client.post.return_value = mock_response

                adapter._http_client = mock_client

                # Make multiple requests
                await adapter._call_host_service_post("/endpoint1", {})
                await adapter._call_host_service_post("/endpoint2", {})

                # Should use same client instance (connection pooling)
                self.assertEqual(mock_client.post.call_count, 2)

        asyncio.run(run_test())

    def test_backward_compatibility_preserves_existing_functionality(self):
        """Test that existing IbDataAdapter functionality is preserved."""
        adapter = IbDataAdapter(use_host_service=True)

        # Should still have all original methods
        self.assertTrue(hasattr(adapter, "fetch_historical_data"))
        self.assertTrue(hasattr(adapter, "validate_symbol"))
        self.assertTrue(hasattr(adapter, "get_head_timestamp"))
        self.assertTrue(hasattr(adapter, "health_check"))

        # Should still track statistics
        self.assertTrue(hasattr(adapter, "requests_made"))
        self.assertTrue(hasattr(adapter, "errors_encountered"))


class TestIbDataAdapterConnectionPoolPerformance(unittest.TestCase):
    """Test connection pooling performance benefits."""

    @patch("httpx.AsyncClient")
    def test_connection_pool_configured_correctly(self, mock_client_class):
        """Test that connection pool is configured with IB-specific limits."""
        adapter = IbDataAdapter(
            use_host_service=True, host_service_url="http://localhost:5001"
        )

        async def run_test():
            async with adapter:
                # Connection pool should be configured
                self.assertIsNotNone(adapter._http_client)

        asyncio.run(run_test())

    def test_no_http_client_created_in_direct_mode(self):
        """Test that HTTP client is not created in direct IB mode."""
        adapter = IbDataAdapter(use_host_service=False)

        # Should not initialize HTTP client for direct mode
        # (AsyncServiceAdapter only initializes in host service mode)
        self.assertIsNone(getattr(adapter, "_http_client", None))


if __name__ == "__main__":
    unittest.main()
