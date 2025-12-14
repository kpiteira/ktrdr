"""Unit tests for simplified agent CLI commands.

Tests verify:
- ktrdr agent trigger - starts research cycle
- ktrdr agent status - shows current state
- No cancel command (use operations CLI)

Task 1.6 of M1: Simplified CLI matching new API.
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

    def test_no_cancel_command(self):
        """Test that cancel command is removed."""
        result = runner.invoke(agent_app, ["cancel", "123"])

        # Should fail - command doesn't exist
        assert result.exit_code != 0
