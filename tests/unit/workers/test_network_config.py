"""Unit tests for worker network configuration and IP detection."""

import socket
from unittest.mock import Mock, patch

import pytest

from ktrdr.backtesting.worker_registration import (
    WorkerRegistration as BacktestWorkerRegistration,
)
from ktrdr.training.worker_registration import (
    WorkerRegistration as TrainingWorkerRegistration,
)


class TestWorkerEndpointURLDiscovery:
    """Test worker endpoint URL discovery with IP detection."""

    def test_explicit_worker_endpoint_url_takes_priority(self, monkeypatch):
        """WORKER_ENDPOINT_URL environment variable should take highest priority."""
        explicit_url = "http://192.168.1.201:5003"
        monkeypatch.setenv("WORKER_ENDPOINT_URL", explicit_url)
        monkeypatch.setenv("KTRDR_API_URL", "http://backend:8000")

        registration = BacktestWorkerRegistration()
        endpoint_url = registration.get_endpoint_url()

        assert endpoint_url == explicit_url

    def test_auto_detect_ip_when_no_explicit_url(self, monkeypatch):
        """Should auto-detect IP address when WORKER_ENDPOINT_URL not set."""
        monkeypatch.delenv("WORKER_ENDPOINT_URL", raising=False)
        monkeypatch.setenv("KTRDR_API_URL", "http://192.168.1.100:8000")
        monkeypatch.setenv("WORKER_PORT", "5003")

        # Mock socket to return specific IP
        mock_socket = Mock()
        mock_socket.getsockname.return_value = ("192.168.1.201", 12345)

        with patch("socket.socket", return_value=mock_socket):
            registration = BacktestWorkerRegistration()
            endpoint_url = registration.get_endpoint_url()

            # Should use auto-detected IP
            assert endpoint_url.startswith("http://192.168.1.201:")
            assert ":5003" in endpoint_url

    def test_fallback_to_hostname_when_ip_detection_fails(self, monkeypatch):
        """Should fallback to hostname when IP detection fails."""
        monkeypatch.delenv("WORKER_ENDPOINT_URL", raising=False)
        monkeypatch.setenv("KTRDR_API_URL", "http://backend:8000")
        monkeypatch.setenv("WORKER_PORT", "5003")

        # Mock socket to raise exception (simulating network failure)
        with patch("socket.socket", side_effect=OSError("Network unreachable")):
            registration = BacktestWorkerRegistration()
            endpoint_url = registration.get_endpoint_url()

            # Should fallback to hostname
            hostname = socket.gethostname()
            assert endpoint_url == f"http://{hostname}:5003"

    def test_ip_detection_uses_backend_host_for_routing(self, monkeypatch):
        """IP detection should connect to backend host to discover correct route."""
        monkeypatch.delenv("WORKER_ENDPOINT_URL", raising=False)
        monkeypatch.setenv("KTRDR_API_URL", "http://192.168.1.100:8000")

        mock_socket = Mock()
        mock_socket.getsockname.return_value = ("192.168.1.201", 54321)

        with patch("socket.socket", return_value=mock_socket):
            registration = BacktestWorkerRegistration()
            registration.get_endpoint_url()

            # Should connect to backend host (192.168.1.100) on port 80
            mock_socket.connect.assert_called_once()
            call_args = mock_socket.connect.call_args
            assert call_args[0][0][0] == "192.168.1.100"  # Backend host
            assert call_args[0][0][1] == 80  # Dummy port for route discovery

    def test_training_worker_uses_same_ip_detection(self, monkeypatch):
        """Training workers should use same IP detection logic."""
        monkeypatch.delenv("WORKER_ENDPOINT_URL", raising=False)
        monkeypatch.setenv("KTRDR_API_URL", "http://192.168.1.100:8000")
        monkeypatch.setenv("WORKER_PORT", "5004")

        mock_socket = Mock()
        mock_socket.getsockname.return_value = ("192.168.1.211", 12345)

        with patch("socket.socket", return_value=mock_socket):
            registration = TrainingWorkerRegistration()
            endpoint_url = registration.get_endpoint_url()

            assert endpoint_url.startswith("http://192.168.1.211:")
            assert ":5004" in endpoint_url


class TestBackendURLValidation:
    """Test backend URL validation - must be explicitly configured."""

    def test_backend_url_required_for_backtesting(self, monkeypatch):
        """KTRDR_API_URL must be set - no defaults allowed."""
        monkeypatch.delenv("KTRDR_API_URL", raising=False)

        with pytest.raises(
            RuntimeError,
            match="KTRDR_API_URL environment variable is required",
        ):
            BacktestWorkerRegistration()

    def test_backend_url_required_for_training(self, monkeypatch):
        """KTRDR_API_URL must be set for training workers too."""
        monkeypatch.delenv("KTRDR_API_URL", raising=False)

        with pytest.raises(
            RuntimeError,
            match="KTRDR_API_URL environment variable is required",
        ):
            TrainingWorkerRegistration()

    def test_backend_url_explicit_value_accepted(self, monkeypatch):
        """Should accept explicit KTRDR_API_URL value."""
        backend_url = "http://192.168.1.100:8000"
        monkeypatch.setenv("KTRDR_API_URL", backend_url)

        registration = BacktestWorkerRegistration()
        assert registration.backend_url == backend_url

    def test_error_message_provides_example(self, monkeypatch):
        """Error message should provide helpful example."""
        monkeypatch.delenv("KTRDR_API_URL", raising=False)

        with pytest.raises(RuntimeError) as exc_info:
            BacktestWorkerRegistration()

        error_msg = str(exc_info.value)
        assert "KTRDR_API_URL" in error_msg
        assert "Example:" in error_msg or "example" in error_msg.lower()


class TestIPDetectionEdgeCases:
    """Test edge cases in IP detection logic."""

    def test_handles_ipv6_addresses(self, monkeypatch):
        """Should handle IPv6 addresses correctly."""
        monkeypatch.delenv("WORKER_ENDPOINT_URL", raising=False)
        monkeypatch.setenv("KTRDR_API_URL", "http://backend:8000")

        mock_socket = Mock()
        # IPv6 address format
        mock_socket.getsockname.return_value = ("fe80::1", 12345, 0, 0)

        with patch("socket.socket", return_value=mock_socket):
            registration = BacktestWorkerRegistration()
            endpoint_url = registration.get_endpoint_url()

            # Should handle IPv6 (even if just extracting first element)
            assert "fe80::1" in endpoint_url or socket.gethostname() in endpoint_url

    def test_handles_localhost_backend(self, monkeypatch):
        """Should handle localhost backend URL."""
        monkeypatch.delenv("WORKER_ENDPOINT_URL", raising=False)
        monkeypatch.setenv("KTRDR_API_URL", "http://localhost:8000")

        mock_socket = Mock()
        mock_socket.getsockname.return_value = ("127.0.0.1", 12345)

        with patch("socket.socket") as socket_mock:
            socket_mock.return_value.__enter__.return_value = mock_socket

            registration = BacktestWorkerRegistration()
            endpoint_url = registration.get_endpoint_url()

            # Should detect an IP or fall back to hostname
            assert endpoint_url.startswith("http://")

    def test_socket_properly_closed_after_detection(self, monkeypatch):
        """Socket should be properly closed after IP detection."""
        monkeypatch.delenv("WORKER_ENDPOINT_URL", raising=False)
        monkeypatch.setenv("KTRDR_API_URL", "http://192.168.1.100:8000")

        mock_socket = Mock()
        mock_socket.getsockname.return_value = ("192.168.1.201", 12345)

        with patch("socket.socket", return_value=mock_socket):
            registration = BacktestWorkerRegistration()
            registration.get_endpoint_url()

            # Socket should be closed explicitly
            mock_socket.close.assert_called()


class TestWorkerPortConfiguration:
    """Test worker port configuration."""

    def test_default_backtest_port(self, monkeypatch):
        """Backtest workers should default to port 5003."""
        monkeypatch.delenv("WORKER_PORT", raising=False)
        monkeypatch.setenv("KTRDR_API_URL", "http://backend:8000")

        registration = BacktestWorkerRegistration()
        assert registration.port == 5003

    def test_default_training_port(self, monkeypatch):
        """Training workers should default to port 5004."""
        monkeypatch.delenv("WORKER_PORT", raising=False)
        monkeypatch.setenv("KTRDR_API_URL", "http://backend:8000")

        registration = TrainingWorkerRegistration()
        assert registration.port == 5004

    def test_custom_port_via_env(self, monkeypatch):
        """Should respect WORKER_PORT environment variable."""
        monkeypatch.setenv("WORKER_PORT", "9999")
        monkeypatch.setenv("KTRDR_API_URL", "http://backend:8000")

        registration = BacktestWorkerRegistration()
        assert registration.port == 9999
