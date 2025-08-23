"""Tests for AsyncCLIClient base class."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from ktrdr.cli.async_cli_client import AsyncCLIClient, AsyncCLIClientError
from ktrdr.config.settings import CLISettings


class TestAsyncCLIClient:
    """Test suite for AsyncCLIClient base class."""

    @pytest.fixture(autouse=True)
    def mock_cli_settings(self):
        """Mock CLI settings for all tests automatically."""
        settings = CLISettings(
            api_base_url="http://localhost:8000",
            timeout=30.0,
            max_retries=3,
            retry_delay=0.1,  # Fast retries for tests
        )
        with patch(
            "ktrdr.cli.async_cli_client.get_cli_settings", return_value=settings
        ):
            yield settings

    @pytest.fixture
    def cli_config(self):
        """Base configuration for CLI instance."""
        return {
            "base_url": "http://localhost:8000",
            "timeout": 30.0,
            "max_retries": 3,
            "retry_delay": 0.1,  # Fast retries for tests
        }

    @pytest.fixture
    async def cli_instance(self, cli_config):
        """Create CLI instance for testing."""
        cli = AsyncCLIClient(**cli_config)
        yield cli
        # Cleanup
        if hasattr(cli, "_http_client") and cli._http_client:
            await cli._http_client.aclose()

    @pytest.mark.asyncio
    async def test_context_manager_lifecycle(self, cli_config):
        """Test proper async context manager lifecycle."""
        async with AsyncCLIClient(**cli_config) as cli:
            # Client should be created on enter
            assert cli._http_client is not None
            assert isinstance(cli._http_client, httpx.AsyncClient)

            # Client should be usable
            assert not cli._http_client.is_closed

        # Client should be closed on exit
        assert cli._http_client.is_closed

    @pytest.mark.asyncio
    async def test_connection_reuse(self, cli_config):
        """Test that HTTP client is reused across requests."""
        async with AsyncCLIClient(**cli_config) as cli:
            initial_client = cli._http_client

            # Mock the client's request method
            with patch.object(
                initial_client, "request", new_callable=AsyncMock
            ) as mock_request:
                mock_request.return_value.status_code = 200
                mock_request.return_value.json.return_value = {"success": True}

                # Make multiple requests
                await cli._make_request("GET", "/test1")
                await cli._make_request("GET", "/test2")

                # Same client should be used
                assert cli._http_client is initial_client
                assert mock_request.call_count == 2

    @pytest.mark.asyncio
    async def test_proper_error_handling(self, cli_config):
        """Test proper error handling and resource cleanup."""
        async with AsyncCLIClient(**cli_config) as cli:
            with patch.object(
                cli._http_client,
                "request",
                side_effect=httpx.ConnectError("Connection failed"),
            ):
                with pytest.raises(AsyncCLIClientError) as exc_info:
                    await cli._make_request("GET", "/test", retries=0)

                error = exc_info.value
                assert "Could not connect to API server" in error.message
                assert error.error_code == "CLI-ConnectionError"

    @pytest.mark.asyncio
    async def test_timeout_handling(self, cli_config):
        """Test timeout handling."""
        async with AsyncCLIClient(**cli_config) as cli:
            with patch.object(
                cli._http_client,
                "request",
                side_effect=httpx.TimeoutException("Timeout"),
            ):
                with pytest.raises(AsyncCLIClientError) as exc_info:
                    await cli._make_request("GET", "/test", timeout=1.0, retries=0)

                error = exc_info.value
                assert "Request timed out" in error.message
                assert error.error_code == "CLI-TimeoutError"

    @pytest.mark.asyncio
    async def test_retry_logic(self, cli_config):
        """Test retry logic for server errors."""
        async with AsyncCLIClient(**cli_config) as cli:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Server Error"
            mock_response.json.return_value = {"message": "Server Error"}

            with patch.object(
                cli._http_client,
                "request",
                new_callable=AsyncMock,
                return_value=mock_response,
            ) as mock_request:
                with pytest.raises(AsyncCLIClientError) as exc_info:
                    await cli._make_request("GET", "/test", retries=2)

                # Should have made 3 attempts (initial + 2 retries)
                assert mock_request.call_count == 3

                error = exc_info.value
                assert "API server error" in error.message
                assert error.error_code == "CLI-ServerError-500"

    @pytest.mark.asyncio
    async def test_successful_request(self, cli_config):
        """Test successful request handling."""
        async with AsyncCLIClient(**cli_config) as cli:
            expected_data = {"success": True, "data": {"test": "value"}}

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = expected_data

            with patch.object(cli._http_client, "request", return_value=mock_response):
                result = await cli._make_request("GET", "/test")

                assert result == expected_data

    @pytest.mark.asyncio
    async def test_client_error_no_retry(self, cli_config):
        """Test that client errors (4xx) don't trigger retries."""
        async with AsyncCLIClient(**cli_config) as cli:
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.json.return_value = {"message": "Bad Request"}

            with patch.object(
                cli._http_client,
                "request",
                new_callable=AsyncMock,
                return_value=mock_response,
            ) as mock_request:
                with pytest.raises(AsyncCLIClientError) as exc_info:
                    await cli._make_request("GET", "/test", retries=3)

                # Should only make 1 attempt for client errors
                assert mock_request.call_count == 1

                error = exc_info.value
                assert "API request failed" in error.message
                assert error.error_code == "CLI-400"

    @pytest.mark.asyncio
    async def test_configuration_injection(self, cli_config):
        """Test configuration is properly injected."""
        custom_timeout = 60.0
        custom_retries = 5

        cli_config.update(
            {
                "timeout": custom_timeout,
                "max_retries": custom_retries,
            }
        )

        async with AsyncCLIClient(**cli_config) as cli:
            assert cli.timeout == custom_timeout
            assert cli.max_retries == custom_retries
            assert cli.base_url == "http://localhost:8000"

    @pytest.mark.asyncio
    async def test_configuration_defaults_from_settings(self):
        """Test that configuration defaults come from settings when no overrides provided."""
        # Create a custom settings mock for this test
        custom_settings = CLISettings(
            api_base_url="http://custom-api:9999",
            timeout=45.0,
            max_retries=5,
            retry_delay=2.0,
        )

        with patch(
            "ktrdr.cli.async_cli_client.get_cli_settings", return_value=custom_settings
        ):
            # Don't provide any overrides - should use settings defaults
            cli = AsyncCLIClient()

            assert cli.base_url == "http://custom-api:9999"
            assert cli.timeout == 45.0
            assert cli.max_retries == 5
            assert cli.retry_delay == 2.0

    @pytest.mark.asyncio
    async def test_configuration_overrides(self):
        """Test that explicit parameters override configuration defaults."""
        # Create a custom settings mock
        custom_settings = CLISettings(
            api_base_url="http://config-api:8888",
            timeout=60.0,
            max_retries=10,
            retry_delay=3.0,
        )

        with patch(
            "ktrdr.cli.async_cli_client.get_cli_settings", return_value=custom_settings
        ):
            # Override some values explicitly
            cli = AsyncCLIClient(
                base_url="http://override-api:7777",
                timeout=15.0,
                # max_retries not provided - should use config default
                retry_delay=0.5,
            )

            # Overridden values should be used
            assert cli.base_url == "http://override-api:7777"
            assert cli.timeout == 15.0
            assert cli.retry_delay == 0.5

            # Non-overridden value should use config default
            assert cli.max_retries == 10

    @pytest.mark.asyncio
    async def test_thread_safety(self, cli_config):
        """Test thread-safe operation."""
        async with AsyncCLIClient(**cli_config) as cli:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"success": True}

            with patch.object(cli._http_client, "request", return_value=mock_response):
                # Make concurrent requests
                tasks = [cli._make_request("GET", f"/test{i}") for i in range(10)]

                results = await asyncio.gather(*tasks)

                # All requests should succeed
                assert len(results) == 10
                assert all(result["success"] for result in results)

    @pytest.mark.asyncio
    async def test_custom_parameters_per_request(self, cli_config):
        """Test custom timeout and retries per request."""
        async with AsyncCLIClient(**cli_config) as cli:
            custom_timeout = 5.0
            custom_retries = 1

            with patch.object(
                cli._http_client,
                "request",
                side_effect=httpx.TimeoutException("Timeout"),
            ) as mock_request:
                with pytest.raises(AsyncCLIClientError):
                    await cli._make_request(
                        "GET", "/test", timeout=custom_timeout, retries=custom_retries
                    )

                # Should retry custom_retries + 1 times
                assert mock_request.call_count == custom_retries + 1

    @pytest.mark.asyncio
    async def test_resource_cleanup_on_exception(self, cli_config):
        """Test proper resource cleanup when exception occurs in context manager."""
        cli = None
        try:
            async with AsyncCLIClient(**cli_config) as instance:
                cli = instance
                assert cli._http_client is not None
                assert not cli._http_client.is_closed

                # Simulate exception
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Client should still be closed even after exception
        assert cli._http_client.is_closed

    def test_synchronous_usage_not_allowed(self, cli_config):
        """Test that synchronous usage raises appropriate error."""
        cli = AsyncCLIClient(**cli_config)

        # Attempting to use without async context should fail
        with pytest.raises(AsyncCLIClientError) as exc_info:
            # This should not be allowed
            asyncio.run(cli._make_request("GET", "/test"))

        error = exc_info.value
        assert "not properly initialized" in error.message.lower()

    @pytest.mark.asyncio
    async def test_url_construction(self, cli_config):
        """Test proper URL construction."""
        async with AsyncCLIClient(**cli_config) as cli:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"success": True}

            with patch.object(
                cli._http_client, "request", return_value=mock_response
            ) as mock_request:
                await cli._make_request("GET", "/api/v1/test")

                # Check the URL was constructed correctly
                call_args = mock_request.call_args
                assert call_args[1]["url"] == "http://localhost:8000/api/v1/test"

    @pytest.mark.asyncio
    async def test_json_payload_handling(self, cli_config):
        """Test JSON payload is properly handled."""
        async with AsyncCLIClient(**cli_config) as cli:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"success": True}

            test_payload = {"key": "value", "number": 42}

            with patch.object(
                cli._http_client, "request", return_value=mock_response
            ) as mock_request:
                await cli._make_request("POST", "/test", json_data=test_payload)

                # Check JSON payload was passed correctly
                call_args = mock_request.call_args
                assert call_args[1]["json"] == test_payload

    @pytest.mark.asyncio
    async def test_query_parameters_handling(self, cli_config):
        """Test query parameters are properly handled."""
        async with AsyncCLIClient(**cli_config) as cli:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"success": True}

            test_params = {"param1": "value1", "param2": "value2"}

            with patch.object(
                cli._http_client, "request", return_value=mock_response
            ) as mock_request:
                await cli._make_request("GET", "/test", params=test_params)

                # Check params were passed correctly
                call_args = mock_request.call_args
                assert call_args[1]["params"] == test_params
