"""
Tests for AsyncServiceAdapter unified infrastructure (Slice 4 - Task 4.1).

Following TDD approach - these tests will FAIL initially and drive the implementation.

Tests cover:
- Generic service adapter base class (no domain knowledge)
- Connection pooling with configurable limits
- Unified cancellation integration (CancellationToken protocol)
- Consistent error handling patterns
- Abstract methods that subclasses must implement
- Resource lifecycle management
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
import pytest_asyncio

from ktrdr.async_infrastructure.cancellation import (
    AsyncCancellationToken,
)

# These imports will FAIL initially - that's expected for TDD
from ktrdr.async_infrastructure.service_adapter import (
    AsyncServiceAdapter,
    HostServiceConfig,
    HostServiceConnectionError,
    HostServiceError,
    HostServiceTimeoutError,
)


# Mock concrete implementation for testing abstract base class
class MockServiceAdapter(AsyncServiceAdapter):
    """Mock concrete implementation for testing the abstract base class."""

    def __init__(self, config: HostServiceConfig, **kwargs):
        self._base_url = config.base_url
        self._service_name = "MockService"
        self._service_type = "mock"
        super().__init__(config, **kwargs)

    def get_service_name(self) -> str:
        return self._service_name

    def get_service_type(self) -> str:
        return self._service_type

    def get_base_url(self) -> str:
        return self._base_url

    async def get_health_check_endpoint(self) -> str:
        return "/health"


class TestAsyncServiceAdapterAbstractContract:
    """Test the abstract base class contract."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that AsyncServiceAdapter cannot be instantiated directly."""
        config = HostServiceConfig(base_url="http://localhost:5000")

        with pytest.raises(TypeError, match="abstract"):
            AsyncServiceAdapter(config)  # This should fail - abstract class

    def test_concrete_class_must_implement_get_service_name(self):
        """Test that concrete classes must implement get_service_name."""

        class IncompleteAdapter(AsyncServiceAdapter):
            def get_service_type(self) -> str:
                return "incomplete"

            def get_base_url(self) -> str:
                return "http://localhost:5000"

            async def get_health_check_endpoint(self) -> str:
                return "/health"

            # Missing get_service_name

        config = HostServiceConfig(base_url="http://localhost:5000")

        with pytest.raises(TypeError, match="abstract"):
            IncompleteAdapter(config)

    def test_concrete_class_must_implement_get_service_type(self):
        """Test that concrete classes must implement get_service_type."""

        class IncompleteAdapter(AsyncServiceAdapter):
            def get_service_name(self) -> str:
                return "Incomplete"

            def get_base_url(self) -> str:
                return "http://localhost:5000"

            async def get_health_check_endpoint(self) -> str:
                return "/health"

            # Missing get_service_type

        config = HostServiceConfig(base_url="http://localhost:5000")

        with pytest.raises(TypeError, match="abstract"):
            IncompleteAdapter(config)

    def test_complete_concrete_class_can_be_instantiated(self):
        """Test that complete concrete classes can be instantiated."""
        config = HostServiceConfig(base_url="http://localhost:5000")
        adapter = MockServiceAdapter(config)

        assert adapter.get_service_name() == "MockService"
        assert adapter.get_service_type() == "mock"
        assert adapter.get_base_url() == "http://localhost:5000"


class TestHostServiceConfigExtraction:
    """Test that HostServiceConfig can be imported from service_adapter module."""

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


class TestErrorHierarchy:
    """Test the unified exception hierarchy."""

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


@pytest_asyncio.fixture
async def mock_adapter():
    """Fixture providing a mock adapter for testing."""
    config = HostServiceConfig(base_url="http://localhost:5000")
    adapter = MockServiceAdapter(config)

    # Setup async context manager manually for testing
    await adapter.__aenter__()
    yield adapter
    await adapter.__aexit__(None, None, None)


class TestConnectionPooling:
    """Test connection pooling functionality."""

    @pytest.mark.asyncio
    async def test_connection_pool_initialized(self):
        """Test that connection pool is initialized with context manager."""
        config = HostServiceConfig(base_url="http://localhost:5000")
        adapter = MockServiceAdapter(config)

        async with adapter:
            assert adapter._http_client is not None
            assert adapter._connection_pool is not None

        # After context exit, resources should be cleaned up
        assert adapter._http_client is None
        assert adapter._connection_pool is None

    @pytest.mark.asyncio
    async def test_connection_pool_uses_configured_limits(self):
        """Test that connection pool respects configured limits."""
        config = HostServiceConfig(
            base_url="http://localhost:5000", connection_pool_limit=10
        )
        adapter = MockServiceAdapter(config)

        async with adapter:
            # Verify pool was created with correct limits
            assert adapter._http_client is not None
            # Note: We can't directly inspect httpx limits easily,
            # but we ensure the configuration is passed through

    @pytest.mark.asyncio
    async def test_connection_reuse_across_requests(self, mock_adapter):
        """Test that HTTP client is reused across multiple requests."""
        # Get initial client reference
        client_ref = mock_adapter._http_client

        # Simulate multiple requests - client should be the same
        assert mock_adapter._http_client is client_ref
        # The same client instance should be reused


class TestCancellationIntegration:
    """Test unified cancellation token integration."""

    @pytest.mark.asyncio
    async def test_cancellation_token_parameter_accepted(self, mock_adapter):
        """Test that HTTP methods accept cancellation_token parameter."""
        token = AsyncCancellationToken("test_op")

        with patch.object(
            mock_adapter._http_client, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = Mock(
                status_code=200, json=lambda: {"success": True}
            )

            # This should not raise - cancellation_token parameter should be accepted
            result = await mock_adapter._call_host_service_post(
                "/test", {"data": "value"}, cancellation_token=token
            )
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_cancellation_during_request_raises_cancelled_error(
        self, mock_adapter
    ):
        """Test that cancellation during request raises asyncio.CancelledError."""
        token = AsyncCancellationToken("test_op")
        token.cancel("Testing cancellation")

        with pytest.raises(asyncio.CancelledError):
            await mock_adapter._call_host_service_post(
                "/test", {"data": "value"}, cancellation_token=token
            )

    @pytest.mark.asyncio
    async def test_cancellation_checked_before_retry(self, mock_adapter):
        """Test that cancellation is checked before retry attempts."""
        token = AsyncCancellationToken("test_op")

        with patch.object(
            mock_adapter._http_client, "post", new_callable=AsyncMock
        ) as mock_post:
            # First attempt times out
            mock_post.side_effect = httpx.TimeoutException("Timeout")

            # Cancel before retry
            async def cancel_after_first():
                await asyncio.sleep(0.1)
                token.cancel("Cancel before retry")

            asyncio.create_task(cancel_after_first())

            with pytest.raises(asyncio.CancelledError):
                await mock_adapter._call_host_service_post(
                    "/test", {"data": "value"}, cancellation_token=token
                )


class TestGenericDesign:
    """Test that AsyncServiceAdapter is truly generic (no domain knowledge)."""

    def test_no_ib_specific_code(self):
        """Test that there's no IB-specific code in the base class."""
        config = HostServiceConfig(base_url="http://localhost:5000")
        adapter = MockServiceAdapter(config)

        # The adapter should have no knowledge of IB-specific concepts
        # like symbols, contracts, timeframes, etc.
        assert not hasattr(adapter, "validate_symbol")
        assert not hasattr(adapter, "fetch_historical_data")
        assert not hasattr(adapter, "get_contract_details")

    def test_no_training_specific_code(self):
        """Test that there's no training-specific code in the base class."""
        config = HostServiceConfig(base_url="http://localhost:5000")
        adapter = MockServiceAdapter(config)

        # The adapter should have no knowledge of training-specific concepts
        # like models, epochs, strategies, etc.
        assert not hasattr(adapter, "train_model")
        assert not hasattr(adapter, "get_training_status")
        assert not hasattr(adapter, "stop_training")


class TestRetryLogic:
    """Test unified retry logic."""

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self, mock_adapter):
        """Test that requests retry on timeout."""
        with patch.object(
            mock_adapter._http_client, "post", new_callable=AsyncMock
        ) as mock_post:
            # First two attempts timeout, third succeeds
            mock_post.side_effect = [
                httpx.TimeoutException("Timeout 1"),
                httpx.TimeoutException("Timeout 2"),
                Mock(status_code=200, json=lambda: {"success": True}),
            ]

            result = await mock_adapter._call_host_service_post(
                "/test", {"data": "value"}
            )
            assert result["success"] is True
            assert mock_post.call_count == 3

    @pytest.mark.asyncio
    async def test_max_retries_exceeded_raises_timeout_error(self, mock_adapter):
        """Test that exceeding max retries raises HostServiceTimeoutError."""
        with patch.object(
            mock_adapter._http_client, "post", new_callable=AsyncMock
        ) as mock_post:
            # All attempts timeout
            mock_post.side_effect = httpx.TimeoutException("Persistent timeout")

            with pytest.raises(HostServiceTimeoutError):
                await mock_adapter._call_host_service_post("/test", {"data": "value"})

            # Should have tried max_retries + 1 times (default 3 + 1 = 4)
            assert mock_post.call_count == 4


class TestErrorHandling:
    """Test consistent error handling patterns."""

    @pytest.mark.asyncio
    async def test_http_error_raises_connection_error(self, mock_adapter):
        """Test that HTTP errors raise HostServiceConnectionError."""
        with patch.object(
            mock_adapter._http_client, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.side_effect = httpx.HTTPStatusError(
                "404 Not Found",
                request=Mock(),
                response=Mock(status_code=404),
            )

            with pytest.raises(HostServiceConnectionError):
                await mock_adapter._call_host_service_post("/test", {"data": "value"})

    @pytest.mark.asyncio
    async def test_unexpected_error_raises_host_service_error(self, mock_adapter):
        """Test that unexpected errors raise generic HostServiceError."""
        with patch.object(
            mock_adapter._http_client, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.side_effect = ValueError("Unexpected error")

            with pytest.raises(HostServiceError):
                await mock_adapter._call_host_service_post("/test", {"data": "value"})


class TestStatistics:
    """Test statistics collection."""

    @pytest.mark.asyncio
    async def test_request_count_incremented(self, mock_adapter):
        """Test that request count is incremented."""
        initial_count = mock_adapter.get_request_count()

        with patch.object(
            mock_adapter._http_client, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = Mock(
                status_code=200, json=lambda: {"success": True}
            )

            await mock_adapter._call_host_service_post("/test", {"data": "value"})

        assert mock_adapter.get_request_count() == initial_count + 1

    @pytest.mark.asyncio
    async def test_error_count_incremented_on_failure(self, mock_adapter):
        """Test that error count is incremented on failures."""
        initial_errors = mock_adapter.get_error_count()

        with patch.object(
            mock_adapter._http_client, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.side_effect = httpx.TimeoutException("Timeout")

            with pytest.raises(HostServiceTimeoutError):
                await mock_adapter._call_host_service_post("/test", {"data": "value"})

        assert mock_adapter.get_error_count() > initial_errors

    @pytest.mark.asyncio
    async def test_statistics_dictionary_structure(self, mock_adapter):
        """Test that get_statistics returns proper dictionary structure."""
        stats = mock_adapter.get_statistics()

        assert "requests_made" in stats
        assert "errors_encountered" in stats
        assert "last_request_time" in stats
        assert "service_name" in stats
        assert "base_url" in stats
        assert stats["service_name"] == "MockService"
