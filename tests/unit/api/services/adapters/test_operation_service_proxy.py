"""
Unit tests for OperationServiceProxy.

Tests the HTTP client for querying OperationsService on host services.
Uses unittest.mock for mocking HTTP responses.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from ktrdr.api.services.adapters.operation_service_proxy import (
    OperationServiceProxy,
)


@pytest.mark.asyncio
class TestOperationServiceProxyInitialization:
    """Test proxy initialization."""

    async def test_init_with_base_url(self):
        """Test proxy initializes with base URL."""
        proxy = OperationServiceProxy("http://localhost:5002")
        assert proxy.base_url == "http://localhost:5002"
        await proxy.close()

    async def test_init_strips_trailing_slash(self):
        """Test proxy strips trailing slash from base URL."""
        proxy = OperationServiceProxy("http://localhost:5002/")
        assert proxy.base_url == "http://localhost:5002"
        await proxy.close()


@pytest.mark.asyncio
class TestGetOperation:
    """Test get_operation method."""

    async def test_successful_get_operation(self):
        """Test successful GET operation request."""
        base_url = "http://localhost:5002"
        operation_id = "op_training_123"

        # Mock response
        mock_response_data = {
            "operation_id": operation_id,
            "status": "running",
            "operation_type": "training",
            "progress": {"percentage": 50.0, "current_step": "Epoch 5/10"},
            "created_at": "2025-01-20T10:00:00Z",
        }

        # Create mock response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        # Patch httpx.AsyncClient.get
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            # Execute
            proxy = OperationServiceProxy(base_url)
            result = await proxy.get_operation(operation_id)

            # Verify
            assert result == mock_response_data
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert operation_id in str(call_args)
            await proxy.close()

    async def test_get_operation_with_force_refresh(self):
        """Test GET operation includes force_refresh query param."""
        base_url = "http://localhost:5002"
        operation_id = "op_training_123"

        mock_response_data = {"operation_id": operation_id, "status": "running"}
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        # Patch httpx.AsyncClient.get
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            # Execute
            proxy = OperationServiceProxy(base_url)
            result = await proxy.get_operation(operation_id, force_refresh=True)

            # Verify
            assert result == mock_response_data
            mock_get.assert_called_once()
            # Verify params include force_refresh
            call_args = mock_get.call_args
            assert call_args.kwargs.get("params", {}).get("force_refresh") is True
            await proxy.close()

    async def test_get_operation_404_raises_key_error(self):
        """Test 404 response raises KeyError."""
        base_url = "http://localhost:5002"
        operation_id = "op_nonexistent"

        # Mock 404 response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.json.return_value = {"error": "Operation not found"}

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            # Execute and verify
            proxy = OperationServiceProxy(base_url)
            with pytest.raises(KeyError, match=operation_id):
                await proxy.get_operation(operation_id)
            await proxy.close()

    async def test_get_operation_connection_error(self):
        """Test connection error is raised."""
        base_url = "http://localhost:5002"
        operation_id = "op_training_123"

        # Mock connection error
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection refused")

            # Execute and verify
            proxy = OperationServiceProxy(base_url)
            with pytest.raises(httpx.ConnectError):
                await proxy.get_operation(operation_id)
            await proxy.close()

    async def test_get_operation_timeout_error(self):
        """Test timeout error is raised."""
        base_url = "http://localhost:5002"
        operation_id = "op_training_123"

        # Mock timeout
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.TimeoutException("Request timeout")

            # Execute and verify
            proxy = OperationServiceProxy(base_url)
            with pytest.raises(httpx.TimeoutException):
                await proxy.get_operation(operation_id)
            await proxy.close()


@pytest.mark.asyncio
class TestGetMetrics:
    """Test get_metrics method."""

    async def test_successful_get_metrics(self):
        """Test successful GET metrics request."""
        base_url = "http://localhost:5002"
        operation_id = "op_training_123"

        # Mock response
        mock_response_data = {
            "metrics": [
                {"epoch": 0, "train_loss": 2.5, "val_loss": 2.7},
                {"epoch": 1, "train_loss": 2.3, "val_loss": 2.5},
            ],
            "new_cursor": 2,
        }
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            # Execute
            proxy = OperationServiceProxy(base_url)
            metrics, new_cursor = await proxy.get_metrics(operation_id)

            # Verify
            assert metrics == mock_response_data["metrics"]
            assert new_cursor == 2
            mock_get.assert_called_once()
            await proxy.close()

    async def test_get_metrics_with_cursor(self):
        """Test GET metrics includes cursor query param."""
        base_url = "http://localhost:5002"
        operation_id = "op_training_123"

        mock_response_data = {
            "metrics": [{"epoch": 5, "train_loss": 1.8}],
            "new_cursor": 6,
        }
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            # Execute
            proxy = OperationServiceProxy(base_url)
            metrics, new_cursor = await proxy.get_metrics(operation_id, cursor=5)

            # Verify
            assert metrics == mock_response_data["metrics"]
            assert new_cursor == 6
            # Verify cursor param was passed
            call_args = mock_get.call_args
            assert call_args.kwargs.get("params", {}).get("cursor") == 5
            await proxy.close()

    async def test_get_metrics_404_raises_key_error(self):
        """Test 404 response raises KeyError."""
        base_url = "http://localhost:5002"
        operation_id = "op_nonexistent"

        # Mock 404
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.json.return_value = {"error": "Operation not found"}

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            # Execute and verify
            proxy = OperationServiceProxy(base_url)
            with pytest.raises(KeyError, match=operation_id):
                await proxy.get_metrics(operation_id)
            await proxy.close()


@pytest.mark.asyncio
class TestContextManager:
    """Test async context manager protocol."""

    async def test_context_manager_usage(self):
        """Test proxy works as async context manager."""
        async with OperationServiceProxy("http://localhost:5002") as proxy:
            assert proxy.base_url == "http://localhost:5002"
            # Client should be initialized
            assert proxy._client is not None

    async def test_context_manager_cleanup(self):
        """Test context manager properly closes HTTP client."""
        base_url = "http://localhost:5002"
        client = None

        # Use context manager
        async with OperationServiceProxy(base_url) as proxy:
            client = proxy._client
            assert client is not None

        # After exit, client should be closed
        assert client.is_closed


@pytest.mark.asyncio
class TestClose:
    """Test close method."""

    async def test_close_cleanup(self):
        """Test close properly cleans up HTTP client."""
        proxy = OperationServiceProxy("http://localhost:5002")

        # Initialize client by calling a method (will be created lazily)
        # For now just close without using it
        await proxy.close()

        # Client should be None or closed
        assert proxy._client is None or proxy._client.is_closed

    async def test_close_idempotent(self):
        """Test close can be called multiple times safely."""
        proxy = OperationServiceProxy("http://localhost:5002")

        # Multiple closes should not raise
        await proxy.close()
        await proxy.close()
        await proxy.close()
