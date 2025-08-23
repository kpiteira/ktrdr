"""
Commodity Channel Index (CCI) technical indicator implementation.

The Commodity Channel Index (CCI) is a momentum-based oscillator used to help
determine when an investment vehicle has been overbought or oversold. The CCI
measures the variation of a security's price from its statistical mean.

CCI = (Typical Price - 20-period SMA of TP) / (0.015 × Mean Deviation)

Where:
- Typical Price (TP) = (High + Low + Close) / 3
- Mean Deviation = Average of absolute deviations from SMA

**Interpretation:**
- Values above +100 indicate overbought conditions
- Values below -100 indicate oversold conditions
- Values between -100 and +100 indicate normal trading range
- CCI can exceed ±100 during strong trends
"""

import numpy as np
import pandas as pd

from ktrdr.errors import DataError
from ktrdr.indicators.base_indicator import BaseIndicator
from ktrdr.indicators.schemas import CCI_SCHEMA


class CCIIndicator(BaseIndicator):
    """
    Commodity Channel Index (CCI) technical indicator.

    CCI is a momentum oscillator that measures the variation of a price from its
    statistical mean. It was originally developed for commodities but can be applied
    to any financial instrument.

    **Interpretation:**
    - CCI > +100: Overbought condition, potential sell signal
    - CCI < -100: Oversold condition, potential buy signal
    - CCI oscillating between -100 and +100: Normal trading range
    - CCI breaking above/below ±100: Start of new trend

    **Parameters:**
    - period: Number of periods for calculation (default: 20)

    **Output:**
    Returns Series with CCI values (typically ranging from -200 to +200,
    but can exceed these bounds during strong trends).
    """

    def __init__(self, period: int = 20):
        """
        Initialize CCI indicator.

        Args:
            period: Number of periods for CCI calculation (default: 20)
        """
        # Call parent constructor with display_as_overlay=False (separate panel)
        super().__init__(name="CCI", display_as_overlay=False, period=period)

    def _validate_params(self, params):
        """Validate parameters using schema."""
        return CCI_SCHEMA.validate(params)

    def compute(self, data: pd.DataFrame) -> pd.Series:
        """
        Compute Commodity Channel Index (CCI) indicator.

        Args:
            data: DataFrame with OHLC data

        Returns:
            Series with CCI values

        Raises:
            DataError: If required columns are missing or insufficient data
        """
        # Validate parameters
        validated_params = self._validate_params(self.params)
        period = validated_params["period"]

        # Check required columns
        required_columns = ["high", "low", "close"]
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            raise DataError(
                message=f"Missing required columns: {missing_columns}",
                error_code="DATA-MissingColumns",
                details={
                    "missing_columns": missing_columns,
                    "required_columns": required_columns,
                },
            )

        # Check for sufficient data
        if len(data) < period:
            raise DataError(
                message=f"Insufficient data: need at least {period} points, got {len(data)}",
                error_code="DATA-InsufficientData",
                details={"required": period, "provided": len(data)},
            )

        # Calculate Typical Price (TP)
        typical_price = (data["high"] + data["low"] + data["close"]) / 3

        # Calculate Simple Moving Average of Typical Price
        sma_tp = typical_price.rolling(window=period, min_periods=period).mean()

        # Calculate Mean Deviation
        # Mean Deviation = average of absolute deviations from SMA
        def calculate_mean_deviation(tp_series, sma_series, window):
            """Calculate rolling mean deviation."""
            mean_deviations = []

            for i in range(len(tp_series)):
                if i < window - 1:
                    mean_deviations.append(np.nan)
                else:
                    # Get the window of typical prices and corresponding SMA
                    tp_window = tp_series.iloc[i - window + 1 : i + 1]
                    sma_value = sma_series.iloc[i]

                    # Calculate absolute deviations from SMA
                    abs_deviations = np.abs(tp_window - sma_value)

                    # Calculate mean of absolute deviations
                    mean_dev = abs_deviations.mean()
                    mean_deviations.append(mean_dev)

            return pd.Series(mean_deviations, index=tp_series.index)

        mean_deviation = calculate_mean_deviation(typical_price, sma_tp, period)

        # Calculate CCI
        # CCI = (TP - SMA of TP) / (0.015 × Mean Deviation)
        # The 0.015 constant ensures about 70-80% of CCI values fall between -100 and +100
        cci = (typical_price - sma_tp) / (0.015 * mean_deviation)

        return cci

    def get_name(self) -> str:
        """Get indicator name."""
        period = self.params.get("period", 20)
        return f"CCI_{period}"
