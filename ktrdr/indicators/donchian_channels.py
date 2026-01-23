"""
Donchian Channels Indicator.

The Donchian Channels indicator identifies the highest high and lowest low
over a specified period, creating upper and lower channels that help identify
volatility, support/resistance levels, and potential breakout points.

Author: KTRDR
"""

from typing import Any

import pandas as pd

from ktrdr import get_logger
from ktrdr.errors import DataError
from ktrdr.indicators.base_indicator import BaseIndicator

logger = get_logger(__name__)


class DonchianChannelsIndicator(BaseIndicator):
    """
    Donchian Channels indicator implementation.

    Donchian Channels consist of three lines:
    - Upper Channel: Highest high over the specified period
    - Lower Channel: Lowest low over the specified period
    - Middle Line: Average of upper and lower channels

    The channels help identify:
    - Support and resistance levels
    - Volatility expansion/contraction
    - Potential breakout points
    - Trend strength

    Formula:
    Upper Channel = MAX(High, period)
    Lower Channel = MIN(Low, period)
    Middle Line = (Upper Channel + Lower Channel) / 2

    Typical Parameters:
    - period: 20 (most common), 10, 14, 55
    - Use shorter periods for more sensitive signals
    - Use longer periods for smoother, more reliable signals
    """

    @classmethod
    def is_multi_output(cls) -> bool:
        """Donchian Channels produces multiple outputs (Upper, Lower, and optionally Middle)."""
        return True

    @classmethod
    def get_output_names(cls) -> list[str]:
        """Return semantic output names for Donchian Channels."""
        return ["upper", "middle", "lower"]

    def __init__(self, period: int = 20, include_middle: bool = True):
        """
        Initialize Donchian Channels indicator.

        Args:
            period: Number of periods for channel calculation (default: 20)
            include_middle: Whether to include middle line calculation (default: True)
        """
        # Call parent constructor - Donchian Channels can be displayed as overlay
        super().__init__(
            name="DonchianChannels",
            display_as_overlay=True,
            period=period,
            include_middle=include_middle,
        )

    def _validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Validate indicator parameters."""
        period = params.get("period", 20)
        include_middle = params.get("include_middle", True)

        if not isinstance(period, int) or period < 1:
            raise ValueError("period must be a positive integer")

        if period < 2:
            raise ValueError("period must be at least 2")

        if period > 500:
            raise ValueError("period should not exceed 500 for practical purposes")

        return {"period": period, "include_middle": include_middle}

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Compute Donchian Channels.

        Args:
            data: DataFrame containing OHLC data

        Returns:
            DataFrame with Donchian Channels values

        Raises:
            DataError: If required columns are missing or insufficient data
        """
        # Get parameters from self.params
        period = self.params.get("period", 20)
        # M3b: include_middle ignored, always include middle in core outputs

        # Check required columns
        required_columns = ["high", "low", "close"]
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            raise DataError(
                message=f"Donchian Channels requires columns: {', '.join(missing_columns)}",
                error_code="DATA-MissingColumn",
                details={
                    "missing_columns": missing_columns,
                    "required_columns": required_columns,
                    "available_columns": list(data.columns),
                },
            )

        # Check for sufficient data
        if len(data) < period:
            raise DataError(
                message=f"Donchian Channels requires at least {period} data points",
                error_code="DATA-InsufficientData",
                details={
                    "required": period,
                    "provided": len(data),
                    "period": period,
                },
            )

        # Calculate upper channel (highest high)
        upper_channel = data["high"].rolling(window=period, min_periods=period).max()

        # Calculate lower channel (lowest low)
        lower_channel = data["low"].rolling(window=period, min_periods=period).min()

        # Calculate middle line
        middle_line = (upper_channel + lower_channel) / 2

        # M3b: Return semantic column names only (no parameter embedding)
        # Engine will handle prefixing with indicator_id
        result = pd.DataFrame(
            {
                "upper": upper_channel,
                "middle": middle_line,
                "lower": lower_channel,
            },
            index=data.index,
        )

        logger.debug(f"Computed Donchian Channels with period={period}")

        return result

    def get_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Generate trading signals based on Donchian Channels.

        Args:
            data: DataFrame with OHLCV data OR computed Donchian Channels.
                  If semantic columns (upper, lower) not present, will compute them.

        Returns:
            DataFrame with signal columns (semantic names)
        """
        result = pd.DataFrame(index=data.index)

        # Check if we need to compute channels first
        if "upper" not in data.columns or "lower" not in data.columns:
            computed = self.compute(data)
            # Need close price for signals, so merge with original
            work_data = data.copy()
            work_data["upper"] = computed["upper"]
            work_data["lower"] = computed["lower"]
            work_data["middle"] = computed["middle"]
        else:
            work_data = data

        # Calculate position within channel (0 = at lower, 1 = at upper)
        channel_range = work_data["upper"] - work_data["lower"]
        position = (work_data["close"] - work_data["lower"]) / channel_range.replace(
            0, float("nan")
        )

        # Breakout signals
        result["upper_breakout"] = work_data["close"] > work_data["upper"]
        result["lower_breakout"] = work_data["close"] < work_data["lower"]

        # Position-based signals
        result["overbought"] = position > 0.8
        result["oversold"] = position < 0.2

        # Trend signals based on channel position
        result["strong_uptrend"] = position.rolling(window=3).mean() > 0.7
        result["strong_downtrend"] = position.rolling(window=3).mean() < 0.3

        # Include position for analysis
        result["position"] = position

        return result

    def get_analysis(self, data: pd.DataFrame) -> dict[str, Any]:
        """
        Get comprehensive analysis of Donchian Channels.

        Args:
            data: DataFrame with OHLCV data OR computed Donchian Channels

        Returns:
            Dictionary with analysis results
        """
        # Check if we need to compute channels first
        if "upper" not in data.columns or "lower" not in data.columns:
            computed = self.compute(data)
            work_data = data.copy()
            work_data["upper"] = computed["upper"]
            work_data["lower"] = computed["lower"]
            work_data["middle"] = computed["middle"]
        else:
            work_data = data

        # Calculate derived values
        work_data = work_data.copy()
        work_data["width"] = work_data["upper"] - work_data["lower"]
        channel_range = work_data["width"].replace(0, float("nan"))
        work_data["position"] = (
            work_data["close"] - work_data["lower"]
        ) / channel_range

        # Get recent values (last 20 periods)
        recent_data = work_data.tail(20)
        latest = work_data.iloc[-1]

        # Current channel values
        current_upper = latest["upper"]
        current_lower = latest["lower"]
        current_width = latest["width"]
        current_position = latest["position"]
        current_price = latest["close"]

        # Channel width analysis
        avg_width = recent_data["width"].mean()
        width_range = recent_data["width"].max() - recent_data["width"].min()
        width_percentile = (
            ((current_width - recent_data["width"].min()) / width_range * 100)
            if width_range > 0
            else 50.0
        )

        # Breakout analysis
        days_since_upper_breakout = 0
        days_since_lower_breakout = 0

        for i in range(len(recent_data)):
            if (
                recent_data.iloc[-(i + 1)]["close"]
                > recent_data.iloc[-(i + 1)]["upper"]
            ):
                days_since_upper_breakout = i
                break

        for i in range(len(recent_data)):
            if (
                recent_data.iloc[-(i + 1)]["close"]
                < recent_data.iloc[-(i + 1)]["lower"]
            ):
                days_since_lower_breakout = i
                break

        # Determine market state
        if current_position > 0.8:
            market_state = "Near Upper Channel - Potential Resistance"
        elif current_position < 0.2:
            market_state = "Near Lower Channel - Potential Support"
        elif 0.4 <= current_position <= 0.6:
            market_state = "Middle of Channel - Neutral"
        elif current_position > 0.6:
            market_state = "Upper Half - Bullish Bias"
        else:
            market_state = "Lower Half - Bearish Bias"

        # Volatility state
        if width_percentile > 80:
            volatility_state = "High Volatility - Wide Channels"
        elif width_percentile < 20:
            volatility_state = "Low Volatility - Narrow Channels"
        else:
            volatility_state = "Normal Volatility"

        return {
            "current_values": {
                "upper_channel": round(current_upper, 4),
                "lower_channel": round(current_lower, 4),
                "middle_line": round((current_upper + current_lower) / 2, 4),
                "current_price": round(current_price, 4),
                "channel_width": round(current_width, 4),
                "position_in_channel": round(current_position, 4),
            },
            "market_state": market_state,
            "volatility_analysis": {
                "state": volatility_state,
                "current_width": round(current_width, 4),
                "average_width": round(avg_width, 4),
                "width_percentile": round(width_percentile, 1),
            },
            "breakout_analysis": {
                "days_since_upper_breakout": days_since_upper_breakout,
                "days_since_lower_breakout": days_since_lower_breakout,
                "potential_upper_breakout": current_position > 0.9,
                "potential_lower_breakout": current_position < 0.1,
            },
            "support_resistance": {
                "resistance_level": round(current_upper, 4),
                "support_level": round(current_lower, 4),
                "distance_to_resistance": round(current_upper - current_price, 4),
                "distance_to_support": round(current_price - current_lower, 4),
            },
            "signals": {
                "near_breakout": current_position > 0.85 or current_position < 0.15,
                "trending_up": current_position > 0.7,
                "trending_down": current_position < 0.3,
                "consolidating": 0.3 <= current_position <= 0.7,
            },
        }


# Create alias for easier access
DonchianChannels = DonchianChannelsIndicator
