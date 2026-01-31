"""
Rate of Change (ROC) technical indicator implementation.

This module implements the Rate of Change indicator, which measures the percentage
change in price over a specified period to identify momentum and trend strength.
"""

from typing import Union

import pandas as pd
from pydantic import Field

from ktrdr import get_logger
from ktrdr.errors import DataError
from ktrdr.indicators.base_indicator import BaseIndicator

logger = get_logger(__name__)


class ROCIndicator(BaseIndicator):
    """
    Rate of Change (ROC) technical indicator.

    ROC measures the percentage change in price over a specified period.
    It is a momentum oscillator that shows the speed of price change,
    helping to identify trend strength and potential reversals.

    **Formula:**
    ROC = ((Current Price - Price N periods ago) / Price N periods ago) * 100

    **Interpretation:**
    - Positive ROC: Upward price momentum (percentage increase)
    - Negative ROC: Downward price momentum (percentage decrease)
    - Zero ROC: No change in price over the period
    - Higher absolute ROC values indicate stronger momentum
    - ROC crossing zero can signal trend changes

    **Usage:**
    - Momentum analysis: Measure speed and strength of price movements
    - Trend identification: Positive/negative ROC shows trend direction
    - Divergence analysis: ROC vs price divergence signals weakness
    - Overbought/oversold: Extreme ROC values may indicate reversal points
    - Rate comparison: Compare ROC across different periods or assets

    **Advantages over Momentum:**
    - Percentage-based (normalized): Comparable across different price levels
    - Scale-independent: Works equally well for $10 and $1000 stocks
    - Relative measurement: Shows proportional change rather than absolute

    **Parameters:**
    - period: Lookback period for ROC calculation (default: 10)
    - source: Data source column (default: "close")

    **Output:**
    Returns Series with ROC values as percentages (%)
    """

    class Params(BaseIndicator.Params):
        """ROC parameter schema with validation."""

        period: int = Field(
            default=10,
            ge=1,
            le=100,
            strict=True,
            description="Lookback period for ROC calculation",
        )
        source: str = Field(
            default="close", strict=True, description="Price source column"
        )

    # ROC is displayed in a separate panel (oscillator)
    display_as_overlay = False

    def compute(self, data: pd.DataFrame) -> Union[pd.Series, pd.DataFrame]:
        """
        Compute Rate of Change indicator.

        Args:
            data: DataFrame with OHLCV data

        Returns:
            Series with ROC values as percentages

        Raises:
            DataError: If required columns are missing or insufficient data
        """
        # Get parameters from self.params (validated by BaseIndicator)
        period: int = self.params["period"]
        source: str = self.params["source"]

        # Check if source column exists
        if source not in data.columns:
            raise DataError(
                message=f"Source column '{source}' not found in data",
                error_code="DATA-MissingColumn",
                details={"source": source, "available_columns": list(data.columns)},
            )

        # Check for sufficient data
        if len(data) < period + 1:
            raise DataError(
                message=f"Insufficient data: need at least {period + 1} points, got {len(data)}",
                error_code="DATA-InsufficientData",
                details={"required": period + 1, "provided": len(data)},
            )

        # Get the price series
        price_series = data[source]

        # Get the price from N periods ago
        price_n_periods_ago = price_series.shift(period)

        # Calculate ROC: ((Current Price - Price N periods ago) / Price N periods ago) * 100
        # Handle division by zero by replacing with NaN
        roc = ((price_series - price_n_periods_ago) / price_n_periods_ago) * 100

        # Replace infinite values with NaN (in case of division by zero)
        roc = roc.replace([float("inf"), float("-inf")], float("nan"))

        # M3a: Create unnamed Series (engine handles naming)
        # Use .values to avoid inheriting name from source Series
        result_series = pd.Series(roc.values, index=data.index)

        logger.debug(f"Computed ROC with period={period}, source={source}")

        return result_series

    def get_name(self) -> str:
        """Get indicator name."""
        period = self.params.get("period", 10)
        source = self.params.get("source", "close")
        return f"ROC_{period}_{source}"
