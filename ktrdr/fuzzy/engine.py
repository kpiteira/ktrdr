"""
Fuzzy engine implementation for KTRDR.

This module provides the FuzzyEngine class that transforms indicator values
into fuzzy membership degrees according to configured membership functions.
"""

from typing import Optional, Union

import numpy as np
import pandas as pd

from ktrdr import get_logger
from ktrdr.errors import ConfigurationError, ProcessingError
from ktrdr.fuzzy.config import FuzzyConfig
from ktrdr.fuzzy.membership import (
    MembershipFunction,
    MembershipFunctionFactory,
)

# Set up module-level logger
logger = get_logger(__name__)


class FuzzyEngine:
    """
    FuzzyEngine for transforming indicator values into fuzzy membership degrees.

    The FuzzyEngine takes a FuzzyConfig configuration with membership functions
    for different indicators and transforms indicator values into fuzzy membership
    degrees according to these functions.

    Example:
        ```python
        # Create a FuzzyEngine with configuration
        fuzzy_engine = FuzzyEngine(config)

        # Fuzzify indicator values
        rsi_values = pd.Series([30.0, 45.0, 70.0])
        membership_degrees = fuzzy_engine.fuzzify("rsi", rsi_values)

        # Access membership degrees for specific fuzzy sets
        low_membership = membership_degrees["rsi_low"]
        medium_membership = membership_degrees["rsi_medium"]
        high_membership = membership_degrees["rsi_high"]
        ```
    """

    def __init__(self, config: FuzzyConfig):
        """
        Initialize the FuzzyEngine with a configuration.

        Args:
            config: FuzzyConfig object containing membership function configurations
                   for different indicators

        Raises:
            ConfigurationError: If the configuration is invalid
        """
        logger.debug("Initializing FuzzyEngine")
        self._config = config
        self._validate_config()
        self._membership_functions: dict[str, dict[str, MembershipFunction]] = {}
        self._initialize_membership_functions()
        logger.info(
            f"FuzzyEngine initialized with {len(self._membership_functions)} indicators"
        )

    def _validate_config(self) -> None:
        """
        Validate the fuzzy configuration.

        Raises:
            ConfigurationError: If the configuration is invalid
        """
        if not self._config or not self._config.root:
            logger.error("Empty fuzzy configuration")
            raise ConfigurationError(
                message="Fuzzy configuration cannot be empty",
                error_code="ENGINE-EmptyConfig",
                details={},
            )

        # The FuzzyConfig model already validates that each indicator has at least one fuzzy set,
        # and each fuzzy set has a valid membership function configuration.
        # We just need to check if there are any indicators defined.
        indicators = list(self._config.root.keys())
        if not indicators:
            logger.error("No indicators defined in fuzzy configuration")
            raise ConfigurationError(
                message="Fuzzy configuration must define at least one indicator",
                error_code="ENGINE-NoIndicators",
                details={},
            )

        logger.debug(f"Validated fuzzy configuration with indicators: {indicators}")

    def _initialize_membership_functions(self) -> None:
        """
        Initialize membership function instances from the configuration.

        Raises:
            ConfigurationError: If any membership function configuration is invalid
        """
        for indicator, fuzzy_sets in self._config.root.items():
            logger.debug(
                f"Initializing membership functions for indicator: {indicator}"
            )
            self._membership_functions[indicator] = {}

            for set_name, mf_config in fuzzy_sets.root.items():
                try:
                    # Use the membership function factory for all types
                    self._membership_functions[indicator][set_name] = (
                        MembershipFunctionFactory.create(
                            mf_config.type, mf_config.parameters
                        )
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to initialize membership function for {indicator}.{set_name}: {e}"
                    )
                    raise ConfigurationError(
                        message=f"Failed to initialize membership function for {indicator}.{set_name}",
                        error_code="ENGINE-MFInitializationError",
                        details={
                            "indicator": indicator,
                            "set_name": set_name,
                            "original_error": str(e),
                        },
                    ) from e

    def fuzzify(
        self, indicator: str, values: Union[float, pd.Series, np.ndarray]
    ) -> Union[dict[str, Union[float, pd.Series, np.ndarray]], pd.DataFrame]:
        """
        Fuzzify indicator values using the configured membership functions.

        For a single indicator value, returns a dictionary mapping fuzzy set names to membership degrees.
        For a series of indicator values, returns a DataFrame with columns for each fuzzy set.

        Args:
            indicator: Name of the indicator (e.g., "rsi", "macd")
            values: Indicator values to fuzzify (scalar, pandas Series, or numpy array)

        Returns:
            For scalar input: A dictionary mapping fuzzy set names to membership degrees
            For Series/array input: A DataFrame with columns for each fuzzy set

        Raises:
            ProcessingError: If the indicator is not in the configuration
            TypeError: If the input type is not supported
        """
        logger.debug(f"Fuzzifying values for indicator: {indicator}")

        # Check if the indicator exists in the configuration
        if indicator not in self._membership_functions:
            logger.error(f"Unknown indicator: {indicator}")
            raise ProcessingError(
                message=f"Unknown indicator: {indicator}",
                error_code="ENGINE-UnknownIndicator",
                details={
                    "indicator": indicator,
                    "available_indicators": list(self._membership_functions.keys()),
                },
            )

        # Get the membership functions for this indicator
        membership_functions = self._membership_functions[indicator]

        # Handle scalar input
        if isinstance(values, (int, float)):
            logger.debug(f"Fuzzifying scalar value {values} for indicator {indicator}")
            return self._fuzzify_scalar(indicator, values, membership_functions)  # type: ignore[return-value]

        # Handle pandas Series input
        elif isinstance(values, pd.Series):
            logger.debug(
                f"Fuzzifying pandas Series of length {len(values)} for indicator {indicator}"
            )
            return self._fuzzify_series(indicator, values, membership_functions)

        # Handle numpy array input
        elif isinstance(values, np.ndarray):
            logger.debug(
                f"Fuzzifying numpy array of shape {values.shape} for indicator {indicator}"
            )
            # Convert numpy array to pandas Series for consistent handling
            series = pd.Series(values)
            return self._fuzzify_series(indicator, series, membership_functions)

        # Handle unsupported input types
        else:
            logger.error(f"Unsupported input type for fuzzification: {type(values)}")
            raise TypeError(
                f"Unsupported input type: {type(values)}. Expected float, pd.Series, or np.ndarray."
            )

    def _fuzzify_scalar(
        self,
        indicator: str,
        value: float,
        membership_functions: dict[str, MembershipFunction],
    ) -> dict[str, float]:
        """
        Fuzzify a single indicator value.

        Args:
            indicator: Name of the indicator
            value: Indicator value to fuzzify
            membership_functions: Dictionary of membership functions for this indicator

        Returns:
            Dictionary mapping fuzzy set names to membership degrees
        """
        result: dict[str, float] = {}

        for set_name, mf in membership_functions.items():
            # Generate standardized output column name
            output_name = self._get_output_name(indicator, set_name)
            result[output_name] = float(mf.evaluate(value))

        return result

    def _fuzzify_series(
        self,
        indicator: str,
        values: pd.Series,
        membership_functions: dict[str, MembershipFunction],
    ) -> pd.DataFrame:
        """
        Fuzzify a series of indicator values.

        Args:
            indicator: Name of the indicator
            values: Series of indicator values to fuzzify
            membership_functions: Dictionary of membership functions for this indicator

        Returns:
            DataFrame with columns for each fuzzy set's membership degrees
        """
        result_dict = {}

        for set_name, mf in membership_functions.items():
            # Generate standardized output column name
            output_name = self._get_output_name(indicator, set_name)
            result_dict[output_name] = mf.evaluate(values)

        return pd.DataFrame(result_dict, index=values.index)

    def _get_output_name(self, indicator: str, set_name: str) -> str:
        """
        Generate a standardized output name for fuzzy set membership degrees.

        The standard format is: {indicator}_{set_name}
        For example: "rsi_low", "macd_positive"

        Args:
            indicator: Name of the indicator
            set_name: Name of the fuzzy set

        Returns:
            Standardized output name
        """
        return f"{indicator}_{set_name}"

    def get_available_indicators(self) -> list[str]:
        """
        Get a list of available indicators in the configuration.

        Returns:
            List of indicator names
        """
        return list(self._membership_functions.keys())

    def get_fuzzy_sets(self, indicator: str) -> list[str]:
        """
        Get a list of fuzzy sets defined for an indicator.

        Args:
            indicator: Name of the indicator

        Returns:
            List of fuzzy set names

        Raises:
            ProcessingError: If the indicator is not in the configuration
        """
        if indicator not in self._membership_functions:
            logger.error(f"Unknown indicator: {indicator}")
            raise ProcessingError(
                message=f"Unknown indicator: {indicator}",
                error_code="ENGINE-UnknownIndicator",
                details={
                    "indicator": indicator,
                    "available_indicators": list(self._membership_functions.keys()),
                },
            )

        return list(self._membership_functions[indicator].keys())

    def get_output_names(self, indicator: str) -> list[str]:
        """
        Get a list of output column names for an indicator.

        Args:
            indicator: Name of the indicator

        Returns:
            List of output column names

        Raises:
            ProcessingError: If the indicator is not in the configuration
        """
        fuzzy_sets = self.get_fuzzy_sets(indicator)
        return [self._get_output_name(indicator, set_name) for set_name in fuzzy_sets]

    def generate_multi_timeframe_memberships(
        self,
        multi_timeframe_indicators: dict[str, pd.DataFrame],
        fuzzy_sets_config: Optional[dict[str, dict]] = None,
    ) -> dict[str, pd.DataFrame]:
        """
        Generate fuzzy membership values for indicators across multiple timeframes.

        This method processes fuzzy membership generation on multiple timeframes
        simultaneously, applying the same fuzzy set configurations to each
        timeframe's indicator data. It prefixes timeframe identifiers to
        feature names for clarity (e.g., "15m_rsi_low", "1h_macd_bearish").

        Args:
            multi_timeframe_indicators: Dictionary mapping timeframes to indicator DataFrames
                                      Format: {timeframe: indicators_dataframe}
            fuzzy_sets_config: Optional fuzzy set configuration. If None, uses the
                             current engine's configuration for all timeframes.

        Returns:
            Dictionary mapping timeframes to DataFrames with fuzzy membership values
            Format: {timeframe: fuzzy_memberships_dataframe}

        Raises:
            ConfigurationError: If no timeframe data or fuzzy configuration provided
            ProcessingError: If fuzzy membership generation fails for any timeframe

        Example:
            >>> engine = FuzzyEngine(config)
            >>> multi_indicators = {'1h': indicators_1h, '4h': indicators_4h}
            >>> results = engine.generate_multi_timeframe_memberships(multi_indicators)
            >>> # results = {'1h': fuzzy_1h, '4h': fuzzy_4h}
            >>> # fuzzy_1h columns: ['1h_rsi_low', '1h_rsi_neutral', '1h_rsi_high', ...]
        """
        # Validate inputs
        if not multi_timeframe_indicators:
            raise ConfigurationError(
                "No timeframe data provided for multi-timeframe fuzzy processing",
                error_code="MTFUZZ-NoTimeframes",
                details={
                    "timeframes_provided": list(multi_timeframe_indicators.keys())
                },
            )

        # Use provided fuzzy config or current engine configuration
        if fuzzy_sets_config is not None:
            # Create temporary engine with the provided configuration

            # Convert config dict to FuzzyConfig objects if needed
            if isinstance(fuzzy_sets_config, dict):
                try:
                    # Validate that we have the necessary indicators
                    available_indicators: set[str] = set()
                    for tf_data in multi_timeframe_indicators.values():
                        available_indicators.update(tf_data.columns)

                    logger.debug(
                        f"Available indicators in multi-timeframe data: {available_indicators}"
                    )
                    logger.debug(
                        f"Fuzzy sets config keys: {list(fuzzy_sets_config.keys())}"
                    )

                    # Filter fuzzy config to only include indicators that are available
                    filtered_fuzzy_config = {}
                    for indicator, sets_config in fuzzy_sets_config.items():
                        # Check if the base indicator name is in available indicators
                        # or if any column starts with the indicator name
                        matching_indicators = [
                            col
                            for col in available_indicators
                            if col == indicator
                            or col.lower().startswith(indicator.lower())
                        ]

                        if matching_indicators:
                            logger.debug(
                                f"Found matches for {indicator}: {matching_indicators}"
                            )
                            filtered_fuzzy_config[indicator] = sets_config
                        else:
                            logger.warning(
                                f"No matching indicators found for fuzzy set '{indicator}'"
                            )

                    # Only proceed if we have at least one matched fuzzy set
                    if not filtered_fuzzy_config:
                        raise ConfigurationError(
                            f"No fuzzy sets match available indicators. "
                            f"Available: {list(available_indicators)}, "
                            f"Requested: {list(fuzzy_sets_config.keys())}",
                            error_code="MTFUZZ-NoMatches",
                            details={
                                "available_indicators": list(available_indicators),
                                "fuzzy_sets_requested": list(fuzzy_sets_config.keys()),
                            },
                        )

                    # Use FuzzyConfigLoader to properly process the filtered config
                    from ktrdr.fuzzy.config import FuzzyConfigLoader

                    temp_config = FuzzyConfigLoader.load_from_dict(
                        filtered_fuzzy_config
                    )

                    processing_engine = FuzzyEngine(temp_config)
                except Exception as e:
                    raise ConfigurationError(
                        f"Failed to create FuzzyEngine from provided configuration: {str(e)}",
                        error_code="MTFUZZ-ConfigError",
                        details={"config": fuzzy_sets_config, "error": str(e)},
                    ) from e
            else:
                processing_engine = FuzzyEngine(fuzzy_sets_config)
        else:
            if not self._membership_functions:
                raise ConfigurationError(
                    "No fuzzy configuration in engine and no config provided",
                    error_code="MTFUZZ-NoConfig",
                    details={"engine_indicators": len(self._membership_functions)},
                )
            # Use current engine
            processing_engine = self

        logger.info(
            f"Processing fuzzy memberships for {len(multi_timeframe_indicators)} timeframes: "
            f"{list(multi_timeframe_indicators.keys())}"
        )

        results = {}
        processing_errors = {}

        # Process each timeframe
        for timeframe, indicators_data in multi_timeframe_indicators.items():
            try:
                logger.debug(f"Processing fuzzy memberships for timeframe: {timeframe}")

                # Validate timeframe data
                if indicators_data is None or indicators_data.empty:
                    logger.warning(
                        f"Empty indicator data for timeframe {timeframe}, skipping"
                    )
                    processing_errors[timeframe] = "Empty indicator data"
                    continue

                # Process each indicator column and generate fuzzy memberships
                timeframe_fuzzy_data = {}

                for indicator_col in indicators_data.columns:
                    # Skip non-indicator columns (OHLCV data)
                    if indicator_col.lower() in [
                        "open",
                        "high",
                        "low",
                        "close",
                        "volume",
                    ]:
                        continue

                    # Extract base indicator name (remove suffix like "_14" from "rsi_14")
                    base_indicator = self._extract_base_indicator_name(indicator_col)

                    # Check if this indicator has fuzzy configuration
                    if base_indicator in processing_engine._membership_functions:
                        try:
                            # Get indicator values
                            indicator_values = indicators_data[indicator_col]

                            # Generate fuzzy memberships using existing fuzzify method
                            fuzzy_result = processing_engine.fuzzify(
                                base_indicator, indicator_values
                            )

                            # Add timeframe prefix to column names and store results
                            if isinstance(fuzzy_result, pd.DataFrame):
                                for col in fuzzy_result.columns:
                                    # Add timeframe prefix: "rsi_low" -> "15m_rsi_low"
                                    prefixed_col = f"{timeframe}_{col}"
                                    timeframe_fuzzy_data[prefixed_col] = fuzzy_result[
                                        col
                                    ]

                            logger.debug(
                                f"Generated fuzzy memberships for {base_indicator} in {timeframe}"
                            )

                        except Exception as e:
                            logger.warning(
                                f"Failed to process indicator {indicator_col} in {timeframe}: {str(e)}"
                            )
                            continue
                    else:
                        logger.debug(
                            f"No fuzzy configuration for indicator {base_indicator}, skipping"
                        )

                # Create DataFrame with fuzzy membership results
                if timeframe_fuzzy_data:
                    results[timeframe] = pd.DataFrame(
                        timeframe_fuzzy_data, index=indicators_data.index
                    )
                    logger.debug(
                        f"Successfully generated {len(timeframe_fuzzy_data)} fuzzy features "
                        f"for {timeframe} ({len(results[timeframe])} rows)"
                    )
                else:
                    logger.warning(
                        f"No fuzzy features generated for timeframe {timeframe}"
                    )
                    processing_errors[timeframe] = "No fuzzy features generated"

            except Exception as e:
                error_msg = f"Failed to process fuzzy memberships for timeframe {timeframe}: {str(e)}"
                logger.error(error_msg)
                processing_errors[timeframe] = str(e)
                continue

        # Check if we got any results
        if not results:
            raise ProcessingError(
                "Failed to generate fuzzy memberships for any timeframe",
                error_code="MTFUZZ-AllTimeframesFailed",
                details={
                    "requested_timeframes": list(multi_timeframe_indicators.keys()),
                    "processing_errors": processing_errors,
                },
            )

        # Log summary
        successful_timeframes = len(results)
        failed_timeframes = len(processing_errors)
        total_timeframes = len(multi_timeframe_indicators)

        if failed_timeframes > 0:
            logger.warning(
                f"Multi-timeframe fuzzy processing completed with warnings: "
                f"{successful_timeframes}/{total_timeframes} timeframes successful"
            )
            for tf, error in processing_errors.items():
                logger.warning(f"  {tf}: {error}")
        else:
            logger.info(
                f"Successfully generated fuzzy memberships for all {successful_timeframes} timeframes"
            )

        return results

    def _extract_base_indicator_name(self, indicator_col: str) -> str:
        """
        Extract base indicator name from column name.

        Examples:
            "rsi_14" -> "rsi"
            "macd" -> "macd"
            "sma_20" -> "sma"

        Args:
            indicator_col: Full indicator column name

        Returns:
            Base indicator name
        """
        # Common indicator patterns
        common_indicators = ["rsi", "macd", "sma", "ema", "bb", "stoch", "cci", "atr"]

        # Check if the column starts with any known indicator
        for indicator in common_indicators:
            if indicator_col.lower().startswith(indicator.lower()):
                return indicator.lower()

        # Fallback: use the part before the first underscore or number
        base_name = indicator_col.lower()

        # Remove trailing numbers and underscores (e.g., "rsi_14" -> "rsi")
        for i, char in enumerate(base_name):
            if char.isdigit() or char == "_":
                base_name = base_name[:i]
                break

        return base_name if base_name else indicator_col.lower()
