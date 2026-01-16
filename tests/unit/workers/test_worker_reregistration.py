"""Unit tests for worker re-registration monitor (M7.5 Task 7.5.1).

Tests the fix for the bug where the monitor would not check registration
if no health check had ever been received.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestReregistrationMonitor:
    """Tests for WorkerAPIBase re-registration monitor behavior."""

    @pytest.fixture
    def mock_worker(self):
        """Create a mock worker with the essential attributes."""
        from ktrdr.api.models.operations import OperationType
        from ktrdr.api.models.workers import WorkerType
        from ktrdr.workers.base import WorkerAPIBase

        # Patch the FastAPI app creation and other init side effects
        with patch.object(WorkerAPIBase, "__init__", lambda self: None):
            worker = WorkerAPIBase.__new__(WorkerAPIBase)

            # Set essential attributes
            worker.worker_type = WorkerType.BACKTESTING
            worker.operation_type = OperationType.BACKTESTING
            worker.worker_port = 5003
            worker.backend_url = "http://localhost:8000"
            worker.worker_id = "test-worker-1"
            worker._last_health_check_received = None
            worker._health_check_timeout = 30
            worker._reregistration_check_interval = 1  # Fast for testing
            worker._completed_operations = []
            worker._ensure_registered = AsyncMock()
            worker._operations_service = MagicMock()

            return worker

    @pytest.mark.asyncio
    async def test_monitor_checks_registration_when_no_health_check_received(
        self, mock_worker
    ):
        """
        Test that monitor checks registration even if no health check received.

        This tests the fix for the bug where _last_health_check_received = None
        caused the monitor to skip all checks indefinitely.
        """
        # _last_health_check_received is None (never received a health check)
        mock_worker._last_health_check_received = None

        # Run one iteration of the monitor loop
        # We'll cancel after a short delay to test just one iteration
        async def run_monitor_once():
            task = asyncio.create_task(mock_worker._monitor_health_checks())
            await asyncio.sleep(1.5)  # Wait for one check interval
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass  # Expected when cancelling the monitoring task

        await run_monitor_once()

        # _ensure_registered should have been called even without prior health check
        mock_worker._ensure_registered.assert_called()

    @pytest.mark.asyncio
    async def test_monitor_checks_registration_on_health_check_timeout(
        self, mock_worker
    ):
        """Test that monitor checks registration when health check times out."""
        # Set last health check to 40 seconds ago (past the 30s timeout)
        mock_worker._last_health_check_received = datetime.now(UTC) - timedelta(
            seconds=40
        )

        async def run_monitor_once():
            task = asyncio.create_task(mock_worker._monitor_health_checks())
            await asyncio.sleep(1.5)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass  # Expected when cancelling the monitoring task

        await run_monitor_once()

        # _ensure_registered should have been called due to timeout
        mock_worker._ensure_registered.assert_called()

    @pytest.mark.asyncio
    async def test_monitor_skips_when_health_check_recent(self, mock_worker):
        """Test that monitor does NOT check registration when health check is recent."""
        # Set last health check to 5 seconds ago (well within timeout)
        mock_worker._last_health_check_received = datetime.now(UTC) - timedelta(
            seconds=5
        )

        async def run_monitor_once():
            task = asyncio.create_task(mock_worker._monitor_health_checks())
            await asyncio.sleep(1.5)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass  # Expected when cancelling the monitoring task

        await run_monitor_once()

        # _ensure_registered should NOT have been called - health check is recent
        mock_worker._ensure_registered.assert_not_called()

    @pytest.mark.asyncio
    async def test_monitor_resets_timer_after_timeout_check(self, mock_worker):
        """Test that monitor resets the health check timer after checking registration."""
        # Set last health check to 40 seconds ago
        old_time = datetime.now(UTC) - timedelta(seconds=40)
        mock_worker._last_health_check_received = old_time

        async def run_monitor_once():
            task = asyncio.create_task(mock_worker._monitor_health_checks())
            await asyncio.sleep(1.5)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass  # Expected when cancelling the monitoring task

        await run_monitor_once()

        # Timer should have been reset to approximately now
        assert mock_worker._last_health_check_received is not None
        assert mock_worker._last_health_check_received > old_time

    @pytest.mark.asyncio
    async def test_monitor_handles_exception_gracefully(self, mock_worker):
        """Test that monitor continues running even if _ensure_registered raises."""
        mock_worker._last_health_check_received = None
        mock_worker._ensure_registered = AsyncMock(
            side_effect=Exception("Network error")
        )

        # Should not raise, just log the error and continue
        async def run_monitor_once():
            task = asyncio.create_task(mock_worker._monitor_health_checks())
            await asyncio.sleep(1.5)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass  # Expected when cancelling the monitoring task

        # Should not raise
        await run_monitor_once()


class TestEnsureRegistered:
    """Tests for _ensure_registered method."""

    @pytest.fixture
    def mock_worker(self):
        """Create a mock worker for testing _ensure_registered."""
        from ktrdr.api.models.operations import OperationType
        from ktrdr.api.models.workers import WorkerType
        from ktrdr.workers.base import WorkerAPIBase

        with patch.object(WorkerAPIBase, "__init__", lambda self: None):
            worker = WorkerAPIBase.__new__(WorkerAPIBase)

            worker.worker_type = WorkerType.BACKTESTING
            worker.operation_type = OperationType.BACKTESTING
            worker.worker_port = 5003
            worker.backend_url = "http://localhost:8000"
            worker.worker_id = "test-worker-1"
            worker._completed_operations = []
            worker._operations_service = MagicMock()

            return worker

    @pytest.mark.asyncio
    async def test_ensure_registered_does_nothing_when_registered(self, mock_worker):
        """Test that _ensure_registered does nothing if worker is already registered."""

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            # Mock self_register to track if it's called
            mock_worker.self_register = AsyncMock()

            await mock_worker._ensure_registered()

            # self_register should NOT be called since we're already registered
            mock_worker.self_register.assert_not_called()

    @pytest.mark.asyncio
    async def test_ensure_registered_reregisters_on_404(self, mock_worker):
        """Test that _ensure_registered triggers re-registration on 404."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            # Mock self_register
            mock_worker.self_register = AsyncMock()

            await mock_worker._ensure_registered()

            # self_register should be called since we got 404
            mock_worker.self_register.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_registered_handles_connection_error(self, mock_worker):
        """Test that _ensure_registered handles connection errors gracefully."""
        import httpx

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            mock_worker.self_register = AsyncMock()

            # Should not raise
            await mock_worker._ensure_registered()

            # self_register should NOT be called on connection error
            # (we can't tell if we're registered or if backend is just down)
            mock_worker.self_register.assert_not_called()


class TestSelfRegisterRetry:
    """Tests for self_register retry behavior (M7.5 Task 7.5.2)."""

    @pytest.fixture
    def mock_worker(self):
        """Create a mock worker for testing self_register."""
        from ktrdr.api.models.operations import OperationType
        from ktrdr.api.models.workers import WorkerType
        from ktrdr.workers.base import WorkerAPIBase

        with patch.object(WorkerAPIBase, "__init__", lambda self: None):
            worker = WorkerAPIBase.__new__(WorkerAPIBase)

            worker.worker_type = WorkerType.BACKTESTING
            worker.operation_type = OperationType.BACKTESTING
            worker.worker_port = 5003
            worker.backend_url = "http://localhost:8000"
            worker.worker_id = "test-worker-1"
            worker._completed_operations = []

            # Mock _build_registration_payload
            worker._build_registration_payload = AsyncMock(
                return_value={
                    "worker_id": "test-worker-1",
                    "worker_type": "backtesting",
                    "endpoint_url": "http://localhost:5003",
                    "capabilities": {},
                    "current_operation_id": None,
                    "completed_operations": [],
                }
            )

            return worker

    @pytest.mark.asyncio
    async def test_self_register_success_first_attempt(self, mock_worker):
        """Test successful registration on first attempt."""

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await mock_worker.self_register(max_retries=3, initial_delay=0.1)

            assert result is True
            assert mock_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_self_register_retries_on_connection_error(self, mock_worker):
        """Test registration retries on connection error."""
        import httpx

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.ConnectError("Connection refused")
            # Success on 3rd attempt
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            return mock_response

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await mock_worker.self_register(max_retries=5, initial_delay=0.01)

            assert result is True
            assert call_count == 3

    @pytest.mark.asyncio
    async def test_self_register_gives_up_after_max_retries(self, mock_worker):
        """Test registration gives up after max retries."""
        import httpx

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await mock_worker.self_register(max_retries=3, initial_delay=0.01)

            assert result is False
            assert mock_client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_self_register_handles_503_backend_shutting_down(self, mock_worker):
        """Test registration handles 503 (backend shutting down) specially."""

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()
            if call_count < 3:
                mock_response.status_code = 503
            else:
                mock_response.status_code = 200
                mock_response.raise_for_status = MagicMock()
            return mock_response

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await mock_worker.self_register(max_retries=5, initial_delay=0.01)

            assert result is True
            assert call_count == 3  # 2 x 503, then success

    @pytest.mark.asyncio
    async def test_self_register_clears_completed_operations_on_success(
        self, mock_worker
    ):
        """Test that completed operations are cleared after successful registration."""
        from ktrdr.api.models.workers import CompletedOperationReport

        # Add some completed operations
        mock_worker._completed_operations = [
            MagicMock(spec=CompletedOperationReport),
            MagicMock(spec=CompletedOperationReport),
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            await mock_worker.self_register(max_retries=1, initial_delay=0.01)

            assert len(mock_worker._completed_operations) == 0


class TestShutdownNotificationEndpoint:
    """Tests for worker shutdown notification endpoint (M7.5 Task 7.5.4)."""

    @pytest.fixture
    def mock_worker(self):
        """Create a mock worker for testing shutdown notification."""
        from ktrdr.api.models.operations import OperationType
        from ktrdr.api.models.workers import WorkerType
        from ktrdr.workers.base import WorkerAPIBase

        with patch.object(WorkerAPIBase, "__init__", lambda self: None):
            worker = WorkerAPIBase.__new__(WorkerAPIBase)

            worker.worker_type = WorkerType.BACKTESTING
            worker.operation_type = OperationType.BACKTESTING
            worker.worker_port = 5003
            worker.backend_url = "http://localhost:8000"
            worker.worker_id = "test-worker-1"
            worker._reconnection_task = None
            worker._last_health_check_received = None
            worker._completed_operations = []
            worker._poll_for_backend_restart = AsyncMock()
            worker._build_registration_payload = AsyncMock(return_value={})

            # Create a minimal FastAPI app for the endpoint
            from fastapi import FastAPI

            worker.app = FastAPI()
            worker._register_shutdown_notification_endpoint()

            return worker

    @pytest.mark.asyncio
    async def test_shutdown_notification_starts_polling(self, mock_worker):
        """Test that shutdown notification starts the reconnection polling task."""
        from fastapi.testclient import TestClient

        client = TestClient(mock_worker.app)

        response = client.post("/backend-shutdown", json={"message": "test"})

        assert response.status_code == 200
        assert response.json() == {"acknowledged": True}
        # Verify polling was started (the mock was called)
        # Note: Due to async task creation, we check the mock was set up to be called
        assert mock_worker._reconnection_task is not None


class TestPollForBackendRestart:
    """Tests for _poll_for_backend_restart method (M7.5 Task 7.5.4)."""

    @pytest.fixture
    def mock_worker(self):
        """Create a mock worker for testing polling."""
        from ktrdr.api.models.operations import OperationType
        from ktrdr.api.models.workers import WorkerType
        from ktrdr.workers.base import WorkerAPIBase

        with patch.object(WorkerAPIBase, "__init__", lambda self: None):
            worker = WorkerAPIBase.__new__(WorkerAPIBase)

            worker.worker_type = WorkerType.BACKTESTING
            worker.operation_type = OperationType.BACKTESTING
            worker.worker_port = 5003
            worker.backend_url = "http://localhost:8000"
            worker.worker_id = "test-worker-1"
            worker._last_health_check_received = None
            worker._completed_operations = []
            worker._shutdown_event = asyncio.Event()  # Add shutdown event for fix
            worker._build_registration_payload = AsyncMock(
                return_value={
                    "worker_id": "test-worker-1",
                    "worker_type": "backtesting",
                    "endpoint_url": "http://localhost:5003",
                    "capabilities": {},
                    "current_operation_id": None,
                    "completed_operations": [],
                }
            )

            return worker

    @pytest.mark.asyncio
    async def test_poll_succeeds_when_backend_comes_back(self, mock_worker):
        """Test that polling succeeds when backend becomes available."""
        call_count = 0

        async def mock_self_register(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return False  # Backend not ready
            return True  # Backend ready on 3rd attempt

        mock_worker.self_register = mock_self_register

        await mock_worker._poll_for_backend_restart(
            poll_interval=0.01, max_duration=1.0
        )

        assert call_count == 3
        # Timer should be reset after successful re-registration
        assert mock_worker._last_health_check_received is not None

    @pytest.mark.asyncio
    async def test_poll_times_out_if_backend_never_returns(self, mock_worker):
        """Test that polling times out if backend never becomes available."""
        mock_worker.self_register = AsyncMock(return_value=False)

        await mock_worker._poll_for_backend_restart(
            poll_interval=0.01, max_duration=0.05
        )

        # Should have attempted multiple times before timing out
        assert mock_worker.self_register.call_count >= 2
