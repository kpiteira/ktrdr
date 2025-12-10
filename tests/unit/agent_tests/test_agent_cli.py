"""
Unit tests for agent CLI commands.

Note: The main behavior tests for the CLI are now in test_agent_cli_api.py,
which tests the API-based implementation.

This file contains tests for CLI help output and basic structure.
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
        """Test that agent status --help shows options."""
        result = runner.invoke(agent_app, ["status", "--help"])

        assert result.exit_code == 0
        assert "verbose" in result.output.lower() or "-v" in result.output

    def test_trigger_help(self):
        """Test that agent trigger --help shows options."""
        result = runner.invoke(agent_app, ["trigger", "--help"])

        assert result.exit_code == 0
        # Check for either verbose or dry-run options
        output_lower = result.output.lower()
        assert "dry" in output_lower or "verbose" in output_lower
