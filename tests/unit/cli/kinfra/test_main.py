"""Tests for kinfra CLI main app.

Tests the kinfra CLI entry point - the infrastructure CLI for sandbox,
deployment, and worktree management.
"""

import typer


class TestKinfraAppExists:
    """Tests that kinfra app is properly configured."""

    def test_kinfra_app_is_typer_instance(self) -> None:
        """kinfra app should be a Typer instance."""
        from ktrdr.cli.kinfra.main import app

        assert isinstance(app, typer.Typer)

    def test_kinfra_app_has_correct_name(self) -> None:
        """kinfra app should have name 'kinfra'."""
        from ktrdr.cli.kinfra.main import app

        assert app.info.name == "kinfra"


class TestKinfraHelp:
    """Tests for kinfra --help output."""

    def test_kinfra_help_returns_without_error(self, runner) -> None:
        """kinfra --help should return exit code 0."""
        from ktrdr.cli.kinfra.main import app

        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

    def test_kinfra_help_shows_infrastructure_cli(self, runner) -> None:
        """Help text should mention Infrastructure CLI."""
        from ktrdr.cli.kinfra.main import app

        result = runner.invoke(app, ["--help"])
        assert "infrastructure" in result.output.lower()

    def test_kinfra_no_args_shows_help(self, runner) -> None:
        """Running kinfra with no args should show help (no_args_is_help=True)."""
        from ktrdr.cli.kinfra.main import app

        result = runner.invoke(app, [])
        # no_args_is_help shows help, exit code varies by typer version
        # The important thing is that help is shown
        assert (
            "infrastructure" in result.output.lower()
            or "usage" in result.output.lower()
        )
