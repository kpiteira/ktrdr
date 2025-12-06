"""Unit tests for backtest worker self-registration."""

import os
from unittest.mock import AsyncMock, patch

import pytest

from ktrdr.backtesting.worker_registration import WorkerRegistration


class TestWorkerRegistration:
    """Tests for WorkerRegistration class."""

    def test_init_from_environment(self):
        """Test initialization from environment variables."""
        with patch.dict(
            os.environ,
            {
                "WORKER_ID": "backtest-1",
                "WORKER_PORT": "5003",
                "KTRDR_API_URL": "http://backend:8000",
            },
        ):
            registration = WorkerRegistration()

            assert registration.worker_id == "backtest-1"
            assert registration.worker_type == "backtesting"
            assert registration.port == 5003
            assert registration.backend_url == "http://backend:8000"

    def test_init_uses_defaults(self):
        """Test initialization with default values."""
        with patch.dict(
            os.environ, {"KTRDR_API_URL": "http://backend:8000"}, clear=True
        ):
            with patch(
                "ktrdr.backtesting.worker_registration.socket.gethostname",
                return_value="container-abc123",
            ):
                registration = WorkerRegistration()

                assert registration.worker_id == "backtest-container-abc123"
                assert registration.worker_type == "backtesting"
                assert registration.port == 5003
                assert registration.backend_url == "http://backend:8000"

    def test_get_endpoint_url_with_hostname(self):
        """Test endpoint URL construction using hostname as fallback."""
        with patch.dict(
            os.environ,
            {"WORKER_ID": "backtest-1", "KTRDR_API_URL": "http://backend:8000"},
        ):
            with patch(
                "ktrdr.backtesting.worker_registration.socket.gethostname",
                return_value="worker-host",
            ):
                registration = WorkerRegistration()
                # Mock _detect_ip_address to return None so it falls back to hostname
                with patch.object(
                    registration, "_detect_ip_address", return_value=None
                ):
                    endpoint_url = registration.get_endpoint_url()

                    assert endpoint_url == "http://worker-host:5003"

    def test_get_endpoint_url_with_ip_detection(self):
        """Test endpoint URL construction using auto-detected IP address."""
        with patch.dict(
            os.environ,
            {"WORKER_ID": "backtest-1", "KTRDR_API_URL": "http://backend:8000"},
        ):
            registration = WorkerRegistration()
            # Mock _detect_ip_address to return a specific IP
            with patch.object(
                registration, "_detect_ip_address", return_value="192.168.1.100"
            ):
                endpoint_url = registration.get_endpoint_url()

                assert endpoint_url == "http://192.168.1.100:5003"

    def test_get_endpoint_url_with_explicit_env(self):
        """Test endpoint URL from WORKER_ENDPOINT_URL env var takes precedence."""
        with patch.dict(
            os.environ,
            {
                "WORKER_ID": "backtest-1",
                "KTRDR_API_URL": "http://backend:8000",
                "WORKER_ENDPOINT_URL": "http://explicit-url:5003",
            },
        ):
            registration = WorkerRegistration()
            endpoint_url = registration.get_endpoint_url()

            # Explicit env var takes precedence over everything
            assert endpoint_url == "http://explicit-url:5003"

    def test_get_capabilities_default(self):
        """Test getting default capabilities."""
        with patch.dict(
            os.environ, {"KTRDR_API_URL": "http://backend:8000"}, clear=False
        ):
            registration = WorkerRegistration()
            capabilities = registration.get_capabilities()

            # Should have basic capabilities
            assert "cores" in capabilities
            assert "memory_gb" in capabilities
            assert isinstance(capabilities["cores"], int)
            assert isinstance(capabilities["memory_gb"], (int, float))

    @pytest.mark.asyncio
    async def test_register_success(self):
        """Test successful worker registration."""
        with patch.dict(
            os.environ,
            {"WORKER_ID": "backtest-1", "KTRDR_API_URL": "http://backend:8000"},
        ):
            registration = WorkerRegistration()

            # Mock the HTTP client
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "worker_id": "backtest-1",
                "worker_type": "backtesting",
                "status": "available",
            }

            with patch("httpx.AsyncClient.post", return_value=mock_response):
                result = await registration.register()

                assert result is True

    @pytest.mark.asyncio
    async def test_register_handles_connection_error(self):
        """Test registration handles connection errors gracefully."""
        with patch.dict(
            os.environ,
            {"WORKER_ID": "backtest-1", "KTRDR_API_URL": "http://backend:8000"},
        ):
            registration = WorkerRegistration()

            # Mock connection error
            with patch(
                "httpx.AsyncClient.post", side_effect=Exception("Connection refused")
            ):
                result = await registration.register()

                assert result is False

    @pytest.mark.asyncio
    async def test_register_retries_on_failure(self):
        """Test registration retries on failure."""
        with patch.dict(
            os.environ,
            {"WORKER_ID": "backtest-1", "KTRDR_API_URL": "http://backend:8000"},
        ):
            registration = WorkerRegistration(max_retries=3, retry_delay=0.1)

            call_count = 0

            async def mock_post(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    raise Exception("Connection error")
                # Success on 3rd try
                mock_response = AsyncMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"worker_id": "backtest-1"}
                return mock_response

            with patch("httpx.AsyncClient.post", side_effect=mock_post):
                result = await registration.register()

                assert result is True
                assert call_count == 3

    @pytest.mark.asyncio
    async def test_register_gives_up_after_max_retries(self):
        """Test registration gives up after max retries."""
        with patch.dict(
            os.environ,
            {"WORKER_ID": "backtest-1", "KTRDR_API_URL": "http://backend:8000"},
        ):
            registration = WorkerRegistration(max_retries=2, retry_delay=0.1)

            # Always fail
            with patch(
                "httpx.AsyncClient.post", side_effect=Exception("Connection error")
            ):
                result = await registration.register()

                assert result is False
