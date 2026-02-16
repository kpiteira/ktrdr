"""DecisionFunction — stateless decision maker for backtesting.

Maps (features, position, bar, last_signal_time) → TradingDecision.
No model loading, no position tracking, no feature computation.
Just: prepare tensor → run inference → apply filters → return signal.

Replaces DecisionEngine + DecisionOrchestrator.make_decision() for the
backtesting path only. Those classes are preserved for future paper/live
trading use. See DESIGN.md for the full rationale.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from ktrdr.backtesting.position_manager import PositionStatus
from ktrdr.decision.base import Position, Signal, TradingDecision

if TYPE_CHECKING:
    import torch

logger = logging.getLogger(__name__)

# Signal index → Signal enum mapping (same as BaseNeuralModel.predict)
_SIGNAL_MAP = {0: Signal.BUY, 1: Signal.HOLD, 2: Signal.SELL}

# PositionStatus → Position mapping for TradingDecision.current_position
_POSITION_MAP = {
    PositionStatus.FLAT: Position.FLAT,
    PositionStatus.LONG: Position.LONG,
    PositionStatus.SHORT: Position.SHORT,
}


class DecisionFunction:
    """Stateless decision maker: (features, position, bar) → TradingDecision.

    No model loading, no position tracking, no feature computation.
    Just: prepare tensor → run inference → apply filters → return signal.

    All state is received as input parameters. The only instance attributes
    are configuration values set in __init__ and never modified.
    """

    def __init__(
        self,
        model: torch.nn.Module,
        feature_names: list[str],
        decisions_config: dict[str, Any],
    ) -> None:
        """Initialize with a ready-to-infer model and configuration.

        Args:
            model: nn.Module in eval mode, on CPU (from ModelBundle)
            feature_names: Ordered feature names matching model input order
            decisions_config: The 'decisions' section from strategy config
        """
        self.model = model
        self.feature_names = feature_names
        self.confidence_threshold = decisions_config.get("confidence_threshold", 0.5)
        filters = decisions_config.get("filters", {})
        self.min_separation_hours = filters.get("min_signal_separation", 4)
        self.position_awareness = decisions_config.get("position_awareness", True)

    def __call__(
        self,
        features: dict[str, float],
        position: PositionStatus,
        bar: pd.Series,
        last_signal_time: pd.Timestamp | None = None,
    ) -> TradingDecision:
        """Generate trading decision. Pure function (no side effects).

        Args:
            features: Pre-computed feature values keyed by feature name
            position: Current position from PositionManager
            bar: Current OHLCV bar (timestamp from bar.name)
            last_signal_time: When the last trade was executed (for separation filter)

        Returns:
            TradingDecision with filtered signal, confidence, and reasoning
        """
        if isinstance(bar.name, pd.Timestamp):
            timestamp = bar.name
        else:
            timestamp = pd.Timestamp(bar.name)  # type: ignore[arg-type]

        try:
            nn_output = self._predict(features)
        except Exception as e:
            logger.warning(f"Inference error at {timestamp}: {e}")
            return TradingDecision(
                signal=Signal.HOLD,
                confidence=0.0,
                timestamp=timestamp,
                reasoning={"error": str(e)},
                current_position=_POSITION_MAP[position],
            )

        raw_signal = nn_output["signal"]
        confidence = nn_output["confidence"]

        final_signal = self._apply_filters(
            raw_signal, confidence, position, timestamp, last_signal_time
        )

        return TradingDecision(
            signal=final_signal,
            confidence=confidence,
            timestamp=timestamp,
            reasoning={
                "raw_signal": raw_signal.value,
                "nn_probabilities": nn_output["probabilities"],
                "position_aware": self.position_awareness,
            },
            current_position=_POSITION_MAP[position],
        )

    def _predict(self, features: dict[str, float]) -> dict[str, Any]:
        """Run model forward pass and extract signal + confidence.

        Args:
            features: Feature dict to convert to tensor and feed to model

        Returns:
            Dict with 'signal' (Signal enum), 'confidence' (float),
            and 'probabilities' (dict)
        """
        import torch

        # Build tensor in feature_names order
        values = [features[name] for name in self.feature_names]
        tensor = torch.tensor(values, dtype=torch.float32).unsqueeze(0)

        with torch.no_grad():
            outputs = self.model(tensor)

        # Handle output shapes
        if hasattr(outputs, "shape") and len(outputs.shape) == 1:
            outputs = outputs.unsqueeze(0)

        raw_outputs = outputs[0].cpu().numpy()

        # Check if softmax was already applied
        raw_sum = np.sum(raw_outputs)
        if abs(raw_sum - 1.0) < 1e-6:
            probs = raw_outputs
        else:
            # Apply softmax manually (with numerical stability)
            exp_outputs = np.exp(raw_outputs - np.max(raw_outputs))
            probs = exp_outputs / np.sum(exp_outputs)

        signal_idx = int(np.argmax(probs))
        confidence = float(probs[signal_idx])

        return {
            "signal": _SIGNAL_MAP[signal_idx],
            "confidence": confidence,
            "probabilities": {
                "BUY": float(probs[0]),
                "HOLD": float(probs[1]),
                "SELL": float(probs[2]),
            },
        }

    def _apply_filters(
        self,
        raw_signal: Signal,
        confidence: float,
        position: PositionStatus,
        timestamp: pd.Timestamp,
        last_signal_time: pd.Timestamp | None,
    ) -> Signal:
        """Apply position awareness and signal filtering.

        Ported from DecisionEngine._apply_position_logic() with identical logic.

        Args:
            raw_signal: Raw signal from neural network
            confidence: Confidence score
            position: Current position status
            timestamp: Current bar timestamp
            last_signal_time: When the last trade signal was executed

        Returns:
            Filtered signal
        """
        # 1. Confidence threshold filter
        if confidence < self.confidence_threshold:
            return Signal.HOLD

        # 2. Signal separation filter
        if last_signal_time is not None:
            current_ts = timestamp
            last_ts = last_signal_time

            # Ensure both timestamps are timezone-aware UTC for consistent comparison
            if current_ts.tz is None:
                current_ts = current_ts.tz_localize("UTC")
            elif str(current_ts.tz) != "UTC":
                current_ts = current_ts.tz_convert("UTC")

            if last_ts.tz is None:
                last_ts = last_ts.tz_localize("UTC")
            elif str(last_ts.tz) != "UTC":
                last_ts = last_ts.tz_convert("UTC")

            time_since_last = (current_ts - last_ts).total_seconds() / 3600
            if time_since_last < self.min_separation_hours:
                return Signal.HOLD

        # 3. Position awareness filter
        if not self.position_awareness:
            return raw_signal

        # Prevent redundant signals
        if position == PositionStatus.LONG and raw_signal == Signal.BUY:
            return Signal.HOLD
        if position == PositionStatus.SHORT and raw_signal == Signal.SELL:
            return Signal.HOLD

        # No short positions in MVP
        if raw_signal == Signal.SELL and position == PositionStatus.FLAT:
            return Signal.HOLD

        return raw_signal
