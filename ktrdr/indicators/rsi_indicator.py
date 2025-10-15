"""
Relative Strength Index (RSI) indicator implementation.

This module provides the RSIIndicator class which computes the RSI technical
indicator, a momentum oscillator that measures the speed and change of price movements.
"""

import numpy as np
import pandas as pd

from ktrdr import get_logger
from ktrdr.errors import DataError
from ktrdr.indicators.base_indicator import BaseIndicator

logger = get_logger(__name__)


class RSIIndicator(BaseIndicator):
    """
    Relative Strength Index (RSI) technical indicator.

    RSI measures the magnitude of recent price changes to evaluate overbought
    or oversold conditions in the price of a stock or other asset.

    Attributes:
        name (str): The name of the indicator ('RSI')
        params (dict): Parameters for RSI calculation including:
            - period (int): The period for RSI calculation (default: 14)
            - source (str): The price column to use (default: 'close')
    """

    def __init__(self, period: int = 14, source: str = "close"):
        """
        Initialize the RSI indicator.

        Args:
            period (int): The period for RSI calculation, typically 14
            source (str): The column name from DataFrame to use for calculations
        """
        super().__init__(
            name="RSI", display_as_overlay=False, period=period, source=source
        )
        logger.debug(
            f"Initialized RSI indicator with period {period} using {source} prices"
        )

    def _validate_params(self, params):
        """
        Validate parameters for RSI indicator.

        Args:
            params (dict): Parameters to validate

        Returns:
            dict: Validated parameters

        Raises:
            DataError: If parameters are invalid
        """
        # Validate period
        if "period" in params:
            period = params["period"]
            if not isinstance(period, int):
                raise DataError(
                    message="RSI period must be an integer",
                    error_code="DATA-InvalidType",
                    details={
                        "parameter": "period",
                        "expected": "int",
                        "received": type(period).__name__,
                    },
                )
            if period < 2:
                raise DataError(
                    message="RSI period must be at least 2",
                    error_code="DATA-InvalidValue",
                    details={"parameter": "period", "minimum": 2, "received": period},
                )

        # Validate source
        if "source" in params and not isinstance(params["source"], str):
            raise DataError(
                message="Source must be a string",
                error_code="DATA-InvalidType",
                details={
                    "parameter": "source",
                    "expected": "str",
                    "received": type(params["source"]).__name__,
                },
            )

        return params

    def compute(self, df: pd.DataFrame) -> pd.Series:
        """
        Compute the Relative Strength Index (RSI) for the given data.

        Args:
            df (pd.DataFrame): DataFrame containing price data

        Returns:
            pd.Series: Series containing RSI values

        Raises:
            DataError: If input data is invalid or insufficient
        """
        # Validate input data
        source = self.params["source"]
        period = self.params["period"]
        self.validate_input_data(df, [source])
        self.validate_sufficient_data(
            df, period + 1
        )  # Need at least period+1 data points

        logger.debug(
            f"Computing RSI with period={period} on DataFrame with {len(df)} rows"
        )

        try:
            # Calculate price changes
            delta = df[source].diff()

            # Check if the prices are constant (all deltas are zero after the first item)
            all_deltas_after_first = delta.iloc[1:].abs()
            if all_deltas_after_first.sum() == 0:
                # For constant prices, RSI should be 50 after the period
                rsi = pd.Series(index=df.index, dtype=float)
                rsi.iloc[:period] = np.nan
                rsi.iloc[period:] = 50.0
                rsi.name = self.get_feature_id()
                return rsi

            # Normal case - prices have some changes
            # Separate gains and losses
            gain = delta.copy()
            loss = delta.copy()
            gain[gain < 0] = 0
            loss[loss > 0] = 0
            loss = abs(loss)  # Make losses positive

            # Initialize results with NaNs
            rsi = pd.Series(index=df.index, dtype=float)

            # Initial SMA values for the first period
            first_avg_gain = gain.iloc[1 : period + 1].mean()
            first_avg_loss = loss.iloc[1 : period + 1].mean()

            # Set first valid RSI value at position 'period'
            if first_avg_loss != 0:
                rs = first_avg_gain / first_avg_loss
                rsi.iloc[period] = 100 - (100 / (1 + rs))
            else:
                rsi.iloc[period] = 50.0  # If no losses or gains, RSI is 50 (neutral)
                if first_avg_gain > 0:
                    rsi.iloc[period] = (
                        100.0  # If only gains and no losses, RSI is 100 (extremely overbought)
                    )

            # Calculate subsequent RSI values using Wilder's smoothing method
            avg_gain = first_avg_gain
            avg_loss = first_avg_loss

            for i in range(period + 1, len(df)):
                # Calculate the current gain and loss
                current_gain = gain.iloc[i]
                current_loss = loss.iloc[i]

                # Update moving averages using Wilder's smoothing method
                avg_gain = ((avg_gain * (period - 1)) + current_gain) / period
                avg_loss = ((avg_loss * (period - 1)) + current_loss) / period

                # Calculate RSI
                if avg_loss == 0:
                    if avg_gain == 0:
                        rsi.iloc[i] = 50.0  # No movement means neutral RSI
                    else:
                        rsi.iloc[i] = 100.0  # Only gains means overbought
                else:
                    rs = avg_gain / avg_loss
                    rsi.iloc[i] = 100 - (100 / (1 + rs))

            # Set the name for the result Series
            rsi.name = self.get_feature_id()

            logger.debug(f"RSI calculation completed, non-NaN values: {rsi.count()}")
            return rsi

        except Exception as e:
            error_msg = f"Error calculating RSI: {str(e)}"
            logger.error(error_msg)
            raise DataError(
                message=error_msg,
                error_code="DATA-CalculationError",
                details={"indicator": "RSI", "error": str(e)},
            ) from e
