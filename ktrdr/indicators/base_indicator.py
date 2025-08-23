"""
Base class for all technical indicators in the KTRDR system.

This module defines the abstract BaseIndicator class that all indicator
implementations must inherit from, ensuring a consistent interface across
all technical indicators.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union

import pandas as pd

from ktrdr import get_logger
from ktrdr.config.validation import InputValidator
from ktrdr.errors import DataError

logger = get_logger(__name__)


class BaseIndicator(ABC):
    """
    Abstract base class for all technical indicators.

    All indicators in the KTRDR system must inherit from this class
    and implement the compute() method. The BaseIndicator class provides
    common functionality like parameter validation and consistent interfaces.

    Attributes:
        name (str): The name of the indicator (e.g., "RSI", "SMA")
        params (Dict[str, Any]): Dictionary of parameters for the indicator
        display_as_overlay (bool): Whether this indicator can be displayed as an overlay
                                  on price charts by default. Indicators with different
                                  scale than price (like RSI) should set this to False.
    """

    def __init__(self, name: str, display_as_overlay: bool = True, **params):
        """
        Initialize a new indicator with its parameters.

        Args:
            name (str): The name of the indicator
            display_as_overlay (bool): Whether this indicator should be displayed as an overlay
                                     on price charts by default. Set to False for indicators with
                                     a different scale than price (like RSI, Stochastic).
            **params: Variable keyword arguments for indicator parameters
        """
        self.name = InputValidator.validate_string(
            name,
            min_length=1,
            max_length=50,
            pattern=r"^[A-Za-z0-9_]+$",  # alphanumeric and underscore only
        )
        self.params = self._validate_params(params)
        self.display_as_overlay = display_as_overlay

        logger.info(f"Initialized {self.name} indicator with parameters: {self.params}")

    def _validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Validate the parameters passed to the indicator.

        This method should be overridden by subclasses to implement
        specific validation logic for their parameters.

        Args:
            params (Dict[str, Any]): Dictionary of parameters to validate

        Returns:
            Dict[str, Any]: Validated parameters

        Raises:
            DataError: If any parameter validation fails
        """
        return params

    @abstractmethod
    def compute(self, df: pd.DataFrame) -> Union[pd.Series, pd.DataFrame]:
        """
        Compute the indicator values for the given DataFrame.

        This method must be implemented by all indicator subclasses.

        Args:
            df (pd.DataFrame): DataFrame containing OHLCV data with at least
                              the required columns for this indicator

        Returns:
            Union[pd.Series, pd.DataFrame]: Computed indicator values

        Raises:
            DataError: If input data is invalid or insufficient
        """
        pass

    def validate_input_data(self, df: pd.DataFrame, required_columns: list) -> None:
        """
        Validate that the input DataFrame contains the required columns.

        Args:
            df (pd.DataFrame): DataFrame to validate
            required_columns (list): List of column names that must be present

        Raises:
            DataError: If any required column is missing or if the DataFrame is empty
        """
        if df.empty:
            error_msg = "Input DataFrame is empty"
            logger.error(error_msg)
            raise DataError(
                message=error_msg,
                error_code="DATA-EmptyDataFrame",
                details={"indicator": self.name},
            )

        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            error_msg = f"Missing required columns: {missing_columns}"
            logger.error(error_msg)
            raise DataError(
                message=error_msg,
                error_code="DATA-MissingColumns",
                details={
                    "indicator": self.name,
                    "required_columns": required_columns,
                    "available_columns": df.columns.tolist(),
                    "missing_columns": missing_columns,
                },
            )

    def validate_sufficient_data(self, df: pd.DataFrame, min_periods: int) -> None:
        """
        Validate that the DataFrame contains enough data points for calculation.

        Args:
            df (pd.DataFrame): DataFrame to validate
            min_periods (int): Minimum number of data points required

        Raises:
            DataError: If the DataFrame has fewer rows than min_periods
        """
        if len(df) < min_periods:
            error_msg = (
                f"Insufficient data: {len(df)} points available, {min_periods} required"
            )
            logger.error(error_msg)
            raise DataError(
                message=error_msg,
                error_code="DATA-InsufficientDataPoints",
                details={
                    "indicator": self.name,
                    "available_points": len(df),
                    "required_points": min_periods,
                },
            )

    def get_column_name(self, suffix: Optional[str] = None) -> str:
        """
        Generate a standardized column name for the indicator output.

        Args:
            suffix (Optional[str]): Optional suffix to append to the name

        Returns:
            str: Column name for the indicator output
        """
        base_name = self.name.lower()

        # Add parameters to the name if present
        param_str = ""

        # Include only the most relevant parameters in the name
        # Typically for indicators, 'period' is the main parameter to include
        if "period" in self.params:
            param_str += f"_{self.params['period']}"

        # Add additional significant parameters but skip 'source' as it's usually implicit
        for key, value in self.params.items():
            # Skip already included parameters and 'source'
            if key == "period" or key == "source":
                continue

            # Only include numeric or string parameters in the column name
            if isinstance(value, (int, float, str)):
                param_str += f"_{value}"

        # Add suffix if provided
        suffix_str = f"_{suffix}" if suffix else ""

        return f"{base_name}{param_str}{suffix_str}"
