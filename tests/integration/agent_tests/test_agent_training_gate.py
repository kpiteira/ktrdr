"""Integration tests for training gate evaluation.

Tests the training quality gate and its integration with the agent cycle.
"""

import pytest

from ktrdr.agents.gates import check_training_gate


class TestTrainingGateIntegration:
    """Integration tests for training gate evaluation."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_training_gate_failure_stops_cycle(self):
        """Training gate failure returns clear error with values."""
        # Simulate poor training results
        poor_results = {
            "accuracy": 0.35,  # Below 45% threshold
            "final_loss": 0.9,
            "initial_loss": 0.95,
        }

        passed, reason = check_training_gate(poor_results)

        assert passed is False
        assert "accuracy_below_threshold" in reason
        # Format is "35.0%" not "35%"
        assert "35" in reason
        assert "45" in reason

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_training_gate_pass_continues(self):
        """Training gate pass allows continuation."""
        good_results = {
            "accuracy": 0.65,  # Above 45%
            "final_loss": 0.35,  # Below 0.8
            "initial_loss": 0.85,  # >20% decrease
        }

        passed, reason = check_training_gate(good_results)

        assert passed is True
        assert reason == "passed"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_training_gate_failure_high_loss(self):
        """Training gate fails when final loss is too high."""
        high_loss_results = {
            "accuracy": 0.60,  # Good accuracy
            "final_loss": 0.90,  # Above 0.8 threshold
            "initial_loss": 0.95,
        }

        passed, reason = check_training_gate(high_loss_results)

        assert passed is False
        # Reason is "loss_too_high (0.900 > 0.8)"
        assert "loss_too_high" in reason

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_training_gate_failure_insufficient_improvement(self):
        """Training gate fails when loss doesn't improve enough."""
        no_improvement_results = {
            "accuracy": 0.60,  # Good accuracy
            "final_loss": 0.70,  # Below max threshold
            "initial_loss": 0.75,  # Only ~7% improvement (<20%)
        }

        passed, reason = check_training_gate(no_improvement_results)

        assert passed is False
        # Reason is "insufficient_loss_decrease (6.7% < 20%)"
        assert "insufficient_loss_decrease" in reason

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_training_gate_reason_includes_thresholds(self):
        """Gate failure reason includes actual and threshold values."""
        poor_results = {
            "accuracy": 0.35,
            "final_loss": 0.40,
            "initial_loss": 0.85,
        }

        passed, reason = check_training_gate(poor_results)

        # Reason should include both actual and threshold values
        assert passed is False
        # Check that it's informative (contains numbers)
        assert any(char.isdigit() for char in reason)
