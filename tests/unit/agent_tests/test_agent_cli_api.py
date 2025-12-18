"""Unit tests for simplified agent CLI commands using API.

Tests verify that the CLI commands call the simplified API endpoints:
- POST /agent/trigger (no params)
- GET /agent/status (no params)
- DELETE /agent/cancel (no params) - M6 Task 6.3

Task 1.6 of M1: Simplified CLI matching new API contract.
Task 6.3 of M6: Add cancel command.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from ktrdr.cli.agent_commands import agent_app

runner = CliRunner()


class TestAgentStatusViaAPI:
    """Tests for ktrdr agent status command using simplified API."""

    def test_status_calls_api_endpoint(self):
        """Test that status command calls /agent/status API endpoint."""
        with patch("ktrdr.cli.agent_commands.AsyncCLIClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance._make_request = AsyncMock(
                return_value={
                    "status": "idle",
                    "last_cycle": None,
                }
            )
            MockClient.return_value = mock_instance

            result = runner.invoke(agent_app, ["status"])

            # Verify API was called (no params now)
            mock_instance._make_request.assert_called_once_with("GET", "/agent/status")
            assert result.exit_code == 0

    def test_status_displays_active_cycle(self):
        """Test that status displays active cycle info from API response."""
        with patch("ktrdr.cli.agent_commands.AsyncCLIClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance._make_request = AsyncMock(
                return_value={
                    "status": "active",
                    "operation_id": "op_agent_research_12345",
                    "phase": "training",
                    "progress": None,
                    "strategy_name": "momentum_v1",
                    "started_at": "2024-12-13T10:00:00Z",
                }
            )
            MockClient.return_value = mock_instance

            result = runner.invoke(agent_app, ["status"])

            assert result.exit_code == 0
            assert "active" in result.output.lower()
            assert "training" in result.output.lower()

    def test_status_displays_idle_with_last_cycle(self):
        """Test that status displays last cycle info when idle."""
        with patch("ktrdr.cli.agent_commands.AsyncCLIClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance._make_request = AsyncMock(
                return_value={
                    "status": "idle",
                    "last_cycle": {
                        "operation_id": "op_agent_research_previous",
                        "outcome": "completed",
                        "strategy_name": "momentum_v1",
                        "completed_at": "2024-12-13T12:00:00Z",
                    },
                }
            )
            MockClient.return_value = mock_instance

            result = runner.invoke(agent_app, ["status"])

            assert result.exit_code == 0
            assert "idle" in result.output.lower()
            assert "completed" in result.output.lower()


class TestAgentTriggerViaAPI:
    """Tests for ktrdr agent trigger command using simplified API."""

    def test_trigger_calls_api_endpoint(self):
        """Test that trigger command calls /agent/trigger API endpoint."""
        with patch("ktrdr.cli.agent_commands.AsyncCLIClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance._make_request = AsyncMock(
                return_value={
                    "triggered": True,
                    "operation_id": "op_agent_research_12345",
                    "message": "Research cycle started",
                }
            )
            MockClient.return_value = mock_instance

            result = runner.invoke(agent_app, ["trigger"])

            # Verify API was called (no params now)
            mock_instance._make_request.assert_called_once_with(
                "POST", "/agent/trigger"
            )
            assert result.exit_code == 0

    def test_trigger_displays_success_message(self):
        """Test that trigger displays success message from API."""
        with patch("ktrdr.cli.agent_commands.AsyncCLIClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance._make_request = AsyncMock(
                return_value={
                    "triggered": True,
                    "operation_id": "op_agent_research_12345",
                    "message": "Research cycle started",
                }
            )
            MockClient.return_value = mock_instance

            result = runner.invoke(agent_app, ["trigger"])

            assert result.exit_code == 0
            assert "op_agent_research_12345" in result.output

    def test_trigger_displays_conflict_reason(self):
        """Test that trigger displays reason when cycle already active."""
        with patch("ktrdr.cli.agent_commands.AsyncCLIClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance._make_request = AsyncMock(
                return_value={
                    "triggered": False,
                    "reason": "active_cycle_exists",
                    "operation_id": "op_agent_research_existing",
                    "message": "Active cycle exists: op_agent_research_existing",
                }
            )
            MockClient.return_value = mock_instance

            result = runner.invoke(agent_app, ["trigger"])

            assert result.exit_code == 0
            assert (
                "active" in result.output.lower() or "exists" in result.output.lower()
            )

    def test_trigger_handles_api_error(self):
        """Test that trigger handles API errors gracefully."""
        with patch("ktrdr.cli.agent_commands.AsyncCLIClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance._make_request = AsyncMock(
                side_effect=Exception("API connection failed")
            )
            MockClient.return_value = mock_instance

            result = runner.invoke(agent_app, ["trigger"])

            # Should handle error gracefully
            assert result.exit_code == 1
            assert "error" in result.output.lower()


class TestAgentCancelViaAPI:
    """Tests for ktrdr agent cancel command using simplified API - M6 Task 6.3."""

    def test_cancel_calls_api_endpoint(self):
        """Test that cancel command calls /agent/cancel API endpoint."""
        with patch("ktrdr.cli.agent_commands.AsyncCLIClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance._make_request = AsyncMock(
                return_value={
                    "success": True,
                    "operation_id": "op_agent_research_12345",
                    "child_cancelled": "op_training_67890",
                    "message": "Research cycle cancelled",
                }
            )
            MockClient.return_value = mock_instance

            result = runner.invoke(agent_app, ["cancel"])

            # Verify API was called with DELETE method
            mock_instance._make_request.assert_called_once_with(
                "DELETE", "/agent/cancel"
            )
            assert result.exit_code == 0

    def test_cancel_displays_success_message(self):
        """Test that cancel displays success message with operation IDs."""
        with patch("ktrdr.cli.agent_commands.AsyncCLIClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance._make_request = AsyncMock(
                return_value={
                    "success": True,
                    "operation_id": "op_agent_research_12345",
                    "child_cancelled": "op_training_67890",
                    "message": "Research cycle cancelled",
                }
            )
            MockClient.return_value = mock_instance

            result = runner.invoke(agent_app, ["cancel"])

            assert result.exit_code == 0
            assert "cancelled" in result.output.lower()
            assert "op_agent_research_12345" in result.output

    def test_cancel_displays_child_operation_id(self):
        """Test that cancel shows child operation ID when present."""
        with patch("ktrdr.cli.agent_commands.AsyncCLIClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance._make_request = AsyncMock(
                return_value={
                    "success": True,
                    "operation_id": "op_agent_research_12345",
                    "child_cancelled": "op_training_67890",
                    "message": "Research cycle cancelled",
                }
            )
            MockClient.return_value = mock_instance

            result = runner.invoke(agent_app, ["cancel"])

            assert result.exit_code == 0
            assert "op_training_67890" in result.output

    def test_cancel_displays_no_active_cycle_message(self):
        """Test that cancel displays clear message when no active cycle.

        The API returns 404 for no active cycle, which raises AsyncCLIClientError.
        The CLI should handle this gracefully and display a friendly message.
        """
        from ktrdr.cli.async_cli_client import AsyncCLIClientError

        with patch("ktrdr.cli.agent_commands.AsyncCLIClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            # API returns 404 which raises exception
            mock_instance._make_request = AsyncMock(
                side_effect=AsyncCLIClientError(
                    "API request failed: No active research cycle to cancel"
                )
            )
            MockClient.return_value = mock_instance

            result = runner.invoke(agent_app, ["cancel"])

            assert result.exit_code == 0
            assert "no active" in result.output.lower()

    def test_cancel_handles_api_error(self):
        """Test that cancel handles API errors gracefully."""
        with patch("ktrdr.cli.agent_commands.AsyncCLIClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance._make_request = AsyncMock(
                side_effect=Exception("API connection failed")
            )
            MockClient.return_value = mock_instance

            result = runner.invoke(agent_app, ["cancel"])

            # Should handle error gracefully
            assert result.exit_code == 1
            assert "error" in result.output.lower()
