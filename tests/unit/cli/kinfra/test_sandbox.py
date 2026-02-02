"""Tests for kinfra sandbox commands.

Tests that sandbox commands are registered under kinfra and work correctly.
"""


class TestKinfraSandboxRegistration:
    """Tests that sandbox subcommands are registered under kinfra."""

    def test_sandbox_subgroup_registered(self, runner) -> None:
        """kinfra --help should show sandbox subcommand."""
        from ktrdr.cli.kinfra.main import app

        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "sandbox" in result.output.lower()

    def test_sandbox_help_works(self, runner) -> None:
        """kinfra sandbox --help should return without error."""
        from ktrdr.cli.kinfra.main import app

        result = runner.invoke(app, ["sandbox", "--help"])
        assert result.exit_code == 0

    def test_sandbox_help_shows_subcommands(self, runner) -> None:
        """kinfra sandbox --help should list available commands."""
        from ktrdr.cli.kinfra.main import app

        result = runner.invoke(app, ["sandbox", "--help"])
        assert result.exit_code == 0
        help_lower = result.output.lower()
        # Should have key subcommands
        assert "status" in help_lower
        assert "list" in help_lower
        assert "up" in help_lower
        assert "down" in help_lower


class TestKinfraSandboxStatusCommand:
    """Tests for kinfra sandbox status command."""

    def test_status_command_exists(self, runner) -> None:
        """kinfra sandbox status --help should work."""
        from ktrdr.cli.kinfra.main import app

        result = runner.invoke(app, ["sandbox", "status", "--help"])
        assert result.exit_code == 0


class TestKinfraSandboxListCommand:
    """Tests for kinfra sandbox list command."""

    def test_list_command_exists(self, runner) -> None:
        """kinfra sandbox list --help should work."""
        from ktrdr.cli.kinfra.main import app

        result = runner.invoke(app, ["sandbox", "list", "--help"])
        assert result.exit_code == 0
