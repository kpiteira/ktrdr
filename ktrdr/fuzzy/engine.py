"""
Fuzzy engine implementation for KTRDR.

This module provides the FuzzyEngine class that transforms indicator values
into fuzzy membership degrees according to configured membership functions.

V3-only: This engine requires v3 format configuration (dict[str, FuzzySetDefinition]).
V2 FuzzyConfig format is no longer supported.
"""

from typing import Optional, Union

import numpy as np
import pandas as pd

from ktrdr import get_logger
from ktrdr.config.models import FuzzySetDefinition
from ktrdr.errors import ConfigurationError, ProcessingError
from ktrdr.fuzzy.membership import (
    MEMBERSHIP_REGISTRY,
    MembershipFunction,
)

# Set up module-level logger
logger = get_logger(__name__)


class FuzzyEngine:
    """
    FuzzyEngine for transforming indicator values into fuzzy membership degrees.

    The FuzzyEngine takes a v3 format configuration (dict[str, FuzzySetDefinition])
    with membership functions for different indicators and transforms indicator
    values into fuzzy membership degrees according to these functions.

    V3-only: V2 FuzzyConfig format is no longer supported.

    Example:
        ```python
        from ktrdr.config.models import FuzzySetDefinition

        # Create v3 configuration
        config = {
            "rsi_momentum": FuzzySetDefinition(
                indicator="rsi_14",
                low={"type": "triangular", "parameters": [0.0, 30.0, 50.0]},
                medium={"type": "triangular", "parameters": [30.0, 50.0, 70.0]},
                high={"type": "triangular", "parameters": [50.0, 70.0, 100.0]},
            )
        }

        # Create engine and fuzzify
        engine = FuzzyEngine(config)
        rsi_values = pd.Series([30.0, 45.0, 70.0])
        membership_degrees = engine.fuzzify("rsi_momentum", rsi_values)
        ```
    """

    def __init__(self, config: dict[str, FuzzySetDefinition]):
        """
        Initialize the FuzzyEngine with a v3 configuration.

        Args:
            config: Dict mapping fuzzy_set_id to FuzzySetDefinition

        Raises:
            ConfigurationError: If the configuration is invalid or not v3 format
        """
        logger.debug("Initializing FuzzyEngine")

        # V3-only: reject non-dict configs
        if not isinstance(config, dict):
            raise ConfigurationError(
                message="FuzzyEngine requires v3 format (dict[str, FuzzySetDefinition]). "
                "V2 FuzzyConfig is no longer supported.",
                error_code="ENGINE-V2ConfigNotSupported",
                details={"received_type": type(config).__name__},
            )

        # Validate dict values are FuzzySetDefinition (if non-empty)
        if config:
            first_value = next(iter(config.values()))
            if not isinstance(first_value, FuzzySetDefinition):
                raise ConfigurationError(
                    message="FuzzyEngine requires v3 format (dict[str, FuzzySetDefinition]). "
                    "V2 FuzzyConfig is no longer supported.",
                    error_code="ENGINE-V2ConfigNotSupported",
                    details={"received_value_type": type(first_value).__name__},
                )

        logger.debug("Initializing FuzzyEngine with v3 format")
        self._is_v3_mode = True
        self._fuzzy_sets: dict[str, dict[str, MembershipFunction]] = {}
        self._indicator_map: dict[str, str] = {}  # fuzzy_set_id -> indicator_id
        self._initialize_v3(config)
        logger.info(f"FuzzyEngine initialized with {len(self._fuzzy_sets)} fuzzy sets")

    @property
    def is_v3_mode(self) -> bool:
        """Check if this engine was initialized with v3 format configuration."""
        return getattr(self, "_is_v3_mode", False)

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
        membership_names = definition.get_membership_names()

        # Validate at least one membership function is defined
        if not membership_names:
            raise ConfigurationError(
                message="FuzzySetDefinition must have at least one membership function",
                error_code="ENGINE-NoMembershipFunctions",
                details={"indicator": definition.indicator},
            )

        result = {}

        for name in membership_names:
            # Get membership spec via getattr (Pydantic exposes extra fields as attributes)
            membership_def = getattr(definition, name)

            # membership_def is already expanded to {type, parameters} by Pydantic
            try:
                result[name] = self._create_membership_function(membership_def)
            except (KeyError, TypeError, ValueError) as e:
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
        Create a MembershipFunction from a dict specification using the registry.

        Args:
            membership_def: Dict with 'type' and 'parameters' keys

        Returns:
            MembershipFunction instance

        Raises:
            ConfigurationError: If MF type is unknown or parameters are invalid
        """
        mf_type = membership_def["type"]
        parameters = membership_def["parameters"]

        # Use registry for type lookup (case-insensitive)
        mf_cls = MEMBERSHIP_REGISTRY.get_or_raise(mf_type)
        return mf_cls(parameters)

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
        if not getattr(self, "_is_v3_mode", False):
            raise ValueError(
                "get_indicator_for_fuzzy_set() is only available in v3 mode"
            )

        if fuzzy_set_id not in self._indicator_map:
            raise ValueError(f"Unknown fuzzy set: {fuzzy_set_id}")

        return self._indicator_map[fuzzy_set_id]

    def get_membership_names(self, fuzzy_set_id: str) -> list[str]:
        """
        Get ordered list of membership function names for a fuzzy set (v3 only).

        Args:
            fuzzy_set_id: The fuzzy set to query

        Returns:
            List of membership names in definition order
            e.g., ["oversold", "neutral", "overbought"]

        Raises:
            ValueError: If fuzzy_set_id is unknown or engine is in v2 mode
        """
        if not getattr(self, "_is_v3_mode", False):
            raise ValueError("get_membership_names() is only available in v3 mode")

        if fuzzy_set_id not in self._fuzzy_sets:
            raise ValueError(f"Unknown fuzzy set: {fuzzy_set_id}")

        return list(self._fuzzy_sets[fuzzy_set_id].keys())

    def fuzzify(
        self,
        fuzzy_set_id: str,
        values: Union[float, pd.Series, np.ndarray],
        context_data: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Fuzzify indicator values using the configured membership functions.

        Args:
            fuzzy_set_id: The fuzzy set ID to use for fuzzification
            values: Indicator values to fuzzify (scalar, pandas Series, or numpy array)
            context_data: Unused, kept for API compatibility

        Returns:
            DataFrame with {fuzzy_set_id}_{membership} columns

        Raises:
            ValueError: If fuzzy_set_id is unknown
        """
        logger.debug(f"Fuzzifying values for fuzzy_set_id: {fuzzy_set_id}")

        # Validate fuzzy_set_id exists
        if fuzzy_set_id not in self._fuzzy_sets:
            raise ValueError(f"Unknown fuzzy set: {fuzzy_set_id}")

        # Get the fuzzy set (dict of membership functions)
        fuzzy_set = self._fuzzy_sets[fuzzy_set_id]

        # Build result dict with {fuzzy_set_id}_{membership} column names
        result = {}
        for membership_name, mf in fuzzy_set.items():
            col_name = f"{fuzzy_set_id}_{membership_name}"
            result[col_name] = mf.evaluate(values)

        # Return DataFrame with original index
        if isinstance(values, pd.Series):
            return pd.DataFrame(result, index=values.index)
        else:
            # If values is not a Series, create DataFrame without explicit index
            return pd.DataFrame(result)

    def generate_multi_timeframe_memberships(
        self,
        multi_timeframe_indicators: dict[str, pd.DataFrame],
        fuzzy_sets_config: Optional[dict[str, FuzzySetDefinition]] = None,
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
            fuzzy_sets_config: Optional v3 fuzzy set configuration. If None, uses the
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
            # Create temporary engine with the provided v3 configuration
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
                filtered_fuzzy_config: dict[str, FuzzySetDefinition] = {}
                for fuzzy_set_id, definition in fuzzy_sets_config.items():
                    indicator = definition.indicator

                    # Check if the base indicator name is in available indicators
                    # or if any column starts with the indicator name
                    matching_indicators = [
                        col
                        for col in available_indicators
                        if col == indicator or col.lower().startswith(indicator.lower())
                    ]

                    if matching_indicators:
                        logger.debug(
                            f"Found matches for {fuzzy_set_id} (indicator: {indicator}): {matching_indicators}"
                        )
                        filtered_fuzzy_config[fuzzy_set_id] = definition
                    else:
                        logger.warning(
                            f"No matching indicators found for fuzzy set '{fuzzy_set_id}' "
                            f"(looking for indicator: {indicator})"
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

                processing_engine = FuzzyEngine(filtered_fuzzy_config)
            except ConfigurationError:
                raise
            except Exception as e:
                raise ConfigurationError(
                    f"Failed to create FuzzyEngine from provided configuration: {str(e)}",
                    error_code="MTFUZZ-ConfigError",
                    details={"error": str(e)},
                ) from e
        else:
            if not self._fuzzy_sets:
                raise ConfigurationError(
                    "No fuzzy configuration in engine and no config provided",
                    error_code="MTFUZZ-NoConfig",
                    details={"engine_fuzzy_sets": len(self._fuzzy_sets)},
                )
            # Use current engine
            processing_engine = self

        logger.info(
            f"Processing fuzzy memberships for {len(multi_timeframe_indicators)} timeframes: "
            f"{list(multi_timeframe_indicators.keys())}"
        )

        results: dict[str, pd.DataFrame] = {}
        processing_errors: dict[str, str] = {}

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
                timeframe_fuzzy_data: dict[str, pd.Series] = {}

                logger.info(
                    f"Available columns for {timeframe}: {list(indicators_data.columns)}"
                )
                fuzzy_keys = list(processing_engine._fuzzy_sets.keys())
                logger.info(f"Fuzzy membership functions keys: {fuzzy_keys}")

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

                            # Generate fuzzy memberships using fuzzify method
                            fuzzy_result = processing_engine.fuzzify(
                                fuzzy_key,
                                indicator_values,
                            )

                            # Add timeframe prefix to column names and store results
                            for col in fuzzy_result.columns:
                                # Add timeframe prefix: "rsi_low" -> "15m_rsi_low"
                                prefixed_col = f"{timeframe}_{col}"
                                timeframe_fuzzy_data[prefixed_col] = fuzzy_result[col]

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
        2. Indicator match: column_name matches an indicator in _indicator_map
        3. Prefix match with dot notation: column_name starts with indicator + "."
        4. Legacy prefix match with underscore: backward compatibility

        Args:
            column_name: The column name to find a fuzzy key for

        Returns:
            The matching fuzzy key, or None if no match found

        Examples:
            >>> engine._find_fuzzy_key("rsi_14")
            "rsi_momentum"  # Matches via indicator_map
            >>> engine._find_fuzzy_key("bbands_20_2.upper")
            "bbands_width"  # Prefix match (multi-output indicator)
            >>> engine._find_fuzzy_key("unknown_indicator")
            None  # No match
        """
        fuzzy_keys = self._fuzzy_sets.keys()

        # Direct match first (most common case)
        if column_name in fuzzy_keys:
            return column_name

        # Check if column matches an indicator in _indicator_map
        # E.g., column "rsi_14" matches fuzzy_set "rsi_momentum" which has indicator "rsi_14"
        for fuzzy_set_id, indicator in self._indicator_map.items():
            if column_name == indicator:
                return fuzzy_set_id
            # Also check prefix match for multi-output indicators
            if column_name.startswith(f"{indicator}."):
                return fuzzy_set_id

        # For multi-output indicators with dot notation
        # E.g., "bbands_20_2.upper" should match fuzzy key "bbands_20_2"
        for fuzzy_key in fuzzy_keys:
            if column_name.startswith(f"{fuzzy_key}."):
                return fuzzy_key

        # Legacy: For backward compatibility with old underscore-based format
        # E.g., "bbands_20_2_upper" should match fuzzy key "bbands_20_2"
        for fuzzy_key in fuzzy_keys:
            if column_name.startswith(f"{fuzzy_key}_"):
                return fuzzy_key

        return None
