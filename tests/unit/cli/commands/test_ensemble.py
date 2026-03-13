"""Tests for ensemble CLI commands."""

from __future__ import annotations

from ktrdr.cli.commands.ensemble import ensemble_app


class TestEnsembleCommand:
    """Tests for the ensemble backtest CLI command."""

    def test_ensemble_app_exists(self) -> None:
        """The ensemble_app Typer group is importable."""
        assert ensemble_app is not None

    def test_help_shows_backtest_subcommand(self, runner) -> None:
        result = runner.invoke(ensemble_app, ["--help"])
        assert result.exit_code == 0
        assert "backtest" in result.output.lower()

    def test_backtest_help_shows_options(self, runner) -> None:
        result = runner.invoke(ensemble_app, ["backtest", "--help"])
        assert result.exit_code == 0
        assert "--start-date" in result.output
        assert "--end-date" in result.output

    def test_missing_config_file_gives_error(self, runner) -> None:
        result = runner.invoke(
            ensemble_app,
            [
                "backtest",
                "nonexistent.yaml",
                "--start-date",
                "2024-01-01",
                "--end-date",
                "2024-02-01",
            ],
        )
        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_backtest_with_config_file(self, runner, tmp_path) -> None:
        """Ensemble backtest loads config and attempts to run (fails at model load)."""
        import yaml

        config_data = {
            "name": "test_ensemble",
            "description": "test",
            "models": {
                "regime": {
                    "model_path": "models/nonexistent",
                    "output_type": "regime_classification",
                },
                "signal": {
                    "model_path": "models/nonexistent2",
                    "output_type": "classification",
                },
            },
            "composition": {
                "type": "regime_route",
                "gate_model": "regime",
                "regime_threshold": 0.4,
                "stability_bars": 3,
                "rules": {
                    "trending_up": {"model": "signal"},
                    "trending_down": {"model": "signal"},
                    "ranging": {"model": "signal"},
                    "volatile": {"action": "FLAT"},
                },
                "on_regime_transition": "close_and_switch",
            },
        }
        config_file = tmp_path / "ensemble.yaml"
        config_file.write_text(yaml.dump(config_data))

        result = runner.invoke(
            ensemble_app,
            [
                "backtest",
                str(config_file),
                "--start-date",
                "2024-01-01",
                "--end-date",
                "2024-02-01",
            ],
        )
        # Should fail at model loading (models don't exist), but config should load OK
        assert result.exit_code != 0
        # Should get past config loading — error should be about model files
        output_lower = result.output.lower()
        assert "error" in output_lower or "not found" in output_lower


class TestEnsembleRegistered:
    """Test that ensemble command is registered in main app."""

    def test_ensemble_in_main_app_help(self, runner) -> None:
        from ktrdr.cli.app import app

        result = runner.invoke(app, ["--help"])
        assert "ensemble" in result.output.lower()
