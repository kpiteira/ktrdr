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

from ktrdr.agents.gates import (
    BacktestGateConfig,
    check_backtest_gate,
)


class TestBacktestGateConfig:
    """Tests for BacktestGateConfig."""

    def test_default_config(self):
        """Test default configuration values (Baby mode v2.5)."""
        config = BacktestGateConfig()
        assert config.min_win_rate == 0.10  # Baby mode: lax for exploration
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
        """Test that missing env vars use defaults (Baby mode v2.5)."""
        with patch.dict("os.environ", {}, clear=True):
            config = BacktestGateConfig.from_env()
            assert config.min_win_rate == 0.10  # Baby mode
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


class TestCheckBacktestGate:
    """Tests for check_backtest_gate function."""

    @pytest.fixture
    def default_config(self):
        """Default configuration for tests."""
        return BacktestGateConfig()

    # === Happy Path Tests ===

    def test_all_thresholds_pass(self, default_config):
        """Test that good results pass the gate."""
        metrics = {
            "win_rate": 0.55,
            "max_drawdown": 0.25,
            "sharpe_ratio": 1.2,
        }
        passed, reason = check_backtest_gate(metrics, default_config)
        assert passed is True
        assert reason == "passed"

    def test_at_thresholds_passes(self, default_config):
        """Test edge case: values at thresholds should pass."""
        metrics = {
            "win_rate": 0.45,  # at min
            "max_drawdown": 0.4,  # at max
            "sharpe_ratio": -0.5,  # at min
        }
        passed, reason = check_backtest_gate(metrics, default_config)
        assert passed is True
        assert reason == "passed"

    # === Win Rate Failure Tests ===

    def test_win_rate_below_threshold(self, default_config):
        """Test that low win rate fails the gate (Baby mode: 10%)."""
        metrics = {
            "win_rate": 0.05,  # below 0.10 Baby threshold
            "max_drawdown": 0.25,
            "sharpe_ratio": 1.0,
        }
        passed, reason = check_backtest_gate(metrics, default_config)
        assert passed is False
        assert "win_rate_too_low" in reason

    def test_win_rate_just_below_threshold(self, default_config):
        """Test edge case: win rate just below Baby threshold fails."""
        metrics = {
            "win_rate": 0.099,  # just below 0.10 Baby threshold
            "max_drawdown": 0.25,
            "sharpe_ratio": 1.0,
        }
        passed, reason = check_backtest_gate(metrics, default_config)
        assert passed is False
        assert "win_rate" in reason

    # === Drawdown Failure Tests ===

    def test_drawdown_above_threshold(self, default_config):
        """Test that high drawdown fails the gate."""
        metrics = {
            "win_rate": 0.55,
            "max_drawdown": 0.50,  # above 0.4 threshold
            "sharpe_ratio": 1.0,
        }
        passed, reason = check_backtest_gate(metrics, default_config)
        assert passed is False
        assert "drawdown_too_high" in reason

    def test_drawdown_just_above_threshold(self, default_config):
        """Test edge case: drawdown just above threshold fails."""
        metrics = {
            "win_rate": 0.55,
            "max_drawdown": 0.401,  # just above 0.4
            "sharpe_ratio": 1.0,
        }
        passed, reason = check_backtest_gate(metrics, default_config)
        assert passed is False
        assert "drawdown" in reason

    # === Sharpe Ratio Failure Tests ===

    def test_sharpe_below_threshold(self, default_config):
        """Test that low Sharpe ratio fails the gate."""
        metrics = {
            "win_rate": 0.55,
            "max_drawdown": 0.25,
            "sharpe_ratio": -0.8,  # below -0.5 threshold
        }
        passed, reason = check_backtest_gate(metrics, default_config)
        assert passed is False
        assert "sharpe_too_low" in reason

    def test_sharpe_just_below_threshold(self, default_config):
        """Test edge case: Sharpe just below threshold fails."""
        metrics = {
            "win_rate": 0.55,
            "max_drawdown": 0.25,
            "sharpe_ratio": -0.51,  # just below -0.5
        }
        passed, reason = check_backtest_gate(metrics, default_config)
        assert passed is False
        assert "sharpe" in reason

    def test_very_negative_sharpe(self, default_config):
        """Test with very negative Sharpe ratio."""
        metrics = {
            "win_rate": 0.55,
            "max_drawdown": 0.25,
            "sharpe_ratio": -2.5,
        }
        passed, reason = check_backtest_gate(metrics, default_config)
        assert passed is False
        assert "sharpe" in reason

    # === Multiple Failure Tests ===

    def test_multiple_failures_first_wins(self, default_config):
        """Test that first failure encountered is reported."""
        metrics = {
            "win_rate": 0.05,  # fails Baby threshold (10%)
            "max_drawdown": 0.60,  # also fails (> 40%)
            "sharpe_ratio": -1.0,  # also fails (< -0.5)
        }
        passed, reason = check_backtest_gate(metrics, default_config)
        assert passed is False
        # First check is win rate, so that should be in reason
        assert "win_rate" in reason

    # === Custom Config Tests ===

    def test_custom_config_stricter_win_rate(self):
        """Test with stricter win rate threshold."""
        config = BacktestGateConfig(
            min_win_rate=0.6,
            max_drawdown=0.4,
            min_sharpe=-0.5,
        )
        metrics = {
            "win_rate": 0.55,  # would pass default, fails with 0.6
            "max_drawdown": 0.25,
            "sharpe_ratio": 1.0,
        }
        passed, reason = check_backtest_gate(metrics, config)
        assert passed is False
        assert "win_rate" in reason

    def test_custom_config_stricter_drawdown(self):
        """Test with stricter drawdown threshold."""
        config = BacktestGateConfig(
            min_win_rate=0.45,
            max_drawdown=0.2,  # stricter than default
            min_sharpe=-0.5,
        )
        metrics = {
            "win_rate": 0.55,
            "max_drawdown": 0.30,  # would pass default, fails with 0.2
            "sharpe_ratio": 1.0,
        }
        passed, reason = check_backtest_gate(metrics, config)
        assert passed is False
        assert "drawdown" in reason

    def test_custom_config_positive_sharpe_required(self):
        """Test with positive Sharpe requirement."""
        config = BacktestGateConfig(
            min_win_rate=0.45,
            max_drawdown=0.4,
            min_sharpe=0.5,  # requires positive Sharpe
        )
        metrics = {
            "win_rate": 0.55,
            "max_drawdown": 0.25,
            "sharpe_ratio": 0.3,  # positive but below 0.5
        }
        passed, reason = check_backtest_gate(metrics, config)
        assert passed is False
        assert "sharpe" in reason

    # === Edge Cases ===

    def test_zero_win_rate(self, default_config):
        """Test with zero win rate."""
        metrics = {
            "win_rate": 0.0,
            "max_drawdown": 0.25,
            "sharpe_ratio": 1.0,
        }
        passed, reason = check_backtest_gate(metrics, default_config)
        assert passed is False
        assert "win_rate" in reason

    def test_zero_drawdown(self, default_config):
        """Test with zero drawdown (best case)."""
        metrics = {
            "win_rate": 0.55,
            "max_drawdown": 0.0,
            "sharpe_ratio": 1.0,
        }
        passed, reason = check_backtest_gate(metrics, default_config)
        assert passed is True

    def test_excellent_results(self, default_config):
        """Test with excellent backtest results."""
        metrics = {
            "win_rate": 0.75,  # 75% win rate
            "max_drawdown": 0.10,  # only 10% drawdown
            "sharpe_ratio": 2.5,  # excellent Sharpe
        }
        passed, reason = check_backtest_gate(metrics, default_config)
        assert passed is True
        assert reason == "passed"

    def test_missing_results_default_to_fail(self, default_config):
        """Test that missing result fields default to failing values."""
        metrics = {}  # empty metrics
        passed, reason = check_backtest_gate(metrics, default_config)
        # Should fail due to default values
        assert passed is False
