"""Unit tests for simplified agent CLI commands.

Tests verify:
- ktrdr agent trigger - starts research cycle
- ktrdr agent status - shows current state
- ktrdr agent cancel - cancels active cycle (M6 Task 6.3)

Task 1.6 of M1: Simplified CLI matching new API.
Task 6.3 of M6: Add cancel command.
"""

from typer.testing import CliRunner

from ktrdr.cli.agent_commands import agent_app

runner = CliRunner()


class TestAgentCommandsHelp:
    """Tests for CLI help output."""

    def test_agent_help(self):
        """Test that agent --help shows available commands."""
        result = runner.invoke(agent_app, ["--help"])

        assert result.exit_code == 0
        assert "status" in result.output
        assert "trigger" in result.output
        assert "cancel" in result.output

    def test_status_help(self):
        """Test that agent status --help shows description."""
        result = runner.invoke(agent_app, ["status", "--help"])

        assert result.exit_code == 0
        assert "status" in result.output.lower()

    def test_trigger_help(self):
        """Test that agent trigger --help shows description."""
        result = runner.invoke(agent_app, ["trigger", "--help"])

        assert result.exit_code == 0
        assert "trigger" in result.output.lower() or "cycle" in result.output.lower()

    def test_cancel_help(self):
        """Test that agent cancel --help shows description."""
        result = runner.invoke(agent_app, ["cancel", "--help"])

        assert result.exit_code == 0
        assert "cancel" in result.output.lower()

    def test_budget_help(self):
        """Test that agent budget --help shows description."""
        result = runner.invoke(agent_app, ["budget", "--help"])

        assert result.exit_code == 0
        assert "budget" in result.output.lower()

    def test_agent_help_includes_budget(self):
        """Test that agent --help shows budget command."""
        result = runner.invoke(agent_app, ["--help"])

        assert result.exit_code == 0
        assert "budget" in result.output
