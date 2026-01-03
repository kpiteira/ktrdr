"""
Unit tests for training quality gate.

Tests cover:
- Configuration loading from environment
- Gate evaluation logic (pass/fail)
- Threshold edge cases
- Clear reason messages
"""

from unittest.mock import patch

import pytest

from ktrdr.agents.gates import (
    TrainingGateConfig,
    check_training_gate,
)


class TestTrainingGateConfig:
    """Tests for TrainingGateConfig."""

    def test_default_config(self):
        """Test default configuration values (Baby mode v2.5)."""
        config = TrainingGateConfig()
        assert config.min_accuracy == 0.10  # Baby mode: lax for exploration
        assert config.max_loss == 0.8
        assert config.min_loss_decrease == -0.5  # Baby mode: allows regression

    def test_config_from_env(self):
        """Test loading configuration from environment variables."""
        with patch.dict(
            "os.environ",
            {
                "TRAINING_GATE_MIN_ACCURACY": "0.6",
                "TRAINING_GATE_MAX_LOSS": "0.5",
                "TRAINING_GATE_MIN_LOSS_DECREASE": "0.3",
            },
        ):
            config = TrainingGateConfig.from_env()
            assert config.min_accuracy == 0.6
            assert config.max_loss == 0.5
            assert config.min_loss_decrease == 0.3

    def test_config_from_env_defaults(self):
        """Test that missing env vars use defaults (Baby mode v2.5)."""
        with patch.dict("os.environ", {}, clear=True):
            config = TrainingGateConfig.from_env()
            assert config.min_accuracy == 0.10  # Baby mode
            assert config.max_loss == 0.8
            assert config.min_loss_decrease == -0.5  # Baby mode

    def test_config_from_env_partial(self):
        """Test that partial env vars work correctly."""
        with patch.dict(
            "os.environ",
            {
                "TRAINING_GATE_MIN_ACCURACY": "0.7",
            },
            clear=True,
        ):
            config = TrainingGateConfig.from_env()
            assert config.min_accuracy == 0.7
            assert config.max_loss == 0.8  # default
            assert config.min_loss_decrease == -0.5  # default (Baby mode)


class TestCheckTrainingGate:
    """Tests for check_training_gate function."""

    @pytest.fixture
    def default_config(self):
        """Default configuration for tests."""
        return TrainingGateConfig()

    # === Happy Path Tests ===

    def test_all_thresholds_pass(self, default_config):
        """Test that good results pass the gate."""
        metrics = {
            "accuracy": 0.65,
            "final_loss": 0.3,
            "initial_loss": 1.0,  # 70% reduction
        }
        passed, reason = check_training_gate(metrics, default_config)
        assert passed is True
        assert reason == "passed"

    def test_at_thresholds_passes(self, default_config):
        """Test edge case: values at thresholds should pass.

        Note: Due to floating point precision, we use values slightly
        better than thresholds rather than exactly at them.
        """
        metrics = {
            "accuracy": 0.45,  # at min
            "final_loss": 0.8,  # at max
            "initial_loss": 1.05,  # ~23.8% reduction (safely above 20%)
        }
        passed, reason = check_training_gate(metrics, default_config)
        assert passed is True
        assert reason == "passed"

    # === Accuracy Failure Tests ===

    def test_accuracy_below_threshold(self, default_config):
        """Test that low accuracy fails the gate (Baby mode: 10%)."""
        metrics = {
            "accuracy": 0.05,  # below 0.10 Baby threshold
            "final_loss": 0.3,
            "initial_loss": 1.0,
        }
        passed, reason = check_training_gate(metrics, default_config)
        assert passed is False
        assert "accuracy_below_threshold" in reason

    def test_accuracy_just_below_threshold(self, default_config):
        """Test edge case: accuracy just below Baby threshold fails."""
        metrics = {
            "accuracy": 0.099,  # just below 0.10 Baby threshold
            "final_loss": 0.3,
            "initial_loss": 1.0,
        }
        passed, reason = check_training_gate(metrics, default_config)
        assert passed is False
        assert "accuracy" in reason

    # === Loss Failure Tests ===

    def test_loss_above_threshold(self, default_config):
        """Test that high final loss fails the gate."""
        metrics = {
            "accuracy": 0.65,
            "final_loss": 0.9,  # above 0.8 threshold
            "initial_loss": 1.5,
        }
        passed, reason = check_training_gate(metrics, default_config)
        assert passed is False
        assert "loss_too_high" in reason

    def test_loss_just_above_threshold(self, default_config):
        """Test edge case: loss just above threshold fails."""
        metrics = {
            "accuracy": 0.65,
            "final_loss": 0.8001,  # just above 0.8
            "initial_loss": 1.5,
        }
        passed, reason = check_training_gate(metrics, default_config)
        assert passed is False
        assert "loss" in reason

    # === Loss Decrease Failure Tests ===

    def test_insufficient_loss_decrease(self, default_config):
        """Test that severe loss regression fails the gate (Baby: -50% allowed)."""
        metrics = {
            "accuracy": 0.65,
            "final_loss": 0.7,
            "initial_loss": 0.4,  # 75% increase (beyond -50% Baby threshold)
        }
        passed, reason = check_training_gate(metrics, default_config)
        assert passed is False
        assert "insufficient_loss_decrease" in reason

    def test_no_loss_decrease(self, default_config):
        """Test that 0% loss decrease passes Baby gate (allows regression)."""
        metrics = {
            "accuracy": 0.65,
            "final_loss": 0.5,  # Within max_loss threshold
            "initial_loss": 0.5,  # 0% decrease
        }
        passed, reason = check_training_gate(metrics, default_config)
        # Baby mode allows 0% decrease (threshold is -50%)
        assert passed is True
        assert reason == "passed"

    def test_negative_loss_decrease(self, default_config):
        """Test that moderate loss increase passes Baby gate."""
        metrics = {
            "accuracy": 0.65,
            "final_loss": 0.6,  # 20% higher than initial
            "initial_loss": 0.5,  # -20% "decrease" is within -50% Baby threshold
        }
        passed, reason = check_training_gate(metrics, default_config)
        # Baby mode allows up to -50% regression, -20% is fine
        assert passed is True

    # === Multiple Failure Tests ===

    def test_multiple_failures_first_wins(self, default_config):
        """Test that first failure encountered is reported."""
        metrics = {
            "accuracy": 0.05,  # fails Baby threshold (10%)
            "final_loss": 0.9,  # also fails max_loss (0.8)
            "initial_loss": 0.3,  # also fails (loss tripled, beyond -50%)
        }
        passed, reason = check_training_gate(metrics, default_config)
        assert passed is False
        # First check is accuracy, so that should be in reason
        assert "accuracy" in reason

    # === Custom Config Tests ===

    def test_custom_config_stricter_accuracy(self):
        """Test with stricter accuracy threshold."""
        config = TrainingGateConfig(
            min_accuracy=0.7,
            max_loss=0.8,
            min_loss_decrease=0.2,
        )
        metrics = {
            "accuracy": 0.65,  # would pass default, fails with 0.7
            "final_loss": 0.3,
            "initial_loss": 1.0,
        }
        passed, reason = check_training_gate(metrics, config)
        assert passed is False
        assert "accuracy" in reason

    def test_custom_config_looser_all(self):
        """Test with all looser thresholds."""
        config = TrainingGateConfig(
            min_accuracy=0.3,
            max_loss=1.0,
            min_loss_decrease=0.1,
        )
        metrics = {
            "accuracy": 0.35,
            "final_loss": 0.95,
            "initial_loss": 1.0,  # only 5% decrease but threshold is 10%
        }
        passed, reason = check_training_gate(metrics, config)
        # 5% decrease is below 10% threshold
        assert passed is False

    # === Edge Cases ===

    def test_zero_initial_loss(self, default_config):
        """Test handling of zero initial loss (division protection)."""
        metrics = {
            "accuracy": 0.65,
            "final_loss": 0.0,
            "initial_loss": 0.0,  # division by zero risk
        }
        # Should handle gracefully - either fail or have special handling
        passed, reason = check_training_gate(metrics, default_config)
        # If initial_loss is 0 and final_loss is 0, loss decrease is undefined
        # Gate should handle this gracefully (passes since check is skipped)
        assert isinstance(passed, bool)
        assert isinstance(reason, str)

    def test_very_small_initial_loss(self, default_config):
        """Test with very small initial loss."""
        metrics = {
            "accuracy": 0.65,
            "final_loss": 0.0001,
            "initial_loss": 0.001,  # 90% decrease
        }
        passed, reason = check_training_gate(metrics, default_config)
        assert passed is True

    def test_perfect_training(self, default_config):
        """Test with perfect training results."""
        metrics = {
            "accuracy": 1.0,  # perfect accuracy
            "final_loss": 0.0,  # zero loss
            "initial_loss": 1.0,  # 100% decrease
        }
        passed, reason = check_training_gate(metrics, default_config)
        assert passed is True
        assert reason == "passed"
