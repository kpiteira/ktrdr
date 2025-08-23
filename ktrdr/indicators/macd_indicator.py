"""
MACD indicator implementation for KTRDR.

This module provides the MACDIndicator class for calculating the Moving Average Convergence
Divergence (MACD) indicator.
"""

import pandas as pd

from ktrdr import get_logger
from ktrdr.errors import DataError
from ktrdr.indicators.base_indicator import BaseIndicator
from ktrdr.indicators.schemas import MACD_SCHEMA

# Create module-level logger
logger = get_logger(__name__)


class MACDIndicator(BaseIndicator):
    """
    Moving Average Convergence Divergence (MACD) indicator.

    The MACD indicator calculates the difference between two exponential moving
    averages and provides a signal line, which is an EMA of the MACD line.

    Default parameters:
        - fast_period: 12 (12-day EMA)
        - slow_period: 26 (26-day EMA)
        - signal_period: 9 (9-day EMA of MACD line)
        - source: 'close' (use closing prices for calculation)

    Attributes:
        fast_period (int): The shorter EMA period
        slow_period (int): The longer EMA period
        signal_period (int): The signal line's EMA period
        source (str): The data column to use for calculations
    """

    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        source: str = "close",
    ):
        """
        Initialize the MACD indicator.

        Args:
            fast_period: Period for the shorter EMA
            slow_period: Period for the longer EMA
            signal_period: Period for the signal line EMA
            source: Column name to use for calculations
        """
        # Call parent constructor with display_as_overlay=False
        # Parent constructor will call _validate_params()
        super().__init__(
            name="MACD",  # Use simple name, will be enhanced later with parameters
            display_as_overlay=False,
            fast_period=fast_period,
            slow_period=slow_period,
            signal_period=signal_period,
            source=source,
        )

        logger.debug(
            f"Initialized MACD indicator with fast_period={fast_period}, "
            f"slow_period={slow_period}, signal_period={signal_period}, source={source}"
        )

    def _validate_params(self, params):
        """
        Validate parameters for MACD indicator using schema-based validation.

        Args:
            params (dict): Parameters to validate

        Returns:
            dict: Validated parameters with defaults applied

        Raises:
            DataError: If parameters are invalid
        """
        return MACD_SCHEMA.validate(params)

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Compute the MACD indicator.

        Args:
            data: DataFrame containing the source column.

        Returns:
            DataFrame with MACD line, signal line, and histogram.

        Raises:
            DataError: If the source column is not in the data
        """
        # Get parameters from self.params (validated by BaseIndicator)
        fast_period = self.params.get("fast_period", 12)
        slow_period = self.params.get("slow_period", 26)
        signal_period = self.params.get("signal_period", 9)
        source = self.params.get("source", "close")

        # Check if source column exists
        if source not in data.columns:
            raise DataError(
                message=f"Source column '{source}' not found in data",
                error_code="DATA-MissingColumn",
                details={"column": source, "available_columns": list(data.columns)},
            )

        # Check for sufficient data
        min_required = max(slow_period, fast_period) + signal_period
        if len(data) < min_required:
            raise DataError(
                message=f"MACD requires at least {min_required} data points for accurate calculation",
                error_code="DATA-InsufficientData",
                details={
                    "required": min_required,
                    "provided": len(data),
                    "fast_period": fast_period,
                    "slow_period": slow_period,
                    "signal_period": signal_period,
                },
            )

        # Get the source data
        source_data = data[source]

        # Calculate fast and slow EMAs
        fast_ema = source_data.ewm(span=fast_period, adjust=False).mean()
        slow_ema = source_data.ewm(span=slow_period, adjust=False).mean()

        # Calculate MACD line
        macd_line = fast_ema - slow_ema

        # Calculate signal line (EMA of MACD line)
        signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()

        # Calculate histogram (MACD line - signal line)
        histogram = macd_line - signal_line

        # Create result DataFrame with column names that include the parameters
        macd_col = f"MACD_{fast_period}_{slow_period}"
        signal_col = f"MACD_signal_{fast_period}_{slow_period}_{signal_period}"
        hist_col = f"MACD_hist_{fast_period}_{slow_period}_{signal_period}"

        result_df = pd.DataFrame(
            {macd_col: macd_line, signal_col: signal_line, hist_col: histogram},
            index=data.index,
        )

        logger.debug(
            f"Computed MACD with parameters: fast={fast_period}, "
            f"slow={slow_period}, signal={signal_period}"
        )

        return result_df
