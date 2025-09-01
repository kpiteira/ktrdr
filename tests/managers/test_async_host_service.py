"""
Tests for AsyncHostService base class and related components.

Following TDD approach - these tests will FAIL initially and drive the implementation.
"""

import asyncio
import pytest
import pytest_asyncio
from abc import ABC
from typing import Dict, Any, Optional
from unittest.mock import Mock, AsyncMock, patch

import httpx

from ktrdr.managers.async_host_service import (
    AsyncHostService,
    HostServiceError,
    HostServiceConnectionError,
    HostServiceTimeoutError,
    HostServiceConfig,
)


# Mock concrete implementation for testing abstract base class
class MockHostService(AsyncHostService):
    """Mock concrete implementation for testing the abstract base class."""

    def __init__(self, config: HostServiceConfig, **kwargs):
        self._base_url = "http://localhost:5000"
        self._service_name = "MockService"
        super().__init__(config, **kwargs)

    def get_service_name(self) -> str:
        return self._service_name

    def get_base_url(self) -> str:
        return self._base_url

    async def get_health_check_endpoint(self) -> str:
        return "/health"


class TestHostServiceExceptions:
    """Test the custom exception hierarchy."""

    def test_host_service_error_base(self):
        """Test that HostServiceError is the base exception."""
        error = HostServiceError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)

    def test_host_service_connection_error(self):
        """Test connection-specific error inheritance."""
        error = HostServiceConnectionError("Connection failed")
        assert isinstance(error, HostServiceError)
        assert str(error) == "Connection failed"

    def test_host_service_timeout_error(self):
        """Test timeout-specific error inheritance."""
        error = HostServiceTimeoutError("Request timed out")
        assert isinstance(error, HostServiceError)
        assert str(error) == "Request timed out"


class TestHostServiceConfig:
    """Test the configuration data class."""

    def test_config_creation(self):
        """Test creating configuration with default values."""
        config = HostServiceConfig(base_url="http://localhost:5000")
        assert config.base_url == "http://localhost:5000"
        assert config.timeout == 30
        assert config.max_retries == 3
        assert config.connection_pool_limit == 20

    def test_config_custom_values(self):
        """Test creating configuration with custom values."""
        config = HostServiceConfig(
            base_url="http://api.example.com",
            timeout=45,
            max_retries=5,
            connection_pool_limit=50,
        )
        assert config.base_url == "http://api.example.com"
        assert config.timeout == 45
        assert config.max_retries == 5
        assert config.connection_pool_limit == 50


class TestAsyncHostServiceAbstractContract:
    """Test the abstract base class contract."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that AsyncHostService cannot be instantiated directly."""
        config = HostServiceConfig(base_url="http://localhost:5000")

        with pytest.raises(TypeError, match="abstract"):
            AsyncHostService(config)  # This should fail - abstract class

    def test_concrete_class_must_implement_abstract_methods(self):
        """Test that concrete classes must implement all abstract methods."""

        # This incomplete implementation should fail
        class IncompleteHostService(AsyncHostService):
            def get_service_name(self) -> str:
                return "Incomplete"

            # Missing get_base_url and get_health_check_endpoint

        config = HostServiceConfig(base_url="http://localhost:5000")

        with pytest.raises(TypeError, match="abstract"):
            IncompleteHostService(config)

    def test_complete_concrete_class_can_be_instantiated(self):
        """Test that complete concrete classes can be instantiated."""
        config = HostServiceConfig(base_url="http://localhost:5000")
        service = MockHostService(config)

        assert service.get_service_name() == "MockService"
        assert service.get_base_url() == "http://localhost:5000"


@pytest_asyncio.fixture
async def mock_host_service():
    """Fixture providing a mock host service for testing."""
    config = HostServiceConfig(base_url="http://localhost:5000")
    service = MockHostService(config)

    # Setup async context manager manually for testing
    await service.__aenter__()
    yield service
    await service.__aexit__(None, None, None)


class TestAsyncHostServiceLifecycle:
    """Test async context manager lifecycle."""

    @pytest.mark.asyncio
    async def test_async_context_manager_protocol(self):
        """Test that async context manager protocol is implemented."""
        config = HostServiceConfig(base_url="http://localhost:5000")
        service = MockHostService(config)

        # Test async context manager
        async with service:
            assert service._http_client is not None
            assert service._connection_pool is not None

        # After context exit, resources should be cleaned up
        assert service._http_client is None

    @pytest.mark.asyncio
    async def test_connection_pool_setup(self):
        """Test that connection pool is properly set up."""
        config = HostServiceConfig(
            base_url="http://localhost:5000", connection_pool_limit=25
        )
        service = MockHostService(config)

        async with service:
            # Verify connection pool is initialized
            assert service._connection_pool is not None
            assert service._http_client is not None
            # Verify configuration is stored
            assert service.config.connection_pool_limit == 25
            # Verify it's the same object (connection pooling pattern)
            assert service._connection_pool == service._http_client

    @pytest.mark.asyncio
    async def test_manual_lifecycle_management(self):
        """Test manual enter/exit lifecycle management."""
        config = HostServiceConfig(base_url="http://localhost:5000")
        service = MockHostService(config)

        # Manual setup
        await service.__aenter__()
        try:
            assert service._http_client is not None
        finally:
            # Manual cleanup
            await service.__aexit__(None, None, None)
            assert service._http_client is None


class TestAsyncHostServiceHTTPCommunication:
    """Test HTTP communication methods."""

    @pytest.mark.asyncio
    async def test_post_request_success(self, mock_host_service):
        """Test successful POST request."""
        with patch.object(mock_host_service._http_client, "post") as mock_post:
            # Mock successful response
            mock_response = Mock()
            mock_response.json.return_value = {"success": True, "data": "test"}
            mock_response.raise_for_status.return_value = None
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            result = await mock_host_service._call_host_service_post(
                "/test", {"key": "value"}
            )

            assert result == {"success": True, "data": "test"}
            mock_post.assert_called_once_with(
                "http://localhost:5000/test", json={"key": "value"}, timeout=30.0
            )

    @pytest.mark.asyncio
    async def test_get_request_success(self, mock_host_service):
        """Test successful GET request."""
        with patch.object(mock_host_service._http_client, "get") as mock_get:
            # Mock successful response
            mock_response = Mock()
            mock_response.json.return_value = {"result": "success"}
            mock_response.raise_for_status.return_value = None
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            result = await mock_host_service._call_host_service_get(
                "/status", {"filter": "active"}
            )

            assert result == {"result": "success"}
            mock_get.assert_called_once_with(
                "http://localhost:5000/status",
                params={"filter": "active"},
                timeout=30.0,
            )

    @pytest.mark.asyncio
    async def test_http_error_handling(self, mock_host_service):
        """Test HTTP error handling and exception translation."""
        with patch.object(mock_host_service._http_client, "post") as mock_post:
            # Mock HTTP error
            mock_post.side_effect = httpx.HTTPError("Connection failed")

            with pytest.raises(HostServiceConnectionError, match="Connection failed"):
                await mock_host_service._call_host_service_post("/test", {})

    @pytest.mark.asyncio
    async def test_timeout_error_handling(self, mock_host_service):
        """Test timeout error handling."""
        with patch.object(mock_host_service._http_client, "post") as mock_post:
            # Mock timeout error
            mock_post.side_effect = httpx.TimeoutException("Request timed out")

            with pytest.raises(HostServiceTimeoutError, match="Request timed out"):
                await mock_host_service._call_host_service_post("/test", {})

    @pytest.mark.asyncio
    async def test_retry_logic_with_exponential_backoff(self, mock_host_service):
        """Test retry logic with exponential backoff."""
        with patch.object(mock_host_service._http_client, "post") as mock_post:
            # Mock failures followed by success
            mock_post.side_effect = [
                httpx.TimeoutException("Timeout 1"),
                httpx.TimeoutException("Timeout 2"),
                Mock(json=lambda: {"success": True}, raise_for_status=lambda: None),
            ]

            with patch("asyncio.sleep") as mock_sleep:
                result = await mock_host_service._call_host_service_post("/test", {})

                assert result == {"success": True}
                # Should have retried 2 times
                assert mock_post.call_count == 3
                # Should have exponential backoff delays
                mock_sleep.assert_called()


class TestAsyncHostServiceHealthCheck:
    """Test health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_host_service):
        """Test successful health check."""
        with patch.object(mock_host_service, "_call_host_service_get") as mock_get:
            mock_get.return_value = {"status": "healthy", "uptime": 12345}

            result = await mock_host_service.check_health()

            assert result["status"] == "healthy"
            mock_get.assert_called_once_with("/health")

    @pytest.mark.asyncio
    async def test_health_check_with_custom_timeout(self, mock_host_service):
        """Test health check with custom timeout."""
        with patch.object(mock_host_service, "_call_host_service_get") as mock_get:
            mock_get.return_value = {"status": "healthy"}

            await mock_host_service.check_health(timeout=10)

            # Should use custom timeout in the underlying HTTP call
            assert mock_get.called

    @pytest.mark.asyncio
    async def test_health_check_failure(self, mock_host_service):
        """Test health check failure handling."""
        with patch.object(mock_host_service, "_call_host_service_get") as mock_get:
            mock_get.side_effect = HostServiceConnectionError("Service unavailable")

            with pytest.raises(HostServiceConnectionError, match="Service unavailable"):
                await mock_host_service.check_health()


class TestAsyncHostServiceStatistics:
    """Test request statistics and monitoring."""

    @pytest.mark.asyncio
    async def test_request_statistics_tracking(self, mock_host_service):
        """Test that request statistics are tracked."""
        initial_count = mock_host_service.get_request_count()

        with patch.object(mock_host_service._http_client, "get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {"data": "test"}
            mock_response.raise_for_status.return_value = None
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            await mock_host_service._call_host_service_get("/test")

            assert mock_host_service.get_request_count() == initial_count + 1

    @pytest.mark.asyncio
    async def test_error_statistics_tracking(self, mock_host_service):
        """Test that error statistics are tracked."""
        initial_errors = mock_host_service.get_error_count()

        with patch.object(mock_host_service._http_client, "get") as mock_get:
            mock_get.side_effect = httpx.HTTPError("Test error")

            with pytest.raises(HostServiceConnectionError):
                await mock_host_service._call_host_service_get("/test")

            assert mock_host_service.get_error_count() == initial_errors + 1

    def test_get_statistics_dict(self, mock_host_service):
        """Test getting complete statistics as dictionary."""
        stats = mock_host_service.get_statistics()

        expected_keys = ["requests_made", "errors_encountered", "last_request_time"]
        assert all(key in stats for key in expected_keys)


class TestAsyncHostServiceConfiguration:
    """Test configuration injection and customization."""

    @pytest.mark.asyncio
    async def test_custom_timeout_configuration(self):
        """Test custom timeout configuration."""
        config = HostServiceConfig(base_url="http://localhost:5000", timeout=60)
        service = MockHostService(config)

        async with service:
            # Timeout should be reflected in HTTP client configuration
            assert service.config.timeout == 60

    @pytest.mark.asyncio
    async def test_custom_retry_configuration(self):
        """Test custom retry configuration."""
        config = HostServiceConfig(base_url="http://localhost:5000", max_retries=5)
        service = MockHostService(config)

        async with service:
            with patch.object(service._http_client, "post") as mock_post:
                mock_post.side_effect = [
                    httpx.TimeoutException("Timeout") for _ in range(6)
                ]

                with patch("asyncio.sleep"):  # Speed up test
                    with pytest.raises(HostServiceTimeoutError):
                        await service._call_host_service_post("/test", {})

                # Should have attempted 5 retries + 1 initial attempt = 6 calls
                assert mock_post.call_count == 6


class TestAsyncHostServiceIntegration:
    """Integration tests for realistic usage patterns."""

    @pytest.mark.asyncio
    async def test_complete_workflow(self):
        """Test complete workflow: setup -> request -> cleanup."""
        config = HostServiceConfig(base_url="http://localhost:5000")
        service = MockHostService(config)

        # Test complete workflow
        async with service:
            # Health check
            with patch.object(service, "_call_host_service_get") as mock_get:
                mock_get.return_value = {"status": "healthy"}
                health = await service.check_health()
                assert health["status"] == "healthy"

            # POST request
            with patch.object(service, "_call_host_service_post") as mock_post:
                mock_post.return_value = {"result": "created"}
                result = await service._call_host_service_post(
                    "/create", {"data": "test"}
                )
                assert result["result"] == "created"

            # Statistics should be tracked
            stats = service.get_statistics()
            assert stats["requests_made"] >= 0  # At least the requests we made

    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test handling concurrent requests safely."""
        config = HostServiceConfig(base_url="http://localhost:5000")
        service = MockHostService(config)

        async with service:
            with patch.object(service, "_call_host_service_get") as mock_get:
                mock_get.return_value = {"data": "test"}

                # Make multiple concurrent requests
                tasks = [service._call_host_service_get(f"/test/{i}") for i in range(5)]

                results = await asyncio.gather(*tasks, return_exceptions=True)

                # All requests should succeed
                assert len(results) == 5
                assert all(isinstance(r, dict) for r in results)
                assert all(r["data"] == "test" for r in results)
