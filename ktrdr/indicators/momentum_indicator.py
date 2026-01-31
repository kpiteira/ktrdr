"""
Momentum technical indicator implementation.

This module implements the Momentum indicator, which measures the rate of change
in price over a specified period to identify trends and momentum shifts.
"""

from typing import Union

import pandas as pd
from pydantic import Field

from ktrdr import get_logger
from ktrdr.errors import DataError
from ktrdr.indicators.base_indicator import BaseIndicator

logger = get_logger(__name__)


class MomentumIndicator(BaseIndicator):
    """
    Momentum technical indicator.

    Momentum measures the rate of change in price over a specified period.
    It is one of the simplest momentum oscillators, calculated as the difference
    between the current price and the price N periods ago.

    **Formula:**
    Momentum = Current Price - Price N periods ago

    **Interpretation:**
    - Positive momentum indicates upward price movement
    - Negative momentum indicates downward price movement
    - Zero momentum indicates no change in price
    - Increasing momentum suggests accelerating trend
    - Decreasing momentum suggests trend deceleration

    **Usage:**
    - Trend identification: Positive/negative momentum shows trend direction
    - Momentum divergence: Price vs momentum divergence signals trend weakness
    - Zero-line crossovers: Momentum crossing zero can signal trend changes
    - Momentum peaks/troughs: Can indicate potential reversal points

    **Parameters:**
    - period: Lookback period for momentum calculation (default: 10)
    - source: Data source column (default: "close")

    **Output:**
    Returns Series with momentum values (difference in price units)
    """

    class Params(BaseIndicator.Params):
        """Momentum parameter schema with validation."""

        period: int = Field(
            default=10,
            ge=1,
            le=100,
            strict=True,
            description="Lookback period for momentum calculation",
        )
        source: str = Field(
            default="close", strict=True, description="Price source column"
        )

    # Momentum is displayed in a separate panel (oscillator)
    display_as_overlay = False

    def compute(self, data: pd.DataFrame) -> Union[pd.Series, pd.DataFrame]:
        """
        Compute Momentum indicator.

        Args:
            data: DataFrame with OHLCV data

        Returns:
            Series with momentum values

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

        # Calculate momentum: Current Price - Price N periods ago
        price_series = data[source]
        momentum = price_series - price_series.shift(period)

        # M3a: Create unnamed Series (engine handles naming)
        # Use .values to avoid inheriting name from source Series
        result_series = pd.Series(momentum.values, index=data.index)

        logger.debug(f"Computed Momentum with period={period}, source={source}")

        return result_series

    def get_name(self) -> str:
        """Get indicator name."""
        period = self.params.get("period", 10)
        source = self.params.get("source", "close")
        return f"Momentum_{period}_{source}"
