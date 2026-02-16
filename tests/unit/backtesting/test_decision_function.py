"""Tests for DecisionFunction — stateless decision maker for backtesting.

Tests cover:
- Signal mapping from model output (BUY/HOLD/SELL)
- Confidence threshold filter
- Signal separation filter
- Position awareness filter (all branches)
- Model inference error handling
- Feature dict ordering
- Equivalence with DecisionEngine._apply_position_logic
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from ktrdr.backtesting.decision_function import _SIGNAL_MAP, DecisionFunction
from ktrdr.backtesting.position_manager import PositionStatus
from ktrdr.decision.base import Position, Signal, TradingDecision

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bar(timestamp: str | pd.Timestamp = "2024-01-15 10:00:00") -> pd.Series:
    """Create a minimal OHLCV bar with a timestamp index."""
    ts = pd.Timestamp(timestamp, tz="UTC") if isinstance(timestamp, str) else timestamp
    return pd.Series(
        {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 1000},
        name=ts,
    )


def _make_predict_output(signal_idx: int = 0, confidence: float = 0.8) -> dict:
    """Create a _predict() return dict for a given signal and confidence."""
    probs = np.array([0.1, 0.1, 0.1])
    remaining = 1.0 - confidence
    probs[signal_idx] = confidence
    for i in range(3):
        if i != signal_idx:
            probs[i] = remaining / 2.0
    return {
        "signal": _SIGNAL_MAP[signal_idx],
        "confidence": confidence,
        "probabilities": {
            "BUY": float(probs[0]),
            "HOLD": float(probs[1]),
            "SELL": float(probs[2]),
        },
    }


def _make_decision_function(
    signal_idx: int = 0,
    confidence: float = 0.8,
    decisions_config: dict | None = None,
    feature_names: list[str] | None = None,
) -> DecisionFunction:
    """Create a DecisionFunction with _predict mocked to return known output.

    This avoids requiring torch at test time.
    """
    if decisions_config is None:
        decisions_config = _make_decisions_config()
    if feature_names is None:
        feature_names = FEATURE_NAMES

    model = MagicMock()
    df = DecisionFunction(model, feature_names, decisions_config)

    predict_output = _make_predict_output(signal_idx, confidence)
    df._predict = MagicMock(return_value=predict_output)  # type: ignore[method-assign]
    return df


def _make_decisions_config(
    confidence_threshold: float = 0.5,
    min_signal_separation: int = 4,
    position_awareness: bool = True,
) -> dict[str, Any]:
    """Create a decisions config dict matching strategy YAML structure."""
    return {
        "confidence_threshold": confidence_threshold,
        "filters": {
            "min_signal_separation": min_signal_separation,
        },
        "position_awareness": position_awareness,
    }


FEATURE_NAMES = [
    "rsi_1h.low",
    "rsi_1h.medium",
    "rsi_1h.high",
    "bb_1h.low",
    "bb_1h.high",
]


# ---------------------------------------------------------------------------
# Tests: Signal mapping
# ---------------------------------------------------------------------------


class TestDecisionFunctionSignalMapping:
    """Test that model output maps correctly to BUY/HOLD/SELL signals."""

    def test_buy_signal(self):
        """Model predicting class 0 produces BUY signal."""
        df = _make_decision_function(signal_idx=0, confidence=0.8)
        features = dict.fromkeys(FEATURE_NAMES, 0.5)

        decision = df(features, PositionStatus.FLAT, _make_bar())

        assert decision.signal == Signal.BUY
        assert isinstance(decision, TradingDecision)

    def test_hold_signal(self):
        """Model predicting class 1 produces HOLD signal."""
        df = _make_decision_function(signal_idx=1, confidence=0.8)
        features = dict.fromkeys(FEATURE_NAMES, 0.5)

        decision = df(features, PositionStatus.FLAT, _make_bar())

        assert decision.signal == Signal.HOLD

    def test_sell_signal_when_long(self):
        """Model predicting class 2 produces SELL signal when position is LONG."""
        df = _make_decision_function(signal_idx=2, confidence=0.8)
        features = dict.fromkeys(FEATURE_NAMES, 0.5)

        decision = df(features, PositionStatus.LONG, _make_bar())

        assert decision.signal == Signal.SELL

    def test_decision_has_correct_timestamp(self):
        """TradingDecision timestamp comes from bar's index."""
        df = _make_decision_function(signal_idx=1, confidence=0.8)
        features = dict.fromkeys(FEATURE_NAMES, 0.5)

        decision = df(features, PositionStatus.FLAT, _make_bar("2024-06-15 14:30:00"))

        assert decision.timestamp == pd.Timestamp("2024-06-15 14:30:00", tz="UTC")

    def test_decision_has_confidence(self):
        """TradingDecision includes model confidence score."""
        df = _make_decision_function(
            signal_idx=0,
            confidence=0.75,
            decisions_config=_make_decisions_config(confidence_threshold=0.5),
        )
        features = dict.fromkeys(FEATURE_NAMES, 0.5)

        decision = df(features, PositionStatus.FLAT, _make_bar())

        assert decision.confidence == pytest.approx(0.75)

    def test_decision_has_current_position(self):
        """TradingDecision includes current position."""
        df = _make_decision_function(signal_idx=1, confidence=0.8)
        features = dict.fromkeys(FEATURE_NAMES, 0.5)

        decision = df(features, PositionStatus.LONG, _make_bar())

        assert decision.current_position == Position.LONG


# ---------------------------------------------------------------------------
# Tests: Confidence threshold filter
# ---------------------------------------------------------------------------


class TestConfidenceFilter:
    """Test confidence threshold filtering."""

    def test_below_threshold_returns_hold(self):
        """Signal with confidence below threshold is filtered to HOLD."""
        df = _make_decision_function(
            signal_idx=0,
            confidence=0.3,
            decisions_config=_make_decisions_config(confidence_threshold=0.5),
        )
        features = dict.fromkeys(FEATURE_NAMES, 0.5)

        decision = df(features, PositionStatus.FLAT, _make_bar())

        assert decision.signal == Signal.HOLD

    def test_above_threshold_passes(self):
        """Signal with confidence above threshold passes through."""
        df = _make_decision_function(
            signal_idx=0,
            confidence=0.8,
            decisions_config=_make_decisions_config(confidence_threshold=0.5),
        )
        features = dict.fromkeys(FEATURE_NAMES, 0.5)

        decision = df(features, PositionStatus.FLAT, _make_bar())

        assert decision.signal == Signal.BUY

    def test_at_threshold_passes(self):
        """Signal at exactly the threshold passes through (>= semantics)."""
        df = _make_decision_function(
            signal_idx=0,
            confidence=0.5,
            decisions_config=_make_decisions_config(confidence_threshold=0.5),
        )
        features = dict.fromkeys(FEATURE_NAMES, 0.5)

        decision = df(features, PositionStatus.FLAT, _make_bar())

        # The original code uses `confidence < min_confidence` so == passes
        assert decision.signal == Signal.BUY


# ---------------------------------------------------------------------------
# Tests: Signal separation filter
# ---------------------------------------------------------------------------


class TestSignalSeparationFilter:
    """Test minimum time between signals."""

    def test_too_recent_returns_hold(self):
        """Signal within min_separation window is filtered to HOLD."""
        df = _make_decision_function(
            signal_idx=0,
            confidence=0.8,
            decisions_config=_make_decisions_config(min_signal_separation=4),
        )
        features = dict.fromkeys(FEATURE_NAMES, 0.5)
        last_signal = pd.Timestamp("2024-01-15 10:00:00", tz="UTC")

        decision = df(
            features,
            PositionStatus.FLAT,
            _make_bar("2024-01-15 12:00:00"),
            last_signal_time=last_signal,
        )

        assert decision.signal == Signal.HOLD

    def test_outside_window_passes(self):
        """Signal outside min_separation window passes through."""
        df = _make_decision_function(
            signal_idx=0,
            confidence=0.8,
            decisions_config=_make_decisions_config(min_signal_separation=4),
        )
        features = dict.fromkeys(FEATURE_NAMES, 0.5)
        last_signal = pd.Timestamp("2024-01-15 10:00:00", tz="UTC")

        decision = df(
            features,
            PositionStatus.FLAT,
            _make_bar("2024-01-15 15:00:00"),
            last_signal_time=last_signal,
        )

        assert decision.signal == Signal.BUY

    def test_no_last_signal_passes(self):
        """First signal (no prior signal) always passes separation filter."""
        df = _make_decision_function(
            signal_idx=0,
            confidence=0.8,
            decisions_config=_make_decisions_config(min_signal_separation=4),
        )
        features = dict.fromkeys(FEATURE_NAMES, 0.5)

        decision = df(features, PositionStatus.FLAT, _make_bar(), last_signal_time=None)

        assert decision.signal == Signal.BUY

    def test_timezone_naive_timestamps_handled(self):
        """Timezone-naive timestamps are localized to UTC for comparison."""
        df = _make_decision_function(
            signal_idx=0,
            confidence=0.8,
            decisions_config=_make_decisions_config(min_signal_separation=4),
        )
        features = dict.fromkeys(FEATURE_NAMES, 0.5)
        bar = _make_bar(pd.Timestamp("2024-01-15 12:00:00"))  # no tz
        last_signal = pd.Timestamp("2024-01-15 10:00:00")  # no tz

        decision = df(features, PositionStatus.FLAT, bar, last_signal_time=last_signal)

        assert decision.signal == Signal.HOLD


# ---------------------------------------------------------------------------
# Tests: Position awareness filter
# ---------------------------------------------------------------------------


class TestPositionAwarenessFilter:
    """Test position-aware signal filtering."""

    def test_buy_when_long_returns_hold(self):
        """BUY signal when already LONG is filtered to HOLD."""
        df = _make_decision_function(signal_idx=0, confidence=0.8)
        features = dict.fromkeys(FEATURE_NAMES, 0.5)

        decision = df(features, PositionStatus.LONG, _make_bar())

        assert decision.signal == Signal.HOLD

    def test_sell_when_flat_returns_hold(self):
        """SELL signal when FLAT is filtered to HOLD (no short positions in MVP)."""
        df = _make_decision_function(signal_idx=2, confidence=0.8)
        features = dict.fromkeys(FEATURE_NAMES, 0.5)

        decision = df(features, PositionStatus.FLAT, _make_bar())

        assert decision.signal == Signal.HOLD

    def test_sell_when_long_passes(self):
        """SELL signal when LONG passes through (close position)."""
        df = _make_decision_function(signal_idx=2, confidence=0.8)
        features = dict.fromkeys(FEATURE_NAMES, 0.5)

        decision = df(features, PositionStatus.LONG, _make_bar())

        assert decision.signal == Signal.SELL

    def test_buy_when_flat_passes(self):
        """BUY signal when FLAT passes through (open position)."""
        df = _make_decision_function(signal_idx=0, confidence=0.8)
        features = dict.fromkeys(FEATURE_NAMES, 0.5)

        decision = df(features, PositionStatus.FLAT, _make_bar())

        assert decision.signal == Signal.BUY

    def test_sell_when_short_returns_hold(self):
        """SELL signal when already SHORT is filtered to HOLD."""
        df = _make_decision_function(signal_idx=2, confidence=0.8)
        features = dict.fromkeys(FEATURE_NAMES, 0.5)

        decision = df(features, PositionStatus.SHORT, _make_bar())

        assert decision.signal == Signal.HOLD

    def test_position_awareness_disabled(self):
        """When position_awareness is False, position filters are skipped."""
        df = _make_decision_function(
            signal_idx=0,
            confidence=0.8,
            decisions_config=_make_decisions_config(position_awareness=False),
        )
        features = dict.fromkeys(FEATURE_NAMES, 0.5)

        # BUY when LONG would normally be filtered, but awareness is off
        decision = df(features, PositionStatus.LONG, _make_bar())

        assert decision.signal == Signal.BUY


# ---------------------------------------------------------------------------
# Tests: Model inference error handling
# ---------------------------------------------------------------------------


class TestInferenceErrorHandling:
    """Test graceful handling of model inference failures."""

    def test_inference_error_returns_hold(self):
        """Model inference error produces HOLD decision with error metadata."""
        model = MagicMock()
        df = DecisionFunction(model, FEATURE_NAMES, _make_decisions_config())
        df._predict = MagicMock(side_effect=RuntimeError("CUDA out of memory"))  # type: ignore[method-assign]
        features = dict.fromkeys(FEATURE_NAMES, 0.5)

        decision = df(features, PositionStatus.FLAT, _make_bar())

        assert decision.signal == Signal.HOLD
        assert "error" in decision.reasoning

    def test_inference_error_preserves_timestamp(self):
        """Error decisions still have correct timestamp."""
        model = MagicMock()
        df = DecisionFunction(model, FEATURE_NAMES, _make_decisions_config())
        df._predict = MagicMock(side_effect=RuntimeError("inference failed"))  # type: ignore[method-assign]
        features = dict.fromkeys(FEATURE_NAMES, 0.5)

        decision = df(features, PositionStatus.FLAT, _make_bar("2024-03-01 09:30:00"))

        assert decision.timestamp == pd.Timestamp("2024-03-01 09:30:00", tz="UTC")


# ---------------------------------------------------------------------------
# Tests: Feature ordering
# ---------------------------------------------------------------------------


class TestFeatureOrdering:
    """Test that features are passed to _predict correctly."""

    def test_features_passed_to_predict(self):
        """__call__ passes the features dict to _predict unchanged."""
        feature_names = ["alpha", "beta", "gamma"]
        df = _make_decision_function(feature_names=feature_names)

        # Features dict in different order than feature_names
        features = {"gamma": 3.0, "alpha": 1.0, "beta": 2.0}

        df(features, PositionStatus.FLAT, _make_bar())

        # _predict received the features dict (ordering happens inside _predict)
        df._predict.assert_called_once_with(features)


# ---------------------------------------------------------------------------
# Tests: Statelessness
# ---------------------------------------------------------------------------


class TestStatelessness:
    """Verify DecisionFunction doesn't mutate state during __call__."""

    def test_multiple_calls_independent(self):
        """Calling __call__ multiple times produces independent results."""
        df = _make_decision_function(signal_idx=0, confidence=0.8)
        features = dict.fromkeys(FEATURE_NAMES, 0.5)

        bar1 = _make_bar("2024-01-15 10:00:00")
        bar2 = _make_bar("2024-01-15 14:00:00")

        d1 = df(features, PositionStatus.FLAT, bar1)
        d2 = df(features, PositionStatus.FLAT, bar2)

        assert d1.signal == Signal.BUY
        assert d2.signal == Signal.BUY
        # Timestamps differ
        assert d1.timestamp != d2.timestamp

    def test_position_not_tracked_internally(self):
        """DecisionFunction does not track position — each call is independent."""
        df = _make_decision_function(signal_idx=0, confidence=0.8)
        features = dict.fromkeys(FEATURE_NAMES, 0.5)
        bar = _make_bar()

        # Call with FLAT → BUY
        d1 = df(features, PositionStatus.FLAT, bar)
        assert d1.signal == Signal.BUY

        # Call with LONG → HOLD (position awareness)
        d2 = df(features, PositionStatus.LONG, bar)
        assert d2.signal == Signal.HOLD

        # Call with FLAT again → BUY (no state leakage from d2)
        d3 = df(features, PositionStatus.FLAT, bar)
        assert d3.signal == Signal.BUY


# ---------------------------------------------------------------------------
# Tests: Reasoning metadata
# ---------------------------------------------------------------------------


class TestReasoningMetadata:
    """Test that decision reasoning includes useful metadata."""

    def test_reasoning_includes_raw_signal(self):
        """Reasoning dict should include the raw (pre-filter) signal."""
        df = _make_decision_function(signal_idx=0, confidence=0.8)
        features = dict.fromkeys(FEATURE_NAMES, 0.5)

        # BUY when LONG → filtered to HOLD, but raw_signal should be BUY
        decision = df(features, PositionStatus.LONG, _make_bar())

        assert decision.reasoning.get("raw_signal") == "BUY"
        assert decision.signal == Signal.HOLD

    def test_reasoning_includes_probabilities(self):
        """Reasoning dict should include nn output probabilities."""
        df = _make_decision_function(signal_idx=0, confidence=0.8)
        features = dict.fromkeys(FEATURE_NAMES, 0.5)

        decision = df(features, PositionStatus.FLAT, _make_bar())

        assert "nn_probabilities" in decision.reasoning


# ---------------------------------------------------------------------------
# Tests: Equivalence with DecisionEngine._apply_position_logic
# ---------------------------------------------------------------------------


class TestEquivalenceWithDecisionEngine:
    """Prove DecisionFunction filter logic is identical to DecisionEngine.

    This is the M2 gate test. DecisionFunction._apply_filters() must produce
    the same signal as DecisionEngine._apply_position_logic() for every
    combination of (raw_signal, confidence, position, last_signal_time).

    The test builds both systems with the same config, feeds identical inputs,
    and compares outputs.
    """

    @pytest.fixture()
    def decisions_config(self) -> dict[str, Any]:
        """Shared decisions config for both systems."""
        return {
            "confidence_threshold": 0.6,
            "filters": {"min_signal_separation": 4},
            "position_awareness": True,
        }

    @pytest.fixture()
    def decision_engine(self, decisions_config: dict[str, Any]):
        """Create a DecisionEngine with the shared config."""
        pytest.importorskip("torch", reason="DecisionEngine requires torch")
        from ktrdr.decision.engine import DecisionEngine

        # Build a minimal strategy config containing the decisions section
        strategy_config = {
            "decisions": decisions_config,
            "model": {"type": "mlp"},
        }

        engine = DecisionEngine.__new__(DecisionEngine)
        engine.config = strategy_config
        engine.current_position = Position.FLAT
        engine.last_signal_time = None
        engine.neural_model = None
        return engine

    @pytest.fixture()
    def decision_function(self, decisions_config: dict[str, Any]):
        """Create a DecisionFunction with the shared config."""
        # Model is unused — equivalence tests call _apply_filters directly
        model = MagicMock()
        return DecisionFunction(model, FEATURE_NAMES, decisions_config)

    def _compare_filters(
        self,
        decision_engine,
        decision_function,
        raw_signal: Signal,
        confidence: float,
        position: PositionStatus,
        timestamp: pd.Timestamp,
        last_signal_time: pd.Timestamp | None,
    ) -> tuple[Signal, Signal]:
        """Run both filter implementations and return their results.

        Returns:
            (engine_signal, function_signal) tuple
        """
        # DecisionEngine tracks position and last_signal_time as state
        engine_position_map = {
            PositionStatus.FLAT: Position.FLAT,
            PositionStatus.LONG: Position.LONG,
            PositionStatus.SHORT: Position.SHORT,
        }
        decision_engine.current_position = engine_position_map[position]
        decision_engine.last_signal_time = last_signal_time

        engine_result = decision_engine._apply_position_logic(
            raw_signal, confidence, timestamp
        )

        function_result = decision_function._apply_filters(
            raw_signal, confidence, position, timestamp, last_signal_time
        )

        return engine_result, function_result

    # --- Test case 1: BUY with high confidence, no position → BUY ---

    def test_eq_buy_high_confidence_flat(self, decision_engine, decision_function):
        """Equivalence: BUY signal, high confidence, FLAT → BUY."""
        ts = pd.Timestamp("2024-01-15 10:00:00", tz="UTC")
        engine_sig, func_sig = self._compare_filters(
            decision_engine,
            decision_function,
            raw_signal=Signal.BUY,
            confidence=0.8,
            position=PositionStatus.FLAT,
            timestamp=ts,
            last_signal_time=None,
        )
        assert engine_sig == func_sig == Signal.BUY

    # --- Test case 2: BUY with low confidence → HOLD (confidence filter) ---

    def test_eq_buy_low_confidence(self, decision_engine, decision_function):
        """Equivalence: BUY signal, low confidence → HOLD."""
        ts = pd.Timestamp("2024-01-15 10:00:00", tz="UTC")
        engine_sig, func_sig = self._compare_filters(
            decision_engine,
            decision_function,
            raw_signal=Signal.BUY,
            confidence=0.4,
            position=PositionStatus.FLAT,
            timestamp=ts,
            last_signal_time=None,
        )
        assert engine_sig == func_sig == Signal.HOLD

    # --- Test case 3: BUY when already LONG → HOLD (position awareness) ---

    def test_eq_buy_when_long(self, decision_engine, decision_function):
        """Equivalence: BUY signal, already LONG → HOLD."""
        ts = pd.Timestamp("2024-01-15 10:00:00", tz="UTC")
        engine_sig, func_sig = self._compare_filters(
            decision_engine,
            decision_function,
            raw_signal=Signal.BUY,
            confidence=0.8,
            position=PositionStatus.LONG,
            timestamp=ts,
            last_signal_time=None,
        )
        assert engine_sig == func_sig == Signal.HOLD

    # --- Test case 4: SELL when FLAT → HOLD (no short positions) ---

    def test_eq_sell_when_flat(self, decision_engine, decision_function):
        """Equivalence: SELL signal, FLAT → HOLD (no shorts)."""
        ts = pd.Timestamp("2024-01-15 10:00:00", tz="UTC")
        engine_sig, func_sig = self._compare_filters(
            decision_engine,
            decision_function,
            raw_signal=Signal.SELL,
            confidence=0.8,
            position=PositionStatus.FLAT,
            timestamp=ts,
            last_signal_time=None,
        )
        assert engine_sig == func_sig == Signal.HOLD

    # --- Test case 5: SELL when LONG → SELL (close position) ---

    def test_eq_sell_when_long(self, decision_engine, decision_function):
        """Equivalence: SELL signal, LONG → SELL (close position)."""
        ts = pd.Timestamp("2024-01-15 10:00:00", tz="UTC")
        engine_sig, func_sig = self._compare_filters(
            decision_engine,
            decision_function,
            raw_signal=Signal.SELL,
            confidence=0.8,
            position=PositionStatus.LONG,
            timestamp=ts,
            last_signal_time=None,
        )
        assert engine_sig == func_sig == Signal.SELL

    # --- Test case 6: BUY within min_separation window → HOLD ---

    def test_eq_buy_within_separation(self, decision_engine, decision_function):
        """Equivalence: BUY signal, within min_separation → HOLD."""
        ts = pd.Timestamp("2024-01-15 12:00:00", tz="UTC")
        last = pd.Timestamp("2024-01-15 10:00:00", tz="UTC")  # 2h ago < 4h window
        engine_sig, func_sig = self._compare_filters(
            decision_engine,
            decision_function,
            raw_signal=Signal.BUY,
            confidence=0.8,
            position=PositionStatus.FLAT,
            timestamp=ts,
            last_signal_time=last,
        )
        assert engine_sig == func_sig == Signal.HOLD

    # --- Test case 7: BUY outside min_separation window → BUY ---

    def test_eq_buy_outside_separation(self, decision_engine, decision_function):
        """Equivalence: BUY signal, outside min_separation → BUY."""
        ts = pd.Timestamp("2024-01-15 15:00:00", tz="UTC")
        last = pd.Timestamp("2024-01-15 10:00:00", tz="UTC")  # 5h ago > 4h window
        engine_sig, func_sig = self._compare_filters(
            decision_engine,
            decision_function,
            raw_signal=Signal.BUY,
            confidence=0.8,
            position=PositionStatus.FLAT,
            timestamp=ts,
            last_signal_time=last,
        )
        assert engine_sig == func_sig == Signal.BUY

    # --- Test case 8: HOLD from model passes through all filters ---

    def test_eq_hold_from_model_passes_through(
        self, decision_engine, decision_function
    ):
        """Equivalence: HOLD signal passes through all filters unchanged."""
        ts = pd.Timestamp("2024-01-15 10:00:00", tz="UTC")
        engine_sig, func_sig = self._compare_filters(
            decision_engine,
            decision_function,
            raw_signal=Signal.HOLD,
            confidence=0.8,
            position=PositionStatus.FLAT,
            timestamp=ts,
            last_signal_time=None,
        )
        assert engine_sig == func_sig == Signal.HOLD

    # --- Test case 9: Timezone-naive timestamps (both systems must normalize) ---

    def test_eq_timezone_naive_separation(self, decision_engine, decision_function):
        """Equivalence: Both systems handle timezone-naive timestamps identically."""
        ts = pd.Timestamp("2024-01-15 12:00:00")  # naive
        last = pd.Timestamp("2024-01-15 10:00:00")  # naive, 2h ago
        engine_sig, func_sig = self._compare_filters(
            decision_engine,
            decision_function,
            raw_signal=Signal.BUY,
            confidence=0.8,
            position=PositionStatus.FLAT,
            timestamp=ts,
            last_signal_time=last,
        )
        assert engine_sig == func_sig == Signal.HOLD
