"""Tests for WorkerAPIBase graceful shutdown (M6 Task 6.1)."""

import asyncio
import signal
from unittest.mock import MagicMock, patch

import pytest

from ktrdr.api.models.operations import OperationType
from ktrdr.api.models.workers import WorkerType
from ktrdr.workers.base import WorkerAPIBase


class MockWorker(WorkerAPIBase):
    """Mock worker for testing shutdown functionality."""

    def __init__(self):
        super().__init__(
            worker_type=WorkerType.BACKTESTING,
            operation_type=OperationType.BACKTESTING,
            worker_port=5003,
            backend_url="http://backend:8000",
        )


class TestShutdownEventInitialization:
    """Tests for shutdown event initialization (Task 6.1)."""

    def test_shutdown_event_initialized(self):
        """Test _shutdown_event is initialized as asyncio.Event."""
        worker = MockWorker()
        assert hasattr(worker, "_shutdown_event")
        assert isinstance(worker._shutdown_event, asyncio.Event)

    def test_shutdown_event_not_set_initially(self):
        """Test _shutdown_event is not set on initialization."""
        worker = MockWorker()
        assert not worker._shutdown_event.is_set()

    def test_shutdown_timeout_initialized(self):
        """Test _shutdown_timeout is initialized to 25 seconds."""
        worker = MockWorker()
        assert hasattr(worker, "_shutdown_timeout")
        assert worker._shutdown_timeout == 25


class TestSetupSignalHandlers:
    """Tests for signal handler setup (Task 6.1)."""

    def test_setup_signal_handlers_method_exists(self):
        """Test _setup_signal_handlers method exists."""
        worker = MockWorker()
        assert hasattr(worker, "_setup_signal_handlers")
        assert callable(worker._setup_signal_handlers)

    @patch("signal.signal")
    def test_sigterm_handler_registered(self, mock_signal):
        """Test SIGTERM handler is registered when _setup_signal_handlers called."""
        worker = MockWorker()
        worker._setup_signal_handlers()

        # Verify signal.signal was called with SIGTERM
        mock_signal.assert_called_once()
        args = mock_signal.call_args[0]
        assert args[0] == signal.SIGTERM
        # Second arg should be a callable (the handler)
        assert callable(args[1])


class TestSigtermHandler:
    """Tests for SIGTERM handler behavior (Task 6.1)."""

    def test_sigterm_handler_sets_shutdown_event(self):
        """Test that receiving SIGTERM sets the shutdown event."""
        worker = MockWorker()

        # Mock the event loop - captured during _setup_signal_handlers
        mock_loop = MagicMock()
        with patch("asyncio.get_running_loop", return_value=mock_loop):
            with patch("signal.signal") as mock_signal:
                worker._setup_signal_handlers()
                handler = mock_signal.call_args[0][1]

        # Call the handler (simulating SIGTERM) - loop was captured during setup
        handler(signal.SIGTERM, None)

        # Verify call_soon_threadsafe was called to set the event
        mock_loop.call_soon_threadsafe.assert_called_once()
        # The argument should be _shutdown_event.set
        assert (
            mock_loop.call_soon_threadsafe.call_args[0][0] == worker._shutdown_event.set
        )

    @patch("ktrdr.workers.base.logger")
    def test_sigterm_handler_logs_message(self, mock_logger):
        """Test that SIGTERM handler logs when signal received."""
        worker = MockWorker()

        # Mock the event loop - captured during _setup_signal_handlers
        mock_loop = MagicMock()
        with patch("asyncio.get_running_loop", return_value=mock_loop):
            with patch("signal.signal") as mock_signal:
                worker._setup_signal_handlers()
                handler = mock_signal.call_args[0][1]

        # Call the handler
        handler(signal.SIGTERM, None)

        # Verify logging
        mock_logger.info.assert_called()
        log_message = mock_logger.info.call_args[0][0]
        assert "SIGTERM" in log_message
        assert "graceful shutdown" in log_message.lower()


class TestWaitForShutdown:
    """Tests for wait_for_shutdown method (Task 6.1)."""

    def test_wait_for_shutdown_method_exists(self):
        """Test wait_for_shutdown method exists."""
        worker = MockWorker()
        assert hasattr(worker, "wait_for_shutdown")
        assert asyncio.iscoroutinefunction(worker.wait_for_shutdown)

    @pytest.mark.asyncio
    async def test_wait_for_shutdown_returns_true_when_signaled(self):
        """Test wait_for_shutdown returns True when shutdown event is set."""
        worker = MockWorker()

        # Set the event immediately
        worker._shutdown_event.set()

        result = await worker.wait_for_shutdown()
        assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_shutdown_returns_false_on_timeout(self):
        """Test wait_for_shutdown returns False when timeout expires."""
        worker = MockWorker()
        # Use a very short timeout for test
        worker._shutdown_timeout = 0.01  # 10ms

        result = await worker.wait_for_shutdown()
        assert result is False

    @pytest.mark.asyncio
    async def test_wait_for_shutdown_uses_configured_timeout(self):
        """Test wait_for_shutdown uses _shutdown_timeout value."""
        worker = MockWorker()
        worker._shutdown_timeout = 0.05  # 50ms

        # Event not set, should timeout
        import time

        start = time.time()
        result = await worker.wait_for_shutdown()
        elapsed = time.time() - start

        assert result is False
        # Should have waited approximately the timeout duration
        assert elapsed >= 0.04  # Allow some tolerance
        assert elapsed < 0.2  # But not too long


class TestSignalHandlerRegistrationOnStartup:
    """Tests for signal handler registration during startup (Task 6.1)."""

    @patch.object(WorkerAPIBase, "_setup_signal_handlers")
    def test_signal_handlers_registered_on_startup(self, mock_setup):
        """Test that _setup_signal_handlers is called during worker startup."""
        # This test verifies the startup event calls _setup_signal_handlers
        # We need to trigger the startup event
        from fastapi.testclient import TestClient

        worker = MockWorker()
        # Using TestClient triggers startup events
        with TestClient(worker.app):
            pass

        # Verify _setup_signal_handlers was called
        mock_setup.assert_called_once()

    @patch("signal.signal")
    @patch("ktrdr.workers.base.logger")
    def test_signal_handler_registration_logged(self, mock_logger, mock_signal):
        """Test that signal handler registration is logged."""
        worker = MockWorker()
        worker._setup_signal_handlers()

        # Check for registration log message
        log_calls = [call[0][0] for call in mock_logger.info.call_args_list]
        registration_logged = any(
            "SIGTERM handler registered" in msg for msg in log_calls
        )
        assert registration_logged, f"Expected registration log, got: {log_calls}"
