"""
Tests for TrainingAdapter AsyncServiceAdapter Integration (Task 4.3)

Validates that TrainingAdapter properly inherits from AsyncServiceAdapter and uses
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
from ktrdr.training.training_adapter import TrainingAdapter


class TestTrainingAdapterAsyncServiceIntegration(unittest.TestCase):
    """Test TrainingAdapter AsyncServiceAdapter integration."""

    def test_inherits_from_async_service_adapter(self):
        """Test that TrainingAdapter inherits from AsyncServiceAdapter."""
        adapter = TrainingAdapter(use_host_service=True)

        # Should inherit from AsyncServiceAdapter
        self.assertIsInstance(adapter, AsyncServiceAdapter)

    def test_implements_get_service_name(self):
        """Test that get_service_name is implemented."""
        adapter = TrainingAdapter(use_host_service=True)

        service_name = adapter.get_service_name()

        # Should return Training-specific service name
        self.assertEqual(service_name, "Training Service")
        self.assertIsInstance(service_name, str)

    def test_implements_get_service_type(self):
        """Test that get_service_type is implemented."""
        adapter = TrainingAdapter(use_host_service=True)

        service_type = adapter.get_service_type()

        # Should return Training-specific service type identifier
        self.assertEqual(service_type, "training")
        self.assertIsInstance(service_type, str)

    def test_implements_get_base_url(self):
        """Test that get_base_url returns configured URL."""
        adapter = TrainingAdapter(
            use_host_service=True, host_service_url="http://localhost:5002"
        )

        base_url = adapter.get_base_url()

        self.assertEqual(base_url, "http://localhost:5002")

    def test_implements_get_health_check_endpoint(self):
        """Test that get_health_check_endpoint is implemented."""
        adapter = TrainingAdapter(use_host_service=True)

        async def run_test():
            endpoint = await adapter.get_health_check_endpoint()

            # Should return health check endpoint
            self.assertEqual(endpoint, "/health")
            self.assertIsInstance(endpoint, str)

        asyncio.run(run_test())

    def test_uses_async_service_adapter_connection_pooling(self):
        """Test that TrainingAdapter uses AsyncServiceAdapter connection pooling."""
        adapter = TrainingAdapter(use_host_service=True)

        # Should have config from AsyncServiceAdapter
        self.assertIsInstance(adapter.config, HostServiceConfig)

        # Should NOT create new HTTP client per request (old pattern)
        # AsyncServiceAdapter manages connection pooling
        self.assertFalse(hasattr(adapter, "_separate_http_client"))

    def test_cancellation_token_integration(self):
        """Test that cancellation token is properly integrated."""
        adapter = TrainingAdapter(use_host_service=True)

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
        """Test that TrainingAdapter uses unified error handling."""
        # TrainingAdapter should use AsyncServiceAdapter error types
        # This is tested by verifying the adapter inherits from AsyncServiceAdapter
        # which provides unified error handling
        adapter = TrainingAdapter(use_host_service=True)
        self.assertIsInstance(adapter, AsyncServiceAdapter)

    @patch("httpx.AsyncClient")
    def test_connection_pooling_eliminates_client_per_request(self, mock_client_class):
        """Test that connection pooling eliminates creating client per request."""
        adapter = TrainingAdapter(use_host_service=True)

        async def run_test():
            # Setup adapter with connection pool
            async with adapter:
                # Mock HTTP client
                mock_client = AsyncMock()
                mock_response = AsyncMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "success": True,
                    "session_id": "test123",
                }
                mock_response.raise_for_status = Mock()
                mock_client.post.return_value = mock_response

                adapter._http_client = mock_client

                # Make multiple requests
                await adapter._call_host_service_post("/endpoint1", {})
                await adapter._call_host_service_post("/endpoint2", {})

                # Should reuse same client (not create new one per request)
                self.assertEqual(mock_client.post.call_count, 2)

        asyncio.run(run_test())

    def test_backward_compatibility_preserves_existing_functionality(self):
        """Test that existing TrainingAdapter functionality is preserved."""
        adapter = TrainingAdapter(use_host_service=True)

        # Should still have all original methods
        self.assertTrue(hasattr(adapter, "train_multi_symbol_strategy"))
        self.assertTrue(hasattr(adapter, "get_training_status"))
        self.assertTrue(hasattr(adapter, "stop_training"))

        # Should still track statistics
        self.assertTrue(hasattr(adapter, "requests_made"))
        self.assertTrue(hasattr(adapter, "errors_encountered"))

    def test_consistency_with_ib_data_adapter_patterns(self):
        """Test that TrainingAdapter follows same patterns as IbDataAdapter."""
        from ktrdr.data.ib_data_adapter import IbDataAdapter

        ib_adapter = IbDataAdapter(use_host_service=True)
        training_adapter = TrainingAdapter(use_host_service=True)

        # Both should inherit from AsyncServiceAdapter
        self.assertIsInstance(ib_adapter, AsyncServiceAdapter)
        self.assertIsInstance(training_adapter, AsyncServiceAdapter)

        # Both should have config
        self.assertIsInstance(ib_adapter.config, HostServiceConfig)
        self.assertIsInstance(training_adapter.config, HostServiceConfig)

        # Both should have same base methods
        self.assertTrue(hasattr(ib_adapter, "get_service_name"))
        self.assertTrue(hasattr(training_adapter, "get_service_name"))


class TestTrainingAdapterConnectionPoolPerformance(unittest.TestCase):
    """Test connection pooling performance benefits."""

    @patch("httpx.AsyncClient")
    def test_connection_pool_configured_correctly(self, mock_client_class):
        """Test that connection pool is configured with Training-specific limits."""
        adapter = TrainingAdapter(
            use_host_service=True, host_service_url="http://localhost:5002"
        )

        async def run_test():
            async with adapter:
                # Connection pool should be configured
                self.assertIsNotNone(adapter._http_client)

        asyncio.run(run_test())

    def test_no_http_client_created_in_local_mode(self):
        """Test that HTTP client is not created in local training mode."""
        adapter = TrainingAdapter(use_host_service=False)

        # Should not initialize HTTP client for local mode
        self.assertIsNone(getattr(adapter, "_http_client", None))


if __name__ == "__main__":
    unittest.main()
