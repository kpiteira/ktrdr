"""Tests for DecisionFunction handling triple barrier 3-class output.

Verifies that TB models (BUY/HOLD/SELL classification) produce correct
signals through the DecisionFunction classification path.
"""

import pandas as pd
import pytest

torch = pytest.importorskip("torch")

from ktrdr.backtesting.decision_function import DecisionFunction  # noqa: E402
from ktrdr.backtesting.position_manager import PositionStatus  # noqa: E402
from ktrdr.decision.base import Signal  # noqa: E402


@pytest.fixture
def mock_tb_model():
    """Create a mock model that returns configurable 3-class logits."""

    class ConfigurableModel(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self._logits = torch.tensor([[0.0, 0.0, 0.0]])

        def set_logits(self, logits: list[float]):
            self._logits = torch.tensor([logits])

        def forward(self, x):
            return self._logits

    return ConfigurableModel()


@pytest.fixture
def feature_names():
    return ["rsi_zone_oversold", "rsi_zone_overbought"]


@pytest.fixture
def bar():
    return pd.Series(
        {"open": 1.1, "high": 1.101, "low": 1.099, "close": 1.1005, "volume": 100},
        name=pd.Timestamp("2024-06-01 12:00:00"),
    )


class TestTBClassMapping:
    """Test 3-class TB output maps to correct signals."""

    def test_buy_signal_from_class_0(self, mock_tb_model, feature_names, bar):
        """Class 0 (highest prob) maps to BUY signal."""
        mock_tb_model.set_logits([5.0, 0.0, 0.0])  # Strong class 0

        df = DecisionFunction(
            model=mock_tb_model,
            feature_names=feature_names,
            decisions_config={
                "output_format": "classification",
                "confidence_threshold": 0.3,
            },
            output_type="classification",
        )

        features = {"rsi_zone_oversold": 0.8, "rsi_zone_overbought": 0.1}
        decision = df(features, PositionStatus.FLAT, bar, None)

        assert decision.signal == Signal.BUY

    def test_hold_signal_from_class_1(self, mock_tb_model, feature_names, bar):
        """Class 1 (highest prob) maps to HOLD signal."""
        mock_tb_model.set_logits([0.0, 5.0, 0.0])  # Strong class 1

        df = DecisionFunction(
            model=mock_tb_model,
            feature_names=feature_names,
            decisions_config={
                "output_format": "classification",
                "confidence_threshold": 0.3,
            },
            output_type="classification",
        )

        features = {"rsi_zone_oversold": 0.5, "rsi_zone_overbought": 0.5}
        decision = df(features, PositionStatus.FLAT, bar, None)

        assert decision.signal == Signal.HOLD

    def test_sell_signal_from_class_2(self, mock_tb_model, feature_names, bar):
        """Class 2 (highest prob) maps to SELL signal."""
        mock_tb_model.set_logits([0.0, 0.0, 5.0])  # Strong class 2

        df = DecisionFunction(
            model=mock_tb_model,
            feature_names=feature_names,
            decisions_config={
                "output_format": "classification",
                "confidence_threshold": 0.3,
                "allow_short_from_flat": True,
            },
            output_type="classification",
        )

        features = {"rsi_zone_oversold": 0.1, "rsi_zone_overbought": 0.9}
        decision = df(features, PositionStatus.FLAT, bar, None)

        assert decision.signal == Signal.SELL


class TestConfidenceThreshold:
    """Test confidence threshold filtering with TB models."""

    def test_low_confidence_returns_hold(self, mock_tb_model, feature_names, bar):
        """Low max probability should be filtered to HOLD."""
        # Equal logits → uniform probs → max prob ≈ 0.33 < threshold 0.5
        mock_tb_model.set_logits([1.0, 0.9, 0.8])

        df = DecisionFunction(
            model=mock_tb_model,
            feature_names=feature_names,
            decisions_config={
                "output_format": "classification",
                "confidence_threshold": 0.5,
            },
        )

        features = {"rsi_zone_oversold": 0.5, "rsi_zone_overbought": 0.5}
        decision = df(features, PositionStatus.FLAT, bar, None)

        assert decision.signal == Signal.HOLD

    def test_high_confidence_passes_threshold(self, mock_tb_model, feature_names, bar):
        """High max probability should pass threshold filter."""
        mock_tb_model.set_logits([5.0, -1.0, -1.0])  # BUY with high confidence

        df = DecisionFunction(
            model=mock_tb_model,
            feature_names=feature_names,
            decisions_config={
                "output_format": "classification",
                "confidence_threshold": 0.5,
            },
        )

        features = {"rsi_zone_oversold": 0.8, "rsi_zone_overbought": 0.1}
        decision = df(features, PositionStatus.FLAT, bar, None)

        assert decision.signal == Signal.BUY
        assert decision.confidence > 0.5


class TestProbabilitiesOutput:
    """Test that probabilities dict has correct class names."""

    def test_probabilities_have_three_classes(self, mock_tb_model, feature_names, bar):
        """Probabilities dict should have BUY, HOLD, SELL keys."""
        mock_tb_model.set_logits([2.0, 1.0, 0.5])

        df = DecisionFunction(
            model=mock_tb_model,
            feature_names=feature_names,
            decisions_config={
                "output_format": "classification",
                "confidence_threshold": 0.3,
            },
        )

        features = {"rsi_zone_oversold": 0.5, "rsi_zone_overbought": 0.5}
        decision = df(features, PositionStatus.FLAT, bar, None)

        probs = decision.reasoning["nn_probabilities"]
        assert "BUY" in probs
        assert "HOLD" in probs
        assert "SELL" in probs
        # Probabilities should sum to 1.0
        assert sum(probs.values()) == pytest.approx(1.0, abs=0.01)

    def test_probabilities_reflect_model_output(
        self, mock_tb_model, feature_names, bar
    ):
        """Probabilities should reflect relative model logits."""
        mock_tb_model.set_logits([5.0, 0.0, 0.0])  # Strong BUY

        df = DecisionFunction(
            model=mock_tb_model,
            feature_names=feature_names,
            decisions_config={
                "output_format": "classification",
                "confidence_threshold": 0.1,
            },
        )

        features = {"rsi_zone_oversold": 0.5, "rsi_zone_overbought": 0.5}
        decision = df(features, PositionStatus.FLAT, bar, None)

        probs = decision.reasoning["nn_probabilities"]
        assert probs["BUY"] > probs["HOLD"]
        assert probs["BUY"] > probs["SELL"]
        assert probs["BUY"] > 0.9  # Should be very confident
