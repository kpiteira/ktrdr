"""
Bollinger Bands technical indicator implementation.

Bollinger Bands consist of three lines:
- Middle Band: Simple Moving Average (SMA)
- Upper Band: SMA + (multiplier × Standard Deviation)
- Lower Band: SMA - (multiplier × Standard Deviation)

The indicator is commonly used to identify overbought/oversold conditions
and potential breakout points.
"""

from typing import Union

import pandas as pd
from pydantic import Field

from ktrdr.errors import DataError
from ktrdr.indicators.base_indicator import BaseIndicator


class BollingerBandsIndicator(BaseIndicator):
    """
    Bollinger Bands technical indicator.

    Bollinger Bands are volatility bands placed above and below a moving average.
    Volatility is based on the standard deviation, which changes as volatility
    increases and decreases. The bands automatically widen when volatility
    increases and narrow when volatility decreases.

    This is a multi-output indicator that produces three columns:
    - upper: Upper Bollinger Band (primary output)
    - middle: Middle Band (SMA)
    - lower: Lower Bollinger Band

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

    class Params(BaseIndicator.Params):
        """BollingerBands parameter schema with validation."""

        period: int = Field(
            default=20,
            ge=2,
            le=200,
            strict=True,
            description="Moving average period",
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

    # BollingerBands is displayed as overlay on price chart
    display_as_overlay = True

    @classmethod
    def is_multi_output(cls) -> bool:
        """Bollinger Bands produces multiple outputs (upper, middle, lower)."""
        return True

    @classmethod
    def get_output_names(cls) -> list[str]:
        """Return semantic output names for Bollinger Bands."""
        return ["upper", "middle", "lower"]

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

        # Calculate middle band (SMA)
        middle_band = data[source].rolling(window=period, min_periods=period).mean()

        # Calculate standard deviation
        rolling_std = data[source].rolling(window=period, min_periods=period).std()

        # Calculate upper and lower bands
        upper_band = middle_band + (multiplier * rolling_std)
        lower_band = middle_band - (multiplier * rolling_std)

        # M3b: Return DataFrame with semantic column names only
        # Engine handles prefixing with indicator_id to prevent collisions
        result = pd.DataFrame(
            {
                "upper": upper_band,
                "middle": middle_band,
                "lower": lower_band,
            },
            index=data.index,
        )

        return result

    def get_name(self) -> str:
        """Get indicator name."""
        period = self.params.get("period", 20)
        multiplier = self.params.get("multiplier", 2.0)
        return f"BollingerBands_{period}_{multiplier}"
