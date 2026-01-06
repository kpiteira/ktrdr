"""
Fuzzy engine implementation for KTRDR.

This module provides the FuzzyEngine class that transforms indicator values
into fuzzy membership degrees according to configured membership functions.
"""

from typing import Optional, Union

import numpy as np
import pandas as pd

from ktrdr import get_logger
from ktrdr.config.models import FuzzySetDefinition
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

    def __init__(self, config: Union[FuzzyConfig, dict[str, FuzzySetDefinition]]):
        """
        Initialize the FuzzyEngine with a configuration.

        Supports both v2 and v3 formats:
        - v2: FuzzyConfig object (legacy)
        - v3: dict[str, FuzzySetDefinition] mapping fuzzy_set_id to definition

        Args:
            config: Either FuzzyConfig (v2) or dict mapping fuzzy_set_id to
                   FuzzySetDefinition (v3)

        Raises:
            ConfigurationError: If the configuration is invalid
        """
        logger.debug("Initializing FuzzyEngine")

        # Detect format and initialize appropriately
        if isinstance(config, dict):
            # V3 format: dict[str, FuzzySetDefinition]
            logger.debug("Initializing FuzzyEngine with v3 format")
            self._config = None
            self._fuzzy_sets: dict[str, dict[str, MembershipFunction]] = {}
            self._indicator_map: dict[str, str] = {}  # fuzzy_set_id -> indicator_id
            self._initialize_v3(config)
            logger.info(
                f"FuzzyEngine initialized with {len(self._fuzzy_sets)} fuzzy sets"
            )
        else:
            # V2 format: FuzzyConfig
            logger.debug("Initializing FuzzyEngine with v2 format")
            self._config = config
            self._membership_functions: dict[str, dict[str, MembershipFunction]] = {}
            self._validate_config()
            self._initialize_membership_functions()
            logger.info(
                f"FuzzyEngine initialized with {len(self._membership_functions)} indicators"
            )

    def _validate_config(self) -> None:
        """
        Validate the fuzzy configuration (v2 only).

        Raises:
            ConfigurationError: If the configuration is invalid
        """
        assert self._config is not None, "v2 mode: _config must be set"
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
        Initialize membership function instances from the configuration (v2 only).

        Raises:
            ConfigurationError: If any membership function configuration is invalid
        """
        assert self._config is not None, "v2 mode: _config must be set"
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

    def _initialize_v3(self, fuzzy_sets: dict[str, FuzzySetDefinition]) -> None:
        """
        Initialize FuzzyEngine from v3 format (dict[str, FuzzySetDefinition]).

        Args:
            fuzzy_sets: Dict mapping fuzzy_set_id to FuzzySetDefinition

        Raises:
            ConfigurationError: If the configuration is invalid
        """
        if not fuzzy_sets:
            logger.error("Empty fuzzy sets dict")
            raise ConfigurationError(
                message="Fuzzy sets configuration cannot be empty",
                error_code="ENGINE-EmptyConfig",
                details={},
            )

        for fuzzy_set_id, definition in fuzzy_sets.items():
            logger.debug(f"Initializing fuzzy set: {fuzzy_set_id}")

            # Build membership functions for this fuzzy set
            self._fuzzy_sets[fuzzy_set_id] = self._build_membership_functions(
                definition
            )

            # Track which indicator this fuzzy set references
            self._indicator_map[fuzzy_set_id] = definition.indicator

        logger.debug(f"Initialized {len(self._fuzzy_sets)} fuzzy sets from v3 config")

    def _build_membership_functions(
        self, definition: FuzzySetDefinition
    ) -> dict[str, MembershipFunction]:
        """
        Build MembershipFunction objects from FuzzySetDefinition.

        Args:
            definition: FuzzySetDefinition containing membership function specs

        Returns:
            Dict mapping membership name to MembershipFunction instance

        Raises:
            ConfigurationError: If membership function creation fails
        """
        result = {}

        for name in definition.get_membership_names():
            # Get membership spec from model_extra
            membership_def = getattr(definition, name)

            # membership_def is already expanded to {type, parameters} by Pydantic
            try:
                result[name] = self._create_membership_function(membership_def)
            except Exception as e:
                logger.error(
                    f"Failed to create membership function '{name}' for fuzzy set: {e}"
                )
                raise ConfigurationError(
                    message=f"Failed to create membership function '{name}'",
                    error_code="ENGINE-MFCreationError",
                    details={
                        "membership_name": name,
                        "membership_def": membership_def,
                        "original_error": str(e),
                    },
                ) from e

        return result

    def _create_membership_function(self, membership_def: dict) -> MembershipFunction:
        """
        Create a MembershipFunction from a dict specification.

        Args:
            membership_def: Dict with 'type' and 'parameters' keys

        Returns:
            MembershipFunction instance
        """
        return MembershipFunctionFactory.create(
            membership_def["type"], membership_def["parameters"]
        )

    def get_indicator_for_fuzzy_set(self, fuzzy_set_id: str) -> str:
        """
        Get the indicator_id that a fuzzy_set references (v3 only).

        Args:
            fuzzy_set_id: The fuzzy set to query

        Returns:
            The indicator_id that this fuzzy set interprets

        Raises:
            ValueError: If fuzzy_set_id is unknown or engine is in v2 mode
        """
        if not self._indicator_map:
            raise ValueError(
                "get_indicator_for_fuzzy_set() is only available in v3 mode"
            )

        if fuzzy_set_id not in self._indicator_map:
            raise ValueError(f"Unknown fuzzy set: {fuzzy_set_id}")

        return self._indicator_map[fuzzy_set_id]

    def fuzzify(
        self,
        indicator: str,
        values: Union[float, pd.Series, np.ndarray],
        context_data: Optional[pd.DataFrame] = None,
    ) -> Union[dict[str, Union[float, pd.Series, np.ndarray]], pd.DataFrame]:
        """
        Fuzzify indicator values using the configured membership functions.

        Supports both v2 and v3 modes:
        - v3 mode: First parameter is fuzzy_set_id, second is indicator_values (Series only)
        - v2 mode: First parameter is indicator name, second is values (scalar/Series/array)

        For v3 mode, returns a DataFrame with {fuzzy_set_id}_{membership} columns.
        For v2 mode with scalar input, returns a dict mapping fuzzy set names to membership degrees.
        For v2 mode with Series/array input, returns a DataFrame with columns for each fuzzy set.

        Args:
            indicator: Name of the indicator (v2) or fuzzy_set_id (v3)
            values: Indicator values to fuzzify (scalar, pandas Series, or numpy array)
            context_data: Optional DataFrame containing price data (open, high, low, close)
                         required for price_ratio transforms (v2 only)

        Returns:
            For v3 mode: DataFrame with {fuzzy_set_id}_{membership} columns
            For v2 scalar input: A dictionary mapping fuzzy set names to membership degrees
            For v2 Series/array input: A DataFrame with columns for each fuzzy set

        Raises:
            ValueError: If fuzzy_set_id is unknown (v3 mode)
            ProcessingError: If the indicator is not in the configuration (v2 mode) or if
                           required context_data is missing
            TypeError: If the input type is not supported
        """
        # V3 mode detection: check if _fuzzy_sets exists and is populated
        if hasattr(self, "_fuzzy_sets") and self._fuzzy_sets:
            # V3 mode: First parameter is fuzzy_set_id, second is indicator_values
            fuzzy_set_id = indicator  # In v3, first param is fuzzy_set_id
            indicator_values = values  # In v3, second param is indicator_values

            logger.debug(f"V3: Fuzzifying values for fuzzy_set_id: {fuzzy_set_id}")

            # Validate fuzzy_set_id exists
            if fuzzy_set_id not in self._fuzzy_sets:
                raise ValueError(f"Unknown fuzzy set: {fuzzy_set_id}")

            # Get the fuzzy set (dict of membership functions)
            fuzzy_set = self._fuzzy_sets[fuzzy_set_id]

            # Build result dict with {fuzzy_set_id}_{membership} column names
            result = {}
            for membership_name, mf in fuzzy_set.items():
                col_name = f"{fuzzy_set_id}_{membership_name}"
                result[col_name] = mf.evaluate(indicator_values)

            # Return DataFrame with original index
            if isinstance(indicator_values, pd.Series):
                return pd.DataFrame(result, index=indicator_values.index)
            else:
                # If values is not a Series, create DataFrame without explicit index
                return pd.DataFrame(result)

        # V2 mode: existing logic
        logger.debug(f"V2: Fuzzifying values for indicator: {indicator}")

        # Check if the indicator exists in the configuration
        if indicator not in self._membership_functions:
            logger.error(f"Unknown indicator: {indicator}")

            # Get list of available indicators
            available_indicators = list(self._membership_functions.keys())

            # Try to find a close match (typo detection)
            suggestion = self._find_close_match(indicator, available_indicators)

            # Build error message with suggestion
            error_msg = f"Feature ID '{indicator}' not found in fuzzy configuration"

            # Build suggestion text
            suggestion_text = (
                f"Available feature IDs: {', '.join(available_indicators[:10])}"
            )
            if len(available_indicators) > 10:
                suggestion_text += f" (and {len(available_indicators) - 10} more)"

            if suggestion:
                suggestion_text += f"\n\nDid you mean '{suggestion}'?"

            # Build details dict with suggestion
            error_details = {
                "indicator": indicator,
                "available_indicators": available_indicators,
            }
            if suggestion:
                error_details["suggestion"] = suggestion

            raise ProcessingError(
                message=error_msg,
                error_code="ENGINE-UnknownIndicator",
                details=error_details,
                suggestion=suggestion_text,
            )

        # Get the membership functions for this indicator
        membership_functions = self._membership_functions[indicator]

        # Apply input transform if configured
        transformed_values = self._apply_transform(indicator, values, context_data)

        # Handle scalar input
        if isinstance(transformed_values, (int, float)):
            logger.debug(
                f"Fuzzifying scalar value {transformed_values} for indicator {indicator}"
            )
            return self._fuzzify_scalar(indicator, transformed_values, membership_functions)  # type: ignore[return-value]

        # Handle pandas Series input
        elif isinstance(transformed_values, pd.Series):
            logger.debug(
                f"Fuzzifying pandas Series of length {len(transformed_values)} for indicator {indicator}"
            )
            return self._fuzzify_series(
                indicator, transformed_values, membership_functions
            )

        # Handle numpy array input
        elif isinstance(transformed_values, np.ndarray):
            logger.debug(
                f"Fuzzifying numpy array of shape {transformed_values.shape} for indicator {indicator}"
            )
            # Convert numpy array to pandas Series for consistent handling
            series = pd.Series(transformed_values)
            return self._fuzzify_series(indicator, series, membership_functions)

        # Handle unsupported input types
        else:
            logger.error(
                f"Unsupported input type for fuzzification: {type(transformed_values)}"
            )
            raise TypeError(
                f"Unsupported input type: {type(transformed_values)}. Expected float, pd.Series, or np.ndarray."
            )

    def _apply_transform(
        self,
        indicator: str,
        values: Union[float, pd.Series, np.ndarray],
        context_data: Optional[pd.DataFrame] = None,
    ) -> Union[float, pd.Series, np.ndarray]:
        """
        Apply input transform to indicator values before fuzzification (v2 only).

        Args:
            indicator: Name of the indicator
            values: Indicator values to transform
            context_data: Optional DataFrame containing price data for transforms

        Returns:
            Transformed values (same type as input)

        Raises:
            ProcessingError: If required context_data is missing or invalid
        """
        # v2 mode only - _config must be set
        assert self._config is not None, "v2 mode: _config must be set"

        # Get the fuzzy set config for this indicator
        fuzzy_set_config = self._config.root[indicator]

        # Get the input transform (may be None)
        input_transform = fuzzy_set_config.input_transform

        # If no transform or identity transform, return values unchanged
        if input_transform is None or input_transform.type == "identity":
            logger.debug(f"No transform or identity transform for {indicator}")
            return values

        # Handle price_ratio transform
        if input_transform.type == "price_ratio":
            # Type narrowing for mypy - at this point we know it's PriceRatioTransformConfig
            assert hasattr(
                input_transform, "reference"
            ), "price_ratio transform must have reference attribute"
            logger.debug(
                f"Applying price_ratio transform for {indicator} with reference '{input_transform.reference}'"
            )

            # Validate context_data is provided
            if context_data is None:
                logger.error(
                    f"context_data is required for price_ratio transform for {indicator}"
                )
                raise ProcessingError(
                    message=f"context_data is required for price_ratio transform for indicator '{indicator}'. Pass context_data DataFrame with price columns (open, high, low, close)",
                    error_code="ENGINE-MissingContextData",
                    details={
                        "indicator": indicator,
                        "transform_type": "price_ratio",
                        "reference": input_transform.reference,
                    },
                )

            # Validate reference column exists in context_data
            if input_transform.reference not in context_data.columns:
                logger.error(
                    f"Reference column '{input_transform.reference}' not found in context_data"
                )
                raise ProcessingError(
                    message=f"Reference column '{input_transform.reference}' not found in context_data. Ensure context_data contains '{input_transform.reference}' column",
                    error_code="ENGINE-MissingReferenceColumn",
                    details={
                        "indicator": indicator,
                        "reference": input_transform.reference,
                        "available_columns": list(context_data.columns),
                    },
                )

            # Get reference values
            reference_values = context_data[input_transform.reference]

            # Apply price ratio transformation: reference / indicator
            if isinstance(values, (int, float)):
                # Scalar case
                transformed_scalar = float(reference_values.iloc[0]) / float(values)
                logger.debug(
                    f"Transformed scalar {values} -> {transformed_scalar} (ratio with {input_transform.reference})"
                )
                return transformed_scalar
            elif isinstance(values, pd.Series):
                # Series case
                transformed_series = reference_values / values
                logger.debug(
                    f"Transformed series (length {len(values)}) with price_ratio transform"
                )
                return transformed_series
            else:  # numpy array
                # Convert to series, transform, convert back
                series = pd.Series(values)
                transformed_series_arr = reference_values / series
                logger.debug(
                    f"Transformed numpy array (shape {values.shape}) with price_ratio transform"
                )
                return np.array(transformed_series_arr.values)

        # Unknown transform type (should never happen due to discriminator)
        logger.error(f"Unknown transform type: {input_transform.type}")
        raise ProcessingError(
            message=f"Unknown transform type: {input_transform.type}",
            error_code="ENGINE-UnknownTransformType",
            details={"indicator": indicator, "transform_type": input_transform.type},
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

                logger.info(
                    f"Available columns for {timeframe}: {list(indicators_data.columns)}"
                )
                logger.info(
                    f"Fuzzy membership functions keys: {list(processing_engine._membership_functions.keys())}"
                )

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

                    # Find matching fuzzy configuration using systematic feature_id lookup
                    fuzzy_key = processing_engine._find_fuzzy_key(indicator_col)

                    if fuzzy_key:
                        try:
                            # Get indicator values
                            indicator_values = indicators_data[indicator_col]

                            # Generate fuzzy memberships using existing fuzzify method
                            # ROOT CAUSE FIX: Pass context_data for price_ratio transforms!
                            fuzzy_result = processing_engine.fuzzify(
                                fuzzy_key,
                                indicator_values,
                                context_data=indicators_data,
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
                                f"Generated fuzzy memberships for {fuzzy_key} ({indicator_col}) in {timeframe}"
                            )

                        except Exception as e:
                            logger.warning(
                                f"Failed to process indicator {indicator_col} in {timeframe}: {str(e)}"
                            )
                            continue
                    else:
                        logger.debug(f"No fuzzy match for column: {indicator_col}")

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

    def _find_fuzzy_key(self, column_name: str) -> Optional[str]:
        """
        Find fuzzy configuration key for a column, prioritizing feature_id matching.

        This method implements systematic feature_id lookup:
        1. Direct match: column_name exactly matches a fuzzy key (e.g., "rsi_14")
        2. Prefix match with dot notation: column_name starts with fuzzy key + "." (e.g., "bbands_20_2.upper" matches "bbands_20_2")
        3. Legacy prefix match with underscore: column_name starts with fuzzy key + "_" (backward compatibility)

        Args:
            column_name: The column name to find a fuzzy key for

        Returns:
            The matching fuzzy key, or None if no match found

        Examples:
            >>> engine._find_fuzzy_key("rsi_14")
            "rsi_14"  # Direct match
            >>> engine._find_fuzzy_key("bbands_20_2.upper")
            "bbands_20_2"  # M4: Dot notation prefix match (multi-output indicator)
            >>> engine._find_fuzzy_key("bbands_20_2_upper")
            "bbands_20_2"  # Legacy: Underscore prefix match (backward compatibility)
            >>> engine._find_fuzzy_key("unknown_indicator")
            None  # No match
        """
        # Direct match first (most common case)
        if column_name in self._membership_functions:
            return column_name

        # M4: For multi-output indicators with dot notation (new format from M3b)
        # E.g., "bbands_20_2.upper" should match fuzzy key "bbands_20_2"
        for fuzzy_key in self._membership_functions.keys():
            if column_name.startswith(f"{fuzzy_key}."):
                return fuzzy_key

        # Legacy: For backward compatibility with old underscore-based format
        # E.g., "bbands_20_2_upper" should match fuzzy key "bbands_20_2"
        for fuzzy_key in self._membership_functions.keys():
            if column_name.startswith(f"{fuzzy_key}_"):
                return fuzzy_key

        return None

    def _find_close_match(
        self, target: str, candidates: list[str], max_distance: int = 3
    ) -> Optional[str]:
        """
        Find a close match for typo detection using Levenshtein distance.

        This method helps users identify typos by suggesting feature_ids that
        are similar to what they typed. Uses Levenshtein distance to measure
        similarity.

        Args:
            target: The feature_id that wasn't found (potential typo)
            candidates: List of valid feature_ids to compare against
            max_distance: Maximum edit distance to consider (default: 3)

        Returns:
            The closest matching feature_id, or None if no close match found

        Examples:
            >>> engine._find_close_match("rsi_1", ["rsi_14", "rsi_21", "macd"])
            "rsi_14"  # Close match (distance: 1)
            >>> engine._find_close_match("xyz", ["rsi_14", "macd"])
            None  # Too different
        """
        if not candidates:
            return None

        # Calculate Levenshtein distance for each candidate
        distances = []
        for candidate in candidates:
            distance = self._levenshtein_distance(target.lower(), candidate.lower())
            distances.append((distance, candidate))

        # Sort by distance (closest first)
        distances.sort(key=lambda x: x[0])

        # Return closest match if within threshold
        closest_distance, closest_match = distances[0]
        if closest_distance <= max_distance:
            return closest_match

        return None

    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """
        Calculate Levenshtein distance between two strings.

        The Levenshtein distance is the minimum number of single-character edits
        (insertions, deletions, or substitutions) required to change one string
        into another.

        Args:
            s1: First string
            s2: Second string

        Returns:
            Edit distance between the strings

        Examples:
            >>> engine._levenshtein_distance("rsi_1", "rsi_14")
            1  # One character difference
            >>> engine._levenshtein_distance("rsi", "macd")
            4  # Four edits required
        """
        # Handle edge cases
        if len(s1) == 0:
            return len(s2)
        if len(s2) == 0:
            return len(s1)

        # Create distance matrix
        matrix = [[0] * (len(s2) + 1) for _ in range(len(s1) + 1)]

        # Initialize first column and row
        for i in range(len(s1) + 1):
            matrix[i][0] = i
        for j in range(len(s2) + 1):
            matrix[0][j] = j

        # Fill matrix
        for i in range(1, len(s1) + 1):
            for j in range(1, len(s2) + 1):
                if s1[i - 1] == s2[j - 1]:
                    cost = 0
                else:
                    cost = 1

                matrix[i][j] = min(
                    matrix[i - 1][j] + 1,  # deletion
                    matrix[i][j - 1] + 1,  # insertion
                    matrix[i - 1][j - 1] + cost,  # substitution
                )

        return matrix[len(s1)][len(s2)]
