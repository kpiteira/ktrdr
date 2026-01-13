"""Tests for OperationRunner wrapper.

Tests the unified start/follow wrapper for all operation commands.
"""

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from ktrdr.cli.state import CLIState


class MockAdapter:
    """Mock operation adapter for testing."""

    def __init__(
        self,
        endpoint: str = "/test/start",
        payload: dict[str, Any] | None = None,
        operation_id: str = "op_test123",
    ):
        self._endpoint = endpoint
        self._payload = payload or {"param": "value"}
        self._operation_id = operation_id

    def get_start_endpoint(self) -> str:
        return self._endpoint

    def get_start_payload(self) -> dict[str, Any]:
        return self._payload

    def parse_start_response(self, response: dict[str, Any]) -> str:
        return self._operation_id


class TestOperationRunnerFireAndForget:
    """Tests for fire-and-forget mode (follow=False)."""

    def test_operation_runner_fire_and_forget_prints_id(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """Fire-and-forget mode prints operation ID and returns."""
        from ktrdr.cli.operation_runner import OperationRunner

        state = CLIState(json_mode=False)
        runner = OperationRunner(state)
        adapter = MockAdapter(operation_id="op_abc123")

        # Mock the HTTP client
        with patch("ktrdr.cli.operation_runner.AsyncCLIClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(
                return_value={"data": {"operation_id": "op_abc123"}}
            )
            mock_client_class.return_value = mock_client

            runner.start(adapter, follow=False)

        captured = capsys.readouterr()
        assert "op_abc123" in captured.out
        assert "Started" in captured.out

    def test_operation_runner_fire_and_forget_uses_adapter_endpoint(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """Fire-and-forget mode POSTs to adapter endpoint."""
        from ktrdr.cli.operation_runner import OperationRunner

        state = CLIState()
        runner = OperationRunner(state)
        adapter = MockAdapter(endpoint="/custom/endpoint", payload={"key": "val"})

        with patch("ktrdr.cli.operation_runner.AsyncCLIClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(
                return_value={"data": {"operation_id": "op_x"}}
            )
            mock_client_class.return_value = mock_client

            runner.start(adapter, follow=False)

            # Verify the endpoint and payload were used
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "/custom/endpoint"
            assert call_args[1]["json"] == {"key": "val"}


class TestOperationRunnerJSON:
    """Tests for JSON output mode."""

    def test_operation_runner_json_output(self, capsys: pytest.CaptureFixture) -> None:
        """JSON mode produces valid JSON with operation details."""
        from ktrdr.cli.operation_runner import OperationRunner

        state = CLIState(json_mode=True)
        runner = OperationRunner(state)
        adapter = MockAdapter(operation_id="op_json456")

        with patch("ktrdr.cli.operation_runner.AsyncCLIClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(
                return_value={"data": {"operation_id": "op_json456"}}
            )
            mock_client_class.return_value = mock_client

            runner.start(adapter, follow=False)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["operation_id"] == "op_json456"
        assert output["status"] == "started"


class TestOperationRunnerFollowMode:
    """Tests for follow mode (follow=True)."""

    def test_operation_runner_follow_mode_calls_execute(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """Follow mode calls execute_operation on the client."""
        from ktrdr.cli.operation_runner import OperationRunner

        state = CLIState(json_mode=False)
        runner = OperationRunner(state)
        adapter = MockAdapter()

        with patch("ktrdr.cli.operation_runner.AsyncCLIClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.execute_operation = AsyncMock(
                return_value={"status": "completed", "operation_id": "op_follow"}
            )
            mock_client_class.return_value = mock_client

            runner.start(adapter, follow=True)

            # Verify execute_operation was called
            mock_client.execute_operation.assert_called_once()

    def test_operation_runner_follow_mode_exits_on_failure(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """Follow mode raises SystemExit(1) on operation failure."""
        from ktrdr.cli.operation_runner import OperationRunner

        state = CLIState(json_mode=False)
        runner = OperationRunner(state)
        adapter = MockAdapter()

        with patch("ktrdr.cli.operation_runner.AsyncCLIClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.execute_operation = AsyncMock(
                return_value={"status": "failed", "error": "Test failure"}
            )
            mock_client_class.return_value = mock_client

            with pytest.raises(SystemExit) as exc_info:
                runner.start(adapter, follow=True)

            assert exc_info.value.code == 1


class TestOperationRunnerAPIURL:
    """Tests for API URL handling."""

    def test_operation_runner_uses_state_api_url(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """OperationRunner uses api_url from CLIState."""
        from ktrdr.cli.operation_runner import OperationRunner

        custom_url = "http://custom-backend:9000"
        state = CLIState(api_url=custom_url)
        runner = OperationRunner(state)
        adapter = MockAdapter()

        with patch("ktrdr.cli.operation_runner.AsyncCLIClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(
                return_value={"data": {"operation_id": "op_x"}}
            )
            mock_client_class.return_value = mock_client

            runner.start(adapter, follow=False)

            # Verify AsyncCLIClient was created with correct base_url
            mock_client_class.assert_called_once_with(base_url=custom_url)


class TestOperationRunnerInit:
    """Tests for OperationRunner initialization."""

    def test_operation_runner_stores_state(self) -> None:
        """OperationRunner stores CLIState for later use."""
        from ktrdr.cli.operation_runner import OperationRunner

        state = CLIState(json_mode=True, verbose=True, api_url="http://test:8000")
        runner = OperationRunner(state)

        assert runner.state is state
        assert runner.state.json_mode is True
        assert runner.state.verbose is True
        assert runner.state.api_url == "http://test:8000"
