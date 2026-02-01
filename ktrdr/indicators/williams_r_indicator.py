"""
Williams %R indicator implementation for KTRDR.

Williams %R is a momentum indicator that measures overbought and oversold levels.
It is similar to the Stochastic Oscillator but is plotted upside-down on a scale of -100 to 0.
"""

import pandas as pd
from pydantic import Field

from ktrdr import get_logger
from ktrdr.errors import DataError
from ktrdr.indicators.base_indicator import BaseIndicator

# Create module-level logger
logger = get_logger(__name__)


class WilliamsRIndicator(BaseIndicator):
    """
    Williams %R momentum indicator.

    Williams %R is calculated as:
    %R = ((Highest High - Close) / (Highest High - Lowest Low)) × -100

    The indicator oscillates between -100 and 0:
    - Values above -20 indicate overbought conditions
    - Values below -80 indicate oversold conditions
    - The negative scale differentiates it from Stochastic (which uses 0-100)

    Default parameters:
        - period: 14 (lookback period for calculation)

    Attributes:
        period (int): Lookback period for Williams %R calculation
    """

    class Params(BaseIndicator.Params):
        """Williams %R parameter schema with validation."""

        period: int = Field(
            default=14,
            ge=1,
            le=100,
            strict=True,
            description="Lookback period for Williams %R calculation",
        )

    # Williams %R is displayed in a separate panel (oscillator)
    display_as_overlay = False

    def compute(self, data: pd.DataFrame) -> pd.Series:
        """
        Compute the Williams %R indicator.

        Args:
            data: DataFrame containing OHLC data

        Returns:
            Series with Williams %R values (-100 to 0)

        Raises:
            DataError: If required columns are missing or insufficient data
        """
        # Get parameters from self.params (validated by BaseIndicator)
        period = self.params.get("period", 14)

        # Check required columns
        required_columns = ["high", "low", "close"]
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            raise DataError(
                message=f"Williams %R requires columns: {', '.join(missing_columns)}",
                error_code="DATA-MissingColumn",
                details={
                    "missing_columns": missing_columns,
                    "required_columns": required_columns,
                    "available_columns": list(data.columns),
                },
            )

        # Check for sufficient data
        if len(data) < period:
            raise DataError(
                message=f"Williams %R requires at least {period} data points for accurate calculation",
                error_code="DATA-InsufficientData",
                details={
                    "required": period,
                    "provided": len(data),
                    "period": period,
                },
            )

        # Check for duplicate columns - this indicates a bug in the caller
        duplicate_cols = [
            col for col in ["high", "low", "close"] if list(data.columns).count(col) > 1
        ]
        if duplicate_cols:
            raise DataError(
                message=f"Williams %R received DataFrame with duplicate columns: {duplicate_cols}",
                error_code="DATA-DuplicateColumns",
                details={
                    "duplicate_columns": duplicate_cols,
                    "all_columns": list(data.columns),
                },
            )

        # Extract high/low/close as Series
        high_data = data["high"]
        low_data = data["low"]
        close_data = data["close"]

        # Calculate rolling highest high and lowest low over period
        highest_high = high_data.rolling(window=period, min_periods=period).max()
        lowest_low = low_data.rolling(window=period, min_periods=period).min()

        # Calculate Williams %R
        # %R = ((Highest High - Close) / (Highest High - Lowest Low)) × -100
        williams_r = ((highest_high - close_data) / (highest_high - lowest_low)) * -100

        # Handle division by zero (when high == low)
        # In this case, price is at the midpoint, so use -50.0 (neutral)
        williams_r = williams_r.fillna(-50.0)

        # M3a: Create unnamed Series (engine handles naming)
        result_series = pd.Series(williams_r, index=data.index)

        logger.debug(f"Computed Williams %R with period={period}")

        return result_series
