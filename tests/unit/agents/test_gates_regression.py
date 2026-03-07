"""Tests for regression-specific gate checks."""

from ktrdr.agents.gates import (
    BacktestGateConfig,
    TrainingGateConfig,
    check_backtest_gate,
    check_training_gate,
)


class TestTrainingGateRegression:
    """Training gate checks for regression output_format."""

    def test_regression_passes_with_good_directional_accuracy(self):
        """Regression gate passes when directional_accuracy > 0.5."""
        metrics = {
            "output_format": "regression",
            "test_metrics": {
                "directional_accuracy": 0.55,
                "test_loss": 0.001,
            },
            "training_metrics": {"history": {"train_loss": [0.01, 0.005]}},
        }
        passed, reason = check_training_gate(metrics)
        assert passed is True
        assert reason == "passed"

    def test_regression_fails_on_low_directional_accuracy(self):
        """Regression gate fails when directional_accuracy <= 0.5."""
        metrics = {
            "output_format": "regression",
            "test_metrics": {
                "directional_accuracy": 0.45,
                "test_loss": 0.001,
            },
        }
        passed, reason = check_training_gate(metrics)
        assert passed is False
        assert (
            "directional_accuracy" in reason.lower() or "directional" in reason.lower()
        )

    def test_regression_fails_on_exactly_50_percent(self):
        """Directional accuracy at exactly 50% should fail (must beat coin flip)."""
        metrics = {
            "output_format": "regression",
            "test_metrics": {
                "directional_accuracy": 0.50,
                "test_loss": 0.001,
            },
        }
        passed, reason = check_training_gate(metrics)
        assert passed is False

    def test_regression_still_checks_loss(self):
        """Regression training gate still checks max_loss."""
        metrics = {
            "output_format": "regression",
            "test_metrics": {
                "directional_accuracy": 0.6,
                "test_loss": 0.9,
            },
        }
        passed, reason = check_training_gate(metrics)
        assert passed is False
        assert "loss" in reason.lower()

    def test_classification_gate_unchanged(self):
        """Classification gate still uses accuracy check."""
        metrics = {
            "test_metrics": {"test_accuracy": 0.15, "test_loss": 0.5},
        }
        passed, reason = check_training_gate(metrics)
        assert passed is True

    def test_classification_gate_fails_on_low_accuracy(self):
        """Classification gate fails with low accuracy."""
        metrics = {
            "test_metrics": {"test_accuracy": 0.05, "test_loss": 0.5},
        }
        passed, reason = check_training_gate(metrics)
        assert passed is False
        assert "accuracy" in reason.lower()

    def test_default_no_output_format_is_classification(self):
        """Without output_format, gate behaves as classification."""
        metrics = {
            "test_metrics": {"test_accuracy": 0.15, "test_loss": 0.5},
        }
        passed, reason = check_training_gate(metrics)
        assert passed is True

    def test_regression_config_from_env(self, monkeypatch):
        """TrainingGateConfig loads regression fields from env."""
        monkeypatch.setenv("TRAINING_GATE_MIN_DIRECTIONAL_ACCURACY", "0.55")
        config = TrainingGateConfig.from_env()
        assert config.min_directional_accuracy == 0.55


class TestBacktestGateRegression:
    """Backtest gate checks for regression output_format."""

    def test_regression_passes_with_good_metrics(self):
        """Regression backtest gate passes with positive return and enough trades."""
        metrics = {
            "output_format": "regression",
            "net_return": 0.01,
            "trade_count": 10,
            "win_rate": 0.5,
            "max_drawdown": 0.1,
            "sharpe_ratio": 0.5,
        }
        passed, reason = check_backtest_gate(metrics)
        assert passed is True

    def test_regression_fails_on_negative_net_return(self):
        """Regression backtest gate fails when net_return < 0."""
        metrics = {
            "output_format": "regression",
            "net_return": -0.05,
            "trade_count": 10,
            "win_rate": 0.5,
            "max_drawdown": 0.1,
            "sharpe_ratio": 0.5,
        }
        passed, reason = check_backtest_gate(metrics)
        assert passed is False
        assert "net_return" in reason.lower() or "return" in reason.lower()

    def test_regression_fails_on_too_few_trades(self):
        """Regression backtest gate fails when trade_count < 5."""
        metrics = {
            "output_format": "regression",
            "net_return": 0.01,
            "trade_count": 3,
            "win_rate": 0.5,
            "max_drawdown": 0.1,
            "sharpe_ratio": 0.5,
        }
        passed, reason = check_backtest_gate(metrics)
        assert passed is False
        assert "trade" in reason.lower()

    def test_classification_backtest_gate_unchanged(self):
        """Classification backtest gate still uses win_rate check."""
        metrics = {
            "win_rate": 0.15,
            "max_drawdown": 0.1,
            "sharpe_ratio": 0.5,
        }
        passed, reason = check_backtest_gate(metrics)
        assert passed is True

    def test_regression_backtest_config_from_env(self, monkeypatch):
        """BacktestGateConfig loads regression fields from env."""
        monkeypatch.setenv("BACKTEST_GATE_MIN_NET_RETURN", "0.01")
        monkeypatch.setenv("BACKTEST_GATE_MIN_TRADES", "10")
        config = BacktestGateConfig.from_env()
        assert config.min_net_return == 0.01
        assert config.min_trades == 10
