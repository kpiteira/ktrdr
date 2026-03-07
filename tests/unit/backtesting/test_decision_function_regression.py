"""Tests for DecisionFunction regression path."""

import pytest

torch = pytest.importorskip("torch")

import pandas as pd  # noqa: E402
import torch.nn as nn  # noqa: E402

from ktrdr.backtesting.decision_function import DecisionFunction  # noqa: E402
from ktrdr.backtesting.position_manager import PositionStatus  # noqa: E402
from ktrdr.decision.base import Signal  # noqa: E402


def make_regression_decisions_config(
    round_trip_cost: float = 0.003,
    min_edge_multiplier: float = 1.5,
    **overrides,
) -> dict:
    """Create decisions config for regression mode."""
    config = {
        "output_format": "regression",
        "cost_model": {
            "round_trip_cost": round_trip_cost,
            "min_edge_multiplier": min_edge_multiplier,
        },
        "filters": {"min_signal_separation": 0},
        "position_awareness": True,
    }
    config.update(overrides)
    return config


def make_classification_decisions_config() -> dict:
    """Create standard classification decisions config."""
    return {
        "output_format": "classification",
        "confidence_threshold": 0.5,
        "filters": {"min_signal_separation": 0},
        "position_awareness": True,
    }


class FixedOutputModel(nn.Module):
    """Model that returns a fixed output value for testing."""

    def __init__(self, output_value: float):
        super().__init__()
        self._output = output_value

    def forward(self, x):
        batch_size = x.shape[0]
        return torch.full((batch_size, 1), self._output)


class FixedClassificationModel(nn.Module):
    """Model that returns fixed logits for classification testing."""

    def __init__(self, logits: list[float]):
        super().__init__()
        self._logits = logits

    def forward(self, x):
        batch_size = x.shape[0]
        return torch.tensor([self._logits] * batch_size)


def make_bar(timestamp: str = "2024-06-01 12:00") -> pd.Series:
    """Create a mock bar."""
    return pd.Series(
        {"open": 1.1, "high": 1.2, "low": 1.0, "close": 1.1, "volume": 100},
        name=pd.Timestamp(timestamp),
    )


FEATURE_NAMES = ["f1", "f2"]
FEATURES = {"f1": 0.5, "f2": 0.7}


class TestDecisionFunctionRegressionThreshold:
    """Test cost-aware threshold logic for regression mode."""

    def test_buy_when_above_threshold(self):
        """Predicted return > threshold -> BUY signal."""
        model = FixedOutputModel(0.01)  # well above threshold (0.0045)
        df = DecisionFunction(model, FEATURE_NAMES, make_regression_decisions_config())
        decision = df(FEATURES, PositionStatus.FLAT, make_bar())
        assert decision.signal == Signal.BUY

    def test_sell_when_below_negative_threshold(self):
        """Predicted return < -threshold -> SELL signal."""
        model = FixedOutputModel(-0.01)  # well below -threshold
        df = DecisionFunction(model, FEATURE_NAMES, make_regression_decisions_config())
        decision = df(FEATURES, PositionStatus.LONG, make_bar())
        # Position awareness: SELL from LONG closes position
        assert decision.signal == Signal.SELL

    def test_hold_when_within_threshold(self):
        """Predicted return between -threshold and +threshold -> HOLD."""
        model = FixedOutputModel(0.001)  # within ±0.0045 threshold
        df = DecisionFunction(model, FEATURE_NAMES, make_regression_decisions_config())
        decision = df(FEATURES, PositionStatus.FLAT, make_bar())
        assert decision.signal == Signal.HOLD

    def test_hold_at_exact_threshold(self):
        """Predicted return at exactly threshold -> HOLD (must exceed, not equal)."""
        threshold = 0.003 * 1.5  # 0.0045
        model = FixedOutputModel(threshold)
        df = DecisionFunction(model, FEATURE_NAMES, make_regression_decisions_config())
        decision = df(FEATURES, PositionStatus.FLAT, make_bar())
        assert decision.signal == Signal.HOLD

    def test_sell_from_flat_allowed_in_regression(self):
        """Regression mode allows SELL from FLAT (forex has no real 'short')."""
        model = FixedOutputModel(-0.01)  # well below -threshold
        df = DecisionFunction(model, FEATURE_NAMES, make_regression_decisions_config())
        decision = df(FEATURES, PositionStatus.FLAT, make_bar())
        assert decision.signal == Signal.SELL

    def test_threshold_calculation(self):
        """Threshold = round_trip_cost * min_edge_multiplier."""
        config = make_regression_decisions_config(
            round_trip_cost=0.005, min_edge_multiplier=2.0
        )
        df = DecisionFunction(FixedOutputModel(0.0), FEATURE_NAMES, config)
        assert df.trade_threshold == pytest.approx(0.01)


class TestDecisionFunctionRegressionConfidence:
    """Test cosmetic confidence in regression mode."""

    def test_confidence_in_range(self):
        """Cosmetic confidence should be in [0, 1] range."""
        model = FixedOutputModel(0.02)
        df = DecisionFunction(model, FEATURE_NAMES, make_regression_decisions_config())
        decision = df(FEATURES, PositionStatus.FLAT, make_bar())
        assert 0.0 <= decision.confidence <= 1.0

    def test_confidence_capped_at_1(self):
        """Very large predictions cap confidence at 1.0."""
        model = FixedOutputModel(0.5)  # huge prediction
        df = DecisionFunction(model, FEATURE_NAMES, make_regression_decisions_config())
        decision = df(FEATURES, PositionStatus.FLAT, make_bar())
        assert decision.confidence == pytest.approx(1.0)

    def test_confidence_zero_at_zero_prediction(self):
        """Zero prediction -> zero confidence."""
        model = FixedOutputModel(0.0)
        df = DecisionFunction(model, FEATURE_NAMES, make_regression_decisions_config())
        decision = df(FEATURES, PositionStatus.FLAT, make_bar())
        assert decision.confidence == pytest.approx(0.0)


class TestDecisionFunctionRegressionFilters:
    """Test filter behavior in regression mode."""

    def test_confidence_filter_skipped(self):
        """Confidence threshold filter should not apply in regression mode."""
        # Set a high confidence threshold that would block classification signals
        config = make_regression_decisions_config()
        config["confidence_threshold"] = 0.99
        model = FixedOutputModel(0.01)  # above cost threshold
        df = DecisionFunction(model, FEATURE_NAMES, config)
        decision = df(FEATURES, PositionStatus.FLAT, make_bar())
        # Should NOT be filtered by confidence threshold
        assert decision.signal == Signal.BUY

    def test_signal_separation_still_applied(self):
        """Signal separation filter still applies in regression mode."""
        config = make_regression_decisions_config()
        config["filters"]["min_signal_separation"] = 100  # 100 hours
        model = FixedOutputModel(0.01)
        df = DecisionFunction(model, FEATURE_NAMES, config)
        last_signal = pd.Timestamp("2024-06-01 11:00")
        decision = df(FEATURES, PositionStatus.FLAT, make_bar(), last_signal)
        assert decision.signal == Signal.HOLD

    def test_position_awareness_still_applied(self):
        """Position awareness filter still applies in regression mode."""
        model = FixedOutputModel(0.01)  # BUY signal
        df = DecisionFunction(model, FEATURE_NAMES, make_regression_decisions_config())
        # Already long -> BUY should be filtered to HOLD
        decision = df(FEATURES, PositionStatus.LONG, make_bar())
        assert decision.signal == Signal.HOLD


class TestDecisionFunctionClassificationUnchanged:
    """Verify classification path is completely unchanged."""

    def test_classification_still_works(self):
        """Classification model produces correct signals."""
        model = FixedClassificationModel([10.0, 0.0, 0.0])  # Strong BUY logits
        df = DecisionFunction(
            model, FEATURE_NAMES, make_classification_decisions_config()
        )
        decision = df(FEATURES, PositionStatus.FLAT, make_bar())
        assert decision.signal == Signal.BUY

    def test_default_is_classification(self):
        """No output_format defaults to classification behavior."""
        config = {"confidence_threshold": 0.5, "filters": {"min_signal_separation": 0}}
        model = FixedClassificationModel([10.0, 0.0, 0.0])
        df = DecisionFunction(model, FEATURE_NAMES, config)
        decision = df(FEATURES, PositionStatus.FLAT, make_bar())
        assert decision.signal == Signal.BUY


class TestDecisionFunctionRegressionMetadata:
    """Test that regression decisions include predicted_return."""

    def test_predicted_return_in_reasoning(self):
        """Reasoning dict should include predicted_return for regression."""
        model = FixedOutputModel(0.008)
        df = DecisionFunction(model, FEATURE_NAMES, make_regression_decisions_config())
        decision = df(FEATURES, PositionStatus.FLAT, make_bar())
        assert "predicted_return" in decision.reasoning
        assert decision.reasoning["predicted_return"] == pytest.approx(0.008, abs=1e-4)


class TestPositionManagerShortSelling:
    """Test that PositionManager supports short-selling for regression/forex."""

    def test_sell_from_flat_opens_short(self):
        """SELL from FLAT should open a SHORT position."""
        from ktrdr.backtesting.position_manager import PositionManager

        pm = PositionManager(initial_capital=100000.0)
        trade = pm.execute_trade(
            signal=Signal.SELL,
            price=1.08,
            timestamp=pd.Timestamp("2024-03-01"),
            symbol="EURUSD",
        )
        assert trade is not None
        assert trade.side == "SELL_ENTRY"
        assert pm.current_position_status == PositionStatus.SHORT

    def test_buy_from_short_closes_position(self):
        """BUY from SHORT should close the short position."""
        from ktrdr.backtesting.position_manager import PositionManager

        pm = PositionManager(initial_capital=100000.0, commission=0.001, slippage=0.0)
        pm.execute_trade(
            signal=Signal.SELL,
            price=1.08,
            timestamp=pd.Timestamp("2024-03-01"),
            symbol="EURUSD",
        )
        assert pm.current_position_status == PositionStatus.SHORT

        trade = pm.execute_trade(
            signal=Signal.BUY,
            price=1.07,
            timestamp=pd.Timestamp("2024-03-02"),
            symbol="EURUSD",
        )
        assert trade is not None
        assert trade.side == "SHORT"
        assert trade.net_pnl > 0  # Price dropped, short profits
        assert pm.current_position_status == PositionStatus.FLAT

    def test_short_pnl_negative_when_price_rises(self):
        """Short position loses money when price rises."""
        from ktrdr.backtesting.position_manager import PositionManager

        pm = PositionManager(initial_capital=100000.0, commission=0.001, slippage=0.0)
        pm.execute_trade(
            signal=Signal.SELL,
            price=1.08,
            timestamp=pd.Timestamp("2024-03-01"),
            symbol="EURUSD",
        )
        trade = pm.execute_trade(
            signal=Signal.BUY,
            price=1.10,
            timestamp=pd.Timestamp("2024-03-02"),
            symbol="EURUSD",
        )
        assert trade is not None
        assert trade.gross_pnl < 0  # Price rose, short loses

    def test_force_close_short_position(self):
        """Force close should handle SHORT positions at backtest end."""
        from ktrdr.backtesting.position_manager import PositionManager

        pm = PositionManager(initial_capital=100000.0)
        pm.execute_trade(
            signal=Signal.SELL,
            price=1.08,
            timestamp=pd.Timestamp("2024-03-01"),
            symbol="EURUSD",
        )
        trade = pm.force_close_position(
            price=1.07,
            timestamp=pd.Timestamp("2024-03-02"),
            symbol="EURUSD",
        )
        assert trade is not None
        assert pm.current_position_status == PositionStatus.FLAT

    def test_classification_sell_from_flat_still_blocked(self):
        """Classification mode should still block SELL from FLAT."""
        config = {"confidence_threshold": 0.3, "filters": {"min_signal_separation": 0}}
        model = FixedClassificationModel([0.0, 0.0, 10.0])  # strong SELL
        df = DecisionFunction(model, FEATURE_NAMES, config)
        decision = df(FEATURES, PositionStatus.FLAT, make_bar())
        assert decision.signal == Signal.HOLD  # Blocked for classification
