"""Feature caching system for backtesting performance optimization."""

import pickle
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from .. import get_logger
from ..fuzzy.config import FuzzyConfigLoader
from ..fuzzy.engine import FuzzyEngine
from ..indicators.indicator_engine import IndicatorEngine

logger = get_logger(__name__)


class FeatureCache:
    """Pre-computes and caches indicators and fuzzy memberships for backtesting."""

    def __init__(self, strategy_config: dict[str, Any]):
        """Initialize feature cache with strategy configuration.

        Args:
            strategy_config: Strategy configuration dictionary
        """
        self.strategy_config = strategy_config
        self.indicators_df: Optional[pd.DataFrame] = None
        self.fuzzy_df: Optional[pd.DataFrame] = None
        self.mapped_indicators_df: Optional[pd.DataFrame] = None

        # Initialize engines
        self._setup_indicator_engine()
        self._setup_fuzzy_engine()

    def _setup_indicator_engine(self):
        """Setup indicator engine from strategy config."""
        indicator_configs = self.strategy_config["indicators"]
        fixed_configs = []

        # Use same mapping as training to ensure consistency
        name_mapping = {
            "bollinger_bands": "BollingerBands",
            "keltner_channels": "KeltnerChannels",
            "momentum": "Momentum",
            "volume_sma": "SMA",
            "atr": "ATR",
            "rsi": "RSI",
            "sma": "SMA",
            "ema": "EMA",
            "macd": "MACD",
        }

        for config in indicator_configs:
            if isinstance(config, dict) and "type" not in config:
                config = config.copy()
                indicator_name = config["name"].lower()
                if indicator_name in name_mapping:
                    config["type"] = name_mapping[indicator_name]
                else:
                    # Fallback: convert snake_case to PascalCase
                    config["type"] = "".join(
                        word.capitalize() for word in indicator_name.split("_")
                    )
            fixed_configs.append(config)

        self.indicator_engine = IndicatorEngine(indicators=fixed_configs)

    def _setup_fuzzy_engine(self):
        """Setup fuzzy engine from strategy config."""
        strategy_fuzzy_sets = self.strategy_config.get("fuzzy_sets", {})
        if not strategy_fuzzy_sets:
            raise ValueError("No fuzzy_sets found in strategy configuration")

        fuzzy_config = FuzzyConfigLoader.load_from_dict(strategy_fuzzy_sets)
        self.fuzzy_engine = FuzzyEngine(fuzzy_config)

    def compute_all_features(self, historical_data: pd.DataFrame) -> None:
        """Pre-compute all indicators and fuzzy memberships for entire dataset.

        Args:
            historical_data: Complete historical OHLCV data
        """
        logger.debug(f"🚀 Pre-computing features for {len(historical_data)} bars...")

        # Step 1: Compute all indicators at once
        logger.debug("📊 Computing indicators...")
        self.indicators_df = self.indicator_engine.apply(historical_data)

        # Step 2: Map indicators to original names (optimized but correct approach)
        logger.debug("🗺️ Mapping indicators to original names...")
        mapped_data = []

        # PERFORMANCE OPTIMIZATION: Use full dataset indicators but map correctly
        # The key insight: indicators computed on full dataset are equivalent to sliding window
        # for most indicators once sufficient lookback is available
        for idx in range(len(historical_data)):
            # Skip early bars with insufficient data for indicators
            if idx < 50:  # Minimum lookback for indicators
                # Don't add empty dictionaries - skip entirely
                continue

            current_bar_indicators = {}

            for config in self.strategy_config["indicators"]:
                original_name = config["name"]
                indicator_type = config["name"].upper()

                # Find matching columns (same logic as orchestrator)
                for col in self.indicators_df.columns:
                    if col.upper().startswith(indicator_type):
                        if indicator_type in ["SMA", "EMA"]:
                            # Use price ratio for moving averages
                            # This matches real-time: current_price / indicator_value
                            current_bar_indicators[original_name] = (
                                historical_data["close"].iloc[idx]
                                / self.indicators_df[col].iloc[idx]
                            )
                        elif indicator_type == "MACD":
                            # Use main MACD line
                            if (
                                col.startswith("MACD_")
                                and "_signal_" not in col
                                and "_hist_" not in col
                            ):
                                current_bar_indicators[original_name] = (
                                    self.indicators_df[col].iloc[idx]
                                )
                                break
                        else:
                            # Use raw values for other indicators
                            current_bar_indicators[original_name] = self.indicators_df[
                                col
                            ].iloc[idx]
                            break

            mapped_data.append(current_bar_indicators)

        # Convert to DataFrame with historical_data index (skip first 50 bars)
        self.mapped_indicators_df = pd.DataFrame(
            mapped_data, index=historical_data.index[50:]
        )

        # Step 3: Compute all fuzzy memberships
        logger.debug("🔀 Computing fuzzy memberships...")
        fuzzy_data = []

        for idx in range(len(self.mapped_indicators_df)):
            current_bar_fuzzy = {}
            current_indicators = self.mapped_indicators_df.iloc[idx]

            for indicator_name, indicator_value in current_indicators.items():
                if indicator_name in self.strategy_config["fuzzy_sets"]:
                    # Skip NaN values
                    if pd.isna(indicator_value):
                        continue

                    # Fuzzify this indicator
                    membership_result = self.fuzzy_engine.fuzzify(
                        indicator_name, indicator_value
                    )
                    current_bar_fuzzy.update(membership_result)

            fuzzy_data.append(current_bar_fuzzy)

        # Convert to DataFrame with historical_data index (skip first 50 bars)
        self.fuzzy_df = pd.DataFrame(fuzzy_data, index=historical_data.index[50:])

        # Step 4: PRE-COMPUTE TEMPORAL FEATURES (lag features) to fix backtesting NaN issue
        logger.debug("⏰ Pre-computing temporal fuzzy features...")
        self._add_temporal_features()

        logger.debug("✅ Feature pre-computation complete!")
        logger.debug(f"   Indicators: {len(self.mapped_indicators_df.columns)} columns")
        logger.debug(f"   Fuzzy features: {len(self.fuzzy_df.columns)} columns")

    def get_features_for_timestamp(
        self, timestamp: pd.Timestamp
    ) -> tuple[dict[str, float], dict[str, float]]:
        """Get pre-computed features for a specific timestamp.

        Args:
            timestamp: Target timestamp

        Returns:
            Tuple of (mapped_indicators, fuzzy_memberships) dictionaries

        Raises:
            ValueError: If timestamp not found or features not computed
        """
        if self.mapped_indicators_df is None or self.fuzzy_df is None:
            raise ValueError(
                "Features not computed. Call compute_all_features() first."
            )

        # Handle timezone-aware timestamp matching - PREVENT LOOK-AHEAD BIAS
        if timestamp not in self.mapped_indicators_df.index:
            # Use 'pad' method to only look backward (no future data)
            closest_idx = self.mapped_indicators_df.index.get_indexer(
                [timestamp], method="pad"
            )[0]
            if closest_idx == -1:
                raise ValueError(
                    f"Timestamp {timestamp} not found in pre-computed features (no past data available)"
                )
            actual_timestamp = self.mapped_indicators_df.index[closest_idx]

            # Ensure we're not using future data (actual_timestamp <= timestamp)
            if actual_timestamp > timestamp:
                raise ValueError(
                    f"Look-ahead bias detected: {actual_timestamp} > {timestamp}"
                )

            # Check if within tolerance (1 hour backward)
            time_diff = (timestamp - actual_timestamp).total_seconds()
            if time_diff > 3600:  # 1 hour in seconds
                raise ValueError(
                    f"Closest past timestamp {actual_timestamp} is {time_diff/3600:.1f}h before {timestamp}"
                )

            timestamp = actual_timestamp

        # Get features for this timestamp
        indicators = self.mapped_indicators_df.loc[timestamp].to_dict()
        fuzzy_memberships = self.fuzzy_df.loc[timestamp].to_dict()

        # Remove NaN values
        indicators = {k: v for k, v in indicators.items() if not pd.isna(v)}
        fuzzy_memberships = {
            k: v for k, v in fuzzy_memberships.items() if not pd.isna(v)
        }

        return indicators, fuzzy_memberships

    def _add_temporal_features(self) -> None:
        """Add temporal (lag) features to fuzzy_df to fix backtesting NaN issue.

        This method pre-computes lag features on the full dataset, preventing the
        single-row DataFrame issue that causes all lag features to be NaN during backtesting.
        """
        # Get lookback periods from strategy config
        model_config = self.strategy_config.get("model", {})
        feature_config = model_config.get("features", {})
        lookback = feature_config.get("lookback_periods", 0)

        if lookback < 1:
            logger.debug("⏰ No temporal features configured (lookback_periods = 0)")
            return

        logger.debug(
            f"⏰ Adding {lookback} lag periods for {len(self.fuzzy_df.columns)} base fuzzy features"
        )

        # Get base fuzzy columns
        base_fuzzy_columns = list(self.fuzzy_df.columns)

        # Create lag features
        temporal_data = {}

        for lag in range(1, lookback + 1):
            for column in base_fuzzy_columns:
                lag_column_name = f"{column}_lag_{lag}"
                # Create lagged values using shift operation on the full dataset
                temporal_data[lag_column_name] = self.fuzzy_df[column].shift(lag)

        # Add temporal features to the fuzzy DataFrame
        for lag_column_name, lag_values in temporal_data.items():
            self.fuzzy_df[lag_column_name] = lag_values

        logger.debug(f"⏰ Added {len(temporal_data)} temporal features to fuzzy_df")
        logger.debug(f"⏰ Total fuzzy features now: {len(self.fuzzy_df.columns)}")

    def save_cache(self, filepath: str) -> None:
        """Save computed features to disk.

        Args:
            filepath: Path to save cache file
        """
        cache_data = {
            "indicators_df": self.indicators_df,
            "mapped_indicators_df": self.mapped_indicators_df,
            "fuzzy_df": self.fuzzy_df,
            "strategy_config": self.strategy_config,
        }

        with open(filepath, "wb") as f:
            pickle.dump(cache_data, f)

        logger.info(f"💾 Feature cache saved to {filepath}")

    def load_cache(self, filepath: str) -> bool:
        """Load cached features from disk.

        Args:
            filepath: Path to cache file

        Returns:
            True if loaded successfully, False if file doesn't exist or invalid
        """
        if not Path(filepath).exists():
            return False

        try:
            with open(filepath, "rb") as f:
                cache_data = pickle.load(f)

            # Verify cache is for same strategy config
            if cache_data["strategy_config"] != self.strategy_config:
                logger.warning("📋 Cache strategy config mismatch, ignoring cache")
                return False

            self.indicators_df = cache_data["indicators_df"]
            self.mapped_indicators_df = cache_data["mapped_indicators_df"]
            self.fuzzy_df = cache_data["fuzzy_df"]

            logger.info(f"📂 Feature cache loaded from {filepath}")
            return True

        except Exception as e:
            logger.warning(f"❌ Failed to load cache: {e}")
            return False

    def is_ready(self) -> bool:
        """Check if features are computed and ready for use.

        Returns:
            True if features are computed, False otherwise
        """
        return (
            self.indicators_df is not None
            and self.mapped_indicators_df is not None
            and self.fuzzy_df is not None
        )
