"""
Parabolic SAR (Stop and Reverse) technical indicator implementation.

This module implements the Parabolic SAR indicator, which is a trend-following
indicator that provides potential stop-and-reverse points for trending markets.
"""

from typing import Union

import numpy as np
import pandas as pd
from pydantic import Field

from ktrdr import get_logger
from ktrdr.errors import DataError
from ktrdr.indicators.base_indicator import BaseIndicator

logger = get_logger(__name__)


class ParabolicSARIndicator(BaseIndicator):
    """
    Parabolic SAR (Stop and Reverse) technical indicator.

    The Parabolic SAR is a trend-following indicator that provides potential
    stop-and-reverse points. It appears as a series of dots above or below
    the price action, indicating the potential direction of price movement.

    **Formula:**
    SAR(tomorrow) = SAR(today) + AF × (EP - SAR(today))

    Where:
    - SAR = Stop and Reverse value
    - AF = Acceleration Factor (starts at initial_af, increases by step_af each period)
    - EP = Extreme Point (highest high in uptrend, lowest low in downtrend)

    **Key Concepts:**
    - **Uptrend**: SAR dots appear below price, EP tracks highest high
    - **Downtrend**: SAR dots appear above price, EP tracks lowest low
    - **Reversal**: When price crosses SAR, trend reverses and AF resets
    - **Acceleration**: AF increases each period until max_af is reached

    **Interpretation:**
    - **Buy Signal**: Price moves above SAR dots (trend reversal to uptrend)
    - **Sell Signal**: Price moves below SAR dots (trend reversal to downtrend)
    - **Stop Loss**: SAR provides dynamic stop-loss levels
    - **Trend Following**: Dots follow price at increasing acceleration

    **Usage:**
    - **Trailing Stop**: Use SAR as dynamic stop-loss in trending markets
    - **Trend Identification**: Dot position indicates current trend direction
    - **Entry/Exit Signals**: SAR crossovers provide entry and exit points
    - **Risk Management**: Built-in stop-loss mechanism for position sizing

    **Advantages:**
    - Automatic stop-loss adjustment with trend
    - Clear visual trend indication
    - Self-adjusting acceleration mechanism
    - Works well in trending markets

    **Limitations:**
    - Generates false signals in sideways markets
    - Lag in trend change recognition
    - Not suitable for choppy/ranging markets
    - May produce whipsaws in volatile conditions

    **Best Used With:**
    - Trending markets with clear directional movement
    - Combine with momentum indicators (RSI, MACD)
    - Volume confirmation for signal validation
    - Support/resistance levels for entry timing

    Default parameters:
        - initial_af: 0.02 (initial acceleration factor)
        - step_af: 0.02 (acceleration factor increment)
        - max_af: 0.20 (maximum acceleration factor)

    Attributes:
        initial_af (float): Initial acceleration factor
        step_af (float): Acceleration factor increment
        max_af (float): Maximum acceleration factor
    """

    class Params(BaseIndicator.Params):
        """Parabolic SAR parameter schema with validation."""

        initial_af: float = Field(
            default=0.02,
            ge=0.001,
            le=0.1,
            description="Initial acceleration factor",
        )
        step_af: float = Field(
            default=0.02,
            ge=0.001,
            le=0.1,
            description="Acceleration factor increment",
        )
        max_af: float = Field(
            default=0.20,
            ge=0.01,
            le=1.0,
            description="Maximum acceleration factor",
        )

    # Parabolic SAR is displayed as overlay on price charts
    display_as_overlay = True

    def compute(self, data: pd.DataFrame) -> Union[pd.Series, pd.DataFrame]:
        """
        Compute Parabolic SAR indicator.

        Args:
            data: DataFrame with OHLC data (high, low, close required)

        Returns:
            Series with Parabolic SAR values

        Raises:
            DataError: If required columns are missing or insufficient data
        """
        # Get parameters from self.params (validated by BaseIndicator)
        initial_af: float = self.params["initial_af"]
        step_af: float = self.params["step_af"]
        max_af: float = self.params["max_af"]

        # Required columns for Parabolic SAR
        required_columns = ["high", "low", "close"]
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            raise DataError(
                message=f"Missing required columns: {missing_columns}",
                error_code="DATA-MissingColumns",
                details={
                    "missing_columns": missing_columns,
                    "required_columns": required_columns,
                    "available_columns": list(data.columns),
                },
            )

        # Check for sufficient data (need at least 2 periods)
        min_data_points = 2
        if len(data) < min_data_points:
            raise DataError(
                message=f"Insufficient data: need at least {min_data_points} points, got {len(data)}",
                error_code="DATA-InsufficientData",
                details={"required": min_data_points, "provided": len(data)},
            )

        # Extract price data
        high = data["high"].values
        low = data["low"].values
        close = data["close"].values

        # Initialize SAR array
        length = len(data)
        sar = np.full(length, np.nan)

        # Initialize variables for SAR calculation
        af = initial_af
        ep = 0.0  # Extreme point
        trend = 0  # 1 for uptrend, -1 for downtrend, 0 for initial

        # Initialize trend direction based on first two periods
        if length >= 2:
            if close[1] > close[0]:
                trend = 1  # Uptrend
                ep = high[1]  # Extreme point is highest high
                sar[1] = low[0]  # SAR starts at previous low
            else:
                trend = -1  # Downtrend
                ep = low[1]  # Extreme point is lowest low
                sar[1] = high[0]  # SAR starts at previous high

            # Set first SAR value (no previous period to calculate from)
            sar[0] = np.nan  # No SAR for first period

        # Calculate SAR for remaining periods
        for i in range(2, length):
            # Calculate new SAR value
            sar[i] = sar[i - 1] + af * (ep - sar[i - 1])

            # Check for trend reversal
            if trend == 1:  # Currently in uptrend
                # Check if price breaks below SAR (reversal to downtrend)
                if low[i] <= sar[i]:
                    # Trend reversal: switch to downtrend
                    trend = -1
                    sar[i] = ep  # SAR becomes the extreme point
                    af = initial_af  # Reset acceleration factor
                    ep = low[i]  # New extreme point is current low
                else:
                    # Continue uptrend
                    # SAR should not exceed previous two lows
                    sar[i] = min(
                        sar[i], low[i - 1], low[i - 2] if i >= 2 else low[i - 1]
                    )

                    # Update extreme point if new high
                    if high[i] > ep:
                        ep = high[i]
                        af = min(af + step_af, max_af)  # Increase AF, cap at max

            else:  # Currently in downtrend (trend == -1)
                # Check if price breaks above SAR (reversal to uptrend)
                if high[i] >= sar[i]:
                    # Trend reversal: switch to uptrend
                    trend = 1
                    sar[i] = ep  # SAR becomes the extreme point
                    af = initial_af  # Reset acceleration factor
                    ep = high[i]  # New extreme point is current high
                else:
                    # Continue downtrend
                    # SAR should not fall below previous two highs
                    sar[i] = max(
                        sar[i], high[i - 1], high[i - 2] if i >= 2 else high[i - 1]
                    )

                    # Update extreme point if new low
                    if low[i] < ep:
                        ep = low[i]
                        af = min(af + step_af, max_af)  # Increase AF, cap at max

        # Create result series with proper index
        # M3a: Create unnamed Series (engine handles naming)
        result_series = pd.Series(sar, index=data.index)

        logger.debug(
            f"Computed Parabolic SAR with initial_af={initial_af}, step_af={step_af}, max_af={max_af}"
        )

        return result_series

    def get_name(self) -> str:
        """
        Get the formatted name for this indicator instance.

        Returns:
            Formatted string name including parameters
        """
        initial_af = self.params.get("initial_af", 0.02)
        step_af = self.params.get("step_af", 0.02)
        max_af = self.params.get("max_af", 0.20)
        return f"ParabolicSAR_{initial_af}_{step_af}_{max_af}"
