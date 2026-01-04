"""Unit tests for AsyncCLIClient."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from ktrdr.cli.client.async_client import AsyncCLIClient
from ktrdr.cli.client.errors import APIError, ConnectionError, TimeoutError


class TestAsyncCLIClientContextManager:
    """Tests for async context manager lifecycle."""

    @pytest.mark.asyncio
    @patch("ktrdr.cli.client.async_client.resolve_url")
    @patch("ktrdr.cli.client.async_client.httpx.AsyncClient")
    async def test_aenter_creates_client(self, mock_client_class, mock_resolve):
        """__aenter__ creates httpx.AsyncClient instance."""
        mock_resolve.return_value = "http://localhost:8000/api/v1"
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client

        async with AsyncCLIClient() as client:
            assert client._client is mock_client
            mock_client_class.assert_called_once()

    @pytest.mark.asyncio
    @patch("ktrdr.cli.client.async_client.resolve_url")
    @patch("ktrdr.cli.client.async_client.httpx.AsyncClient")
    async def test_aexit_closes_client(self, mock_client_class, mock_resolve):
        """__aexit__ closes the httpx.AsyncClient."""
        mock_resolve.return_value = "http://localhost:8000/api/v1"
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client

        async with AsyncCLIClient():
            pass

        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    @patch("ktrdr.cli.client.async_client.resolve_url")
    @patch("ktrdr.cli.client.async_client.httpx.AsyncClient")
    async def test_client_is_none_after_exit(self, mock_client_class, mock_resolve):
        """Client reference is cleared after exit."""
        mock_resolve.return_value = "http://localhost:8000/api/v1"
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client

        client = AsyncCLIClient()
        async with client:
            assert client._client is not None
        assert client._client is None

    @pytest.mark.asyncio
    @patch("ktrdr.cli.client.async_client.resolve_url")
    @patch("ktrdr.cli.client.async_client.httpx.AsyncClient")
    async def test_uses_config_timeout(self, mock_client_class, mock_resolve):
        """Client is created with configured timeout."""
        mock_resolve.return_value = "http://localhost:8000/api/v1"
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client

        async with AsyncCLIClient(timeout=60.0):
            pass

        call_kwargs = mock_client_class.call_args.kwargs
        assert call_kwargs["timeout"] == 60.0

    @pytest.mark.asyncio
    @patch("ktrdr.cli.client.async_client.resolve_url")
    @patch("ktrdr.cli.client.async_client.httpx.AsyncClient")
    async def test_uses_resolved_url(self, mock_client_class, mock_resolve):
        """Client uses resolved base URL."""
        mock_resolve.return_value = "http://custom:9000/api/v1"
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client

        async with AsyncCLIClient() as client:
            assert client.config.base_url == "http://custom:9000/api/v1"


class TestAsyncCLIClientHTTPMethods:
    """Tests for HTTP method dispatch."""

    @pytest.mark.asyncio
    @patch("ktrdr.cli.client.async_client.resolve_url")
    @patch("ktrdr.cli.client.async_client.httpx.AsyncClient")
    async def test_get_calls_correct_method(self, mock_client_class, mock_resolve):
        """get() dispatches to HTTP GET."""
        mock_resolve.return_value = "http://localhost:8000/api/v1"
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "value"}
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client

        async with AsyncCLIClient() as client:
            result = await client.get("/test")

        mock_client.request.assert_called_once()
        call_kwargs = mock_client.request.call_args.kwargs
        assert call_kwargs["method"] == "GET"
        assert "/test" in call_kwargs["url"]
        assert result == {"data": "value"}

    @pytest.mark.asyncio
    @patch("ktrdr.cli.client.async_client.resolve_url")
    @patch("ktrdr.cli.client.async_client.httpx.AsyncClient")
    async def test_post_calls_correct_method(self, mock_client_class, mock_resolve):
        """post() dispatches to HTTP POST."""
        mock_resolve.return_value = "http://localhost:8000/api/v1"
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client

        async with AsyncCLIClient() as client:
            result = await client.post("/test", json={"key": "value"})

        mock_client.request.assert_called_once()
        call_kwargs = mock_client.request.call_args.kwargs
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["json"] == {"key": "value"}
        assert result == {"success": True}

    @pytest.mark.asyncio
    @patch("ktrdr.cli.client.async_client.resolve_url")
    @patch("ktrdr.cli.client.async_client.httpx.AsyncClient")
    async def test_delete_calls_correct_method(self, mock_client_class, mock_resolve):
        """delete() dispatches to HTTP DELETE."""
        mock_resolve.return_value = "http://localhost:8000/api/v1"
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"deleted": True}
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client

        async with AsyncCLIClient() as client:
            result = await client.delete("/test/123")

        mock_client.request.assert_called_once()
        call_kwargs = mock_client.request.call_args.kwargs
        assert call_kwargs["method"] == "DELETE"
        assert result == {"deleted": True}

    @pytest.mark.asyncio
    @patch("ktrdr.cli.client.async_client.resolve_url")
    @patch("ktrdr.cli.client.async_client.httpx.AsyncClient")
    async def test_get_passes_params(self, mock_client_class, mock_resolve):
        """get() passes query parameters."""
        mock_resolve.return_value = "http://localhost:8000/api/v1"
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client

        async with AsyncCLIClient() as client:
            await client.get("/test", params={"limit": 10})

        call_kwargs = mock_client.request.call_args.kwargs
        assert call_kwargs["params"] == {"limit": 10}


class TestAsyncCLIClientRetryBehavior:
    """Tests for retry behavior."""

    @pytest.mark.asyncio
    @patch("ktrdr.cli.client.async_client.resolve_url")
    @patch("ktrdr.cli.client.async_client.httpx.AsyncClient")
    @patch("ktrdr.cli.client.async_client.calculate_backoff")
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_retries_on_5xx(
        self, mock_sleep, mock_backoff, mock_client_class, mock_resolve
    ):
        """Retries request on 5xx server errors."""
        mock_resolve.return_value = "http://localhost:8000/api/v1"
        mock_backoff.return_value = 0.1
        mock_client = AsyncMock()

        # First call fails with 500, second succeeds
        response_500 = MagicMock()
        response_500.status_code = 500
        response_500.json.return_value = {"detail": "Server error"}

        response_200 = MagicMock()
        response_200.status_code = 200
        response_200.json.return_value = {"success": True}

        mock_client.request.side_effect = [response_500, response_200]
        mock_client_class.return_value = mock_client

        async with AsyncCLIClient(max_retries=3) as client:
            result = await client.get("/test")

        assert mock_client.request.call_count == 2
        assert result == {"success": True}
        mock_sleep.assert_called_once()

    @pytest.mark.asyncio
    @patch("ktrdr.cli.client.async_client.resolve_url")
    @patch("ktrdr.cli.client.async_client.httpx.AsyncClient")
    async def test_no_retry_on_4xx(self, mock_client_class, mock_resolve):
        """Does not retry on 4xx client errors."""
        mock_resolve.return_value = "http://localhost:8000/api/v1"
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"detail": "Not found"}
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client

        async with AsyncCLIClient(max_retries=3) as client:
            with pytest.raises(APIError) as exc_info:
                await client.get("/test")

        # Should only try once (no retries)
        assert mock_client.request.call_count == 1
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    @patch("ktrdr.cli.client.async_client.resolve_url")
    @patch("ktrdr.cli.client.async_client.httpx.AsyncClient")
    @patch("ktrdr.cli.client.async_client.calculate_backoff")
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_raises_after_max_retries(
        self, mock_sleep, mock_backoff, mock_client_class, mock_resolve
    ):
        """Raises APIError after all retries exhausted."""
        mock_resolve.return_value = "http://localhost:8000/api/v1"
        mock_backoff.return_value = 0.1
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"detail": "Server error"}
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client

        async with AsyncCLIClient(max_retries=2) as client:
            with pytest.raises(APIError) as exc_info:
                await client.get("/test")

        # Initial attempt + 2 retries = 3 total
        assert mock_client.request.call_count == 3
        assert exc_info.value.status_code == 500


class TestAsyncCLIClientErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    @patch("ktrdr.cli.client.async_client.resolve_url")
    @patch("ktrdr.cli.client.async_client.httpx.AsyncClient")
    async def test_raises_connection_error(self, mock_client_class, mock_resolve):
        """Raises ConnectionError on connection failure."""
        mock_resolve.return_value = "http://localhost:8000/api/v1"
        mock_client = AsyncMock()
        mock_client.request.side_effect = httpx.ConnectError("Connection refused")
        mock_client_class.return_value = mock_client

        async with AsyncCLIClient(max_retries=0) as client:
            with pytest.raises(ConnectionError) as exc_info:
                await client.get("/test")

        assert "connect" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    @patch("ktrdr.cli.client.async_client.resolve_url")
    @patch("ktrdr.cli.client.async_client.httpx.AsyncClient")
    async def test_raises_timeout_error(self, mock_client_class, mock_resolve):
        """Raises TimeoutError on request timeout."""
        mock_resolve.return_value = "http://localhost:8000/api/v1"
        mock_client = AsyncMock()
        mock_client.request.side_effect = httpx.TimeoutException("Request timed out")
        mock_client_class.return_value = mock_client

        async with AsyncCLIClient(max_retries=0) as client:
            with pytest.raises(TimeoutError) as exc_info:
                await client.get("/test")

        assert "timed out" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    @patch("ktrdr.cli.client.async_client.resolve_url")
    @patch("ktrdr.cli.client.async_client.httpx.AsyncClient")
    async def test_raises_api_error_with_status_code(
        self, mock_client_class, mock_resolve
    ):
        """APIError includes status code."""
        mock_resolve.return_value = "http://localhost:8000/api/v1"
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"detail": "Bad request"}
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client

        async with AsyncCLIClient() as client:
            with pytest.raises(APIError) as exc_info:
                await client.get("/test")

        assert exc_info.value.status_code == 400
        assert "Bad request" in exc_info.value.message

    @pytest.mark.asyncio
    @patch("ktrdr.cli.client.async_client.resolve_url")
    @patch("ktrdr.cli.client.async_client.httpx.AsyncClient")
    @patch("ktrdr.cli.client.async_client.calculate_backoff")
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_retries_connection_errors(
        self, mock_sleep, mock_backoff, mock_client_class, mock_resolve
    ):
        """Retries on connection errors until max_retries exhausted."""
        mock_resolve.return_value = "http://localhost:8000/api/v1"
        mock_backoff.return_value = 0.1
        mock_client = AsyncMock()

        # First call fails, second succeeds
        response_200 = MagicMock()
        response_200.status_code = 200
        response_200.json.return_value = {"success": True}

        mock_client.request.side_effect = [
            httpx.ConnectError("Connection refused"),
            response_200,
        ]
        mock_client_class.return_value = mock_client

        async with AsyncCLIClient(max_retries=3) as client:
            result = await client.get("/test")

        assert mock_client.request.call_count == 2
        assert result == {"success": True}


class TestAsyncCLIClientHealthCheck:
    """Tests for health_check method."""

    @pytest.mark.asyncio
    @patch("ktrdr.cli.client.async_client.resolve_url")
    @patch("ktrdr.cli.client.async_client.httpx.AsyncClient")
    async def test_health_check_returns_true_on_success(
        self, mock_client_class, mock_resolve
    ):
        """health_check returns True when server responds."""
        mock_resolve.return_value = "http://localhost:8000/api/v1"
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client

        async with AsyncCLIClient() as client:
            result = await client.health_check()

        assert result is True

    @pytest.mark.asyncio
    @patch("ktrdr.cli.client.async_client.resolve_url")
    @patch("ktrdr.cli.client.async_client.httpx.AsyncClient")
    async def test_health_check_returns_false_on_error(
        self, mock_client_class, mock_resolve
    ):
        """health_check returns False when server unavailable."""
        mock_resolve.return_value = "http://localhost:8000/api/v1"
        mock_client = AsyncMock()
        mock_client.request.side_effect = httpx.ConnectError("Connection refused")
        mock_client_class.return_value = mock_client

        async with AsyncCLIClient() as client:
            result = await client.health_check()

        assert result is False

    @pytest.mark.asyncio
    @patch("ktrdr.cli.client.async_client.resolve_url")
    @patch("ktrdr.cli.client.async_client.httpx.AsyncClient")
    async def test_health_check_returns_false_on_server_error(
        self, mock_client_class, mock_resolve
    ):
        """health_check returns False on 5xx error."""
        mock_resolve.return_value = "http://localhost:8000/api/v1"
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"detail": "Server error"}
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client

        async with AsyncCLIClient() as client:
            result = await client.health_check()

        assert result is False

    @pytest.mark.asyncio
    @patch("ktrdr.cli.client.async_client.resolve_url")
    @patch("ktrdr.cli.client.async_client.httpx.AsyncClient")
    async def test_health_check_uses_short_timeout(
        self, mock_client_class, mock_resolve
    ):
        """health_check uses short timeout and no retries."""
        mock_resolve.return_value = "http://localhost:8000/api/v1"
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client

        async with AsyncCLIClient() as client:
            await client.health_check()

        # Should only try once (no retries for health check)
        assert mock_client.request.call_count == 1


class TestAsyncCLIClientConfiguration:
    """Tests for client configuration."""

    @patch("ktrdr.cli.client.async_client.resolve_url")
    def test_default_config_values(self, mock_resolve):
        """Client uses sensible defaults."""
        mock_resolve.return_value = "http://localhost:8000/api/v1"

        client = AsyncCLIClient()

        assert client.config.base_url == "http://localhost:8000/api/v1"
        assert client.config.timeout == 30.0
        assert client.config.max_retries == 3
        assert client.config.retry_delay == 1.0

    @patch("ktrdr.cli.client.async_client.resolve_url")
    def test_explicit_url_overrides_resolve(self, mock_resolve):
        """Explicit base_url parameter overrides resolution."""
        mock_resolve.return_value = "http://resolved:8000/api/v1"

        # When explicit URL is passed, it should be used directly
        AsyncCLIClient(base_url="http://explicit:9000/api/v1")

        # resolve_url should be called with the explicit URL
        mock_resolve.assert_called_with("http://explicit:9000/api/v1")

    @patch("ktrdr.cli.client.async_client.resolve_url")
    def test_custom_config_values(self, mock_resolve):
        """Client accepts custom configuration."""
        mock_resolve.return_value = "http://localhost:8000/api/v1"

        client = AsyncCLIClient(
            timeout=60.0,
            max_retries=5,
            retry_delay=2.0,
        )

        assert client.config.timeout == 60.0
        assert client.config.max_retries == 5
        assert client.config.retry_delay == 2.0


class TestAsyncCLIClientExecuteOperation:
    """Tests for execute_operation method."""

    @pytest.mark.asyncio
    @patch("ktrdr.cli.client.async_client.resolve_url")
    @patch("ktrdr.cli.client.async_client.httpx.AsyncClient")
    async def test_execute_operation_exists(self, mock_client_class, mock_resolve):
        """execute_operation method exists and is callable."""
        mock_resolve.return_value = "http://localhost:8000/api/v1"
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client

        async with AsyncCLIClient() as client:
            # Verify method exists and is async
            assert hasattr(client, "execute_operation")
            assert callable(client.execute_operation)

    @pytest.mark.asyncio
    @patch("ktrdr.cli.client.async_client.resolve_url")
    @patch("ktrdr.cli.client.async_client.httpx.AsyncClient")
    async def test_execute_operation_signature(self, mock_client_class, mock_resolve):
        """execute_operation accepts expected parameters."""
        mock_resolve.return_value = "http://localhost:8000/api/v1"
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client

        async with AsyncCLIClient() as client:
            # Test that method accepts adapter, on_progress, and poll_interval
            import inspect

            sig = inspect.signature(client.execute_operation)
            params = list(sig.parameters.keys())
            assert "adapter" in params
            assert "on_progress" in params
            assert "poll_interval" in params
