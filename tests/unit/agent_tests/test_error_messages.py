"""Unit tests for improved error messages - M6 Task 6.4.

Tests verify:
- CycleError base class exists and works
- GateError includes gate name and metrics
- Error messages include context (phase, values)
- Gate failures include actual vs threshold values
"""

import pytest

from ktrdr.agents.workers.research_worker import (
    CycleError,
    GateError,
    WorkerError,
)


class TestCycleErrorClass:
    """Test CycleError base class."""

    def test_cycle_error_exists(self):
        """CycleError class should exist."""
        assert CycleError is not None

    def test_cycle_error_is_exception(self):
        """CycleError should be an Exception."""
        assert issubclass(CycleError, Exception)

    def test_cycle_error_message(self):
        """CycleError should have message accessible."""
        error = CycleError("Test error message")
        assert str(error) == "Test error message"

    def test_worker_error_is_cycle_error(self):
        """WorkerError should inherit from CycleError."""
        assert issubclass(WorkerError, CycleError)


class TestGateErrorClass:
    """Test GateError with structured attributes."""

    def test_gate_error_exists(self):
        """GateError class should exist."""
        assert GateError is not None

    def test_gate_error_is_cycle_error(self):
        """GateError should inherit from CycleError."""
        assert issubclass(GateError, CycleError)

    def test_gate_error_has_gate_attribute(self):
        """GateError should have 'gate' attribute."""
        error = GateError(
            message="Training gate failed",
            gate="training",
            metrics={"accuracy": 0.42},
        )
        assert error.gate == "training"

    def test_gate_error_has_metrics_attribute(self):
        """GateError should have 'metrics' attribute with actual values."""
        metrics = {"accuracy": 0.42, "final_loss": 0.9}
        error = GateError(
            message="Training gate failed",
            gate="training",
            metrics=metrics,
        )
        assert error.metrics == metrics
        assert error.metrics["accuracy"] == 0.42

    def test_gate_error_message(self):
        """GateError message should be accessible via str()."""
        error = GateError(
            message="Training gate failed: accuracy_below_threshold (42.0% < 45%)",
            gate="training",
            metrics={"accuracy": 0.42},
        )
        assert "accuracy_below_threshold" in str(error)
        assert "42.0%" in str(error)

    def test_gate_error_for_training_gate(self):
        """GateError works for training gate failures."""
        error = GateError(
            message="Training gate failed: accuracy_below_threshold (42.3% < 45%)",
            gate="training",
            metrics={
                "accuracy": 0.423,
                "final_loss": 0.35,
                "initial_loss": 0.8,
            },
        )
        assert error.gate == "training"
        assert error.metrics["accuracy"] == 0.423

    def test_gate_error_for_backtest_gate(self):
        """GateError works for backtest gate failures."""
        error = GateError(
            message="Backtest gate failed: drawdown_too_high (45.2% > 40%)",
            gate="backtest",
            metrics={
                "win_rate": 0.55,
                "max_drawdown": 0.452,
                "sharpe_ratio": 1.2,
            },
        )
        assert error.gate == "backtest"
        assert error.metrics["max_drawdown"] == 0.452


class TestErrorMessageContext:
    """Test that error messages include proper context."""

    def test_worker_error_includes_phase_context(self):
        """WorkerError message should include phase when provided."""
        error = WorkerError("Design phase failed: Claude API error")
        assert "Design" in str(error)

    def test_gate_error_includes_values(self):
        """GateError message should include actual vs threshold values."""
        error = GateError(
            message="Training gate failed: accuracy_below_threshold (42.3% < 45%)",
            gate="training",
            metrics={"accuracy": 0.423},
        )
        # Message includes both actual (42.3%) and threshold (45%)
        assert "42.3%" in str(error)
        assert "45%" in str(error)

    def test_gate_error_reason_format(self):
        """GateError message follows expected format."""
        error = GateError(
            message="Backtest gate failed: win_rate_too_low (40.0% < 45%)",
            gate="backtest",
            metrics={"win_rate": 0.40},
        )
        # Should have format: "gate_name failed: reason (actual vs threshold)"
        msg = str(error)
        assert "gate failed" in msg.lower()
        assert "win_rate_too_low" in msg


class TestErrorRaising:
    """Test that errors can be raised and caught correctly."""

    def test_cycle_error_can_be_raised(self):
        """CycleError can be raised and caught."""
        with pytest.raises(CycleError):
            raise CycleError("Test cycle error")

    def test_worker_error_caught_as_cycle_error(self):
        """WorkerError can be caught as CycleError."""
        with pytest.raises(CycleError):
            raise WorkerError("Test worker error")

    def test_gate_error_caught_as_cycle_error(self):
        """GateError can be caught as CycleError."""
        with pytest.raises(CycleError):
            raise GateError(
                message="Test gate error",
                gate="training",
                metrics={},
            )

    def test_gate_error_attributes_accessible_in_except(self):
        """GateError attributes accessible when caught."""
        try:
            raise GateError(
                message="Gate failed",
                gate="backtest",
                metrics={"sharpe": -1.0},
            )
        except GateError as e:
            assert e.gate == "backtest"
            assert e.metrics["sharpe"] == -1.0
