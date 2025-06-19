"""
Fuzzy engine implementation for KTRDR.

This module provides the FuzzyEngine class that transforms indicator values
into fuzzy membership degrees according to configured membership functions.
"""

from typing import Dict, List, Optional, Tuple, Union, Any

import pandas as pd
import numpy as np

from ktrdr import get_logger
from ktrdr.errors import ConfigurationError, ProcessingError
from ktrdr.fuzzy.config import FuzzyConfig, FuzzySetConfig, MembershipFunctionConfig
from ktrdr.fuzzy.membership import (
    MembershipFunction,
    TriangularMF,
    TrapezoidalMF,
    GaussianMF,
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
        self._membership_functions: Dict[str, Dict[str, MembershipFunction]] = {}
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
    ) -> Union[Dict[str, float], pd.DataFrame]:
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
            return self._fuzzify_scalar(indicator, values, membership_functions)

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
        membership_functions: Dict[str, MembershipFunction],
    ) -> Dict[str, float]:
        """
        Fuzzify a single indicator value.

        Args:
            indicator: Name of the indicator
            value: Indicator value to fuzzify
            membership_functions: Dictionary of membership functions for this indicator

        Returns:
            Dictionary mapping fuzzy set names to membership degrees
        """
        result = {}

        for set_name, mf in membership_functions.items():
            # Generate standardized output column name
            output_name = self._get_output_name(indicator, set_name)
            result[output_name] = mf.evaluate(value)

        return result

    def _fuzzify_series(
        self,
        indicator: str,
        values: pd.Series,
        membership_functions: Dict[str, MembershipFunction],
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

    def get_available_indicators(self) -> List[str]:
        """
        Get a list of available indicators in the configuration.

        Returns:
            List of indicator names
        """
        return list(self._membership_functions.keys())

    def get_fuzzy_sets(self, indicator: str) -> List[str]:
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

    def get_output_names(self, indicator: str) -> List[str]:
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
