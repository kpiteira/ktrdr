"""
Keltner Channels Indicator.

Keltner Channels are volatility-based bands that consist of an exponential moving average
in the center with upper and lower bands calculated using the Average True Range (ATR).
They help identify volatility, trend direction, and potential reversal points.

Author: KTRDR
"""

from typing import Any, Optional

import pandas as pd

from ktrdr import get_logger
from ktrdr.errors import DataError
from ktrdr.indicators.base_indicator import BaseIndicator

logger = get_logger(__name__)


class KeltnerChannelsIndicator(BaseIndicator):
    """
    Keltner Channels indicator implementation.

    Keltner Channels consist of three lines:
    - Middle Line: Exponential Moving Average (EMA) of the close price
    - Upper Channel: EMA + (ATR multiplier * ATR)
    - Lower Channel: EMA - (ATR multiplier * ATR)

    The channels help identify:
    - Volatility expansion/contraction
    - Trend direction and strength
    - Potential support and resistance levels
    - Overbought/oversold conditions
    - Breakout opportunities

    Formula:
    Middle Line = EMA(Close, period)
    Upper Channel = EMA + (multiplier * ATR(atr_period))
    Lower Channel = EMA - (multiplier * ATR(atr_period))

    Typical Parameters:
    - period: 20 (EMA period)
    - atr_period: 10 (ATR calculation period)
    - multiplier: 2.0 (ATR multiplier for band width)
    """

    @classmethod
    def is_multi_output(cls) -> bool:
        """Keltner Channels produces multiple outputs (Middle, Upper, Lower)."""
        return True

    @classmethod
    def get_output_names(cls) -> list[str]:
        """Return semantic output names for Keltner Channels."""
        return ["upper", "middle", "lower"]

    @classmethod
    def get_primary_output_suffix(cls) -> str:
        """Primary output is the Middle line (EMA)."""
        return "Middle"

    def get_column_name(self, suffix: Optional[str] = None) -> str:
        """
        Generate column name matching what compute() actually produces.

        Keltner Channels format:
        - Middle: "KC_Middle_{period}"
        - Upper: "KC_Upper_{period}_{atr_period}_{multiplier}"
        - Lower: "KC_Lower_{period}_{atr_period}_{multiplier}"

        Args:
            suffix: Optional suffix ("Middle", "Upper", "Lower", or None for Middle)

        Returns:
            Column name matching compute() output format
        """
        period = self.params.get("period", 20)
        atr_period = self.params.get("atr_period", 10)
        multiplier = self.params.get("multiplier", 2.0)

        if suffix == "Upper":
            return f"KC_Upper_{period}_{atr_period}_{multiplier}"
        elif suffix == "Lower":
            return f"KC_Lower_{period}_{atr_period}_{multiplier}"
        else:
            # Default to Middle (primary)
            return f"KC_Middle_{period}"

    def __init__(self, period: int = 20, atr_period: int = 10, multiplier: float = 2.0):
        """
        Initialize Keltner Channels indicator.

        Args:
            period: Period for the EMA middle line (default: 20)
            atr_period: Period for ATR calculation (default: 10)
            multiplier: Multiplier for ATR to determine band width (default: 2.0)
        """
        # Call parent constructor - Keltner Channels can be displayed as overlay
        super().__init__(
            name="KeltnerChannels",
            display_as_overlay=True,
            period=period,
            atr_period=atr_period,
            multiplier=multiplier,
        )

    def _validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Validate indicator parameters."""
        period = params.get("period", 20)
        atr_period = params.get("atr_period", 10)
        multiplier = params.get("multiplier", 2.0)

        if not isinstance(period, int) or period < 1:
            raise ValueError("period must be a positive integer")

        if period < 2:
            raise ValueError("period must be at least 2")

        if period > 500:
            raise ValueError("period should not exceed 500 for practical purposes")

        if not isinstance(atr_period, int) or atr_period < 1:
            raise ValueError("atr_period must be a positive integer")

        if atr_period < 2:
            raise ValueError("atr_period must be at least 2")

        if atr_period > 200:
            raise ValueError("atr_period should not exceed 200 for practical purposes")

        if not isinstance(multiplier, (int, float)) or multiplier <= 0:
            raise ValueError("multiplier must be a positive number")

        if multiplier > 10:
            raise ValueError("multiplier should not exceed 10 for practical purposes")

        return {"period": period, "atr_period": atr_period, "multiplier": multiplier}

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Compute Keltner Channels.

        Args:
            data: DataFrame containing OHLC data

        Returns:
            DataFrame with Keltner Channels values

        Raises:
            DataError: If required columns are missing or insufficient data
        """
        # Get parameters from self.params
        period = self.params.get("period", 20)
        atr_period = self.params.get("atr_period", 10)
        multiplier = self.params.get("multiplier", 2.0)

        # Check required columns
        required_columns = ["high", "low", "close"]
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            raise DataError(
                message=f"Keltner Channels requires columns: {', '.join(missing_columns)}",
                error_code="DATA-MissingColumn",
                details={
                    "missing_columns": missing_columns,
                    "required_columns": required_columns,
                    "available_columns": list(data.columns),
                },
            )

        # Check for sufficient data
        min_required = max(period, atr_period) + 1  # +1 for ATR calculation
        if len(data) < min_required:
            raise DataError(
                message=f"Keltner Channels requires at least {min_required} data points",
                error_code="DATA-InsufficientData",
                details={
                    "required": min_required,
                    "provided": len(data),
                    "period": period,
                    "atr_period": atr_period,
                },
            )

        # Calculate EMA for middle line
        ema = data["close"].ewm(span=period, adjust=False).mean()

        # Calculate ATR (Average True Range)
        high = data["high"]
        low = data["low"]
        close = data["close"]
        prev_close = close.shift(1)

        # True Range components
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()

        # True Range is the maximum of the three
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # For the first data point, True Range is just High - Low
        true_range.iloc[0] = tr1.iloc[0]

        # Calculate ATR as simple moving average of True Range
        atr = true_range.rolling(window=atr_period, min_periods=atr_period).mean()

        # Calculate channel bands
        band_width = multiplier * atr
        upper_channel = ema + band_width
        lower_channel = ema - band_width

        # M3b: Return semantic column names only (no parameter embedding)
        # Engine will handle prefixing with indicator_id
        result = pd.DataFrame(
            {
                "upper": upper_channel,
                "middle": ema,
                "lower": lower_channel,
            },
            index=data.index,
        )

        logger.debug(
            f"Computed Keltner Channels with period={period}, atr_period={atr_period}, multiplier={multiplier}"
        )

        return result

    def get_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Generate trading signals based on Keltner Channels.

        Args:
            data: DataFrame with calculated Keltner Channels

        Returns:
            DataFrame with signal columns added
        """
        result = pd.DataFrame(
            index=data.index
        )  # CRITICAL FIX: Only return computed columns

        period = self.params.get("period", 20)
        atr_period = self.params.get("atr_period", 10)
        multiplier = self.params.get("multiplier", 2.0)

        suffix = f"{period}_{atr_period}_{multiplier}"
        middle_col = f"KC_Middle_{period}"
        upper_col = f"KC_Upper_{suffix}"
        lower_col = f"KC_Lower_{suffix}"
        position_col = f"KC_Position_{suffix}"
        squeeze_col = f"KC_Squeeze_{suffix}"

        if upper_col not in data.columns or lower_col not in data.columns:
            result = self.compute(data)

        # Breakout signals
        # Upper breakout: Close above upper channel
        upper_breakout = result["close"] > result[upper_col]
        result[f"KC_Upper_Breakout_{suffix}"] = upper_breakout

        # Lower breakout: Close below lower channel
        lower_breakout = result["close"] < result[lower_col]
        result[f"KC_Lower_Breakout_{suffix}"] = lower_breakout

        # Trend signals based on price relative to middle line
        above_middle = result["close"] > result[middle_col]
        below_middle = result["close"] < result[middle_col]
        result[f"KC_Above_Middle_{suffix}"] = above_middle
        result[f"KC_Below_Middle_{suffix}"] = below_middle

        # Channel position signals
        # Overbought: Position > 0.8
        overbought = result[position_col] > 0.8
        result[f"KC_Overbought_{suffix}"] = overbought

        # Oversold: Position < 0.2
        oversold = result[position_col] < 0.2
        result[f"KC_Oversold_{suffix}"] = oversold

        # Squeeze signals (low volatility)
        # Squeeze: Small price range relative to channel width
        squeeze = result[squeeze_col] < 0.25
        result[f"KC_Squeeze_Signal_{suffix}"] = squeeze

        # Expansion signals (high volatility)
        expansion = result[squeeze_col] > 0.75
        result[f"KC_Expansion_{suffix}"] = expansion

        # Trend strength signals
        # Strong uptrend: Price consistently in upper half of channel
        strong_uptrend = result[position_col].rolling(window=3).mean() > 0.7
        result[f"KC_Strong_Uptrend_{suffix}"] = strong_uptrend

        # Strong downtrend: Price consistently in lower half of channel
        strong_downtrend = result[position_col].rolling(window=3).mean() < 0.3
        result[f"KC_Strong_Downtrend_{suffix}"] = strong_downtrend

        return result

    def get_analysis(self, data: pd.DataFrame) -> dict[str, Any]:
        """
        Get comprehensive analysis of Keltner Channels.

        Args:
            data: DataFrame with calculated Keltner Channels

        Returns:
            Dictionary with analysis results
        """
        period = self.params.get("period", 20)
        atr_period = self.params.get("atr_period", 10)
        multiplier = self.params.get("multiplier", 2.0)

        suffix = f"{period}_{atr_period}_{multiplier}"
        middle_col = f"KC_Middle_{period}"
        upper_col = f"KC_Upper_{suffix}"
        lower_col = f"KC_Lower_{suffix}"
        width_col = f"KC_Width_{suffix}"
        position_col = f"KC_Position_{suffix}"
        squeeze_col = f"KC_Squeeze_{suffix}"
        atr_col = f"KC_ATR_{atr_period}"

        if upper_col not in data.columns:
            data = self.compute(data)

        # Get recent values (last 20 periods)
        recent_data = data.tail(20)
        latest = data.iloc[-1]

        # Current channel values
        current_middle = latest[middle_col]
        current_upper = latest[upper_col]
        current_lower = latest[lower_col]
        current_width = latest[width_col]
        current_position = latest[position_col]
        current_squeeze = latest[squeeze_col]
        current_atr = latest[atr_col]
        current_price = latest["close"]

        # Volatility analysis
        avg_width = recent_data[width_col].mean()
        avg_atr = recent_data[atr_col].mean()
        width_percentile = (
            (
                (current_width - recent_data[width_col].min())
                / (recent_data[width_col].max() - recent_data[width_col].min())
                * 100
            )
            if recent_data[width_col].max() > recent_data[width_col].min()
            else 50
        )

        # Trend analysis
        ema_slope = (
            (current_middle - data[middle_col].iloc[-5]) / 4 if len(data) >= 5 else 0
        )
        trend_direction = (
            "Uptrend" if ema_slope > 0 else "Downtrend" if ema_slope < 0 else "Sideways"
        )

        # Breakout analysis
        days_since_upper_breakout = 0
        days_since_lower_breakout = 0

        for i in range(len(recent_data)):
            if (
                recent_data.iloc[-(i + 1)]["close"]
                > recent_data.iloc[-(i + 1)][upper_col]
            ):
                days_since_upper_breakout = i
                break

        for i in range(len(recent_data)):
            if (
                recent_data.iloc[-(i + 1)]["close"]
                < recent_data.iloc[-(i + 1)][lower_col]
            ):
                days_since_lower_breakout = i
                break

        # Market state analysis
        if current_position > 0.8:
            market_state = "Near Upper Channel - Potential Resistance"
        elif current_position < 0.2:
            market_state = "Near Lower Channel - Potential Support"
        elif current_price > current_middle:
            market_state = "Above Middle - Bullish Bias"
        elif current_price < current_middle:
            market_state = "Below Middle - Bearish Bias"
        else:
            market_state = "At Middle Line - Neutral"

        # Volatility state
        if current_squeeze < 0.25:
            volatility_state = "Low Volatility - Potential Squeeze"
        elif current_squeeze > 0.75:
            volatility_state = "High Volatility - Active Market"
        else:
            volatility_state = "Normal Volatility"

        # Channel efficiency (how well price respects the channels)
        breakout_rate = (
            (
                (recent_data["close"] > recent_data[upper_col]).sum()
                + (recent_data["close"] < recent_data[lower_col]).sum()
            )
            / len(recent_data)
            * 100
        )

        return {
            "current_values": {
                "middle_line": round(current_middle, 4),
                "upper_channel": round(current_upper, 4),
                "lower_channel": round(current_lower, 4),
                "current_price": round(current_price, 4),
                "channel_width": round(current_width, 4),
                "position_in_channel": round(current_position, 4),
                "atr": round(current_atr, 4),
                "squeeze_ratio": round(current_squeeze, 4),
            },
            "market_state": market_state,
            "trend_analysis": {
                "direction": trend_direction,
                "ema_slope": round(ema_slope, 4),
                "above_middle": current_price > current_middle,
                "strength": "Strong" if abs(ema_slope) > avg_atr * 0.1 else "Weak",
            },
            "volatility_analysis": {
                "state": volatility_state,
                "current_width": round(current_width, 4),
                "average_width": round(avg_width, 4),
                "width_percentile": round(width_percentile, 1),
                "current_atr": round(current_atr, 4),
                "average_atr": round(avg_atr, 4),
            },
            "breakout_analysis": {
                "days_since_upper_breakout": days_since_upper_breakout,
                "days_since_lower_breakout": days_since_lower_breakout,
                "breakout_rate": round(breakout_rate, 1),
                "potential_upper_breakout": current_position > 0.9,
                "potential_lower_breakout": current_position < 0.1,
            },
            "support_resistance": {
                "resistance_level": round(current_upper, 4),
                "support_level": round(current_lower, 4),
                "middle_support_resistance": round(current_middle, 4),
                "distance_to_resistance": round(current_upper - current_price, 4),
                "distance_to_support": round(current_price - current_lower, 4),
            },
            "signals": {
                "squeeze": current_squeeze < 0.25,
                "expansion": current_squeeze > 0.75,
                "bullish": current_price > current_middle and current_position > 0.5,
                "bearish": current_price < current_middle and current_position < 0.5,
                "overbought": current_position > 0.8,
                "oversold": current_position < 0.2,
                "breakout_imminent": current_position > 0.85 or current_position < 0.15,
            },
        }


# Create alias for easier access
KeltnerChannels = KeltnerChannelsIndicator
