"""
Tests for the sandbox CLI subcommand module.

Task 2.3: Verify the sandbox CLI module is properly registered and provides help.
"""

import pytest
from typer.testing import CliRunner

from ktrdr.cli import cli_app


@pytest.fixture
def runner():
    """Create a Typer CLI runner for testing."""
    return CliRunner()


class TestSandboxCLIRegistration:
    """Tests that sandbox CLI is properly registered."""

    def test_sandbox_module_imports_without_error(self):
        """Verify sandbox module can be imported."""
        # This will fail if the module doesn't exist or has import errors
        from ktrdr.cli.sandbox import sandbox_app

        assert sandbox_app is not None
        assert sandbox_app.info.name == "sandbox"

    def test_sandbox_registered_in_cli(self, runner):
        """Verify sandbox subcommand is registered in main CLI."""
        result = runner.invoke(cli_app, ["--help"])

        assert result.exit_code == 0
        assert "sandbox" in result.output.lower()

    def test_sandbox_help_displays(self, runner):
        """Verify 'ktrdr sandbox --help' shows help text."""
        result = runner.invoke(cli_app, ["sandbox", "--help"])

        assert result.exit_code == 0
        assert "sandbox" in result.output.lower()
        # Should describe what sandbox does
        assert "isolated" in result.output.lower() or "manage" in result.output.lower()

    def test_sandbox_no_args_shows_help(self, runner):
        """Verify 'ktrdr sandbox' with no args shows help (no_args_is_help=True)."""
        result = runner.invoke(cli_app, ["sandbox"])

        # With no_args_is_help=True, Typer shows help but returns exit code 2
        # (standard behavior - help shown but no command executed)
        assert result.exit_code == 2
        assert "Usage" in result.output or "usage" in result.output.lower()
