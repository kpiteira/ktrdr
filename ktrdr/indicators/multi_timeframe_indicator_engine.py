"""
Multi-Timeframe Indicator Engine for KTRDR Phase 5.

This module provides the MultiTimeframeIndicatorEngine class, which computes
technical indicators across multiple timeframes with standardized column naming.
"""

from dataclasses import dataclass
from typing import Any

import pandas as pd

from ktrdr.errors import ConfigurationError, ProcessingError
from ktrdr.indicators.indicator_engine import IndicatorEngine
from ktrdr.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TimeframeIndicatorConfig:
    """Configuration for indicators on a specific timeframe."""

    timeframe: str
    indicators: list[dict[str, Any]]
    enabled: bool = True
    weight: float = 1.0


class MultiTimeframeIndicatorEngine:
    """
    Engine for computing technical indicators across multiple timeframes.

    This engine extends the standard IndicatorEngine to support multi-timeframe
    analysis with standardized column naming conventions. It ensures that
    indicators computed on different timeframes can be properly identified
    and used in multi-timeframe neuro-fuzzy systems.

    Column Naming Convention:
    - Format: {indicator_name}_{timeframe}
    - Examples: RSI_1h, SMA_20_4h, MACD_line_1d
    """

    def __init__(self, timeframe_configs: list[TimeframeIndicatorConfig]):
        """
        Initialize the MultiTimeframeIndicatorEngine.

        Args:
            timeframe_configs: List of timeframe-specific indicator configurations
        """
        self.timeframe_configs = timeframe_configs
        self.engines: dict[str, IndicatorEngine] = {}

        # Initialize individual engines for each timeframe
        for config in timeframe_configs:
            if config.enabled:
                self.engines[config.timeframe] = IndicatorEngine(config.indicators)

        logger.info(
            f"Initialized MultiTimeframeIndicatorEngine with {len(self.engines)} timeframes"
        )

    def get_supported_timeframes(self) -> list[str]:
        """
        Get list of supported timeframes.

        Returns:
            List of supported timeframes
        """
        return list(self.engines.keys())

    def apply_multi_timeframe(
        self, multi_timeframe_data: dict[str, pd.DataFrame]
    ) -> dict[str, pd.DataFrame]:
        """
        Apply indicators to multi-timeframe data with standardized naming.

        Args:
            multi_timeframe_data: Dictionary mapping timeframes to DataFrames
                                 containing OHLCV data

        Returns:
            Dictionary mapping timeframes to DataFrames with computed indicators
            using standardized column naming

        Raises:
            ConfigurationError: If timeframe data is missing or invalid
            ProcessingError: If indicator computation fails
        """
        if not multi_timeframe_data:
            raise ConfigurationError(
                "No multi-timeframe data provided", "CONFIG-EmptyData", {}
            )

        result = {}

        for timeframe, engine in self.engines.items():
            if timeframe not in multi_timeframe_data:
                logger.warning(f"Missing data for timeframe {timeframe}")
                continue

            data = multi_timeframe_data[timeframe]
            if data is None or data.empty:
                logger.warning(f"Empty data for timeframe {timeframe}")
                continue

            try:
                # Apply indicators for this timeframe
                logger.debug(f"Computing indicators for timeframe {timeframe}")
                indicators_df = engine.apply(data)

                # Standardize column names
                standardized_df = self._standardize_column_names(
                    indicators_df, timeframe, data.columns.tolist()
                )

                result[timeframe] = standardized_df
                logger.debug(f"Successfully computed indicators for {timeframe}")

            except Exception as e:
                logger.error(
                    f"Error computing indicators for timeframe {timeframe}: {str(e)}"
                )
                raise ProcessingError(
                    f"Failed to compute indicators for timeframe {timeframe}: {str(e)}",
                    "PROC-MultiTimeframeIndicatorFailed",
                    {"timeframe": timeframe, "error": str(e)},
                ) from e

        logger.info(f"Successfully computed indicators for {len(result)} timeframes")
        return result

    def _standardize_column_names(
        self, indicators_df: pd.DataFrame, timeframe: str, original_columns: list[str]
    ) -> pd.DataFrame:
        """
        Standardize column names with timeframe suffix.

        Args:
            indicators_df: DataFrame with computed indicators
            timeframe: The timeframe being processed
            original_columns: List of original OHLCV columns to preserve

        Returns:
            DataFrame with standardized column names
        """
        standardized_df = indicators_df.copy()

        # Preserve original OHLCV columns without timeframe suffix
        preserved_columns = set(original_columns + ["timestamp", "volume"])

        # Rename indicator columns with timeframe suffix
        column_mapping = {}
        for col in indicators_df.columns:
            if col not in preserved_columns:
                # Add timeframe suffix to indicator columns
                if not col.endswith(f"_{timeframe}"):
                    column_mapping[col] = f"{col}_{timeframe}"

        if column_mapping:
            standardized_df = standardized_df.rename(columns=column_mapping)
            logger.debug(
                f"Renamed {len(column_mapping)} indicator columns for timeframe {timeframe}"
            )

        return standardized_df

    def get_indicator_columns(self, timeframe: str) -> list[str]:
        """
        Get list of indicator column names for a specific timeframe.

        Args:
            timeframe: The timeframe to get indicator columns for

        Returns:
            List of standardized indicator column names
        """
        if timeframe not in self.engines:
            return []

        engine = self.engines[timeframe]
        indicator_names = []

        for indicator in engine.indicators:
            # Get the indicator's output column names
            indicator_name = getattr(indicator, "name", indicator.__class__.__name__)

            # Apply standardization
            standardized_name = f"{indicator_name}_{timeframe}"
            indicator_names.append(standardized_name)

        return indicator_names

    def get_all_indicator_columns(self) -> dict[str, list[str]]:
        """
        Get all indicator column names for all timeframes.

        Returns:
            Dictionary mapping timeframes to lists of indicator column names
        """
        return {
            timeframe: self.get_indicator_columns(timeframe)
            for timeframe in self.engines.keys()
        }

    def compute_specific_indicator(
        self, data: pd.DataFrame, timeframe: str, indicator_type: str, **kwargs: Any
    ) -> pd.DataFrame:
        """
        Compute a specific indicator for a timeframe with standardized naming.

        Args:
            data: DataFrame with OHLCV data
            timeframe: The timeframe identifier
            indicator_type: Type of indicator (RSI, SMA, etc.)
            **kwargs: Additional parameters for the indicator

        Returns:
            DataFrame with the computed indicator using standardized naming
        """
        if timeframe not in self.engines:
            raise ConfigurationError(
                f"No engine configured for timeframe {timeframe}",
                "CONFIG-InvalidTimeframe",
                {"timeframe": timeframe},
            )

        engine = self.engines[timeframe]

        # Use specific compute methods from IndicatorEngine
        if indicator_type.upper() == "RSI":
            result_df = engine.compute_rsi(data, **kwargs)
        elif indicator_type.upper() == "SMA":
            result_df = engine.compute_sma(data, **kwargs)
        elif indicator_type.upper() == "EMA":
            result_df = engine.compute_ema(data, **kwargs)
        elif indicator_type.upper() == "MACD":
            result_df = engine.compute_macd(data, **kwargs)
        else:
            raise ConfigurationError(
                f"Unsupported indicator type: {indicator_type}",
                "CONFIG-UnsupportedIndicator",
                {"indicator_type": indicator_type},
            )

        # Standardize column names
        original_columns = data.columns.tolist()
        standardized_df = self._standardize_column_names(
            result_df, timeframe, original_columns
        )

        return standardized_df

    def create_cross_timeframe_features(
        self,
        multi_timeframe_indicators: dict[str, pd.DataFrame],
        feature_specs: dict[str, dict[str, Any]],
    ) -> pd.DataFrame:
        """
        Create cross-timeframe features by combining indicators from different timeframes.

        Args:
            multi_timeframe_indicators: Dict of timeframe -> indicators DataFrame
            feature_specs: Specifications for cross-timeframe features

        Returns:
            DataFrame with cross-timeframe features
        """
        cross_features = {}

        for feature_name, spec in feature_specs.items():
            try:
                primary_tf = spec.get("primary_timeframe")
                secondary_tf = spec.get("secondary_timeframe")
                operation = spec.get("operation", "ratio")

                if (
                    primary_tf not in multi_timeframe_indicators
                    or secondary_tf not in multi_timeframe_indicators
                ):
                    logger.warning(
                        f"Missing timeframe data for cross-feature {feature_name}"
                    )
                    continue

                primary_col = spec.get("primary_column")
                secondary_col = spec.get("secondary_column")

                primary_data = multi_timeframe_indicators[primary_tf]
                secondary_data = multi_timeframe_indicators[secondary_tf]

                if (
                    primary_col not in primary_data.columns
                    or secondary_col not in secondary_data.columns
                ):
                    logger.warning(f"Missing columns for cross-feature {feature_name}")
                    continue

                # Align the data by timestamp (use latest available values)
                primary_values = primary_data[primary_col].ffill()
                secondary_values = secondary_data[secondary_col].ffill()

                # Perform the specified operation
                if operation == "ratio":
                    cross_features[feature_name] = primary_values / secondary_values
                elif operation == "difference":
                    cross_features[feature_name] = primary_values - secondary_values
                elif operation == "correlation":
                    # Rolling correlation
                    window = spec.get("window", 20)
                    cross_features[feature_name] = primary_values.rolling(window).corr(
                        secondary_values
                    )
                else:
                    logger.warning(
                        f"Unknown operation {operation} for cross-feature {feature_name}"
                    )

            except Exception as e:
                logger.error(f"Error creating cross-feature {feature_name}: {str(e)}")
                continue

        if cross_features:
            return pd.DataFrame(cross_features)
        else:
            return pd.DataFrame()

    def validate_configuration(self) -> dict[str, Any]:
        """
        Validate the multi-timeframe indicator configuration.

        Returns:
            Dictionary with validation results and recommendations
        """
        validation_results: dict[str, Any] = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "recommendations": [],
            "summary": {},
        }

        # Check timeframe coverage
        timeframes = list(self.engines.keys())
        validation_results["summary"]["timeframes"] = timeframes
        validation_results["summary"]["total_engines"] = len(self.engines)

        # Validate timeframe hierarchy
        expected_hierarchy = ["1m", "5m", "15m", "1h", "4h", "1d", "1w"]
        hierarchy_violations = []

        for i, tf in enumerate(timeframes):
            if tf in expected_hierarchy:
                tf_index = expected_hierarchy.index(tf)
                # Check if we have appropriate higher timeframes
                higher_tfs = [
                    t for t in timeframes if t in expected_hierarchy[tf_index + 1 :]
                ]
                if not higher_tfs and i < len(timeframes) - 1:
                    hierarchy_violations.append(
                        f"Timeframe {tf} lacks higher timeframe context"
                    )

        if hierarchy_violations:
            validation_results["warnings"].extend(hierarchy_violations)

        # Check indicator consistency across timeframes
        indicator_types_by_tf = {}
        for tf, engine in self.engines.items():
            indicator_types = [ind.__class__.__name__ for ind in engine.indicators]
            indicator_types_by_tf[tf] = set(indicator_types)

        # Find common indicators across timeframes
        if len(indicator_types_by_tf) > 1:
            common_indicators = set.intersection(*indicator_types_by_tf.values())
            unique_indicators = {}

            for tf, indicators in indicator_types_by_tf.items():
                unique = indicators - common_indicators
                if unique:
                    unique_indicators[tf] = unique

            validation_results["summary"]["common_indicators"] = list(common_indicators)
            validation_results["summary"]["unique_indicators"] = unique_indicators

            if len(common_indicators) == 0:
                validation_results["warnings"].append(
                    "No common indicators across timeframes - may reduce cross-timeframe signal quality"
                )

        # Performance recommendations
        total_indicators = sum(
            len(engine.indicators) for engine in self.engines.values()
        )
        if total_indicators > 50:
            validation_results["recommendations"].append(
                f"High indicator count ({total_indicators}) may impact performance"
            )

        # Check for redundant indicators
        redundant_pairs = []
        for tf, engine in self.engines.items():
            indicator_classes = [ind.__class__.__name__ for ind in engine.indicators]
            class_counts: dict[str, int] = {}
            for cls in indicator_classes:
                class_counts[cls] = class_counts.get(cls, 0) + 1

            for cls, count in class_counts.items():
                if count > 1:
                    redundant_pairs.append(f"{tf}: {count}x {cls}")

        if redundant_pairs:
            validation_results["warnings"].append(
                f"Redundant indicators found: {redundant_pairs}"
            )

        # Final validation status
        if validation_results["errors"]:
            validation_results["valid"] = False

        logger.info(
            f"Multi-timeframe indicator configuration validation completed: {validation_results['valid']}"
        )
        return validation_results


def create_multi_timeframe_engine_from_config(
    config: dict[str, Any],
) -> MultiTimeframeIndicatorEngine:
    """
    Create MultiTimeframeIndicatorEngine from configuration dictionary.

    Args:
        config: Configuration dictionary with timeframe specifications

    Returns:
        Configured MultiTimeframeIndicatorEngine instance
    """
    timeframe_configs = []

    for timeframe, tf_config in config.get("timeframes", {}).items():
        indicators = tf_config.get("indicators", [])
        enabled = tf_config.get("enabled", True)
        weight = tf_config.get("weight", 1.0)

        tf_indicator_config = TimeframeIndicatorConfig(
            timeframe=timeframe, indicators=indicators, enabled=enabled, weight=weight
        )
        timeframe_configs.append(tf_indicator_config)

    return MultiTimeframeIndicatorEngine(timeframe_configs)
