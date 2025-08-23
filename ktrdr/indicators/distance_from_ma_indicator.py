"""
Distance from Moving Average indicator implementation.

Distance from MA calculates the percentage distance between the current price
and a moving average, providing a normalized measure of how far price has
deviated from its trend.
"""

from typing import Union

import numpy as np
import pandas as pd

from ktrdr.errors import DataError
from ktrdr.indicators.base_indicator import BaseIndicator
from ktrdr.indicators.ma_indicators import ExponentialMovingAverage, SimpleMovingAverage
from ktrdr.indicators.schemas import DISTANCE_FROM_MA_SCHEMA


class DistanceFromMAIndicator(BaseIndicator):
    """
    Distance from Moving Average technical indicator.

    This indicator calculates the percentage distance between the current price
    and a moving average:
    Distance = (Current Price - Moving Average) / Moving Average * 100

    The result is a percentage that shows how far price has moved from its trend,
    with positive values indicating price is above the MA and negative values
    indicating price is below the MA.

    **Interpretation:**
    - Positive values: Price is above the moving average (uptrend/bullish)
    - Negative values: Price is below the moving average (downtrend/bearish)
    - Values near 0: Price is close to the moving average (neutral)
    - Extreme values (>±10%): Price may be overextended and due for reversion

    **Parameters:**
    - period: Period for moving average calculation (default: 20)
    - ma_type: Type of moving average - "SMA" or "EMA" (default: "SMA")
    - source: Data source column (default: "close")

    **Output:**
    Returns Series with Distance from MA values as percentages
    """

    def __init__(self, period: int = 20, ma_type: str = "SMA", source: str = "close"):
        """
        Initialize Distance from MA indicator.

        Args:
            period: Period for moving average calculation (default: 20)
            ma_type: Type of moving average - "SMA" or "EMA" (default: "SMA")
            source: Data source column (default: "close")
        """
        # Call parent constructor with display_as_overlay=False (separate panel)
        super().__init__(
            name="DistanceFromMA",
            display_as_overlay=False,
            period=period,
            ma_type=ma_type,
            source=source,
        )

    def _validate_params(self, params):
        """Validate parameters using schema."""
        return DISTANCE_FROM_MA_SCHEMA.validate(params)

    def compute(self, data: pd.DataFrame) -> Union[pd.Series, pd.DataFrame]:
        """
        Compute Distance from Moving Average indicator.

        Args:
            data: DataFrame with OHLCV data

        Returns:
            Series with Distance from MA values as percentages

        Raises:
            DataError: If required columns are missing or insufficient data
        """
        # Validate parameters
        validated_params = self._validate_params(self.params)
        period = validated_params["period"]
        ma_type = validated_params["ma_type"]
        source = validated_params["source"]

        # Check if source column exists
        if source not in data.columns:
            raise DataError(
                message=f"Source column '{source}' not found in data",
                error_code="DATA-MissingColumn",
                details={"source": source, "available_columns": list(data.columns)},
            )

        # Check for sufficient data
        if len(data) < period:
            raise DataError(
                message=f"Insufficient data: need at least {period} points, got {len(data)}",
                error_code="DATA-InsufficientData",
                details={"required": period, "provided": len(data)},
            )

        # Calculate moving average based on type
        if ma_type == "SMA":
            ma_indicator = SimpleMovingAverage(period=period, source=source)
        elif ma_type == "EMA":
            ma_indicator = ExponentialMovingAverage(period=period, source=source)
        else:
            raise DataError(
                message=f"Invalid ma_type '{ma_type}'. Must be 'SMA' or 'EMA'",
                error_code="DATA-InvalidParameter",
                details={"ma_type": ma_type, "valid_types": ["SMA", "EMA"]},
            )

        # Calculate moving average
        ma_values = ma_indicator.compute(data)
        current_price = data[source]

        # Calculate percentage distance using safe division (same logic as training pipeline)
        # Only calculate where MA values are not NaN
        distance_pct = np.where(
            (pd.notna(ma_values))
            & (np.abs(ma_values) > 1e-10),  # Avoid NaN and tiny denominators
            (current_price - ma_values) / ma_values * 100,
            np.nan,  # Keep NaN where MA is NaN, 0.0 where MA is ~0
        )

        # Handle case where MA is ~0 but not NaN
        distance_pct = np.where(
            (pd.notna(ma_values)) & (np.abs(ma_values) <= 1e-10), 0.0, distance_pct
        )

        # Create result Series
        result_series = pd.Series(
            distance_pct,
            index=data.index,
            name=self.get_column_name(),
        )

        return result_series

    def get_name(self) -> str:
        """Get indicator name."""
        period = self.params.get("period", 20)
        ma_type = self.params.get("ma_type", "SMA")
        return f"DistanceFromMA_{ma_type}_{period}"
