"""Feature caching system for backtesting performance optimization."""

from typing import TYPE_CHECKING, Any

import pandas as pd

from .. import get_logger
from ..fuzzy.engine import FuzzyEngine
from ..indicators.indicator_engine import IndicatorEngine

logger = get_logger(__name__)


class FeatureCache:
    """Feature cache for v3 strategy configurations.

    This class computes features for backtesting using v3 strategy config
    and validates them against model metadata to ensure feature alignment
    with training.

    The feature ordering is CRITICAL:
    - Features must be computed in the same order as training
    - Order is validated against ModelMetadata.resolved_features
    - Any mismatch will cause garbage predictions

    Mirrors TrainingPipeline.prepare_features() but for single-symbol data.
    """

    def __init__(
        self,
        config: "StrategyConfigurationV3",
        model_metadata: "ModelMetadata",
    ):
        """Initialize FeatureCache with v3 strategy configuration.

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

        # Cached features for backtesting
        self._cached_features: pd.DataFrame | None = None
        self._cached_index: pd.Index | None = None

        logger.info(
            f"FeatureCache initialized: "
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

    def compute_all_features(self, historical_data: pd.DataFrame) -> None:
        """Pre-compute all features for backtesting.

        Args:
            historical_data: Complete historical OHLCV data
        """
        logger.info(
            f"FeatureCache: Pre-computing features for {len(historical_data)} bars..."
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
                "FeatureCache: base_timeframe not found in config; "
                'falling back to default "1h". This may cause mismatches if '
                "the model was trained on a different base timeframe."
            )
            base_timeframe = "1h"

        # compute_features expects dict[timeframe, DataFrame]
        data = {base_timeframe: historical_data}

        # Compute features
        self._cached_features = self.compute_features(data)
        self._cached_index = historical_data.index

        logger.info(
            f"FeatureCache: Cached {len(self._cached_features)} bars x "
            f"{len(self._cached_features.columns)} features"
        )

    def get_features_for_timestamp(
        self,
        timestamp: pd.Timestamp,
    ) -> dict[str, float] | None:
        """Get pre-computed features for a specific timestamp.

        Args:
            timestamp: Target timestamp

        Returns:
            Dict of feature_id -> value, or None if not found
        """
        if not self.is_ready():
            return None

        if self._cached_features is None:
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
        return self._cached_features is not None and len(self._cached_features) > 0

    def _group_requirements_by_timeframe(
        self, resolved: list["ResolvedFeature"]
    ) -> dict[str, dict[str, Any]]:
        """Group indicator and fuzzy set requirements by timeframe.

        Args:
            resolved: List of resolved features from FeatureResolver

        Returns:
            Dict mapping timeframe to {indicators: set, fuzzy_sets: set}
        """
        result: dict[str, dict[str, Any]] = {}
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


if TYPE_CHECKING:
    from ktrdr.config.feature_resolver import ResolvedFeature
    from ktrdr.config.models import StrategyConfigurationV3
    from ktrdr.models.model_metadata import ModelMetadata
