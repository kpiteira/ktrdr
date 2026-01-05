"""
Williams %R indicator implementation for KTRDR.

Williams %R is a momentum indicator that measures overbought and oversold levels.
It is similar to the Stochastic Oscillator but is plotted upside-down on a scale of -100 to 0.
"""

from typing import Any

import pandas as pd

from ktrdr import get_logger
from ktrdr.errors import DataError
from ktrdr.indicators.base_indicator import BaseIndicator
from ktrdr.indicators.schemas import WILLIAMS_R_SCHEMA

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

    def __init__(self, period: int = 14):
        """
        Initialize the Williams %R indicator.

        Args:
            period: Lookback period for Williams %R calculation
        """
        # Call parent constructor with display_as_overlay=False (separate panel)
        super().__init__(
            name="WilliamsR",
            display_as_overlay=False,
            period=period,
        )

        logger.debug(f"Initialized Williams %R indicator with period={period}")

    def _validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Validate parameters for Williams %R indicator using schema-based validation.

        Args:
            params: Parameters to validate

        Returns:
            Validated parameters with defaults applied

        Raises:
            DataError: If parameters are invalid
        """
        return WILLIAMS_R_SCHEMA.validate(params)

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

        # Check for duplicate columns and extract as Series
        duplicate_cols = [
            col for col in ["high", "low", "close"] if list(data.columns).count(col) > 1
        ]
        if duplicate_cols:
            logger.error(
                f"[CRITICAL BUG] WilliamsR found duplicate columns: {duplicate_cols}"
            )

        # Extract high/low/close, ensuring they are Series not DataFrames
        high_data = data["high"]
        if isinstance(high_data, pd.DataFrame):
            logger.error(
                f"[CRITICAL BUG] data['high'] returned DataFrame with {len(high_data.columns)} columns!"
            )
            high_data = high_data.iloc[:, 0]

        low_data = data["low"]
        if isinstance(low_data, pd.DataFrame):
            logger.error(
                f"[CRITICAL BUG] data['low'] returned DataFrame with {len(low_data.columns)} columns!"
            )
            low_data = low_data.iloc[:, 0]

        close_data = data["close"]
        if isinstance(close_data, pd.DataFrame):
            logger.error(
                f"[CRITICAL BUG] data['close'] returned DataFrame with {len(close_data.columns)} columns!"
            )
            close_data = close_data.iloc[:, 0]

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
