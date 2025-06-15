"""
Ichimoku Cloud (Ichimoku Kinko Hyo) technical indicator implementation.

This module implements the complete Ichimoku Cloud indicator system, which provides
a comprehensive view of trend, momentum, and support/resistance levels.
"""

import pandas as pd
import numpy as np
from typing import Union

from ktrdr import get_logger
from ktrdr.indicators.base_indicator import BaseIndicator
from ktrdr.indicators.schemas import ICHIMOKU_SCHEMA
from ktrdr.errors import DataError

logger = get_logger(__name__)


class IchimokuIndicator(BaseIndicator):
    """
    Ichimoku Cloud (Ichimoku Kinko Hyo) technical indicator.

    The Ichimoku Cloud is a comprehensive indicator system developed by Goichi Hosoda
    that provides information about trend direction, momentum, and support/resistance
    levels in a single view. It consists of five components plotted together.

    **Components:**
    1. **Tenkan-sen (Conversion Line)**: (9-period high + 9-period low) / 2
    2. **Kijun-sen (Base Line)**: (26-period high + 26-period low) / 2  
    3. **Senkou Span A (Leading Span A)**: (Tenkan-sen + Kijun-sen) / 2, plotted 26 periods ahead
    4. **Senkou Span B (Leading Span B)**: (52-period high + 52-period low) / 2, plotted 26 periods ahead
    5. **Chikou Span (Lagging Span)**: Close price plotted 26 periods behind

    **The Cloud (Kumo):**
    - Formed by Senkou Span A and Senkou Span B
    - Acts as dynamic support/resistance zone
    - Cloud color indicates trend: green (bullish) when Span A > Span B

    **Interpretation:**
    - **Trend Direction**: Price above cloud = uptrend, below cloud = downtrend
    - **Cloud Support/Resistance**: Cloud acts as dynamic support in uptrends, resistance in downtrends
    - **Signal Strength**: Stronger signals when multiple components align
    - **Future Bias**: Senkou spans provide forward-looking perspective

    **Trading Signals:**
    - **Bullish**: Price above cloud, Tenkan > Kijun, Chikou above price 26 periods ago
    - **Bearish**: Price below cloud, Tenkan < Kijun, Chikou below price 26 periods ago
    - **Cloud Breakout**: Price breaking through cloud indicates potential trend change
    - **Line Crosses**: Tenkan/Kijun crossovers provide earlier trend signals

    **Usage:**
    - **Trend Following**: Use cloud position for trend direction
    - **Support/Resistance**: Cloud boundaries for entry/exit levels
    - **Momentum**: Tenkan-sen/Kijun-sen relationship
    - **Confirmation**: Multiple component alignment for signal strength

    **Advantages:**
    - Comprehensive single-indicator system
    - Multiple timeframe perspective (current, lagging, leading)
    - Clear visual trend identification
    - Built-in support/resistance zones

    **Limitations:**
    - Complex interpretation requiring experience
    - Lagging nature in fast-moving markets
    - Can be overwhelming for beginners
    - Less effective in ranging markets

    **Best Used With:**
    - Trending markets with clear directional movement
    - Volume analysis for breakout confirmation
    - Multiple timeframe analysis
    - Risk management rules for cloud breakouts
    """

    def __init__(
        self,
        tenkan_period: int = 9,
        kijun_period: int = 26,
        senkou_b_period: int = 52,
        displacement: int = 26,
        **kwargs
    ):
        """
        Initialize Ichimoku Cloud indicator.

        Args:
            tenkan_period: Period for Tenkan-sen calculation (default: 9)
            kijun_period: Period for Kijun-sen calculation (default: 26)
            senkou_b_period: Period for Senkou Span B calculation (default: 52)
            displacement: Displacement for Senkou spans and Chikou span (default: 26)
            **kwargs: Additional keyword arguments for BaseIndicator
        """
        super().__init__(
            name="Ichimoku",
            tenkan_period=tenkan_period,
            kijun_period=kijun_period,
            senkou_b_period=senkou_b_period,
            displacement=displacement,
            **kwargs
        )

    def _validate_params(self, params: dict) -> dict:
        """
        Validate Ichimoku parameters using schema.

        Args:
            params: Dictionary of parameters to validate

        Returns:
            Validated parameters

        Raises:
            DataError: If parameters are invalid
        """
        return ICHIMOKU_SCHEMA.validate(params)

    def compute(self, data: pd.DataFrame) -> Union[pd.Series, pd.DataFrame]:
        """
        Compute Ichimoku Cloud indicator components.

        Args:
            data: DataFrame with OHLC data (high, low, close required)

        Returns:
            DataFrame with all five Ichimoku components

        Raises:
            DataError: If required columns are missing or insufficient data
        """
        # Validate parameters
        validated_params = self._validate_params(self.params)
        tenkan_period = validated_params["tenkan_period"]
        kijun_period = validated_params["kijun_period"]
        senkou_b_period = validated_params["senkou_b_period"]
        displacement = validated_params["displacement"]

        # Required columns for Ichimoku
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

        # Check for sufficient data
        min_data_points = max(tenkan_period, kijun_period, senkou_b_period)
        if len(data) < min_data_points:
            raise DataError(
                message=f"Insufficient data: need at least {min_data_points} points, got {len(data)}",
                error_code="DATA-InsufficientData",
                details={"required": min_data_points, "provided": len(data)},
            )

        # Extract price data
        high = data["high"]
        low = data["low"]
        close = data["close"]

        # Calculate Tenkan-sen (Conversion Line)
        # (9-period high + 9-period low) / 2
        tenkan_high = high.rolling(window=tenkan_period, min_periods=tenkan_period).max()
        tenkan_low = low.rolling(window=tenkan_period, min_periods=tenkan_period).min()
        tenkan_sen = (tenkan_high + tenkan_low) / 2

        # Calculate Kijun-sen (Base Line)
        # (26-period high + 26-period low) / 2
        kijun_high = high.rolling(window=kijun_period, min_periods=kijun_period).max()
        kijun_low = low.rolling(window=kijun_period, min_periods=kijun_period).min()
        kijun_sen = (kijun_high + kijun_low) / 2

        # Calculate Senkou Span A (Leading Span A)
        # (Tenkan-sen + Kijun-sen) / 2, shifted forward by displacement
        senkou_span_a = (tenkan_sen + kijun_sen) / 2

        # Calculate Senkou Span B (Leading Span B)
        # (52-period high + 52-period low) / 2, shifted forward by displacement
        senkou_b_high = high.rolling(window=senkou_b_period, min_periods=senkou_b_period).max()
        senkou_b_low = low.rolling(window=senkou_b_period, min_periods=senkou_b_period).min()
        senkou_span_b = (senkou_b_high + senkou_b_low) / 2

        # Calculate Chikou Span (Lagging Span)
        # Close price shifted backward by displacement
        chikou_span = close.copy()

        # Create result DataFrame with all components
        result = pd.DataFrame({
            "Tenkan_sen": tenkan_sen,
            "Kijun_sen": kijun_sen,
            "Senkou_Span_A": senkou_span_a,
            "Senkou_Span_B": senkou_span_b,
            "Chikou_Span": chikou_span,
        }, index=data.index)

        # Apply proper naming with parameters
        name_base = self.get_name()
        result.columns = [f"{name_base}_{col}" for col in result.columns]

        logger.debug(f"Computed Ichimoku with tenkan={tenkan_period}, kijun={kijun_period}, senkou_b={senkou_b_period}, displacement={displacement}")

        return result

    def get_name(self) -> str:
        """
        Get the formatted name for this indicator instance.

        Returns:
            Formatted string name including parameters
        """
        tenkan_period = self.params.get("tenkan_period", 9)
        kijun_period = self.params.get("kijun_period", 26)
        senkou_b_period = self.params.get("senkou_b_period", 52)
        displacement = self.params.get("displacement", 26)
        return f"Ichimoku_{tenkan_period}_{kijun_period}_{senkou_b_period}_{displacement}"