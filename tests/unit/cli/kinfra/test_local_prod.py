"""Tests for kinfra local-prod commands.

Tests that local-prod commands are registered under kinfra and work correctly.
"""


class TestKinfraLocalProdRegistration:
    """Tests that local-prod subcommands are registered under kinfra."""

    def test_local_prod_subgroup_registered(self, runner) -> None:
        """kinfra --help should show local-prod subcommand."""
        from ktrdr.cli.kinfra.main import app

        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "local-prod" in result.output.lower()

    def test_local_prod_help_works(self, runner) -> None:
        """kinfra local-prod --help should return without error."""
        from ktrdr.cli.kinfra.main import app

        result = runner.invoke(app, ["local-prod", "--help"])
        assert result.exit_code == 0

    def test_local_prod_help_shows_subcommands(self, runner) -> None:
        """kinfra local-prod --help should list available commands."""
        from ktrdr.cli.kinfra.main import app

        result = runner.invoke(app, ["local-prod", "--help"])
        assert result.exit_code == 0
        help_lower = result.output.lower()
        # Should have key subcommands
        assert "status" in help_lower
        assert "up" in help_lower
        assert "down" in help_lower
        assert "init" in help_lower


class TestKinfraLocalProdStatusCommand:
    """Tests for kinfra local-prod status command."""

    def test_status_command_exists(self, runner) -> None:
        """kinfra local-prod status --help should work."""
        from ktrdr.cli.kinfra.main import app

        result = runner.invoke(app, ["local-prod", "status", "--help"])
        assert result.exit_code == 0
