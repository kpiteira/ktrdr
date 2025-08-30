"""Decision engine for generating trading signals from neural network outputs."""

from pathlib import Path
from typing import Any, Optional

import pandas as pd
import torch

from .. import get_logger
from ..neural.models.base_model import BaseNeuralModel
from ..neural.models.mlp import MLPTradingModel
from .base import Position, Signal, TradingDecision

logger = get_logger(__name__)


class DecisionEngine:
    """Core decision generation logic with position awareness."""

    def __init__(
        self, strategy_config: dict[str, Any], model_path: Optional[str] = None
    ):
        """Initialize the decision engine.

        Args:
            strategy_config: Strategy configuration dictionary
            model_path: Optional path to pre-trained model
        """
        self.config = strategy_config
        self.neural_model: Optional[BaseNeuralModel] = None
        self.current_position = Position.FLAT
        self.last_signal_time: Optional[pd.Timestamp] = None

        # Load or initialize neural model
        self._initialize_model(model_path)

    def _initialize_model(self, model_path: Optional[str] = None):
        """Initialize the neural network model.

        Args:
            model_path: Optional path to pre-trained model
        """
        model_config = self.config.get("model", {})
        model_type = model_config.get("type", "mlp").lower()

        # Create model based on type
        if model_type == "mlp":
            self.neural_model = MLPTradingModel(model_config)
        else:
            raise ValueError(f"Unknown model type: {model_type}")

        # Load pre-trained model if path provided
        if model_path and Path(model_path).exists():
            self.neural_model.load_model(model_path)

    def generate_decision(
        self,
        current_data: pd.Series,
        fuzzy_memberships: dict[str, float],
        indicators: dict[str, float],
    ) -> TradingDecision:
        """Generate trading decision from current market data.

        Args:
            current_data: Current OHLCV data
            fuzzy_memberships: Current fuzzy membership values
            indicators: Current indicator values

        Returns:
            TradingDecision object with signal and metadata
        """
        # Normalize timestamp to ensure proper handling FIRST
        if isinstance(current_data.name, pd.Timestamp):
            timestamp = current_data.name
        else:
            timestamp = pd.Timestamp(current_data.name)  # type: ignore[arg-type]

        # Get timestamp for logging
        timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M")

        logger.debug(
            f"🌎 [{timestamp_str}] DecisionEngine.generate_decision called with {len(fuzzy_memberships)} fuzzy features"
        )

        if self.neural_model is None:
            logger.error(f"🚨 [{timestamp_str}] Neural model not initialized!")
            raise ValueError("Neural model not initialized")

        if not self.neural_model.is_trained:
            logger.error(
                f"🚨 [{timestamp_str}] Neural model not trained! is_trained={self.neural_model.is_trained}"
            )
            raise ValueError("Neural model not trained")

        logger.debug(f"✅ [{timestamp_str}] Neural model ready, preparing features...")

        # Prepare features for neural network
        logger.debug(
            f"🛠️ [{timestamp_str}] Preparing features from {len(fuzzy_memberships)} fuzzy + {len(indicators)} indicators..."
        )
        logger.debug(
            f"🔍 [{timestamp_str}] Fuzzy features available: {list(fuzzy_memberships.keys())}"
        )

        try:
            features = self._prepare_decision_features(
                fuzzy_memberships, indicators, current_data
            )
            logger.debug(
                f"✅ [{timestamp_str}] Features prepared: shape={features.shape}, mean={features.mean():.4f}, std={features.std():.4f}"
            )
        except Exception as e:
            # Check if this is a warm-up period error (normal and expected)
            is_warmup_error = "No fuzzy membership features found" in str(
                e
            ) or "likely warm-up period" in str(e)

            if is_warmup_error:
                logger.debug(
                    f"🔄 [{timestamp_str}] Feature preparation failed (warm-up period): {e}"
                )
            else:
                logger.error(f"🚨 [{timestamp_str}] Feature preparation failed: {e}")
            raise

        # Get neural network prediction with timestamp for debugging
        nn_output = self.neural_model.predict(features, market_timestamp=timestamp)
        raw_signal = Signal[nn_output["signal"]]
        confidence = nn_output["confidence"]

        # Timestamp already normalized above

        # Apply position awareness and filters
        logger.debug(
            f"🚫 [{timestamp_str}] Applying position logic - Raw signal: {raw_signal.value}, Confidence: {confidence:.4f}, Current position: {self.current_position.value}"
        )

        final_signal = self._apply_position_logic(raw_signal, confidence, timestamp)

        if final_signal != raw_signal:
            # logger.info(f"🚫 [{timestamp_str}] Position logic OVERRODE {raw_signal.value} → {final_signal.value}")  # Commented for performance
            pass
        else:
            logger.debug(
                f"✅ [{timestamp_str}] Position logic kept {final_signal.value}"
            )

        # Create decision object
        decision = TradingDecision(
            signal=final_signal,
            confidence=confidence,
            timestamp=timestamp,
            reasoning={
                "fuzzy_memberships": fuzzy_memberships,
                "nn_probabilities": nn_output["probabilities"],
                "indicators": indicators,
                "filters_applied": self._get_active_filters(),
                "raw_signal": raw_signal.value,
                "position_aware": self.config.get("decisions", {}).get(
                    "position_awareness", True
                ),
            },
            current_position=self.current_position,
        )

        return decision

    def _prepare_decision_features(
        self,
        fuzzy_memberships: dict[str, float],
        indicators: dict[str, float],
        current_data: pd.Series,
    ) -> torch.Tensor:
        """Prepare features for neural network from current data.

        Args:
            fuzzy_memberships: Dictionary of fuzzy membership values
            indicators: Dictionary of indicator values
            current_data: Current OHLCV data

        Returns:
            Feature tensor for neural network
        """
        # Convert dictionaries to DataFrames for compatibility with model
        fuzzy_df = pd.DataFrame([fuzzy_memberships])
        indicators_df = pd.DataFrame([indicators])

        # Add price data to indicators
        for col in ["open", "high", "low", "close", "volume"]:
            if col in current_data:
                indicators_df[col] = current_data[col]

        # Use model's feature preparation with saved scaler for consistent scaling
        if self.neural_model is not None:
            return self.neural_model.prepare_features(
                fuzzy_df, indicators_df, self.neural_model.feature_scaler
            )
        else:
            raise ValueError("Neural model is not available")

    def _apply_position_logic(
        self, raw_signal: Signal, confidence: float, timestamp: pd.Timestamp
    ) -> Signal:
        """Apply position awareness and signal filtering.

        Args:
            raw_signal: Raw signal from neural network
            confidence: Confidence score
            timestamp: Current timestamp

        Returns:
            Filtered signal
        """
        decision_config = self.config.get("decisions", {})

        # Confidence threshold filter
        min_confidence = decision_config.get("confidence_threshold", 0.5)
        if confidence < min_confidence:
            return Signal.HOLD

        # Signal separation filter
        filters = decision_config.get("filters", {})
        min_separation_hours = filters.get("min_signal_separation", 4)

        if self.last_signal_time is not None:
            # Ensure both timestamps are timezone-aware UTC for consistent comparison
            current_ts = timestamp
            last_ts = self.last_signal_time

            # Convert to UTC if needed
            if current_ts.tz is None:
                current_ts = current_ts.tz_localize("UTC")
            elif str(current_ts.tz) != "UTC":
                current_ts = current_ts.tz_convert("UTC")

            if last_ts.tz is None:
                last_ts = last_ts.tz_localize("UTC")
            elif str(last_ts.tz) != "UTC":
                last_ts = last_ts.tz_convert("UTC")

            time_since_last = (current_ts - last_ts).total_seconds() / 3600
            if time_since_last < min_separation_hours:
                return Signal.HOLD

        # Position awareness logic
        if not decision_config.get("position_awareness", True):
            return raw_signal

        # Prevent redundant signals
        if self.current_position == Position.LONG and raw_signal == Signal.BUY:
            return Signal.HOLD
        if self.current_position == Position.SHORT and raw_signal == Signal.SELL:
            return Signal.HOLD

        # For now, we don't support SHORT positions in MVP
        if raw_signal == Signal.SELL and self.current_position == Position.FLAT:
            return Signal.HOLD  # Don't open short positions

        return raw_signal

    def _get_active_filters(self) -> list[str]:
        """Get list of currently active filters.

        Returns:
            List of filter names
        """
        active_filters = []
        decision_config = self.config.get("decisions", {})

        if decision_config.get("confidence_threshold", 0) > 0:
            active_filters.append("confidence_threshold")

        filters = decision_config.get("filters", {})
        if filters.get("min_signal_separation", 0) > 0:
            active_filters.append("min_signal_separation")

        if filters.get("volume_filter", False):
            active_filters.append("volume_filter")

        if decision_config.get("position_awareness", False):
            active_filters.append("position_awareness")

        return active_filters

    def update_position(
        self, executed_signal: Signal, timestamp: Optional[pd.Timestamp] = None
    ):
        """Update internal position tracking after trade execution.

        Args:
            executed_signal: The signal that was executed
            timestamp: The timestamp of the signal (defaults to now if not provided)
        """
        if timestamp is None:
            timestamp = pd.Timestamp.now(tz="UTC")

        # Ensure timestamp is timezone-aware UTC
        if timestamp.tz is None:
            timestamp = timestamp.tz_localize("UTC")
        elif str(timestamp.tz) != "UTC":
            timestamp = timestamp.tz_convert("UTC")

        if executed_signal == Signal.BUY:
            self.current_position = Position.LONG
            self.last_signal_time = timestamp
        elif executed_signal == Signal.SELL:
            if self.current_position == Position.LONG:
                self.current_position = Position.FLAT
            else:
                # We don't support short positions in MVP
                self.current_position = Position.FLAT
            self.last_signal_time = timestamp

    def reset(self):
        """Reset engine state."""
        self.current_position = Position.FLAT
        self.last_signal_time = None
