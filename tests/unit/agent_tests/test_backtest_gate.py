"""
Unit tests for backtest quality gate.

Tests cover:
- Configuration loading from environment
- Gate evaluation logic (pass/fail)
- Threshold edge cases
- Clear reason messages
"""

from unittest.mock import patch

import pytest

# Import will fail initially - TDD red phase
from research_agents.gates.backtest_gate import (
    BacktestGateConfig,
    evaluate_backtest_gate,
)


class TestBacktestGateConfig:
    """Tests for BacktestGateConfig."""

    def test_default_config(self):
        """Test default configuration values from design doc."""
        config = BacktestGateConfig()
        assert config.min_win_rate == 0.45
        assert config.max_drawdown == 0.4
        assert config.min_sharpe == -0.5

    def test_config_from_env(self):
        """Test loading configuration from environment variables."""
        with patch.dict(
            "os.environ",
            {
                "BACKTEST_GATE_MIN_WIN_RATE": "0.55",
                "BACKTEST_GATE_MAX_DRAWDOWN": "0.3",
                "BACKTEST_GATE_MIN_SHARPE": "0.0",
            },
        ):
            config = BacktestGateConfig.from_env()
            assert config.min_win_rate == 0.55
            assert config.max_drawdown == 0.3
            assert config.min_sharpe == 0.0

    def test_config_from_env_defaults(self):
        """Test that missing env vars use defaults."""
        with patch.dict("os.environ", {}, clear=True):
            config = BacktestGateConfig.from_env()
            assert config.min_win_rate == 0.45
            assert config.max_drawdown == 0.4
            assert config.min_sharpe == -0.5

    def test_config_from_env_partial(self):
        """Test that partial env vars work correctly."""
        with patch.dict(
            "os.environ",
            {
                "BACKTEST_GATE_MIN_WIN_RATE": "0.6",
            },
            clear=True,
        ):
            config = BacktestGateConfig.from_env()
            assert config.min_win_rate == 0.6
            assert config.max_drawdown == 0.4  # default
            assert config.min_sharpe == -0.5  # default


class TestEvaluateBacktestGate:
    """Tests for evaluate_backtest_gate function."""

    @pytest.fixture
    def default_config(self):
        """Default configuration for tests."""
        return BacktestGateConfig()

    # === Happy Path Tests ===

    def test_all_thresholds_pass(self, default_config):
        """Test that good results pass the gate."""
        results = {
            "win_rate": 0.55,
            "max_drawdown": 0.25,
            "sharpe_ratio": 1.2,
        }
        passed, reason = evaluate_backtest_gate(results, default_config)
        assert passed is True
        assert reason == "All thresholds passed"

    def test_at_thresholds_passes(self, default_config):
        """Test edge case: values at thresholds should pass."""
        results = {
            "win_rate": 0.45,  # at min
            "max_drawdown": 0.4,  # at max
            "sharpe_ratio": -0.5,  # at min
        }
        passed, reason = evaluate_backtest_gate(results, default_config)
        assert passed is True
        assert reason == "All thresholds passed"

    # === Win Rate Failure Tests ===

    def test_win_rate_below_threshold(self, default_config):
        """Test that low win rate fails the gate."""
        results = {
            "win_rate": 0.40,  # below 0.45 threshold
            "max_drawdown": 0.25,
            "sharpe_ratio": 1.0,
        }
        passed, reason = evaluate_backtest_gate(results, default_config)
        assert passed is False
        assert "Win rate" in reason
        assert "below threshold" in reason.lower()

    def test_win_rate_just_below_threshold(self, default_config):
        """Test edge case: win rate just below threshold fails."""
        results = {
            "win_rate": 0.449,  # just below 0.45
            "max_drawdown": 0.25,
            "sharpe_ratio": 1.0,
        }
        passed, reason = evaluate_backtest_gate(results, default_config)
        assert passed is False
        assert "Win rate" in reason

    # === Drawdown Failure Tests ===

    def test_drawdown_above_threshold(self, default_config):
        """Test that high drawdown fails the gate."""
        results = {
            "win_rate": 0.55,
            "max_drawdown": 0.50,  # above 0.4 threshold
            "sharpe_ratio": 1.0,
        }
        passed, reason = evaluate_backtest_gate(results, default_config)
        assert passed is False
        assert "Max drawdown" in reason or "drawdown" in reason.lower()
        assert "above threshold" in reason.lower()

    def test_drawdown_just_above_threshold(self, default_config):
        """Test edge case: drawdown just above threshold fails."""
        results = {
            "win_rate": 0.55,
            "max_drawdown": 0.401,  # just above 0.4
            "sharpe_ratio": 1.0,
        }
        passed, reason = evaluate_backtest_gate(results, default_config)
        assert passed is False
        assert "drawdown" in reason.lower()

    # === Sharpe Ratio Failure Tests ===

    def test_sharpe_below_threshold(self, default_config):
        """Test that low Sharpe ratio fails the gate."""
        results = {
            "win_rate": 0.55,
            "max_drawdown": 0.25,
            "sharpe_ratio": -0.8,  # below -0.5 threshold
        }
        passed, reason = evaluate_backtest_gate(results, default_config)
        assert passed is False
        assert "Sharpe" in reason
        assert "below threshold" in reason.lower()

    def test_sharpe_just_below_threshold(self, default_config):
        """Test edge case: Sharpe just below threshold fails."""
        results = {
            "win_rate": 0.55,
            "max_drawdown": 0.25,
            "sharpe_ratio": -0.51,  # just below -0.5
        }
        passed, reason = evaluate_backtest_gate(results, default_config)
        assert passed is False
        assert "Sharpe" in reason

    def test_very_negative_sharpe(self, default_config):
        """Test with very negative Sharpe ratio."""
        results = {
            "win_rate": 0.55,
            "max_drawdown": 0.25,
            "sharpe_ratio": -2.5,
        }
        passed, reason = evaluate_backtest_gate(results, default_config)
        assert passed is False
        assert "Sharpe" in reason

    # === Multiple Failure Tests ===

    def test_multiple_failures_first_wins(self, default_config):
        """Test that first failure encountered is reported."""
        results = {
            "win_rate": 0.30,  # fails first
            "max_drawdown": 0.60,  # also fails
            "sharpe_ratio": -1.0,  # also fails
        }
        passed, reason = evaluate_backtest_gate(results, default_config)
        assert passed is False
        # First check is win rate, so that should be in reason
        assert "Win rate" in reason

    # === Custom Config Tests ===

    def test_custom_config_stricter_win_rate(self):
        """Test with stricter win rate threshold."""
        config = BacktestGateConfig(
            min_win_rate=0.6,
            max_drawdown=0.4,
            min_sharpe=-0.5,
        )
        results = {
            "win_rate": 0.55,  # would pass default, fails with 0.6
            "max_drawdown": 0.25,
            "sharpe_ratio": 1.0,
        }
        passed, reason = evaluate_backtest_gate(results, config)
        assert passed is False
        assert "Win rate" in reason

    def test_custom_config_stricter_drawdown(self):
        """Test with stricter drawdown threshold."""
        config = BacktestGateConfig(
            min_win_rate=0.45,
            max_drawdown=0.2,  # stricter than default
            min_sharpe=-0.5,
        )
        results = {
            "win_rate": 0.55,
            "max_drawdown": 0.30,  # would pass default, fails with 0.2
            "sharpe_ratio": 1.0,
        }
        passed, reason = evaluate_backtest_gate(results, config)
        assert passed is False
        assert "drawdown" in reason.lower()

    def test_custom_config_positive_sharpe_required(self):
        """Test with positive Sharpe requirement."""
        config = BacktestGateConfig(
            min_win_rate=0.45,
            max_drawdown=0.4,
            min_sharpe=0.5,  # requires positive Sharpe
        )
        results = {
            "win_rate": 0.55,
            "max_drawdown": 0.25,
            "sharpe_ratio": 0.3,  # positive but below 0.5
        }
        passed, reason = evaluate_backtest_gate(results, config)
        assert passed is False
        assert "Sharpe" in reason

    # === Edge Cases ===

    def test_zero_win_rate(self, default_config):
        """Test with zero win rate."""
        results = {
            "win_rate": 0.0,
            "max_drawdown": 0.25,
            "sharpe_ratio": 1.0,
        }
        passed, reason = evaluate_backtest_gate(results, default_config)
        assert passed is False
        assert "Win rate" in reason

    def test_zero_drawdown(self, default_config):
        """Test with zero drawdown (best case)."""
        results = {
            "win_rate": 0.55,
            "max_drawdown": 0.0,
            "sharpe_ratio": 1.0,
        }
        passed, reason = evaluate_backtest_gate(results, default_config)
        assert passed is True

    def test_excellent_results(self, default_config):
        """Test with excellent backtest results."""
        results = {
            "win_rate": 0.75,  # 75% win rate
            "max_drawdown": 0.10,  # only 10% drawdown
            "sharpe_ratio": 2.5,  # excellent Sharpe
        }
        passed, reason = evaluate_backtest_gate(results, default_config)
        assert passed is True
        assert reason == "All thresholds passed"

    def test_missing_results_default_to_fail(self, default_config):
        """Test that missing result fields default to failing values."""
        results = {}  # empty results
        passed, reason = evaluate_backtest_gate(results, default_config)
        # Should fail due to default values
        assert passed is False
