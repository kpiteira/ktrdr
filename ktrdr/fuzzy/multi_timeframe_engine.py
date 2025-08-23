"""
Multi-Timeframe Fuzzy Engine for KTRDR.

This module extends the existing FuzzyEngine to handle multi-timeframe indicator
data with timeframe-specific fuzzy sets and configurations.
"""

from dataclasses import dataclass
from typing import Any, Optional, Union

import pandas as pd

from ktrdr import get_logger
from ktrdr.errors import ConfigurationError, DataValidationError, ProcessingError
from ktrdr.fuzzy.config import (
    FuzzyConfig,
    FuzzySetConfig,
    GaussianMFConfig,
    TrapezoidalMFConfig,
    TriangularMFConfig,
)
from ktrdr.fuzzy.engine import FuzzyEngine

# Set up module-level logger
logger = get_logger(__name__)


@dataclass
class TimeframeConfig:
    """Configuration for a specific timeframe's fuzzy logic processing."""

    timeframe: str
    indicators: list[str]
    fuzzy_sets: dict[str, FuzzySetConfig]
    weight: float = 1.0
    enabled: bool = True


@dataclass
class MultiTimeframeFuzzyResult:
    """Result of multi-timeframe fuzzy processing."""

    fuzzy_values: dict[str, float]
    timeframe_results: dict[str, dict[str, float]]
    metadata: dict[str, Any]
    warnings: list[str]
    processing_time: float


class MultiTimeframeFuzzyEngine(FuzzyEngine):
    """
    Fuzzy engine with multi-timeframe input support.

    This engine extends the base FuzzyEngine to handle indicators across multiple
    timeframes with timeframe-specific fuzzy sets and membership functions.

    Features:
    - Timeframe-specific fuzzy configurations
    - Automatic timeframe validation
    - Graceful degradation when timeframes unavailable
    - Consistent naming convention for multi-timeframe outputs

    Example:
        ```python
        # Create multi-timeframe fuzzy engine
        mt_engine = MultiTimeframeFuzzyEngine(multi_timeframe_config)

        # Process indicators across timeframes
        indicator_data = {
            "1h": {"rsi": 35.0, "macd": -0.02},
            "4h": {"rsi": 45.0, "macd": 0.01},
            "1d": {"trend_strength": 0.6}
        }

        result = mt_engine.fuzzify_multi_timeframe(indicator_data)
        print(result.fuzzy_values)  # All fuzzy membership values
        ```
    """

    def __init__(self, config: Union[FuzzyConfig, dict[str, Any]]):
        """
        Initialize the MultiTimeframeFuzzyEngine.

        Args:
            config: Either a FuzzyConfig for backward compatibility or a dict
                   containing multi-timeframe fuzzy configuration

        Raises:
            ConfigurationError: If the configuration is invalid
        """
        logger.debug("Initializing MultiTimeframeFuzzyEngine")

        # Handle backward compatibility with single-timeframe configs
        if isinstance(config, FuzzyConfig):
            logger.info(
                "Backward compatibility mode: converting single-timeframe config"
            )
            super().__init__(config)
            self._timeframe_configs = {}
            self._is_multi_timeframe = False
        else:
            # Multi-timeframe configuration
            self._multi_config = config
            self._validate_multi_timeframe_config()
            self._timeframe_configs = self._build_timeframe_configs()
            self._is_multi_timeframe = True

            # Initialize base class with merged config for compatibility
            merged_config = self._create_merged_config()
            super().__init__(merged_config)

        logger.info(
            f"MultiTimeframeFuzzyEngine initialized "
            f"(multi-timeframe: {self._is_multi_timeframe})"
        )

    def _validate_multi_timeframe_config(self) -> None:
        """
        Validate the multi-timeframe fuzzy configuration.

        Raises:
            ConfigurationError: If the configuration is invalid
        """
        if not self._multi_config:
            raise ConfigurationError(
                message="Multi-timeframe fuzzy configuration cannot be empty",
                error_code="MTFUZZY-EmptyConfig",
                details={},
            )

        required_keys = ["timeframes", "indicators"]
        for key in required_keys:
            if key not in self._multi_config:
                raise ConfigurationError(
                    message=f"Multi-timeframe config missing required key: {key}",
                    error_code="MTFUZZY-MissingKey",
                    details={"missing_key": key, "required_keys": required_keys},
                )

        # Validate timeframes
        timeframes = self._multi_config["timeframes"]
        if not timeframes or not isinstance(timeframes, dict):
            raise ConfigurationError(
                message="Timeframes configuration must be a non-empty dictionary",
                error_code="MTFUZZY-InvalidTimeframes",
                details={"timeframes": timeframes},
            )

        # Validate each timeframe configuration
        for tf_name, tf_config in timeframes.items():
            self._validate_timeframe_config(tf_name, tf_config)

        logger.debug(
            f"Validated multi-timeframe config with timeframes: {list(timeframes.keys())}"
        )

    def _validate_timeframe_config(
        self, timeframe: str, config: dict[str, Any]
    ) -> None:
        """
        Validate configuration for a specific timeframe.

        Args:
            timeframe: Timeframe name (e.g., "1h", "4h", "1d")
            config: Timeframe-specific configuration

        Raises:
            ConfigurationError: If the timeframe configuration is invalid
        """
        required_keys = ["indicators", "fuzzy_sets"]
        for key in required_keys:
            if key not in config:
                raise ConfigurationError(
                    message=f"Timeframe {timeframe} missing required key: {key}",
                    error_code="MTFUZZY-MissingTimeframeKey",
                    details={
                        "timeframe": timeframe,
                        "missing_key": key,
                        "required_keys": required_keys,
                    },
                )

        # Validate indicators
        indicators = config["indicators"]
        if not indicators or not isinstance(indicators, list):
            raise ConfigurationError(
                message=f"Timeframe {timeframe} indicators must be a non-empty list",
                error_code="MTFUZZY-InvalidIndicators",
                details={"timeframe": timeframe, "indicators": indicators},
            )

        # Validate fuzzy sets
        fuzzy_sets = config["fuzzy_sets"]
        if not fuzzy_sets or not isinstance(fuzzy_sets, dict):
            raise ConfigurationError(
                message=f"Timeframe {timeframe} fuzzy_sets must be a non-empty dictionary",
                error_code="MTFUZZY-InvalidFuzzySets",
                details={"timeframe": timeframe, "fuzzy_sets": fuzzy_sets},
            )

    def _build_timeframe_configs(self) -> dict[str, TimeframeConfig]:
        """
        Build TimeframeConfig objects from the configuration.

        Returns:
            Dictionary mapping timeframe names to TimeframeConfig objects
        """
        configs = {}

        for tf_name, tf_config in self._multi_config["timeframes"].items():
            # Convert fuzzy sets to FuzzySetConfig objects
            fuzzy_sets = {}
            for indicator, sets in tf_config["fuzzy_sets"].items():
                for set_name, mf_config in sets.items():
                    key = f"{indicator}_{set_name}"

                    # Create the appropriate membership function config based on type
                    mf_type = mf_config["type"].lower()
                    if mf_type == "triangular":
                        mf_instance = TriangularMFConfig(**mf_config)
                    elif mf_type == "trapezoidal":
                        mf_instance = TrapezoidalMFConfig(**mf_config)
                    elif mf_type == "gaussian":
                        mf_instance = GaussianMFConfig(**mf_config)
                    else:
                        raise ConfigurationError(
                            message=f"Unknown membership function type: {mf_type}",
                            error_code="MTFUZZY-UnknownMFType",
                            details={
                                "type": mf_type,
                                "supported": ["triangular", "trapezoidal", "gaussian"],
                            },
                        )

                    fuzzy_sets[key] = FuzzySetConfig(root={set_name: mf_instance})

            configs[tf_name] = TimeframeConfig(
                timeframe=tf_name,
                indicators=tf_config["indicators"],
                fuzzy_sets=fuzzy_sets,
                weight=tf_config.get("weight", 1.0),
                enabled=tf_config.get("enabled", True),
            )

        return configs

    def _create_merged_config(self) -> FuzzyConfig:
        """
        Create a merged FuzzyConfig for base class compatibility.

        Returns:
            FuzzyConfig with all timeframe configurations merged
        """
        merged_indicators = {}

        for tf_name, tf_config in self._timeframe_configs.items():
            if not tf_config.enabled:
                continue

            for indicator in tf_config.indicators:
                # Create timeframe-specific indicator name
                tf_indicator = f"{indicator}_{tf_name}"

                # Get fuzzy sets for this indicator from timeframe config
                indicator_fuzzy_sets = {}
                for key, fuzzy_set_config in tf_config.fuzzy_sets.items():
                    if key.startswith(f"{indicator}_"):
                        set_name = key[len(f"{indicator}_") :]
                        for fs_name, mf_config in fuzzy_set_config.root.items():
                            indicator_fuzzy_sets[fs_name] = mf_config

                if indicator_fuzzy_sets:
                    merged_indicators[tf_indicator] = FuzzySetConfig(
                        root=indicator_fuzzy_sets
                    )

        return FuzzyConfig(root=merged_indicators)

    def fuzzify_multi_timeframe(
        self,
        indicator_data: dict[str, dict[str, float]],
        timeframe_filter: Optional[list[str]] = None,
    ) -> MultiTimeframeFuzzyResult:
        """
        Fuzzify indicators across multiple timeframes.

        Args:
            indicator_data: Nested dict {timeframe: {indicator: value}}
            timeframe_filter: Optional list of timeframes to process

        Returns:
            MultiTimeframeFuzzyResult with all fuzzy membership values

        Raises:
            DataValidationError: If input data is invalid
            ProcessingError: If fuzzification fails
        """
        import time

        start_time = time.time()

        logger.debug(
            f"Processing multi-timeframe fuzzy logic for {len(indicator_data)} timeframes"
        )

        # Validate input data
        self._validate_indicator_data(indicator_data)

        # Filter timeframes if requested
        timeframes_to_process = self._get_timeframes_to_process(
            indicator_data, timeframe_filter
        )

        # Process each timeframe
        all_fuzzy_values = {}
        timeframe_results = {}
        warnings = []

        for timeframe in timeframes_to_process:
            try:
                tf_result = self._process_timeframe(
                    timeframe, indicator_data[timeframe]
                )

                # Only add to results if timeframe is enabled and has results
                if tf_result:  # Only add if results exist
                    timeframe_results[timeframe] = tf_result

                    # Add timeframe prefix to fuzzy values
                    for key, value in tf_result.items():
                        prefixed_key = f"{key}_{timeframe}"
                        all_fuzzy_values[prefixed_key] = value

            except Exception as e:
                warning_msg = f"Failed to process timeframe {timeframe}: {str(e)}"
                warnings.append(warning_msg)
                logger.warning(warning_msg)
                continue

        processing_time = time.time() - start_time

        # Create result
        result = MultiTimeframeFuzzyResult(
            fuzzy_values=all_fuzzy_values,
            timeframe_results=timeframe_results,
            metadata={
                "processed_timeframes": list(timeframe_results.keys()),
                "total_fuzzy_values": len(all_fuzzy_values),
                "input_timeframes": list(indicator_data.keys()),
            },
            warnings=warnings,
            processing_time=processing_time,
        )

        logger.info(
            f"Multi-timeframe fuzzy processing completed in {processing_time:.3f}s "
            f"({len(timeframe_results)} timeframes, {len(all_fuzzy_values)} fuzzy values)"
        )

        return result

    def _validate_indicator_data(
        self, indicator_data: dict[str, dict[str, float]]
    ) -> None:
        """
        Validate the input indicator data structure.

        Args:
            indicator_data: Nested dict {timeframe: {indicator: value}}

        Raises:
            DataValidationError: If the data structure is invalid
        """
        if not indicator_data:
            raise DataValidationError(
                message="Indicator data cannot be empty",
                error_code="MTFUZZY-EmptyData",
                details={},
            )

        for timeframe, indicators in indicator_data.items():
            if not isinstance(indicators, dict):
                raise DataValidationError(
                    message=f"Indicators for timeframe {timeframe} must be a dictionary",
                    error_code="MTFUZZY-InvalidIndicatorStructure",
                    details={"timeframe": timeframe, "type": type(indicators).__name__},
                )

            for indicator, value in indicators.items():
                if not isinstance(value, (int, float)) or pd.isna(value):
                    raise DataValidationError(
                        message=f"Invalid value for {timeframe}.{indicator}: {value}",
                        error_code="MTFUZZY-InvalidIndicatorValue",
                        details={
                            "timeframe": timeframe,
                            "indicator": indicator,
                            "value": value,
                            "type": type(value).__name__,
                        },
                    )

    def _get_timeframes_to_process(
        self,
        indicator_data: dict[str, dict[str, float]],
        timeframe_filter: Optional[list[str]],
    ) -> list[str]:
        """
        Determine which timeframes to process based on available data and config.

        Args:
            indicator_data: Input indicator data
            timeframe_filter: Optional filter for specific timeframes

        Returns:
            List of timeframes to process
        """
        available_timeframes = set(indicator_data.keys())

        if self._is_multi_timeframe:
            configured_timeframes = set(self._timeframe_configs.keys())
            # Filter out disabled timeframes
            enabled_timeframes = {
                tf for tf, config in self._timeframe_configs.items() if config.enabled
            }
            # Only process timeframes that are available, configured, and enabled
            candidate_timeframes = available_timeframes.intersection(
                configured_timeframes
            ).intersection(enabled_timeframes)
        else:
            # Single-timeframe mode: process all available timeframes
            candidate_timeframes = available_timeframes

        # Apply filter if provided
        if timeframe_filter:
            candidate_timeframes = candidate_timeframes.intersection(
                set(timeframe_filter)
            )

        return sorted(list(candidate_timeframes))

    def _process_timeframe(
        self, timeframe: str, indicators: dict[str, float]
    ) -> dict[str, float]:
        """
        Process fuzzy logic for a single timeframe.

        Args:
            timeframe: Timeframe identifier (e.g., "1h", "4h")
            indicators: Dict of {indicator: value} for this timeframe

        Returns:
            Dict of {fuzzy_set_name: membership_value}

        Raises:
            ProcessingError: If processing fails
        """
        logger.debug(f"Processing fuzzy logic for timeframe {timeframe}")

        result = {}

        # Get timeframe configuration
        if self._is_multi_timeframe and timeframe in self._timeframe_configs:
            tf_config = self._timeframe_configs[timeframe]
            if not tf_config.enabled:
                logger.debug(f"Timeframe {timeframe} is disabled, skipping")
                return result

            configured_indicators = tf_config.indicators
        else:
            # Single-timeframe mode or unconfigured timeframe: process all indicators
            configured_indicators = list(indicators.keys())

        # Process each indicator
        for indicator in configured_indicators:
            if indicator not in indicators:
                logger.warning(
                    f"Indicator {indicator} not available for timeframe {timeframe}"
                )
                continue

            value = indicators[indicator]

            try:
                # Create timeframe-specific indicator name for base class
                tf_indicator = (
                    f"{indicator}_{timeframe}"
                    if self._is_multi_timeframe
                    else indicator
                )

                # Use base class fuzzify method
                fuzzy_result = self.fuzzify(tf_indicator, value)

                # Remove timeframe suffix from output names for cleaner result
                for fuzzy_name, membership in fuzzy_result.items():
                    if self._is_multi_timeframe and fuzzy_name.endswith(
                        f"_{timeframe}"
                    ):
                        clean_name = fuzzy_name[: -len(f"_{timeframe}")]
                    else:
                        clean_name = fuzzy_name
                    result[clean_name] = membership

            except Exception as e:
                logger.error(
                    f"Failed to fuzzify {indicator} for timeframe {timeframe}: {e}"
                )
                raise ProcessingError(
                    message=f"Fuzzification failed for {indicator} in timeframe {timeframe}",
                    error_code="MTFUZZY-FuzzificationError",
                    details={
                        "timeframe": timeframe,
                        "indicator": indicator,
                        "value": value,
                        "original_error": str(e),
                    },
                ) from e

        return result

    def get_timeframe_configurations(self) -> dict[str, TimeframeConfig]:
        """
        Get all timeframe configurations.

        Returns:
            Dictionary mapping timeframe names to TimeframeConfig objects
        """
        return self._timeframe_configs.copy()

    def get_supported_timeframes(self) -> list[str]:
        """
        Get list of supported timeframes.

        Returns:
            List of supported timeframe identifiers
        """
        if self._is_multi_timeframe:
            return list(self._timeframe_configs.keys())
        else:
            return []  # Single-timeframe mode

    def is_multi_timeframe_enabled(self) -> bool:
        """
        Check if multi-timeframe processing is enabled.

        Returns:
            True if multi-timeframe processing is enabled
        """
        return self._is_multi_timeframe


def create_multi_timeframe_fuzzy_engine(
    config: dict[str, Any],
) -> MultiTimeframeFuzzyEngine:
    """
    Factory function to create a MultiTimeframeFuzzyEngine.

    Args:
        config: Multi-timeframe fuzzy configuration

    Returns:
        Configured MultiTimeframeFuzzyEngine instance
    """
    return MultiTimeframeFuzzyEngine(config)
