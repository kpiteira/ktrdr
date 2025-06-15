"""
Momentum technical indicator implementation.

This module implements the Momentum indicator, which measures the rate of change
in price over a specified period to identify trends and momentum shifts.
"""

import pandas as pd
from typing import Union

from ktrdr import get_logger
from ktrdr.indicators.base_indicator import BaseIndicator
from ktrdr.indicators.schemas import MOMENTUM_SCHEMA
from ktrdr.errors import DataError

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

    def __init__(self, period: int = 10, source: str = "close"):
        """
        Initialize Momentum indicator.

        Args:
            period: Lookback period for momentum calculation (default: 10)
            source: Data source column (default: "close")
        """
        # Call parent constructor with display_as_overlay=False (separate panel)
        super().__init__(
            name="Momentum",
            display_as_overlay=False,
            period=period,
            source=source,
        )

    def _validate_params(self, params):
        """Validate parameters using schema."""
        return MOMENTUM_SCHEMA.validate(params)

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
        # Validate parameters
        validated_params = self._validate_params(self.params)
        period = validated_params["period"]
        source = validated_params["source"]

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

        # Create result series with proper index
        result_series = pd.Series(momentum, index=data.index, name=self.get_name())

        logger.debug(f"Computed Momentum with period={period}, source={source}")

        return result_series

    def get_name(self) -> str:
        """Get indicator name."""
        period = self.params.get("period", 10)
        source = self.params.get("source", "close")
        return f"Momentum_{period}_{source}"