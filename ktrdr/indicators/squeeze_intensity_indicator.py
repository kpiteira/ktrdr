"""
Squeeze Intensity indicator implementation.

Squeeze Intensity measures how much Bollinger Bands are compressed inside
Keltner Channels. This composite indicator helps identify periods of low
volatility that often precede significant price movements.
"""

import pandas as pd
import numpy as np
from typing import Union

from ktrdr.indicators.base_indicator import BaseIndicator
from ktrdr.indicators.schemas import SQUEEZE_INTENSITY_SCHEMA
from ktrdr.errors import DataError
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

    def __init__(
        self,
        bb_period: int = 20,
        bb_multiplier: float = 2.0,
        kc_period: int = 20,
        kc_multiplier: float = 2.0,
        source: str = "close",
    ):
        """
        Initialize Squeeze Intensity indicator.

        Args:
            bb_period: Period for Bollinger Bands (default: 20)
            bb_multiplier: Standard deviation multiplier for BB (default: 2.0)
            kc_period: Period for Keltner Channels (default: 20)
            kc_multiplier: ATR multiplier for KC (default: 2.0)
            source: Data source column (default: "close")
        """
        # Call parent constructor with display_as_overlay=False (separate panel)
        super().__init__(
            name="SqueezeIntensity",
            display_as_overlay=False,
            bb_period=bb_period,
            bb_multiplier=bb_multiplier,
            kc_period=kc_period,
            kc_multiplier=kc_multiplier,
            source=source,
        )

    def _validate_params(self, params):
        """Validate parameters using schema."""
        return SQUEEZE_INTENSITY_SCHEMA.validate(params)

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
        # Validate parameters
        validated_params = self._validate_params(self.params)
        bb_period = validated_params["bb_period"]
        bb_multiplier = validated_params["bb_multiplier"]
        kc_period = validated_params["kc_period"]
        kc_multiplier = validated_params["kc_multiplier"]
        source = validated_params["source"]

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
        bb_upper = bb_data["upper"]
        bb_lower = bb_data["lower"]

        # Calculate Keltner Channels (KeltnerChannels uses close by default)
        # Note: KeltnerChannels uses atr_period=10 by default
        kc_indicator = KeltnerChannelsIndicator(
            period=kc_period, multiplier=kc_multiplier
        )
        kc_data = kc_indicator.compute(data)

        # KeltnerChannels returns column names with parameters
        # Format: KC_Upper_{period}_{atr_period}_{multiplier}
        atr_period = 10  # KeltnerChannels default
        kc_upper = kc_data[f"KC_Upper_{kc_period}_{atr_period}_{kc_multiplier}"]
        kc_lower = kc_data[f"KC_Lower_{kc_period}_{atr_period}_{kc_multiplier}"]

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

        # Create result Series
        result_series = pd.Series(
            squeeze_intensity,
            index=data.index,
            name=self.get_column_name(),
        )

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
