"""Unit tests for operations module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from ktrdr.cli.client.errors import APIError


class MockAdapter:
    """Mock operation adapter for testing."""

    def __init__(
        self,
        *,
        start_endpoint: str = "/operations/start",
        start_payload: dict | None = None,
        operation_id: str = "op_test123",
    ):
        self.start_endpoint = start_endpoint
        self.start_payload = start_payload or {"test": "data"}
        self.operation_id = operation_id
        self.display_results_called = False
        self.display_results_data = None

    def get_start_endpoint(self) -> str:
        return self.start_endpoint

    def get_start_payload(self) -> dict:
        return self.start_payload

    def parse_start_response(self, response: dict) -> str:
        return response["data"]["operation_id"]

    async def display_results(
        self, final_status: dict, console: MagicMock, http_client: AsyncMock
    ) -> None:
        self.display_results_called = True
        self.display_results_data = final_status


class TestExecuteOperationStartsAndPolls:
    """Tests for operation starting and polling."""

    @pytest.mark.asyncio
    async def test_starts_operation_via_adapter(self):
        """execute_operation starts operation using adapter endpoints."""
        from ktrdr.cli.client.operations import execute_operation

        # Mock client
        mock_client = AsyncMock()
        mock_client.post.return_value = {
            "success": True,
            "data": {"operation_id": "op_abc123"},
        }
        mock_client.get.return_value = {
            "success": True,
            "data": {"status": "completed", "operation_id": "op_abc123"},
        }
        mock_client.config = MagicMock()
        mock_client.config.base_url = "http://localhost:8000/api/v1"

        adapter = MockAdapter(
            start_endpoint="/training/start",
            start_payload={"model": "test"},
            operation_id="op_abc123",
        )

        await execute_operation(mock_client, adapter)

        # Verify start endpoint was called
        mock_client.post.assert_called_once_with(
            "/training/start", json={"model": "test"}
        )

    @pytest.mark.asyncio
    async def test_polls_until_completed(self):
        """execute_operation polls status endpoint until completed."""
        from ktrdr.cli.client.operations import execute_operation

        mock_client = AsyncMock()
        mock_client.post.return_value = {
            "success": True,
            "data": {"operation_id": "op_abc123"},
        }
        # Simulate: running -> running -> completed
        mock_client.get.side_effect = [
            {
                "success": True,
                "data": {"status": "running", "progress": {"percentage": 25}},
            },
            {
                "success": True,
                "data": {"status": "running", "progress": {"percentage": 50}},
            },
            {
                "success": True,
                "data": {"status": "completed", "operation_id": "op_abc123"},
            },
        ]
        mock_client.config = MagicMock()
        mock_client.config.base_url = "http://localhost:8000/api/v1"

        adapter = MockAdapter()

        await execute_operation(mock_client, adapter, poll_interval=0.01)

        # Verify polling happened (3 GET calls)
        assert mock_client.get.call_count == 3
        # All calls to the operations status endpoint (uses ID from response, not adapter)
        for call_args in mock_client.get.call_args_list:
            assert "/operations/op_abc123" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_returns_final_result(self):
        """execute_operation returns the final operation result."""
        from ktrdr.cli.client.operations import execute_operation

        mock_client = AsyncMock()
        mock_client.post.return_value = {
            "success": True,
            "data": {"operation_id": "op_abc123"},
        }
        mock_client.get.return_value = {
            "success": True,
            "data": {
                "status": "completed",
                "operation_id": "op_abc123",
                "result": {"accuracy": 0.95},
            },
        }
        mock_client.config = MagicMock()
        mock_client.config.base_url = "http://localhost:8000/api/v1"

        adapter = MockAdapter()

        result = await execute_operation(mock_client, adapter)

        assert result["status"] == "completed"
        assert result["result"] == {"accuracy": 0.95}


class TestExecuteOperationProgress:
    """Tests for progress callback invocation."""

    @pytest.mark.asyncio
    async def test_invokes_progress_callback(self):
        """execute_operation invokes on_progress with percentage and message."""
        from ktrdr.cli.client.operations import execute_operation

        mock_client = AsyncMock()
        mock_client.post.return_value = {
            "success": True,
            "data": {"operation_id": "op_abc123"},
        }
        mock_client.get.side_effect = [
            {
                "success": True,
                "data": {
                    "status": "running",
                    "progress": {"percentage": 50, "current_step": "Training..."},
                },
            },
            {
                "success": True,
                "data": {"status": "completed", "progress": {"percentage": 100}},
            },
        ]
        mock_client.config = MagicMock()
        mock_client.config.base_url = "http://localhost:8000/api/v1"

        adapter = MockAdapter()
        progress_calls = []

        def on_progress(pct: int, msg: str) -> None:
            progress_calls.append((pct, msg))

        await execute_operation(
            mock_client, adapter, on_progress=on_progress, poll_interval=0.01
        )

        # Verify progress was called with percentage and message
        assert len(progress_calls) >= 1
        assert progress_calls[0][0] == 50  # percentage
        assert "Training" in progress_calls[0][1]  # message

    @pytest.mark.asyncio
    async def test_progress_callback_optional(self):
        """execute_operation works without progress callback."""
        from ktrdr.cli.client.operations import execute_operation

        mock_client = AsyncMock()
        mock_client.post.return_value = {
            "success": True,
            "data": {"operation_id": "op_abc123"},
        }
        mock_client.get.return_value = {
            "success": True,
            "data": {"status": "completed"},
        }
        mock_client.config = MagicMock()
        mock_client.config.base_url = "http://localhost:8000/api/v1"

        adapter = MockAdapter()

        # Should not raise
        result = await execute_operation(mock_client, adapter)
        assert result["status"] == "completed"


class TestExecuteOperationCancellation:
    """Tests for cancellation handling."""

    @pytest.mark.asyncio
    async def test_handles_asyncio_cancellation(self):
        """execute_operation handles asyncio.CancelledError gracefully."""
        from ktrdr.cli.client.operations import execute_operation

        mock_client = AsyncMock()
        mock_client.post.return_value = {
            "success": True,
            "data": {"operation_id": "op_abc123"},
        }
        # First poll raises CancelledError
        mock_client.get.side_effect = asyncio.CancelledError()
        mock_client.delete.return_value = {"success": True}
        mock_client.config = MagicMock()
        mock_client.config.base_url = "http://localhost:8000/api/v1"

        adapter = MockAdapter()

        result = await execute_operation(mock_client, adapter)

        # Should return cancelled status
        assert result["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_sends_cancellation_to_backend(self):
        """execute_operation sends DELETE to cancel operation on backend."""
        from ktrdr.cli.client.operations import execute_operation

        mock_client = AsyncMock()
        mock_client.post.return_value = {
            "success": True,
            "data": {"operation_id": "op_abc123"},
        }
        mock_client.get.side_effect = asyncio.CancelledError()
        mock_client.delete.return_value = {"success": True}
        mock_client.config = MagicMock()
        mock_client.config.base_url = "http://localhost:8000/api/v1"

        adapter = MockAdapter()

        await execute_operation(mock_client, adapter)

        # Verify DELETE was called to cancel (uses ID from response)
        mock_client.delete.assert_called_once()
        call_args = mock_client.delete.call_args
        assert "/operations/op_abc123" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_cancellation_returns_partial_progress(self):
        """Cancelled operation returns progress info in result."""
        from ktrdr.cli.client.operations import execute_operation

        mock_client = AsyncMock()
        mock_client.post.return_value = {
            "success": True,
            "data": {"operation_id": "op_abc123"},
        }
        # Poll once then cancel
        get_count = 0

        async def mock_get(*args, **kwargs):
            nonlocal get_count
            get_count += 1
            if get_count == 1:
                return {
                    "success": True,
                    "data": {"status": "running", "progress": {"percentage": 50}},
                }
            raise asyncio.CancelledError()

        mock_client.get.side_effect = mock_get
        mock_client.delete.return_value = {"success": True}
        mock_client.config = MagicMock()
        mock_client.config.base_url = "http://localhost:8000/api/v1"

        adapter = MockAdapter()

        result = await execute_operation(mock_client, adapter, poll_interval=0.01)

        assert result["status"] == "cancelled"
        # operation_id comes from the POST response, not the adapter
        assert result["operation_id"] == "op_abc123"


class TestExecuteOperationFailure:
    """Tests for operation failure handling."""

    @pytest.mark.asyncio
    async def test_returns_failed_status(self):
        """execute_operation returns failed status on operation failure."""
        from ktrdr.cli.client.operations import execute_operation

        mock_client = AsyncMock()
        mock_client.post.return_value = {
            "success": True,
            "data": {"operation_id": "op_abc123"},
        }
        mock_client.get.return_value = {
            "success": True,
            "data": {
                "status": "failed",
                "error_message": "Training diverged",
                "operation_id": "op_abc123",
            },
        }
        mock_client.config = MagicMock()
        mock_client.config.base_url = "http://localhost:8000/api/v1"

        adapter = MockAdapter()

        result = await execute_operation(mock_client, adapter)

        assert result["status"] == "failed"
        assert result["error_message"] == "Training diverged"

    @pytest.mark.asyncio
    async def test_raises_on_start_failure(self):
        """execute_operation raises APIError when start fails."""
        from ktrdr.cli.client.operations import execute_operation

        mock_client = AsyncMock()
        mock_client.post.side_effect = APIError(
            message="Invalid configuration",
            status_code=400,
            details={"field": "epochs"},
        )
        mock_client.config = MagicMock()
        mock_client.config.base_url = "http://localhost:8000/api/v1"

        adapter = MockAdapter()

        with pytest.raises(APIError) as exc_info:
            await execute_operation(mock_client, adapter)

        assert exc_info.value.status_code == 400


class TestExecuteOperationTerminalStates:
    """Tests for terminal state recognition."""

    @pytest.mark.asyncio
    async def test_completed_is_terminal(self):
        """Operation with 'completed' status ends polling."""
        from ktrdr.cli.client.operations import execute_operation

        mock_client = AsyncMock()
        mock_client.post.return_value = {
            "success": True,
            "data": {"operation_id": "op_abc123"},
        }
        mock_client.get.return_value = {
            "success": True,
            "data": {"status": "completed"},
        }
        mock_client.config = MagicMock()
        mock_client.config.base_url = "http://localhost:8000/api/v1"

        adapter = MockAdapter()

        result = await execute_operation(mock_client, adapter)

        assert result["status"] == "completed"
        assert mock_client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_failed_is_terminal(self):
        """Operation with 'failed' status ends polling."""
        from ktrdr.cli.client.operations import execute_operation

        mock_client = AsyncMock()
        mock_client.post.return_value = {
            "success": True,
            "data": {"operation_id": "op_abc123"},
        }
        mock_client.get.return_value = {
            "success": True,
            "data": {"status": "failed", "error_message": "Error"},
        }
        mock_client.config = MagicMock()
        mock_client.config.base_url = "http://localhost:8000/api/v1"

        adapter = MockAdapter()

        result = await execute_operation(mock_client, adapter)

        assert result["status"] == "failed"
        assert mock_client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_cancelled_is_terminal(self):
        """Operation with 'cancelled' status ends polling."""
        from ktrdr.cli.client.operations import execute_operation

        mock_client = AsyncMock()
        mock_client.post.return_value = {
            "success": True,
            "data": {"operation_id": "op_abc123"},
        }
        mock_client.get.return_value = {
            "success": True,
            "data": {"status": "cancelled"},
        }
        mock_client.config = MagicMock()
        mock_client.config.base_url = "http://localhost:8000/api/v1"

        adapter = MockAdapter()

        result = await execute_operation(mock_client, adapter)

        assert result["status"] == "cancelled"
        assert mock_client.get.call_count == 1
