"""
Unit tests for AsyncOperationExecutor.

Tests the generic async operation executor in isolation using mocked
HTTP client and adapter interface.
"""

import asyncio
import signal
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from rich.console import Console

from ktrdr.cli.operation_adapters import OperationAdapter
from ktrdr.cli.operation_executor import AsyncOperationExecutor


class MockAdapter(OperationAdapter):
    """Mock adapter for testing executor."""

    def __init__(
        self,
        endpoint: str = "/api/v1/test/start",
        payload: dict[str, Any] | None = None,
        operation_id: str = "test-op-123",
    ):
        self.endpoint = endpoint
        self.payload = payload or {"test": "data"}
        self.operation_id = operation_id
        self.display_called = False
        self.display_args = None

    def get_start_endpoint(self) -> str:
        return self.endpoint

    def get_start_payload(self) -> dict[str, Any]:
        return self.payload

    def parse_start_response(self, response: dict) -> str:
        return response["data"]["operation_id"]

    async def display_results(
        self,
        final_status: dict,
        console: Console,
        http_client: httpx.AsyncClient,
    ) -> None:
        self.display_called = True
        self.display_args = (final_status, console, http_client)


@pytest.fixture
def mock_adapter():
    """Create a mock adapter for testing."""
    return MockAdapter()


@pytest.fixture
def console():
    """Create a Rich console for testing."""
    return Console()


@pytest.fixture
def executor():
    """Create an executor instance for testing."""
    return AsyncOperationExecutor(base_url="http://test-api:8000")


class TestAsyncOperationExecutorInitialization:
    """Test executor initialization."""

    def test_init_with_defaults(self):
        """Test executor initializes with default values."""
        executor = AsyncOperationExecutor()
        assert executor.base_url is not None
        assert executor.poll_interval == 0.3
        assert executor.timeout == 30.0
        assert executor.cancelled is False

    def test_init_with_custom_values(self):
        """Test executor initializes with custom values."""
        executor = AsyncOperationExecutor(
            base_url="http://custom:9000",
            poll_interval=0.5,
            timeout=60.0,
        )
        assert executor.base_url == "http://custom:9000"
        assert executor.poll_interval == 0.5
        assert executor.timeout == 60.0


class TestAsyncOperationExecutorStartOperation:
    """Test operation start flow."""

    @pytest.mark.asyncio
    async def test_start_operation_success(self, executor, mock_adapter):
        """Test successful operation start."""
        # Mock HTTP response
        mock_response_data = {
            "success": True,
            "data": {"operation_id": "test-op-123", "status": "running"},
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Create mock response object
            mock_resp = AsyncMock()
            mock_resp.json = Mock(return_value=mock_response_data)  # Sync method
            mock_resp.status_code = 200
            mock_resp.raise_for_status = Mock()
            mock_client.post.return_value = mock_resp

            operation_id = await executor._start_operation(mock_adapter, mock_client)

            assert operation_id == "test-op-123"
            mock_client.post.assert_called_once_with(
                "http://test-api:8000/api/v1/test/start",
                json={"test": "data"},
                timeout=30.0,
            )

    @pytest.mark.asyncio
    async def test_start_operation_http_error(self, executor, mock_adapter):
        """Test operation start handles HTTP errors."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = httpx.HTTPError("Connection failed")

            with pytest.raises(httpx.HTTPError):
                await executor._start_operation(mock_adapter, mock_client)


class TestAsyncOperationExecutorPolling:
    """Test operation polling logic."""

    @pytest.mark.asyncio
    async def test_poll_completed_operation(self, executor):
        """Test polling an operation that completes successfully."""
        # Mock responses: running -> running -> completed
        responses = [
            {
                "success": True,
                "data": {
                    "operation_id": "test-op",
                    "status": "running",
                    "progress": {"percentage": 30},
                },
            },
            {
                "success": True,
                "data": {
                    "operation_id": "test-op",
                    "status": "running",
                    "progress": {"percentage": 60},
                },
            },
            {
                "success": True,
                "data": {
                    "operation_id": "test-op",
                    "status": "completed",
                    "progress": {"percentage": 100},
                },
            },
        ]

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Create mock response objects
            mock_responses = []
            for resp_data in responses:
                mock_resp = AsyncMock()
                mock_resp.json = Mock(return_value=resp_data)  # Sync method
                mock_resp.status_code = 200
                mock_resp.raise_for_status = Mock()
                mock_responses.append(mock_resp)

            mock_client.get.side_effect = mock_responses

            final_status = await executor._poll_until_complete(
                "test-op", mock_client, progress_callback=None
            )

            assert final_status["status"] == "completed"
            assert mock_client.get.call_count == 3

    @pytest.mark.asyncio
    async def test_poll_failed_operation(self, executor):
        """Test polling an operation that fails."""
        responses = [
            {
                "success": True,
                "data": {
                    "operation_id": "test-op",
                    "status": "running",
                    "progress": {"percentage": 50},
                },
            },
            {
                "success": True,
                "data": {
                    "operation_id": "test-op",
                    "status": "failed",
                    "error_message": "Something went wrong",
                },
            },
        ]

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_responses = []
            for resp_data in responses:
                mock_resp = AsyncMock()
                mock_resp.json = Mock(return_value=resp_data)  # Sync method
                mock_resp.status_code = 200
                mock_resp.raise_for_status = Mock()
                mock_responses.append(mock_resp)

            mock_client.get.side_effect = mock_responses

            final_status = await executor._poll_until_complete(
                "test-op", mock_client, progress_callback=None
            )

            assert final_status["status"] == "failed"


class TestAsyncOperationExecutorCancellation:
    """Test cancellation flow."""

    @pytest.mark.asyncio
    async def test_cancel_operation_success(self, executor, console):
        """Test successful operation cancellation."""
        cancel_response_data = {
            "success": True,
            "data": {"operation_id": "test-op", "status": "cancelled"},
        }

        status_response_data = {
            "success": True,
            "data": {"operation_id": "test-op", "status": "cancelled"},
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock DELETE response for cancellation request
            mock_delete_resp = AsyncMock()
            mock_delete_resp.json = Mock(return_value=cancel_response_data)
            mock_delete_resp.status_code = 200
            mock_client.delete.return_value = mock_delete_resp

            # Mock GET response for status polling
            mock_get_resp = AsyncMock()
            mock_get_resp.json = Mock(return_value=status_response_data)
            mock_get_resp.status_code = 200
            mock_get_resp.raise_for_status = Mock()
            mock_client.get.return_value = mock_get_resp

            await executor._handle_cancellation("test-op", mock_client, console)

            mock_client.delete.assert_called_once()
            call_args = mock_client.delete.call_args
            assert "test-op" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_cancel_operation_already_finished(self, executor, console):
        """Test cancelling an already finished operation."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock 400 error for already finished
            mock_resp = AsyncMock()
            mock_resp.status_code = 400
            mock_resp.json = Mock(
                return_value={
                    "detail": "Operation cannot be cancelled - already completed"
                }
            )
            mock_client.delete.return_value = mock_resp

            # Should not raise - best effort cancellation
            result = await executor._handle_cancellation(
                "test-op", mock_client, console
            )

            # Should return cancelled status even if backend says 400
            assert result["status"] == "cancelled"


class TestAsyncOperationExecutorSignalHandling:
    """Test signal handler setup and teardown."""

    @pytest.mark.asyncio
    async def test_signal_handler_registration(self, executor):
        """Test signal handler is registered correctly."""
        with patch("asyncio.get_running_loop") as mock_loop:
            loop = asyncio.get_event_loop()
            mock_loop.return_value = loop

            # Mock add_signal_handler
            with patch.object(loop, "add_signal_handler") as mock_add_signal:
                executor._setup_signal_handler()

                mock_add_signal.assert_called_once()
                call_args = mock_add_signal.call_args
                assert call_args[0][0] == signal.SIGINT

    @pytest.mark.asyncio
    async def test_signal_handler_sets_cancelled_flag(self, executor):
        """Test signal handler sets cancelled flag."""
        assert executor.cancelled is False

        # Manually trigger the signal handler
        executor._signal_handler()

        assert executor.cancelled is True

    @pytest.mark.asyncio
    async def test_signal_handler_cleanup(self, executor):
        """Test signal handler is cleaned up."""
        with patch("asyncio.get_running_loop") as mock_loop:
            loop = asyncio.get_event_loop()
            mock_loop.return_value = loop

            with patch.object(loop, "remove_signal_handler") as mock_remove_signal:
                # Mark handler as registered first
                executor._signal_handler_registered = True
                executor._cleanup_signal_handler()

                mock_remove_signal.assert_called_once_with(signal.SIGINT)


class TestAsyncOperationExecutorEndToEnd:
    """Test end-to-end operation execution."""

    @pytest.mark.asyncio
    async def test_execute_operation_success(self, executor, mock_adapter, console):
        """Test successful end-to-end operation execution."""
        # Mock start response
        start_response = {
            "success": True,
            "data": {"operation_id": "test-op-123", "status": "running"},
        }

        # Mock poll responses
        poll_response = {
            "success": True,
            "data": {
                "operation_id": "test-op-123",
                "status": "completed",
                "progress": {"percentage": 100},
            },
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock POST for start
            mock_post_resp = AsyncMock()
            mock_post_resp.json = Mock(return_value=start_response)
            mock_post_resp.status_code = 200
            mock_post_resp.raise_for_status = Mock()
            mock_client.post.return_value = mock_post_resp

            # Mock GET for polling
            mock_get_resp = AsyncMock()
            mock_get_resp.json = Mock(return_value=poll_response)
            mock_get_resp.status_code = 200
            mock_get_resp.raise_for_status = Mock()
            mock_client.get.return_value = mock_get_resp

            success = await executor.execute_operation(mock_adapter, console)

            assert success is True
            assert mock_adapter.display_called is True

    @pytest.mark.asyncio
    async def test_execute_operation_with_failure(
        self, executor, mock_adapter, console
    ):
        """Test operation execution with failure status."""
        start_response = {
            "success": True,
            "data": {"operation_id": "test-op-123", "status": "running"},
        }

        poll_response = {
            "success": True,
            "data": {
                "operation_id": "test-op-123",
                "status": "failed",
                "error_message": "Test error",
            },
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock POST for start
            mock_post_resp = AsyncMock()
            mock_post_resp.json = Mock(return_value=start_response)
            mock_post_resp.status_code = 200
            mock_post_resp.raise_for_status = Mock()
            mock_client.post.return_value = mock_post_resp

            # Mock GET for polling (failed status)
            mock_get_resp = AsyncMock()
            mock_get_resp.json = Mock(return_value=poll_response)
            mock_get_resp.status_code = 200
            mock_get_resp.raise_for_status = Mock()
            mock_client.get.return_value = mock_get_resp

            success = await executor.execute_operation(mock_adapter, console)

            assert success is False
            assert mock_adapter.display_called is False


class TestAsyncOperationExecutorProgressCallback:
    """Test progress callback integration."""

    @pytest.mark.asyncio
    async def test_progress_callback_called(self, executor):
        """Test that progress callback is invoked during polling when progress display is enabled."""
        callback_invocations = []

        def progress_callback(status_data):
            """Callback that returns formatted string and tracks invocations."""
            callback_invocations.append(status_data)
            return f"Progress: {status_data.get('progress', {}).get('percentage', 0)}%"

        responses = [
            {
                "success": True,
                "data": {
                    "operation_id": "test-op",
                    "status": "running",
                    "progress": {"percentage": 50},
                },
            },
            {
                "success": True,
                "data": {
                    "operation_id": "test-op",
                    "status": "completed",
                    "progress": {"percentage": 100},
                },
            },
        ]

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_responses = []
            for resp_data in responses:
                mock_resp = AsyncMock()
                mock_resp.json = Mock(return_value=resp_data)
                mock_resp.status_code = 200
                mock_resp.raise_for_status = Mock()
                mock_responses.append(mock_resp)

            mock_client.get.side_effect = mock_responses

            # Mock Progress and task_id to enable progress display
            from rich.progress import Progress

            mock_progress = Mock(spec=Progress)
            mock_task_id = "task-123"

            await executor._poll_until_complete(
                "test-op",
                mock_client,
                progress=mock_progress,
                task_id=mock_task_id,
                progress_callback=progress_callback,
            )

            # Callback should be invoked twice (once per poll)
            assert len(callback_invocations) == 2
            assert callback_invocations[0]["progress"]["percentage"] == 50
            assert callback_invocations[1]["progress"]["percentage"] == 100

            # Progress bar should be updated with callback results
            assert mock_progress.update.call_count == 2
