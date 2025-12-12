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

# Import will fail initially - TDD red phase
from research_agents.gates.training_gate import (
    TrainingGateConfig,
    evaluate_training_gate,
)


class TestTrainingGateConfig:
    """Tests for TrainingGateConfig."""

    def test_default_config(self):
        """Test default configuration values from design doc."""
        config = TrainingGateConfig()
        assert config.min_accuracy == 0.45
        assert config.max_loss == 0.8
        assert config.min_loss_reduction == 0.2

    def test_config_from_env(self):
        """Test loading configuration from environment variables."""
        with patch.dict(
            "os.environ",
            {
                "TRAINING_GATE_MIN_ACCURACY": "0.6",
                "TRAINING_GATE_MAX_LOSS": "0.5",
                "TRAINING_GATE_MIN_LOSS_REDUCTION": "0.3",
            },
        ):
            config = TrainingGateConfig.from_env()
            assert config.min_accuracy == 0.6
            assert config.max_loss == 0.5
            assert config.min_loss_reduction == 0.3

    def test_config_from_env_defaults(self):
        """Test that missing env vars use defaults."""
        with patch.dict("os.environ", {}, clear=True):
            config = TrainingGateConfig.from_env()
            assert config.min_accuracy == 0.45
            assert config.max_loss == 0.8
            assert config.min_loss_reduction == 0.2

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
            assert config.min_loss_reduction == 0.2  # default


class TestEvaluateTrainingGate:
    """Tests for evaluate_training_gate function."""

    @pytest.fixture
    def default_config(self):
        """Default configuration for tests."""
        return TrainingGateConfig()

    # === Happy Path Tests ===

    def test_all_thresholds_pass(self, default_config):
        """Test that good results pass the gate."""
        results = {
            "accuracy": 0.65,
            "final_loss": 0.3,
            "initial_loss": 1.0,  # 70% reduction
        }
        passed, reason = evaluate_training_gate(results, default_config)
        assert passed is True
        assert reason == "All thresholds passed"

    def test_at_thresholds_passes(self, default_config):
        """Test edge case: values at thresholds should pass.

        Note: Due to floating point precision, we use values slightly
        better than thresholds rather than exactly at them.
        """
        results = {
            "accuracy": 0.45,  # at min
            "final_loss": 0.8,  # at max
            "initial_loss": 1.05,  # ~23.8% reduction (safely above 20%)
        }
        passed, reason = evaluate_training_gate(results, default_config)
        assert passed is True
        assert reason == "All thresholds passed"

    # === Accuracy Failure Tests ===

    def test_accuracy_below_threshold(self, default_config):
        """Test that low accuracy fails the gate."""
        results = {
            "accuracy": 0.40,  # below 0.45 threshold
            "final_loss": 0.3,
            "initial_loss": 1.0,
        }
        passed, reason = evaluate_training_gate(results, default_config)
        assert passed is False
        assert "Accuracy" in reason
        assert "40.00%" in reason or "40%" in reason
        assert "below threshold" in reason.lower()

    def test_accuracy_just_below_threshold(self, default_config):
        """Test edge case: accuracy just below threshold fails."""
        results = {
            "accuracy": 0.4499,  # just below 0.45
            "final_loss": 0.3,
            "initial_loss": 1.0,
        }
        passed, reason = evaluate_training_gate(results, default_config)
        assert passed is False
        assert "Accuracy" in reason

    # === Loss Failure Tests ===

    def test_loss_above_threshold(self, default_config):
        """Test that high final loss fails the gate."""
        results = {
            "accuracy": 0.65,
            "final_loss": 0.9,  # above 0.8 threshold
            "initial_loss": 1.5,
        }
        passed, reason = evaluate_training_gate(results, default_config)
        assert passed is False
        assert "Final loss" in reason
        assert "0.900" in reason
        assert "above threshold" in reason.lower()

    def test_loss_just_above_threshold(self, default_config):
        """Test edge case: loss just above threshold fails."""
        results = {
            "accuracy": 0.65,
            "final_loss": 0.8001,  # just above 0.8
            "initial_loss": 1.5,
        }
        passed, reason = evaluate_training_gate(results, default_config)
        assert passed is False
        assert "Final loss" in reason

    # === Loss Reduction Failure Tests ===

    def test_insufficient_loss_reduction(self, default_config):
        """Test that insufficient loss reduction fails the gate."""
        results = {
            "accuracy": 0.65,
            "final_loss": 0.7,
            "initial_loss": 0.8,  # only 12.5% reduction (0.8-0.7)/0.8
        }
        passed, reason = evaluate_training_gate(results, default_config)
        assert passed is False
        assert "Loss reduction" in reason
        assert "below threshold" in reason.lower()

    def test_no_loss_reduction(self, default_config):
        """Test that no loss reduction fails the gate."""
        results = {
            "accuracy": 0.65,
            "final_loss": 0.5,  # Within max_loss threshold
            "initial_loss": 0.5,  # 0% reduction
        }
        passed, reason = evaluate_training_gate(results, default_config)
        assert passed is False
        assert "Loss reduction" in reason

    def test_negative_loss_reduction(self, default_config):
        """Test that loss increase fails the gate."""
        results = {
            "accuracy": 0.65,
            "final_loss": 1.2,  # higher than initial!
            "initial_loss": 1.0,  # -20% "reduction"
        }
        passed, reason = evaluate_training_gate(results, default_config)
        assert passed is False
        # Should fail on loss or loss reduction

    # === Multiple Failure Tests ===

    def test_multiple_failures_first_wins(self, default_config):
        """Test that first failure encountered is reported."""
        results = {
            "accuracy": 0.30,  # fails first
            "final_loss": 0.9,  # also fails
            "initial_loss": 1.0,  # also fails (10% reduction)
        }
        passed, reason = evaluate_training_gate(results, default_config)
        assert passed is False
        # First check is accuracy, so that should be in reason
        assert "Accuracy" in reason

    # === Custom Config Tests ===

    def test_custom_config_stricter_accuracy(self):
        """Test with stricter accuracy threshold."""
        config = TrainingGateConfig(
            min_accuracy=0.7,
            max_loss=0.8,
            min_loss_reduction=0.2,
        )
        results = {
            "accuracy": 0.65,  # would pass default, fails with 0.7
            "final_loss": 0.3,
            "initial_loss": 1.0,
        }
        passed, reason = evaluate_training_gate(results, config)
        assert passed is False
        assert "Accuracy" in reason

    def test_custom_config_looser_all(self):
        """Test with all looser thresholds."""
        config = TrainingGateConfig(
            min_accuracy=0.3,
            max_loss=1.0,
            min_loss_reduction=0.1,
        )
        results = {
            "accuracy": 0.35,
            "final_loss": 0.95,
            "initial_loss": 1.0,  # only 5% reduction but threshold is 10%
        }
        passed, reason = evaluate_training_gate(results, config)
        # 5% reduction is below 10% threshold
        assert passed is False

    # === Edge Cases ===

    def test_zero_initial_loss(self, default_config):
        """Test handling of zero initial loss (division protection)."""
        results = {
            "accuracy": 0.65,
            "final_loss": 0.0,
            "initial_loss": 0.0,  # division by zero risk
        }
        # Should handle gracefully - either fail or have special handling
        passed, reason = evaluate_training_gate(results, default_config)
        # If initial_loss is 0 and final_loss is 0, loss reduction is undefined
        # Gate should handle this gracefully (likely fail)
        assert isinstance(passed, bool)
        assert isinstance(reason, str)

    def test_very_small_initial_loss(self, default_config):
        """Test with very small initial loss."""
        results = {
            "accuracy": 0.65,
            "final_loss": 0.0001,
            "initial_loss": 0.001,  # 90% reduction
        }
        passed, reason = evaluate_training_gate(results, default_config)
        assert passed is True

    def test_perfect_training(self, default_config):
        """Test with perfect training results."""
        results = {
            "accuracy": 1.0,  # perfect accuracy
            "final_loss": 0.0,  # zero loss
            "initial_loss": 1.0,  # 100% reduction
        }
        passed, reason = evaluate_training_gate(results, default_config)
        assert passed is True
        assert reason == "All thresholds passed"
