"""Tests for kinfra deploy commands.

Tests that deploy commands are registered under kinfra and work correctly.
"""


class TestKinfraDeployRegistration:
    """Tests that deploy subcommands are registered under kinfra."""

    def test_deploy_subgroup_registered(self, runner) -> None:
        """kinfra --help should show deploy subcommand."""
        from ktrdr.cli.kinfra.main import app

        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "deploy" in result.output.lower()

    def test_deploy_help_works(self, runner) -> None:
        """kinfra deploy --help should return without error."""
        from ktrdr.cli.kinfra.main import app

        result = runner.invoke(app, ["deploy", "--help"])
        assert result.exit_code == 0

    def test_deploy_help_shows_subcommands(self, runner) -> None:
        """kinfra deploy --help should list available commands."""
        from ktrdr.cli.kinfra.main import app

        result = runner.invoke(app, ["deploy", "--help"])
        assert result.exit_code == 0
        help_lower = result.output.lower()
        # Should have key subcommands
        assert "core" in help_lower
        assert "workers" in help_lower
        assert "status" in help_lower


class TestKinfraDeployStatusCommand:
    """Tests for kinfra deploy status command."""

    def test_status_command_exists(self, runner) -> None:
        """kinfra deploy status --help should work."""
        from ktrdr.cli.kinfra.main import app

        result = runner.invoke(app, ["deploy", "status", "--help"])
        assert result.exit_code == 0
