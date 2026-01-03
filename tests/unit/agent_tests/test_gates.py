"""Tests for quality gates with Baby mode thresholds.

Task 3.1: Verify gate thresholds match Baby stage values for exploration.
"""

from ktrdr.agents.gates import (
    BacktestGateConfig,
    TrainingGateConfig,
    check_backtest_gate,
    check_training_gate,
)


class TestTrainingGateConfig:
    """Tests for TrainingGateConfig Baby mode defaults."""

    def test_default_min_accuracy_is_baby_threshold(self):
        """Default min_accuracy should be 10% (Baby mode)."""
        config = TrainingGateConfig()
        assert config.min_accuracy == 0.10

    def test_default_min_loss_decrease_allows_regression(self):
        """Default min_loss_decrease should be -50% (allow exploration)."""
        config = TrainingGateConfig()
        assert config.min_loss_decrease == -0.5

    def test_default_max_loss_unchanged(self):
        """Default max_loss should remain 0.8."""
        config = TrainingGateConfig()
        assert config.max_loss == 0.8


class TestBacktestGateConfig:
    """Tests for BacktestGateConfig Baby mode defaults."""

    def test_default_min_win_rate_is_baby_threshold(self):
        """Default min_win_rate should be 10% (Baby mode)."""
        config = BacktestGateConfig()
        assert config.min_win_rate == 0.10


class TestTrainingGateCatastrophicCheck:
    """Tests for catastrophic failure detection (0% accuracy)."""

    def test_zero_accuracy_always_fails(self):
        """0% accuracy should always fail, regardless of other metrics."""
        metrics = {
            "test_metrics": {"test_accuracy": 0.0, "test_loss": 0.1},
        }
        config = TrainingGateConfig(min_accuracy=0.10)

        passed, reason = check_training_gate(metrics, config)

        assert not passed
        assert "0%" in reason or "accuracy" in reason.lower()

    def test_accuracy_below_baby_threshold_fails(self):
        """8% accuracy should fail Baby gate (< 10%)."""
        metrics = {
            "test_metrics": {"test_accuracy": 0.08, "test_loss": 0.3},
        }
        config = TrainingGateConfig(min_accuracy=0.10)

        passed, reason = check_training_gate(metrics, config)

        assert not passed
        assert "accuracy" in reason.lower()

    def test_accuracy_at_baby_threshold_passes(self):
        """10% accuracy should pass Baby gate."""
        metrics = {
            "test_metrics": {"test_accuracy": 0.10, "test_loss": 0.5},
        }
        config = TrainingGateConfig(min_accuracy=0.10, min_loss_decrease=-0.5)

        passed, reason = check_training_gate(metrics, config)

        assert passed
        assert reason == "passed"

    def test_15_percent_accuracy_passes_baby_gate(self):
        """15% accuracy should pass Baby gate."""
        metrics = {
            "test_metrics": {"test_accuracy": 0.15, "test_loss": 0.5},
        }
        config = TrainingGateConfig(min_accuracy=0.10, min_loss_decrease=-0.5)

        passed, reason = check_training_gate(metrics, config)

        assert passed

    def test_30_percent_accuracy_passes_baby_gate(self):
        """30% accuracy should pass Baby gate (would fail old 45% threshold)."""
        metrics = {
            "test_metrics": {"test_accuracy": 0.30, "test_loss": 0.5},
        }
        config = TrainingGateConfig(min_accuracy=0.10, min_loss_decrease=-0.5)

        passed, reason = check_training_gate(metrics, config)

        assert passed


class TestTrainingGateLossDecrease:
    """Tests for loss decrease check in Baby mode."""

    def test_50_percent_loss_regression_passes_baby_gate(self):
        """50% loss regression (decrease = -0.5) should pass Baby gate.

        Baby mode allows exploration, even if loss regresses.
        """
        metrics = {
            "test_metrics": {"test_accuracy": 0.30, "test_loss": 0.5},
            "training_metrics": {
                "history": {"train_loss": [0.4, 0.6]},  # Loss increased from 0.4 to 0.6
                "final_train_loss": 0.6,
            },
        }
        # Loss decrease = (0.4 - 0.6) / 0.4 = -0.5 (50% regression)
        config = TrainingGateConfig(min_accuracy=0.10, min_loss_decrease=-0.5)

        passed, reason = check_training_gate(metrics, config)

        assert passed

    def test_large_loss_regression_fails_baby_gate(self):
        """60% loss regression should fail even Baby gate."""
        metrics = {
            "test_metrics": {"test_accuracy": 0.30, "test_loss": 0.8},
            "training_metrics": {
                "history": {"train_loss": [0.5, 0.8]},  # Loss increased from 0.5 to 0.8
                "final_train_loss": 0.8,
            },
        }
        # Loss decrease = (0.5 - 0.8) / 0.5 = -0.6 (60% regression)
        config = TrainingGateConfig(min_accuracy=0.10, min_loss_decrease=-0.5)

        passed, reason = check_training_gate(metrics, config)

        assert not passed
        assert "loss" in reason.lower()


class TestBacktestGateBabyMode:
    """Tests for backtest gate in Baby mode."""

    def test_low_win_rate_passes_baby_gate(self):
        """15% win rate should pass Baby gate (would fail old 45% threshold)."""
        metrics = {
            "win_rate": 0.15,
            "max_drawdown": 0.3,
            "sharpe_ratio": 0.0,
        }
        config = BacktestGateConfig(min_win_rate=0.10)

        passed, reason = check_backtest_gate(metrics, config)

        assert passed

    def test_very_low_win_rate_fails_baby_gate(self):
        """5% win rate should fail even Baby gate."""
        metrics = {
            "win_rate": 0.05,
            "max_drawdown": 0.3,
            "sharpe_ratio": 0.0,
        }
        config = BacktestGateConfig(min_win_rate=0.10)

        passed, reason = check_backtest_gate(metrics, config)

        assert not passed
        assert "win_rate" in reason.lower()
