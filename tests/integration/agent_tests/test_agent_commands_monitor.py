"""Unit tests for agent CLI monitor functionality.

Tests verify:
- ktrdr agent trigger --monitor - shows progress and waits for completion
- --follow and -f aliases work
- Polling loop handles terminal states (completed, failed, cancelled)
- Ctrl+C handling via signal handler

Task 9.2 of M9: CLI Monitor Flag + Polling
"""

from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from ktrdr.cli.agent_commands import agent_app

runner = CliRunner()


class TestMonitorFlagParsing:
    """Tests for --monitor, --follow, and -f flag parsing."""

    def test_trigger_help_shows_monitor_flag(self):
        """Test that trigger --help shows the monitor flag."""
        result = runner.invoke(agent_app, ["trigger", "--help"])

        assert result.exit_code == 0
        assert "--monitor" in result.output or "-f" in result.output

    def test_monitor_flag_accepted(self):
        """Test that --monitor flag is accepted by trigger command."""
        with patch("ktrdr.cli.agent_commands.AsyncCLIClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            # Trigger returns, then status shows completed
            mock_instance._make_request = AsyncMock(
                side_effect=[
                    {
                        "triggered": True,
                        "operation_id": "op_test_123",
                        "message": "Started",
                    },
                    # Status poll - completed immediately
                    {
                        "success": True,
                        "data": {
                            "operation_id": "op_test_123",
                            "status": "completed",
                            "progress": {"percentage": 100, "current_step": "Complete"},
                            "result": {"strategy_name": "test_strategy"},
                        },
                    },
                ]
            )
            MockClient.return_value = mock_instance

            result = runner.invoke(agent_app, ["trigger", "--monitor"])

            # Should not error out (flag was recognized)
            assert result.exit_code == 0

    def test_follow_alias_accepted(self):
        """Test that --follow alias is accepted by trigger command."""
        with patch("ktrdr.cli.agent_commands.AsyncCLIClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance._make_request = AsyncMock(
                side_effect=[
                    {
                        "triggered": True,
                        "operation_id": "op_test_123",
                        "message": "Started",
                    },
                    {
                        "success": True,
                        "data": {
                            "operation_id": "op_test_123",
                            "status": "completed",
                            "progress": {"percentage": 100, "current_step": "Complete"},
                            "result": {},
                        },
                    },
                ]
            )
            MockClient.return_value = mock_instance

            result = runner.invoke(agent_app, ["trigger", "--follow"])

            assert result.exit_code == 0

    def test_short_f_alias_accepted(self):
        """Test that -f short alias is accepted by trigger command."""
        with patch("ktrdr.cli.agent_commands.AsyncCLIClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance._make_request = AsyncMock(
                side_effect=[
                    {
                        "triggered": True,
                        "operation_id": "op_test_123",
                        "message": "Started",
                    },
                    {
                        "success": True,
                        "data": {
                            "operation_id": "op_test_123",
                            "status": "completed",
                            "progress": {"percentage": 100, "current_step": "Complete"},
                            "result": {},
                        },
                    },
                ]
            )
            MockClient.return_value = mock_instance

            result = runner.invoke(agent_app, ["trigger", "-f"])

            assert result.exit_code == 0

    def test_monitor_with_model_option(self):
        """Test that -m model -f both work together."""
        with patch("ktrdr.cli.agent_commands.AsyncCLIClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance._make_request = AsyncMock(
                side_effect=[
                    {
                        "triggered": True,
                        "operation_id": "op_test_123",
                        "model": "claude-haiku",
                        "message": "Started",
                    },
                    {
                        "success": True,
                        "data": {
                            "operation_id": "op_test_123",
                            "status": "completed",
                            "progress": {"percentage": 100, "current_step": "Complete"},
                            "result": {},
                        },
                    },
                ]
            )
            MockClient.return_value = mock_instance

            result = runner.invoke(agent_app, ["trigger", "-m", "haiku", "-f"])

            assert result.exit_code == 0


class TestMonitorPollingBehavior:
    """Tests for polling loop terminal state handling."""

    def test_polling_exits_on_completed_status(self):
        """Test that polling loop exits when status is 'completed'."""
        with patch("ktrdr.cli.agent_commands.AsyncCLIClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance._make_request = AsyncMock(
                side_effect=[
                    # Trigger response
                    {
                        "triggered": True,
                        "operation_id": "op_test_123",
                        "message": "Started",
                    },
                    # First poll - still running
                    {
                        "success": True,
                        "data": {
                            "operation_id": "op_test_123",
                            "status": "running",
                            "progress": {
                                "percentage": 50,
                                "current_step": "Training...",
                            },
                        },
                    },
                    # Second poll - completed
                    {
                        "success": True,
                        "data": {
                            "operation_id": "op_test_123",
                            "status": "completed",
                            "progress": {"percentage": 100, "current_step": "Complete"},
                            "result": {"strategy_name": "test_strat"},
                        },
                    },
                ]
            )
            MockClient.return_value = mock_instance

            # Patch asyncio.sleep to speed up test
            with patch(
                "ktrdr.cli.agent_commands.asyncio.sleep", new_callable=AsyncMock
            ):
                result = runner.invoke(agent_app, ["trigger", "--monitor"])

            assert result.exit_code == 0
            assert "complete" in result.output.lower()

    def test_polling_exits_on_failed_status(self):
        """Test that polling loop exits when status is 'failed'."""
        with patch("ktrdr.cli.agent_commands.AsyncCLIClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance._make_request = AsyncMock(
                side_effect=[
                    {
                        "triggered": True,
                        "operation_id": "op_test_123",
                        "message": "Started",
                    },
                    {
                        "success": True,
                        "data": {
                            "operation_id": "op_test_123",
                            "status": "failed",
                            "error": "Training failed: out of memory",
                        },
                    },
                ]
            )
            MockClient.return_value = mock_instance

            with patch(
                "ktrdr.cli.agent_commands.asyncio.sleep", new_callable=AsyncMock
            ):
                result = runner.invoke(agent_app, ["trigger", "--monitor"])

            assert result.exit_code == 0
            assert "failed" in result.output.lower()

    def test_polling_exits_on_cancelled_status(self):
        """Test that polling loop exits when status is 'cancelled'."""
        with patch("ktrdr.cli.agent_commands.AsyncCLIClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance._make_request = AsyncMock(
                side_effect=[
                    {
                        "triggered": True,
                        "operation_id": "op_test_123",
                        "message": "Started",
                    },
                    {
                        "success": True,
                        "data": {
                            "operation_id": "op_test_123",
                            "status": "cancelled",
                            "metadata": {"parameters": {"phase": "training"}},
                        },
                    },
                ]
            )
            MockClient.return_value = mock_instance

            with patch(
                "ktrdr.cli.agent_commands.asyncio.sleep", new_callable=AsyncMock
            ):
                result = runner.invoke(agent_app, ["trigger", "--monitor"])

            assert result.exit_code == 0
            assert "cancelled" in result.output.lower()


class TestMonitorCompletionSummary:
    """Tests for completion summary display."""

    def test_completion_shows_strategy_name(self):
        """Test that completion summary shows strategy name."""
        with patch("ktrdr.cli.agent_commands.AsyncCLIClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance._make_request = AsyncMock(
                side_effect=[
                    {
                        "triggered": True,
                        "operation_id": "op_test_123",
                        "message": "Started",
                    },
                    {
                        "success": True,
                        "data": {
                            "operation_id": "op_test_123",
                            "status": "completed",
                            "progress": {"percentage": 100, "current_step": "Complete"},
                            "result": {
                                "strategy_name": "momentum_breakout_v1",
                                "verdict": "promising",
                            },
                        },
                    },
                ]
            )
            MockClient.return_value = mock_instance

            with patch(
                "ktrdr.cli.agent_commands.asyncio.sleep", new_callable=AsyncMock
            ):
                result = runner.invoke(agent_app, ["trigger", "--monitor"])

            assert result.exit_code == 0
            assert "momentum_breakout_v1" in result.output

    def test_completion_shows_verdict(self):
        """Test that completion summary shows verdict."""
        with patch("ktrdr.cli.agent_commands.AsyncCLIClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance._make_request = AsyncMock(
                side_effect=[
                    {
                        "triggered": True,
                        "operation_id": "op_test_123",
                        "message": "Started",
                    },
                    {
                        "success": True,
                        "data": {
                            "operation_id": "op_test_123",
                            "status": "completed",
                            "progress": {"percentage": 100, "current_step": "Complete"},
                            "result": {
                                "strategy_name": "test_strat",
                                "verdict": "promising",
                            },
                        },
                    },
                ]
            )
            MockClient.return_value = mock_instance

            with patch(
                "ktrdr.cli.agent_commands.asyncio.sleep", new_callable=AsyncMock
            ):
                result = runner.invoke(agent_app, ["trigger", "--monitor"])

            assert result.exit_code == 0
            assert "promising" in result.output.lower()


class TestMonitorWithoutFlag:
    """Tests ensuring behavior without --monitor is unchanged."""

    def test_trigger_without_monitor_does_not_poll(self):
        """Test that trigger without --monitor returns immediately (fire-and-forget)."""
        with patch("ktrdr.cli.agent_commands.AsyncCLIClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance._make_request = AsyncMock(
                return_value={
                    "triggered": True,
                    "operation_id": "op_test_123",
                    "message": "Started",
                }
            )
            MockClient.return_value = mock_instance

            result = runner.invoke(agent_app, ["trigger"])

            assert result.exit_code == 0
            # Should only have called trigger, not polled
            assert mock_instance._make_request.call_count == 1
            # Output should mention using status command
            assert "status" in result.output.lower()
