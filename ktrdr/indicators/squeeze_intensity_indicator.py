"""
Squeeze Intensity indicator implementation.

Squeeze Intensity measures how much Bollinger Bands are compressed inside
Keltner Channels. This composite indicator helps identify periods of low
volatility that often precede significant price movements.
"""

from typing import Union

import numpy as np
import pandas as pd
from pydantic import Field

from ktrdr.errors import DataError
from ktrdr.indicators.base_indicator import BaseIndicator
from ktrdr.indicators.bollinger_bands_indicator import BollingerBandsIndicator
from ktrdr.indicators.keltner_channels import KeltnerChannelsIndicator


class SqueezeIntensityIndicator(BaseIndicator):
    """
    Squeeze Intensity technical indicator.

    This indicator measures the intensity of a "squeeze" condition where
    Bollinger Bands are compressed inside Keltner Channels. The calculation:

    1. Calculate Bollinger Bands (upper, middle, lower)
    2. Calculate Keltner Channels (upper, lower)
    3. Determine how much BB bands are inside KC channels
    4. Return intensity: 1.0 = full squeeze, 0.0 = no squeeze

    **Interpretation:**
    - Values near 1.0 indicate strong squeeze (low volatility)
    - Values near 0.0 indicate no squeeze (normal/high volatility)
    - Squeezes often precede volatility expansion and strong moves
    - Can be used to time entries before breakouts

    **Parameters:**
    - bb_period: Period for Bollinger Bands (default: 20)
    - bb_multiplier: Standard deviation multiplier for BB (default: 2.0)
    - kc_period: Period for Keltner Channels (default: 20)
    - kc_multiplier: ATR multiplier for KC (default: 2.0)
    - source: Data source column (default: "close")

    **Output:**
    Returns Series with Squeeze Intensity values (0.0 to 1.0)
    """

    class Params(BaseIndicator.Params):
        """SqueezeIntensity parameter schema with validation."""

        bb_period: int = Field(
            default=20,
            ge=2,
            le=100,
            strict=True,
            description="Period for Bollinger Bands calculation",
        )
        bb_multiplier: float = Field(
            default=2.0,
            gt=0,
            le=5.0,
            strict=True,
            description="Standard deviation multiplier for Bollinger Bands",
        )
        kc_period: int = Field(
            default=20,
            ge=2,
            le=100,
            strict=True,
            description="Period for Keltner Channels calculation",
        )
        kc_multiplier: float = Field(
            default=2.0,
            gt=0,
            le=5.0,
            strict=True,
            description="ATR multiplier for Keltner Channels",
        )
        source: str = Field(
            default="close",
            strict=True,
            description="Data source column",
        )

    # SqueezeIntensity is displayed in separate panel
    display_as_overlay = False

    def compute(self, data: pd.DataFrame) -> Union[pd.Series, pd.DataFrame]:
        """
        Compute Squeeze Intensity indicator.

        Args:
            data: DataFrame with OHLCV data

        Returns:
            Series with Squeeze Intensity values

        Raises:
            DataError: If required columns are missing or insufficient data
        """
        bb_period: int = self.params["bb_period"]
        bb_multiplier: float = self.params["bb_multiplier"]
        kc_period: int = self.params["kc_period"]
        kc_multiplier: float = self.params["kc_multiplier"]
        source: str = self.params["source"]

        # Check if required columns exist
        required_columns = [source, "high", "low", "close"]
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            raise DataError(
                message=f"Required columns missing: {missing_columns}",
                error_code="DATA-MissingColumn",
                details={
                    "missing_columns": missing_columns,
                    "available_columns": list(data.columns),
                },
            )

        # Check for sufficient data (need max of both periods)
        min_period = max(bb_period, kc_period)
        if len(data) < min_period:
            raise DataError(
                message=f"Insufficient data: need at least {min_period} points, got {len(data)}",
                error_code="DATA-InsufficientData",
                details={"required": min_period, "provided": len(data)},
            )

        # Calculate Bollinger Bands
        bb_indicator = BollingerBandsIndicator(
            period=bb_period, multiplier=bb_multiplier, source=source
        )
        bb_data = bb_indicator.compute(data)

        # M3b: Extract bands using semantic column names (no parameter embedding)
        # BollingerBands now returns columns: 'upper', 'lower'
        bb_upper = bb_data["upper"]
        bb_lower = bb_data["lower"]

        # Calculate Keltner Channels (KeltnerChannels uses close by default)
        kc_indicator = KeltnerChannelsIndicator(
            period=kc_period, multiplier=kc_multiplier
        )
        kc_data = kc_indicator.compute(data)

        # M3b: KeltnerChannels now returns semantic column names: 'upper', 'lower'
        kc_upper = kc_data["upper"]
        kc_lower = kc_data["lower"]

        # Calculate squeeze intensity using same logic as training pipeline
        kc_range = kc_upper - kc_lower

        # Safe division to avoid overflow when KC range is very small
        squeeze_intensity = np.where(
            np.abs(kc_range) > 1e-10,  # Avoid tiny denominators
            np.maximum(
                0,
                np.minimum(
                    (kc_upper - bb_upper) / kc_range, (bb_lower - kc_lower) / kc_range
                ),
            ),
            0.0,  # Default to no squeeze when KC range is ~0
        )

        # M3a: Create unnamed Series (engine handles naming)
        result_series = pd.Series(squeeze_intensity, index=data.index)

        return result_series

    def get_name(self) -> str:
        """Get indicator name."""
        bb_period = self.params.get("bb_period", 20)
        bb_multiplier = self.params.get("bb_multiplier", 2.0)
        kc_period = self.params.get("kc_period", 20)
        kc_multiplier = self.params.get("kc_multiplier", 2.0)
        return (
            f"SqueezeIntensity_{bb_period}_{bb_multiplier}_{kc_period}_{kc_multiplier}"
        )
