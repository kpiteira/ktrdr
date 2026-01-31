"""
Bollinger Band Width indicator implementation.

Bollinger Band Width measures the width of Bollinger Bands relative to the middle band (SMA).
This indicator provides a measure of volatility - wider bands indicate higher volatility,
narrower bands indicate lower volatility.
"""

from typing import Union

import numpy as np
import pandas as pd
from pydantic import Field

from ktrdr.errors import DataError
from ktrdr.indicators.base_indicator import BaseIndicator
from ktrdr.indicators.bollinger_bands_indicator import BollingerBandsIndicator


class BollingerBandWidthIndicator(BaseIndicator):
    """
    Bollinger Band Width technical indicator.

    This indicator calculates the width of Bollinger Bands relative to the middle band:
    Width = (Upper Band - Lower Band) / Middle Band

    The result is a normalized measure of volatility that can be compared across
    different price levels and timeframes.

    **Interpretation:**
    - Higher values indicate higher volatility (bands are wider)
    - Lower values indicate lower volatility (bands are narrower)
    - Can be used to identify volatility expansion/contraction cycles
    - Often used in conjunction with squeeze indicators

    **Parameters:**
    - period: Period for Bollinger Bands calculation (default: 20)
    - multiplier: Standard deviation multiplier for bands (default: 2.0)
    - source: Data source column (default: "close")

    **Output:**
    Returns Series with Bollinger Band Width values (normalized ratio)
    """

    class Params(BaseIndicator.Params):
        """BollingerBandWidth parameter schema with validation."""

        period: int = Field(
            default=20,
            ge=2,
            le=200,
            strict=True,
            description="Period for Bollinger Bands calculation",
        )
        multiplier: float = Field(
            default=2.0,
            gt=0,
            le=10.0,
            description="Standard deviation multiplier for bands",
        )
        source: str = Field(
            default="close",
            strict=True,
            description="Price source column",
        )

    # BollingerBandWidth is displayed in separate panel (not overlay)
    display_as_overlay = False

    def compute(self, data: pd.DataFrame) -> Union[pd.Series, pd.DataFrame]:
        """
        Compute Bollinger Band Width indicator.

        Args:
            data: DataFrame with OHLCV data

        Returns:
            Series with Bollinger Band Width values

        Raises:
            DataError: If required columns are missing or insufficient data
        """
        # Get parameters from self.params (validated by BaseIndicator)
        period: int = self.params["period"]
        multiplier: float = self.params["multiplier"]
        source: str = self.params["source"]

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

        # Create Bollinger Bands indicator with same parameters
        bb_indicator = BollingerBandsIndicator(
            period=period, multiplier=multiplier, source=source
        )

        # Calculate Bollinger Bands
        bb_data = bb_indicator.compute(data)

        # M3b: Extract bands using semantic column names (no parameter embedding)
        # BollingerBands now returns columns: 'upper', 'middle', 'lower'
        upper_band = bb_data["upper"]
        middle_band = bb_data["middle"]
        lower_band = bb_data["lower"]

        # Calculate width using safe division (same logic as training pipeline)
        bb_width = np.where(
            np.abs(middle_band) > 1e-10,  # Avoid tiny denominators
            (upper_band - lower_band) / middle_band,
            0.0,  # Default width when middle is ~0
        )

        # Create result Series
        # M3a: Create unnamed Series (engine handles naming)
        result_series = pd.Series(
            bb_width,
            index=data.index,
        )

        return result_series

    def get_name(self) -> str:
        """Get indicator name."""
        period = self.params.get("period", 20)
        multiplier = self.params.get("multiplier", 2.0)
        return f"BollingerBandWidth_{period}_{multiplier}"
