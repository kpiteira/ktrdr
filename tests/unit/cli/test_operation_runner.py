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

    def test_operation_runner_follow_mode_polls_until_complete(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """Follow mode polls operation status until completed."""
        from ktrdr.cli.operation_runner import OperationRunner

        state = CLIState(json_mode=False)
        runner = OperationRunner(state)
        adapter = MockAdapter(operation_id="op_follow")

        with patch("ktrdr.cli.operation_runner.AsyncCLIClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            # Start operation returns operation_id
            mock_client.post = AsyncMock(
                return_value={"data": {"operation_id": "op_follow"}}
            )
            # Polling returns completed status
            mock_client.get = AsyncMock(
                return_value={
                    "data": {
                        "status": "completed",
                        "operation_id": "op_follow",
                        "progress": {"percentage": 100},
                    }
                }
            )
            mock_client_class.return_value = mock_client

            runner.start(adapter, follow=True)

            # Verify post was called to start operation
            mock_client.post.assert_called_once()
            # Verify get was called to poll status
            mock_client.get.assert_called()

        captured = capsys.readouterr()
        assert "completed" in captured.out.lower()

    def test_operation_runner_follow_mode_exits_on_failure(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """Follow mode raises SystemExit(1) on operation failure."""
        from ktrdr.cli.operation_runner import OperationRunner

        state = CLIState(json_mode=False)
        runner = OperationRunner(state)
        adapter = MockAdapter(operation_id="op_fail")

        with patch("ktrdr.cli.operation_runner.AsyncCLIClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(
                return_value={"data": {"operation_id": "op_fail"}}
            )
            mock_client.get = AsyncMock(
                return_value={
                    "data": {
                        "status": "failed",
                        "error_message": "Test failure",
                        "progress": {"percentage": 50},
                    }
                }
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


class TestOperationRunnerResultDisplay:
    """Tests for consistent result display across operation types."""

    def test_display_results_training_json_mode(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """Training results output valid JSON in JSON mode."""
        from ktrdr.cli.operation_runner import OperationRunner

        state = CLIState(json_mode=True)
        runner = OperationRunner(state)

        op_data = {
            "status": "completed",
            "operation_id": "op_train_123",
            "result_summary": {
                "training_metrics": {
                    "epochs_trained": 50,
                    "final_loss": 0.0234,
                    "final_val_loss": 0.0312,
                },
                "model_path": "/models/test_model.pt",
            },
        }

        runner._display_results(op_data, "training")

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["operation_type"] == "training"
        assert output["results"]["epochs_trained"] == 50
        assert output["results"]["final_loss"] == 0.0234

    def test_display_results_backtest_json_mode(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """Backtest results output valid JSON in JSON mode."""
        from ktrdr.cli.operation_runner import OperationRunner

        state = CLIState(json_mode=True)
        runner = OperationRunner(state)

        op_data = {
            "status": "completed",
            "operation_id": "op_bt_456",
            "result_summary": {
                "metrics": {
                    "total_return_pct": 0.15,
                    "sharpe_ratio": 1.8,
                    "max_drawdown_pct": 0.05,
                    "total_trades": 42,
                    "win_rate": 0.65,
                },
            },
        }

        runner._display_results(op_data, "backtest")

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["operation_type"] == "backtest"
        assert output["results"]["total_return_pct"] == 0.15
        assert output["results"]["sharpe_ratio"] == 1.8

    def test_display_results_unknown_type_json_mode(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """Unknown operation types output their result_summary as JSON."""
        from ktrdr.cli.operation_runner import OperationRunner

        state = CLIState(json_mode=True)
        runner = OperationRunner(state)

        op_data = {
            "status": "completed",
            "operation_id": "op_custom_789",
            "result_summary": {
                "custom_field": "custom_value",
                "count": 100,
            },
        }

        runner._display_results(op_data, "custom_operation")

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["operation_type"] == "custom_operation"
        assert output["results"]["custom_field"] == "custom_value"

    def test_display_results_human_uses_consistent_header(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """Human-readable output uses consistent header format."""
        from ktrdr.cli.operation_runner import OperationRunner

        state = CLIState(json_mode=False)
        runner = OperationRunner(state)

        # Training results
        training_data = {
            "result_summary": {
                "training_metrics": {"epochs_trained": 10, "final_loss": 0.05},
            },
        }
        runner._display_results(training_data, "training")
        training_output = capsys.readouterr().out

        # Backtest results
        backtest_data = {
            "result_summary": {
                "metrics": {"total_return_pct": 0.10, "sharpe_ratio": 1.5},
            },
        }
        runner._display_results(backtest_data, "backtest")
        backtest_output = capsys.readouterr().out

        # Both should use consistent "Results:" header pattern
        assert "Training Results:" in training_output
        assert "Backtest Results:" in backtest_output

    def test_display_results_empty_summary_json_mode(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """Empty result_summary outputs empty results object in JSON mode."""
        from ktrdr.cli.operation_runner import OperationRunner

        state = CLIState(json_mode=True)
        runner = OperationRunner(state)

        op_data = {"status": "completed", "result_summary": {}}

        runner._display_results(op_data, "training")

        captured = capsys.readouterr()
        # Should still output valid JSON (even if empty or minimal)
        output = json.loads(captured.out)
        assert output["operation_type"] == "training"

    def test_display_results_none_summary_json_mode(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """None result_summary outputs appropriate JSON in JSON mode."""
        from ktrdr.cli.operation_runner import OperationRunner

        state = CLIState(json_mode=True)
        runner = OperationRunner(state)

        op_data = {"status": "completed", "result_summary": None}

        runner._display_results(op_data, "training")

        captured = capsys.readouterr()
        # Should output valid JSON with empty results dict
        output = json.loads(captured.out)
        assert output["operation_type"] == "training"
        assert output["results"] == {}
