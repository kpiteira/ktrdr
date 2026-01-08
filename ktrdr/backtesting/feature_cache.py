"""Feature caching system for backtesting performance optimization."""

import pickle
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

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

    @classmethod
    def from_dataframe(cls, indicators_df: pd.DataFrame) -> "FeatureCache":
        """Create FeatureCache from pre-computed indicators DataFrame.

        This is a simplified constructor for use cases where indicators are
        already computed (e.g., testing, or when using IndicatorEngine directly).

        Args:
            indicators_df: DataFrame with indicator columns (new format)

        Returns:
            FeatureCache instance with indicators_df set
        """
        # Create minimal strategy config to satisfy __init__
        dummy_config: dict[str, Any] = {
            "indicators": [],
            "fuzzy_sets": {},
        }
        instance = cls.__new__(cls)
        instance.strategy_config = dummy_config
        instance.indicators_df = indicators_df
        instance.fuzzy_df = None
        instance.mapped_indicators_df = None
        # Don't initialize engines (not needed for simple lookup)
        return instance

    def get_indicator_value(self, feature_id: str, idx: int) -> float:
        """Get indicator value at index using direct column lookup.

        Args:
            feature_id: Column name (e.g., 'rsi_14', 'bbands_20_2.upper', 'bbands_20_2')
            idx: Row index

        Returns:
            Indicator value at the specified index

        Raises:
            KeyError: If column not found in indicators DataFrame
            IndexError: If index out of bounds
        """
        if self.indicators_df is None:
            raise ValueError(
                "No indicators computed. Call compute_all_features() first."
            )

        if feature_id not in self.indicators_df.columns:
            raise KeyError(
                f"Column '{feature_id}' not found in indicators DataFrame. "
                f"Available columns: {list(self.indicators_df.columns)}"
            )

        return self.indicators_df[feature_id].iloc[idx]

    def _setup_indicator_engine(self):
        """Setup indicator engine from strategy config."""
        # Strategy config already has feature_id - just use it directly!
        indicator_configs = self.strategy_config["indicators"]
        self.indicator_engine = IndicatorEngine(indicators=indicator_configs)

    def _setup_fuzzy_engine(self):
        """Setup fuzzy engine from strategy config."""
        strategy_fuzzy_sets = self.strategy_config.get("fuzzy_sets", {})
        if not strategy_fuzzy_sets:
            raise ValueError("No fuzzy_sets found in strategy configuration")

        fuzzy_config = FuzzyConfigLoader.load_from_dict(strategy_fuzzy_sets)
        self.fuzzy_engine = FuzzyEngine(fuzzy_config)

    def _get_timeframe_from_config(self) -> str | None:
        """Extract timeframe from strategy configuration.

        Looks in training_data.timeframes.base_timeframe or deployment.target_timeframes.

        Returns:
            Timeframe string (e.g., "1h") or None if not found.
        """
        # Try training_data config
        training_data = self.strategy_config.get("training_data", {})
        timeframes_config = training_data.get("timeframes", {})
        if base_tf := timeframes_config.get("base_timeframe"):
            return base_tf
        if tf_list := timeframes_config.get("list"):
            return tf_list[0] if tf_list else None

        # Try deployment config
        deployment = self.strategy_config.get("deployment", {})
        target_tf = deployment.get("target_timeframes", {})
        if supported := target_tf.get("supported"):
            return supported[0] if supported else None

        return None

    def compute_all_features(self, historical_data: pd.DataFrame) -> None:
        """Pre-compute all indicators and fuzzy memberships for entire dataset.

        Args:
            historical_data: Complete historical OHLCV data
        """
        logger.debug(f"🚀 Pre-computing features for {len(historical_data)} bars...")

        # Step 1: Compute all indicators at once
        logger.debug("📊 Computing indicators...")
        self.indicators_df = self.indicator_engine.apply(historical_data)

        # Step 2: Map indicators to feature_id keys for fuzzy lookup
        # M4: Simplified with direct column lookup (no more fuzzy string matching)
        logger.debug("🗺️ Mapping indicators to feature_id keys...")
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

            # V3 format: indicators is a dict where key is indicator_id (= feature_id)
            indicators_config = self.strategy_config["indicators"]
            if not isinstance(indicators_config, dict):
                raise ValueError(
                    "Strategy config must use v3 format (indicators as dict). "
                    "Run 'ktrdr strategy migrate' to upgrade."
                )
            indicator_ids = list(indicators_config.keys())

            for feature_id in indicator_ids:
                # Direct O(1) lookup - column name IS the feature_id
                if feature_id in self.indicators_df.columns:
                    current_bar_indicators[feature_id] = self.indicators_df[
                        feature_id
                    ].iloc[idx]
                else:
                    # Column not found - log warning but continue
                    logger.warning(
                        f"Column '{feature_id}' not found in indicators_df at idx {idx}"
                    )

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

            # Get corresponding price data for this bar (needed for input_transform)
            current_price_data = historical_data.iloc[
                50 + idx
            ]  # offset by 50 bars skipped

            for indicator_name, indicator_value in current_indicators.items():
                if indicator_name in self.strategy_config["fuzzy_sets"]:
                    # Skip NaN values
                    if pd.isna(indicator_value):
                        continue

                    # Fuzzify this indicator with context_data for transforms
                    # Pass price data as DataFrame for fuzzy engine's input_transform
                    context_df = pd.DataFrame([current_price_data])
                    membership_result = self.fuzzy_engine.fuzzify(
                        indicator_name, indicator_value, context_data=context_df
                    )
                    current_bar_fuzzy.update(membership_result)

            fuzzy_data.append(current_bar_fuzzy)

        # Convert to DataFrame with historical_data index (skip first 50 bars)
        self.fuzzy_df = pd.DataFrame(fuzzy_data, index=historical_data.index[50:])

        # Step 3b: Add timeframe prefix to match training feature names
        # Training creates features like "1h_obv_flow_volume_selling" while
        # backtest fuzzify creates "obv_flow_volume_selling". This fixes the mismatch.
        timeframe = self._get_timeframe_from_config()
        if timeframe and self.fuzzy_df is not None:
            prefixed_columns = {
                col: f"{timeframe}_{col}" for col in self.fuzzy_df.columns
            }
            self.fuzzy_df = self.fuzzy_df.rename(columns=prefixed_columns)
            logger.debug(
                f"Added timeframe prefix '{timeframe}_' to {len(prefixed_columns)} fuzzy columns"
            )

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
                    f"Closest past timestamp {actual_timestamp} is {time_diff / 3600:.1f}h before {timestamp}"
                )

            timestamp = actual_timestamp

        # Get features for this timestamp
        raw_indicators = self.mapped_indicators_df.loc[timestamp].to_dict()
        raw_fuzzy = self.fuzzy_df.loc[timestamp].to_dict()

        # Remove NaN values and ensure proper types
        indicators: dict[str, float] = {
            str(k): float(v) for k, v in raw_indicators.items() if not pd.isna(v)
        }
        fuzzy_memberships: dict[str, float] = {
            str(k): float(v) for k, v in raw_fuzzy.items() if not pd.isna(v)
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

        if self.fuzzy_df is None:
            logger.warning("No fuzzy data available for temporal features")
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
                if self.fuzzy_df is not None:
                    temporal_data[lag_column_name] = self.fuzzy_df[column].shift(lag)

        # Add temporal features to the fuzzy DataFrame
        if self.fuzzy_df is not None:
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


class FeatureCacheV3:
    """Feature cache for v3 strategy configurations.

    This class computes features for backtesting using v3 strategy config
    and validates them against model metadata to ensure feature alignment
    with training.

    The feature ordering is CRITICAL:
    - Features must be computed in the same order as training
    - Order is validated against ModelMetadataV3.resolved_features
    - Any mismatch will cause garbage predictions

    Mirrors TrainingPipelineV3.prepare_features() but for single-symbol data.

    V2 Compatibility Layer:
        This class includes temporary compatibility methods (compute_all_features,
        get_features_for_timestamp, is_ready) that adapt the v3 interface to work
        with DecisionOrchestrator's v2-style API. These methods are marked for
        removal once DecisionOrchestrator is refactored to use the native v3
        feature interface directly. Do not build new dependencies on these
        compatibility methods.
    """

    def __init__(
        self,
        config: "StrategyConfigurationV3",
        model_metadata: "ModelMetadataV3",
    ):
        """Initialize FeatureCacheV3 with v3 strategy configuration.

        Args:
            config: V3 strategy configuration with indicators, fuzzy_sets, nn_inputs
            model_metadata: Model metadata containing expected feature order
        """
        from ktrdr.config.feature_resolver import FeatureResolver

        self.config = config
        self.metadata = model_metadata
        self.feature_resolver = FeatureResolver()

        # Initialize engines with v3 config
        self.indicator_engine = IndicatorEngine(config.indicators)
        self.fuzzy_engine = FuzzyEngine(config.fuzzy_sets)

        # Expected features from model (ORDERED list - order matters!)
        self.expected_features = model_metadata.resolved_features

        logger.info(
            f"FeatureCacheV3 initialized: "
            f"{len(config.indicators)} indicators, "
            f"{len(config.fuzzy_sets)} fuzzy sets, "
            f"{len(self.expected_features)} expected features"
        )

    def compute_features(
        self,
        data: dict[str, pd.DataFrame],
    ) -> pd.DataFrame:
        """Compute features for backtesting.

        CRITICAL: Must produce same feature_ids AND same order as training.

        Args:
            data: {timeframe: DataFrame} for single symbol

        Returns:
            Feature DataFrame with columns in expected order

        Raises:
            ValueError: If expected features are missing from computed features
        """
        # Resolve what we need
        resolved = self.feature_resolver.resolve(self.config)

        # Group requirements by timeframe
        tf_requirements = self._group_requirements_by_timeframe(resolved)

        feature_dfs: list[pd.DataFrame] = []
        for timeframe, df in data.items():
            if timeframe not in tf_requirements:
                logger.debug(
                    f"Skipping timeframe {timeframe} - not required by nn_inputs"
                )
                continue

            reqs = tf_requirements[timeframe]

            # Compute indicators
            indicator_df = self.indicator_engine.compute_for_timeframe(
                df, timeframe, reqs["indicators"]
            )

            # Apply fuzzy sets
            for fuzzy_set_id in reqs["fuzzy_sets"]:
                indicator_ref = self.fuzzy_engine.get_indicator_for_fuzzy_set(
                    fuzzy_set_id
                )

                # Handle dot notation for multi-output indicators
                if "." in indicator_ref:
                    base_indicator, output_name = indicator_ref.split(".", 1)
                    indicator_col = f"{timeframe}_{base_indicator}.{output_name}"
                else:
                    indicator_col = f"{timeframe}_{indicator_ref}"

                # Check if column exists
                if indicator_col not in indicator_df.columns:
                    raise ValueError(
                        f"Indicator column '{indicator_col}' not found in data. "
                        f"Available columns: {list(indicator_df.columns)}"
                    )

                # Fuzzify indicator values
                fuzzify_result = self.fuzzy_engine.fuzzify(
                    fuzzy_set_id, indicator_df[indicator_col]
                )

                # Type assertion (v3 mode always returns DataFrame for Series input)
                if not isinstance(fuzzify_result, pd.DataFrame):
                    raise TypeError(
                        f"Expected DataFrame from fuzzify, got {type(fuzzify_result)}"
                    )
                fuzzy_df: pd.DataFrame = fuzzify_result

                # Add timeframe prefix to fuzzy columns
                fuzzy_df = fuzzy_df.rename(
                    columns={col: f"{timeframe}_{col}" for col in fuzzy_df.columns}
                )
                feature_dfs.append(fuzzy_df)

        if not feature_dfs:
            raise ValueError("No features computed - check data and configuration")

        result = pd.concat(feature_dfs, axis=1)

        # CRITICAL: Validate and reorder
        self._validate_features(result)
        result = result[self.expected_features]

        return result

    def _group_requirements_by_timeframe(
        self, resolved: list["ResolvedFeature"]
    ) -> dict[str, dict]:
        """Group indicator and fuzzy set requirements by timeframe.

        Args:
            resolved: List of resolved features from FeatureResolver

        Returns:
            Dict mapping timeframe to {indicators: set, fuzzy_sets: set}
        """
        result: dict[str, dict] = {}
        for f in resolved:
            if f.timeframe not in result:
                result[f.timeframe] = {"indicators": set(), "fuzzy_sets": set()}
            result[f.timeframe]["indicators"].add(f.indicator_id)
            result[f.timeframe]["fuzzy_sets"].add(f.fuzzy_set_id)
        return result

    def _validate_features(self, result: pd.DataFrame) -> None:
        """Validate features match expected from model metadata.

        Args:
            result: Computed features DataFrame

        Raises:
            ValueError: If expected features are missing
        """
        produced = set(result.columns)
        expected = set(self.expected_features)

        missing = expected - produced
        if missing:
            raise ValueError(
                f"Feature mismatch: missing {len(missing)} features.\n"
                f"Missing: {sorted(missing)[:5]}{'...' if len(missing) > 5 else ''}\n"
                f"This usually means the strategy config doesn't match the trained model."
            )

        extra = produced - expected
        if extra:
            logger.warning(
                f"Extra features will be ignored: {sorted(extra)[:5]}"
                f"{'...' if len(extra) > 5 else ''}"
            )

    def _validate_feature_order(self, result: pd.DataFrame) -> None:
        """Validate feature order matches expected EXACTLY.

        This is critical because neural networks are not invariant to
        input order — the same features in different order will produce
        garbage predictions.

        Args:
            result: Computed features DataFrame

        Raises:
            ValueError: If feature order doesn't match expected
        """
        computed_order = list(result.columns)
        expected_order = self.expected_features

        if computed_order != expected_order:
            # Check length first
            if len(computed_order) != len(expected_order):
                raise ValueError(
                    f"Feature count mismatch: "
                    f"expected {len(expected_order)}, got {len(computed_order)}. "
                    f"This is a bug in feature generation. Please report this issue."
                )

            # Find first mismatch position
            for i, (computed, expected) in enumerate(
                zip(computed_order, expected_order)
            ):
                if computed != expected:
                    raise ValueError(
                        f"Feature order mismatch at position {i}:\n"
                        f"  Expected: {expected}\n"
                        f"  Got: {computed}\n"
                        f"This is a bug in feature generation. "
                        f"Please report this issue."
                    )

    def compute_all_features(self, historical_data: pd.DataFrame) -> None:
        """Pre-compute all features for backtesting (v2 compatibility interface).

        This method adapts FeatureCacheV3 to the same interface as FeatureCache
        so DecisionOrchestrator can use it seamlessly.

        Lifecycle / migration notes:
        - This method, together with ``get_features_for_timestamp`` and ``is_ready``,
          forms a temporary v2-compatibility layer.
        - The long-term goal is to refactor DecisionOrchestrator (and any other
          consumers) to use the native v3 feature interface directly.
        - Once all callers are migrated to the v3 API, this compatibility layer may
          be removed.

        Args:
            historical_data: Complete historical OHLCV data
        """
        logger.info(
            f"FeatureCacheV3: Pre-computing features for {len(historical_data)} bars..."
        )

        # Get base timeframe from config
        base_timeframe: str | None = None
        if hasattr(self.config, "training_data") and self.config.training_data:
            if hasattr(self.config.training_data, "timeframes"):
                tf = getattr(
                    self.config.training_data.timeframes, "base_timeframe", None
                )
                if tf:
                    base_timeframe = tf

        if base_timeframe is None:
            logger.warning(
                "FeatureCacheV3: base_timeframe not found in config; "
                'falling back to default "1h". This may cause mismatches if '
                "the model was trained on a different base timeframe."
            )
            base_timeframe = "1h"

        # V3 compute_features expects dict[timeframe, DataFrame]
        data = {base_timeframe: historical_data}

        # Compute features
        self._cached_features = self.compute_features(data)
        self._cached_index = historical_data.index

        logger.info(
            f"FeatureCacheV3: Cached {len(self._cached_features)} bars x "
            f"{len(self._cached_features.columns)} features"
        )

    def get_features_for_timestamp(
        self,
        timestamp: pd.Timestamp,
        symbol: str,
        timeframe: str,
    ) -> dict[str, float] | None:
        """Get pre-computed features for a specific timestamp.

        Args:
            timestamp: Target timestamp
            symbol: Trading symbol (unused in v3 - single symbol)
            timeframe: Timeframe (unused in v3 - features already resolved)

        Returns:
            Dict of feature_id -> value, or None if not found
        """
        if not self.is_ready():
            return None

        if timestamp not in self._cached_features.index:
            return None

        row = self._cached_features.loc[timestamp]
        return {str(k): float(v) for k, v in row.to_dict().items()}

    def is_ready(self) -> bool:
        """Check if feature cache has pre-computed features.

        Returns:
            True if features are cached and ready to use
        """
        return (
            hasattr(self, "_cached_features")
            and self._cached_features is not None
            and len(self._cached_features) > 0
        )


if TYPE_CHECKING:
    from ktrdr.config.feature_resolver import ResolvedFeature
    from ktrdr.config.models import StrategyConfigurationV3
    from ktrdr.models.model_metadata import ModelMetadataV3
