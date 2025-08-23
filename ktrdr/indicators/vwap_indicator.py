"""
Volume Weighted Average Price (VWAP) technical indicator implementation.

This module implements the VWAP indicator, which calculates the average price
a security has traded at throughout the day, weighted by volume.
"""

from typing import Union

import pandas as pd

from ktrdr import get_logger
from ktrdr.errors import DataError
from ktrdr.indicators.base_indicator import BaseIndicator
from ktrdr.indicators.schemas import VWAP_SCHEMA

logger = get_logger(__name__)


class VWAPIndicator(BaseIndicator):
    """
    Volume Weighted Average Price (VWAP) technical indicator.

    VWAP calculates the average price a security has traded at throughout
    a specified period, weighted by volume. It gives more weight to prices
    where more volume occurred, providing a more accurate representation
    of the "average" trading price.

    **Formula:**
    VWAP = Sum(Typical Price × Volume) / Sum(Volume)

    Where Typical Price = (High + Low + Close) / 3

    **Calculation Methods:**
    1. Cumulative VWAP: Running total from start of period
    2. Rolling VWAP: Moving window over specified period (default)

    **Interpretation:**
    - Price above VWAP: Indicates bullish sentiment (buying pressure)
    - Price below VWAP: Indicates bearish sentiment (selling pressure)
    - VWAP acts as dynamic support/resistance level
    - Volume-weighted nature makes it more reliable than simple price averages

    **Usage:**
    - Trading benchmark: Compare execution prices against VWAP
    - Trend identification: Price relative to VWAP shows trend strength
    - Support/resistance: VWAP often acts as dynamic support/resistance
    - Institutional trading: Widely used by institutions for execution
    - Fair value estimation: Represents volume-weighted fair value

    **Advantages:**
    - Volume consideration: Accounts for actual trading activity
    - Institutional relevance: Widely used benchmark in professional trading
    - Dynamic levels: Adapts to current market conditions
    - Trend confirmation: Helps confirm price trend validity

    **Parameters:**
    - period: Period for rolling VWAP calculation (default: 20, 0 for cumulative)
    - use_typical_price: Use typical price vs close price (default: True)

    **Output:**
    Returns Series with VWAP values
    """

    def __init__(self, period: int = 20, use_typical_price: bool = True):
        """
        Initialize VWAP indicator.

        Args:
            period: Period for rolling VWAP (default: 20, use 0 for cumulative)
            use_typical_price: Use typical price (H+L+C)/3 vs close price (default: True)
        """
        # Call parent constructor with display_as_overlay=True (price overlay)
        super().__init__(
            name="VWAP",
            display_as_overlay=True,
            period=period,
            use_typical_price=use_typical_price,
        )

    def _validate_params(self, params):
        """Validate parameters using schema."""
        return VWAP_SCHEMA.validate(params)

    def compute(self, data: pd.DataFrame) -> Union[pd.Series, pd.DataFrame]:
        """
        Compute VWAP indicator.

        Args:
            data: DataFrame with OHLCV data

        Returns:
            Series with VWAP values

        Raises:
            DataError: If required columns are missing or insufficient data
        """
        # Validate parameters
        validated_params = self._validate_params(self.params)
        period = validated_params["period"]
        use_typical_price = validated_params["use_typical_price"]

        # Required columns
        required_columns = ["volume"]
        if use_typical_price:
            required_columns.extend(["high", "low", "close"])
        else:
            required_columns.append("close")

        # Check for required columns
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            raise DataError(
                message=f"Missing required columns: {missing_columns}",
                error_code="DATA-MissingColumns",
                details={
                    "missing_columns": missing_columns,
                    "required_columns": required_columns,
                    "available_columns": list(data.columns),
                },
            )

        # Check for sufficient data
        min_data_points = max(1, period) if period > 0 else 1
        if len(data) < min_data_points:
            raise DataError(
                message=f"Insufficient data: need at least {min_data_points} points, got {len(data)}",
                error_code="DATA-InsufficientData",
                details={"required": min_data_points, "provided": len(data)},
            )

        # Calculate price to use
        if use_typical_price:
            # Typical Price = (High + Low + Close) / 3
            price = (data["high"] + data["low"] + data["close"]) / 3
        else:
            # Use close price
            price = data["close"]

        # Get volume
        volume = data["volume"]

        # Calculate price × volume
        price_volume = price * volume

        # Calculate VWAP based on period
        if period == 0:
            # Cumulative VWAP (from start of data)
            cumulative_pv = price_volume.cumsum()
            cumulative_volume = volume.cumsum()

            # Avoid division by zero
            vwap = cumulative_pv / cumulative_volume.replace(0, float("nan"))
        else:
            # Rolling VWAP over specified period
            rolling_pv = price_volume.rolling(window=period, min_periods=1).sum()
            rolling_volume = volume.rolling(window=period, min_periods=1).sum()

            # Avoid division by zero
            vwap = rolling_pv / rolling_volume.replace(0, float("nan"))

        # Replace infinite values with NaN
        vwap = vwap.replace([float("inf"), float("-inf")], float("nan"))

        # Create result series with proper index
        result_series = pd.Series(vwap, index=data.index, name=self.get_name())

        logger.debug(
            f"Computed VWAP with period={period}, use_typical_price={use_typical_price}"
        )

        return result_series

    def get_name(self) -> str:
        """Get indicator name."""
        period = self.params.get("period", 20)
        use_typical_price = self.params.get("use_typical_price", True)
        price_type = "typical" if use_typical_price else "close"
        if period == 0:
            return f"VWAP_cumulative_{price_type}"
        else:
            return f"VWAP_{period}_{price_type}"
