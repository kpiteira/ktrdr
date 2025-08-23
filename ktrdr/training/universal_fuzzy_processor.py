"""Universal fuzzy neural processor for symbol-agnostic feature engineering.

This processor creates features that are independent of symbol scale, enabling
true zero-shot generalization to unseen symbols.
"""

from typing import Any, Optional

import numpy as np
import pandas as pd
import torch

from .. import get_logger

logger = get_logger(__name__)


class UniversalFuzzyNeuralProcessor:
    """Creates symbol-agnostic features for universal trading models.

    All features are normalized to be scale-independent and work across
    any symbol, asset class, or market without retraining.
    """

    def __init__(self, feature_config: dict[str, Any], disable_temporal: bool = False):
        """Initialize universal processor.

        Args:
            feature_config: Feature configuration from strategy
            disable_temporal: Whether to disable temporal feature generation
        """
        self.feature_config = feature_config
        self.disable_temporal = disable_temporal
        self.lookback_periods = feature_config.get("lookback_periods", 5)

    def prepare_universal_input(
        self, fuzzy_data: pd.DataFrame, indicators: pd.DataFrame
    ) -> tuple[torch.Tensor, Optional[torch.Tensor]]:
        """Create universal symbol-agnostic features.

        Args:
            fuzzy_data: DataFrame with fuzzy membership values
            indicators: DataFrame with raw indicator values

        Returns:
            Tuple of (universal_features_tensor, fuzzy_features_tensor)
        """
        logger.debug(
            f"Creating universal features from {len(fuzzy_data)} fuzzy samples"
        )

        # Create universal features from raw indicators
        universal_features = self._create_universal_features(indicators)

        # Normalize fuzzy features for universality
        normalized_fuzzy = self._normalize_fuzzy_features(fuzzy_data)

        # Add temporal features if enabled
        if not self.disable_temporal and self.lookback_periods > 0:
            temporal_fuzzy = self._add_universal_temporal_features(normalized_fuzzy)
        else:
            temporal_fuzzy = normalized_fuzzy

        # Convert to tensors
        universal_tensor = torch.tensor(universal_features.values, dtype=torch.float32)
        fuzzy_tensor = torch.tensor(temporal_fuzzy.values, dtype=torch.float32)

        # Combine universal and normalized fuzzy features
        combined_features = torch.cat([universal_tensor, fuzzy_tensor], dim=1)

        logger.debug(f"Created {combined_features.shape[1]} universal features")

        return combined_features, fuzzy_tensor

    def _create_universal_features(self, indicators: pd.DataFrame) -> pd.DataFrame:
        """Create symbol-agnostic features from raw indicators.

        These features work across any symbol by using relative measures
        instead of absolute values.

        Args:
            indicators: Raw indicator values

        Returns:
            DataFrame with universal features
        """
        universal_features = pd.DataFrame(index=indicators.index)

        # 1. Price momentum as percentages (scale-independent)
        if "close" in indicators.columns:
            close = indicators["close"]
            universal_features["price_momentum_1"] = close.pct_change(1).fillna(0)
            universal_features["price_momentum_5"] = close.pct_change(5).fillna(0)
            universal_features["price_momentum_20"] = close.pct_change(20).fillna(0)

            # Rolling volatility (normalized)
            returns = close.pct_change().fillna(0)
            rolling_vol = returns.rolling(20).std().fillna(0)
            universal_features["volatility_normalized"] = rolling_vol

        # 2. RSI signal strength normalized (-1 to 1 range)
        if "rsi" in indicators.columns:
            rsi = indicators["rsi"]
            universal_features["rsi_signal_normalized"] = (rsi - 50) / 50
            universal_features["rsi_extreme_signal"] = np.where(
                rsi > 70,
                (rsi - 70) / 30,  # Overbought: 0 to 1
                np.where(rsi < 30, (30 - rsi) / 30, 0),  # Oversold: 0 to 1
            )

        # 3. MACD relative to price volatility
        if "macd" in indicators.columns and "close" in indicators.columns:
            macd = indicators["macd"]
            close = indicators["close"]
            price_vol = close.pct_change().rolling(20).std().fillna(1e-6)
            # Normalize MACD by typical price movement
            universal_features["macd_normalized"] = (macd / close) / price_vol

        # 4. Moving average position (relative, not absolute)
        if "sma" in indicators.columns and "close" in indicators.columns:
            sma = indicators["sma"]
            close = indicators["close"]
            # Price position relative to MA (percentage above/below)
            universal_features["ma_position"] = (close - sma) / sma

            # MA slope normalized by volatility
            ma_slope = sma.pct_change(5).fillna(0)
            price_vol = close.pct_change().rolling(20).std().fillna(1e-6)
            universal_features["ma_slope_normalized"] = ma_slope / price_vol

        # 5. Volume surge ratio (if volume available)
        if "volume" in indicators.columns:
            volume = indicators["volume"]
            avg_volume = volume.rolling(20).mean().fillna(volume.mean())
            universal_features["volume_surge_ratio"] = volume / avg_volume

        # 6. Bollinger Bands position (if available)
        if "BollingerBands" in indicators.columns and "close" in indicators.columns:
            bb = indicators["BollingerBands"]
            close = indicators["close"]
            # Position within bands (0 = lower band, 1 = upper band)
            universal_features["bb_position"] = (close - bb) / (
                bb * 0.04
            )  # Assuming 2% bands
            universal_features["bb_position"] = np.clip(
                universal_features["bb_position"], -2, 2
            )

        # Fill any remaining NaN values
        universal_features = universal_features.fillna(0)

        # Clip extreme values to prevent outliers
        for col in universal_features.columns:
            universal_features[col] = np.clip(universal_features[col], -10, 10)

        logger.debug(
            f"Created {len(universal_features.columns)} universal indicator features"
        )

        return universal_features

    def _normalize_fuzzy_features(self, fuzzy_data: pd.DataFrame) -> pd.DataFrame:
        """Normalize fuzzy features for universal use.

        Fuzzy features are already normalized [0,1] but we ensure consistency.

        Args:
            fuzzy_data: Raw fuzzy membership values

        Returns:
            Normalized fuzzy features
        """
        # Fuzzy features are already in [0,1] range, just ensure no outliers
        normalized = fuzzy_data.copy()
        normalized = normalized.clip(0, 1)
        normalized = normalized.fillna(0)

        logger.debug(f"Normalized {len(normalized.columns)} fuzzy features")

        return normalized

    def _add_universal_temporal_features(
        self, fuzzy_data: pd.DataFrame
    ) -> pd.DataFrame:
        """Add temporal lag features for universal patterns.

        Args:
            fuzzy_data: Normalized fuzzy features

        Returns:
            DataFrame with temporal features added
        """
        temporal_features = fuzzy_data.copy()

        # Add lag features for temporal patterns
        for lag in range(1, self.lookback_periods + 1):
            lagged = fuzzy_data.shift(lag)
            lagged.columns = [f"{col}_lag_{lag}" for col in lagged.columns]
            temporal_features = pd.concat([temporal_features, lagged], axis=1)

        # Forward fill initial NaN values from lags
        temporal_features = temporal_features.fillna(method="ffill").fillna(0)

        logger.debug(
            f"Added temporal features, total: {len(temporal_features.columns)}"
        )

        return temporal_features

    def create_features(
        self,
        price_data: pd.DataFrame,
        indicator_data: dict[str, Any],
        labels: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Create features for training (compatibility method).

        Args:
            price_data: OHLCV price data
            indicator_data: Dictionary of indicator results
            labels: Training labels

        Returns:
            Tuple of (universal_features, fuzzy_features)
        """
        # Convert indicator data to DataFrame
        indicators_df = pd.DataFrame(index=price_data.index)

        # Add price data
        for col in ["open", "high", "low", "close", "volume"]:
            if col in price_data.columns:
                indicators_df[col] = price_data[col]

        # Add indicator data
        for name, values in indicator_data.items():
            if hasattr(values, "__len__") and len(values) == len(price_data):
                indicators_df[name] = values

        # Create mock fuzzy data for now (in real implementation, this would come from fuzzy engine)
        fuzzy_features = pd.DataFrame(index=price_data.index)

        # Create universal features
        universal_features = self._create_universal_features(indicators_df)

        # Align with labels
        min_length = min(len(universal_features), len(labels))
        universal_features = universal_features.iloc[-min_length:]

        # Convert to tensors
        universal_tensor = torch.tensor(universal_features.values, dtype=torch.float32)
        fuzzy_tensor = torch.zeros(min_length, 0)  # Empty fuzzy tensor for now

        return universal_tensor, fuzzy_tensor
