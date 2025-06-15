"""
Bollinger Bands technical indicator implementation.

Bollinger Bands consist of three lines:
- Middle Band: Simple Moving Average (SMA)
- Upper Band: SMA + (multiplier × Standard Deviation)
- Lower Band: SMA - (multiplier × Standard Deviation)

The indicator is commonly used to identify overbought/oversold conditions
and potential breakout points.
"""

import pandas as pd
from typing import Union
from ktrdr.indicators.base_indicator import BaseIndicator
from ktrdr.indicators.schemas import BOLLINGER_BANDS_SCHEMA
from ktrdr.errors import DataError


class BollingerBandsIndicator(BaseIndicator):
    """
    Bollinger Bands technical indicator.

    Bollinger Bands are volatility bands placed above and below a moving average.
    Volatility is based on the standard deviation, which changes as volatility
    increases and decreases. The bands automatically widen when volatility
    increases and narrow when volatility decreases.

    **Interpretation:**
    - Price touching upper band may indicate overbought condition
    - Price touching lower band may indicate oversold condition
    - Band width indicates volatility (wider = more volatile)
    - Price breakouts beyond bands may signal trend continuation

    **Parameters:**
    - period: Moving average period (default: 20)
    - multiplier: Standard deviation multiplier (default: 2.0)
    - source: Data source column (default: "close")

    **Output:**
    Returns DataFrame with three columns:
    - upper: Upper Bollinger Band
    - middle: Middle Band (SMA)
    - lower: Lower Bollinger Band
    """

    def __init__(
        self, period: int = 20, multiplier: float = 2.0, source: str = "close"
    ):
        """
        Initialize Bollinger Bands indicator.

        Args:
            period: Moving average period (default: 20)
            multiplier: Standard deviation multiplier (default: 2.0)
            source: Data source column (default: "close")
        """
        # Call parent constructor with display_as_overlay=True (price overlay)
        super().__init__(
            name="BollingerBands",
            display_as_overlay=True,
            period=period,
            multiplier=multiplier,
            source=source,
        )

    def _validate_params(self, params):
        """Validate parameters using schema."""
        return BOLLINGER_BANDS_SCHEMA.validate(params)

    def compute(self, data: pd.DataFrame) -> Union[pd.Series, pd.DataFrame]:
        """
        Compute Bollinger Bands indicator.

        Args:
            data: DataFrame with OHLCV data

        Returns:
            DataFrame with upper, middle, and lower band values

        Raises:
            DataError: If required columns are missing or insufficient data
        """
        # Validate parameters
        validated_params = self._validate_params(self.params)
        period = validated_params["period"]
        multiplier = validated_params["multiplier"]
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

        # Calculate middle band (SMA)
        middle_band = data[source].rolling(window=period, min_periods=period).mean()

        # Calculate standard deviation
        rolling_std = data[source].rolling(window=period, min_periods=period).std()

        # Calculate upper and lower bands
        upper_band = middle_band + (multiplier * rolling_std)
        lower_band = middle_band - (multiplier * rolling_std)

        # Create result DataFrame
        result = pd.DataFrame(
            {"upper": upper_band, "middle": middle_band, "lower": lower_band},
            index=data.index,
        )

        return result

    def get_name(self) -> str:
        """Get indicator name."""
        period = self.params.get("period", 20)
        multiplier = self.params.get("multiplier", 2.0)
        return f"BollingerBands_{period}_{multiplier}"
