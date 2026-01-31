"""
Relative Strength Index (RSI) indicator implementation.

This module provides the RSIIndicator class which computes the RSI technical
indicator, a momentum oscillator that measures the speed and change of price movements.
"""

import numpy as np
import pandas as pd
from pydantic import Field

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
        period (int): The period for RSI calculation (default: 14)
        source (str): The price column to use (default: 'close')
        params (dict): Backward-compatible dict of parameters
    """

    class Params(BaseIndicator.Params):
        """RSI parameter schema with validation."""

        period: int = Field(
            default=14, ge=2, le=100, strict=True, description="RSI lookback period"
        )
        source: str = Field(
            default="close", strict=True, description="Price source column"
        )

    # RSI has different scale than price, don't overlay
    display_as_overlay = False

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
        # Access params via self.params for mypy compatibility
        # (self.period/self.source are set dynamically by BaseIndicator)
        source: str = self.params["source"]
        period: int = self.params["period"]
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
                # M3a: Return unnamed Series (engine handles naming)
                return rsi

            # Normal case - prices have some changes
            # Separate gains and losses
            gain: pd.Series = delta.copy()
            loss: pd.Series = delta.copy()
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

            # M3a: Return unnamed Series (engine handles naming)
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
