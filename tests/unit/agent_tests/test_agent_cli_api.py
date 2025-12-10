"""
Unit tests for agent CLI commands using API.

These tests verify that the CLI commands call the API endpoints instead
of directly using the TriggerService and database.

Task 1.9 requirement: CLI `ktrdr agent trigger` and `ktrdr agent status`
should call API endpoints, not direct service calls.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from ktrdr.cli.agent_commands import agent_app

runner = CliRunner()


class TestAgentStatusViaAPI:
    """Tests for ktrdr agent status command using API."""

    def test_status_calls_api_endpoint(self):
        """Test that status command calls /agent/status API endpoint."""
        with patch("ktrdr.cli.agent_commands.AsyncCLIClient") as MockClient:
            # Setup mock client
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance._make_request = AsyncMock(
                return_value={
                    "has_active_session": False,
                    "session": None,
                    "agent_enabled": True,
                }
            )
            MockClient.return_value = mock_instance

            result = runner.invoke(agent_app, ["status"])

            # Verify API was called
            mock_instance._make_request.assert_called_once_with(
                "GET", "/agent/status", params={"verbose": False}
            )
            assert result.exit_code == 0

    def test_status_displays_active_session_from_api(self):
        """Test that status displays active session info from API response."""
        with patch("ktrdr.cli.agent_commands.AsyncCLIClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance._make_request = AsyncMock(
                return_value={
                    "has_active_session": True,
                    "session": {
                        "id": 42,
                        "phase": "designing",
                        "strategy_name": None,
                        "operation_id": None,
                        "created_at": "2024-12-09T10:00:00Z",
                        "updated_at": "2024-12-09T10:05:00Z",
                    },
                    "agent_enabled": True,
                }
            )
            MockClient.return_value = mock_instance

            result = runner.invoke(agent_app, ["status"])

            assert result.exit_code == 0
            assert "42" in result.output
            assert "designing" in result.output.lower()

    def test_status_verbose_passes_flag_to_api(self):
        """Test that --verbose flag is passed to API."""
        with patch("ktrdr.cli.agent_commands.AsyncCLIClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance._make_request = AsyncMock(
                return_value={
                    "has_active_session": False,
                    "session": None,
                    "agent_enabled": True,
                }
            )
            MockClient.return_value = mock_instance

            result = runner.invoke(agent_app, ["status", "--verbose"])

            # Verify verbose flag was passed
            mock_instance._make_request.assert_called_once_with(
                "GET", "/agent/status", params={"verbose": True}
            )
            assert result.exit_code == 0


class TestAgentTriggerViaAPI:
    """Tests for ktrdr agent trigger command using API."""

    def test_trigger_calls_api_endpoint(self):
        """Test that trigger command calls /agent/trigger API endpoint."""
        with patch("ktrdr.cli.agent_commands.AsyncCLIClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance._make_request = AsyncMock(
                return_value={
                    "success": True,
                    "triggered": True,
                    "session_id": 42,
                    "message": "Research cycle started",
                }
            )
            MockClient.return_value = mock_instance

            result = runner.invoke(agent_app, ["trigger"])

            # Verify API was called
            mock_instance._make_request.assert_called_once_with(
                "POST", "/agent/trigger", params={"dry_run": False}
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
                    "success": True,
                    "triggered": True,
                    "session_id": 42,
                    "message": "Research cycle started",
                }
            )
            MockClient.return_value = mock_instance

            result = runner.invoke(agent_app, ["trigger"])

            assert result.exit_code == 0
            # Should show success and session ID
            assert "42" in result.output or "success" in result.output.lower()

    def test_trigger_displays_not_triggered_reason(self):
        """Test that trigger displays reason when not triggered."""
        with patch("ktrdr.cli.agent_commands.AsyncCLIClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance._make_request = AsyncMock(
                return_value={
                    "success": True,
                    "triggered": False,
                    "reason": "active_session_exists",
                    "active_session_id": 41,
                    "message": "Active session already exists",
                }
            )
            MockClient.return_value = mock_instance

            result = runner.invoke(agent_app, ["trigger"])

            assert result.exit_code == 0
            assert (
                "active" in result.output.lower() or "exists" in result.output.lower()
            )

    def test_trigger_dry_run_passes_flag_to_api(self):
        """Test that --dry-run flag is passed to API."""
        with patch("ktrdr.cli.agent_commands.AsyncCLIClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance._make_request = AsyncMock(
                return_value={
                    "success": True,
                    "triggered": False,
                    "dry_run": True,
                    "would_trigger": True,
                    "message": "Dry run - would trigger new cycle",
                }
            )
            MockClient.return_value = mock_instance

            result = runner.invoke(agent_app, ["trigger", "--dry-run"])

            # Verify dry_run flag was passed
            mock_instance._make_request.assert_called_once_with(
                "POST", "/agent/trigger", params={"dry_run": True}
            )
            assert result.exit_code == 0

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
