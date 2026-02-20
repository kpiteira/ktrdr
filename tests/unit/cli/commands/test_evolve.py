"""Tests for the evolve CLI command."""

from __future__ import annotations

from unittest.mock import patch

from ktrdr.cli.app import app


class TestEvolveCommandRegistration:
    """Tests for evolve command registration."""

    def test_evolve_command_exists(self, runner) -> None:
        """The evolve subcommand should appear in help."""
        result = runner.invoke(app, ["--help"])
        assert "evolve" in result.output.lower()

    def test_evolve_start_help(self, runner) -> None:
        """evolve start should have help text."""
        result = runner.invoke(app, ["evolve", "start", "--help"])
        assert result.exit_code == 0
        assert "--population" in result.output
        assert "--generations" in result.output
        assert "--symbol" in result.output
        assert "--timeframe" in result.output
        assert "--model" in result.output


class TestEvolveStartCommand:
    """Tests for evolve start execution."""

    def test_start_calls_harness(self, runner) -> None:
        """Start command should invoke the generation harness."""
        with patch(
            "ktrdr.cli.commands.evolve._run_evolution"
        ) as mock_run:
            mock_run.return_value = None
            result = runner.invoke(
                app,
                ["evolve", "start", "--population", "3", "--generations", "1"],
            )
            assert result.exit_code == 0
            mock_run.assert_called_once()

    def test_start_rejects_population_below_2(self, runner) -> None:
        """Population < 2 should be rejected."""
        result = runner.invoke(
            app, ["evolve", "start", "--population", "1"]
        )
        assert result.exit_code != 0

    def test_start_rejects_generations_below_1(self, runner) -> None:
        """Generations < 1 should be rejected."""
        result = runner.invoke(
            app, ["evolve", "start", "--generations", "0"]
        )
        assert result.exit_code != 0
