"""
Volume Ratio indicator implementation.

Volume Ratio compares current volume to the simple moving average of volume
over a specified period. This indicator helps identify periods of above or
below average trading activity.
"""

from typing import Union

import numpy as np
import pandas as pd
from pydantic import Field

from ktrdr.errors import DataError
from ktrdr.indicators.base_indicator import BaseIndicator


class VolumeRatioIndicator(BaseIndicator):
    """
    Volume Ratio technical indicator.

    This indicator calculates the ratio of current volume to the simple moving
    average of volume over a specified period:
    Ratio = Current Volume / Volume SMA

    The result is a normalized measure that helps identify volume spikes and
    periods of unusual trading activity.

    **Interpretation:**
    - Values > 1.0 indicate above-average volume
    - Values < 1.0 indicate below-average volume
    - Significant spikes (> 2.0) may indicate strong interest/news
    - Very low values (< 0.5) may indicate lack of interest

    **Parameters:**
    - period: Period for volume SMA calculation (default: 20)

    **Output:**
    Returns Series with Volume Ratio values (ratio of current/average volume)
    """

    class Params(BaseIndicator.Params):
        """VolumeRatio parameter schema with validation."""

        period: int = Field(
            default=20,
            ge=2,
            le=100,
            strict=True,
            description="Period for volume SMA calculation",
        )

    # VolumeRatio is displayed in separate panel
    display_as_overlay = False

    def compute(self, data: pd.DataFrame) -> Union[pd.Series, pd.DataFrame]:
        """
        Compute Volume Ratio indicator.

        Args:
            data: DataFrame with OHLCV data

        Returns:
            Series with Volume Ratio values

        Raises:
            DataError: If required columns are missing or insufficient data
        """
        period: int = self.params["period"]

        # Check if volume column exists
        if "volume" not in data.columns:
            raise DataError(
                message="Volume column 'volume' not found in data",
                error_code="DATA-MissingColumn",
                details={
                    "required_column": "volume",
                    "available_columns": list(data.columns),
                },
            )

        # Check for sufficient data
        if len(data) < period:
            raise DataError(
                message=f"Insufficient data: need at least {period} points, got {len(data)}",
                error_code="DATA-InsufficientData",
                details={"required": period, "provided": len(data)},
            )

        # Calculate volume SMA
        volume = data["volume"]
        volume_sma = volume.rolling(window=period, min_periods=period).mean()

        # Calculate ratio using safe division (same logic as training pipeline)
        volume_ratio = np.where(
            np.abs(volume_sma) > 1e-10,  # Avoid tiny denominators
            volume / volume_sma,
            1.0,  # Default ratio when SMA is ~0
        )

        # M3a: Return unnamed Series (engine handles naming)
        result_series = pd.Series(
            volume_ratio,
            index=data.index,
        )

        return result_series

    def get_name(self) -> str:
        """Get indicator name."""
        period = self.params.get("period", 20)
        return f"VolumeRatio_{period}"
