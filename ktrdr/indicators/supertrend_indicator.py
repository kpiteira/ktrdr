"""
SuperTrend Indicator.

SuperTrend is a trend-following indicator that uses Average True Range (ATR) to calculate
dynamic support and resistance levels. It provides clear buy/sell signals and helps
identify trend direction and potential reversal points.

Author: KTRDR
"""

from typing import Any

import pandas as pd

from ktrdr import get_logger
from ktrdr.errors import DataError
from ktrdr.indicators.base_indicator import BaseIndicator

logger = get_logger(__name__)


class SuperTrendIndicator(BaseIndicator):
    """
    SuperTrend indicator implementation.

    SuperTrend calculation involves the following steps:

    1. Calculate True Range (TR) and Average True Range (ATR)
    2. Calculate Basic Bands:
       - Upper Band = (High + Low) / 2 + (multiplier * ATR)
       - Lower Band = (High + Low) / 2 - (multiplier * ATR)
    3. Calculate Final Bands with trend rules:
       - Final Upper Band considers previous values and current close
       - Final Lower Band considers previous values and current close
    4. Determine SuperTrend line and trend direction

    The indicator helps identify:
    - Trend direction (bullish/bearish)
    - Entry and exit signals
    - Dynamic support and resistance levels
    - Trend strength and continuation

    Key characteristics:
    - Green line (below price) indicates uptrend
    - Red line (above price) indicates downtrend
    - Line crossings generate buy/sell signals
    - Works well in trending markets

    Typical Parameters:
    - period: 10 (ATR period)
    - multiplier: 3.0 (ATR multiplier for band calculation)
    """

    @classmethod
    def is_multi_output(cls) -> bool:
        """SuperTrend produces multiple outputs (SuperTrend and ST_Direction)."""
        return True

    @classmethod
    def get_output_names(cls) -> list[str]:
        """Return semantic output names for SuperTrend."""
        return ["trend", "direction"]

    def __init__(self, period: int = 10, multiplier: float = 3.0):
        """
        Initialize SuperTrend indicator.

        Args:
            period: Period for ATR calculation (default: 10)
            multiplier: Multiplier for ATR to determine band width (default: 3.0)
        """
        # Call parent constructor - SuperTrend can be displayed as overlay
        super().__init__(
            name="SuperTrend",
            display_as_overlay=True,
            period=period,
            multiplier=multiplier,
        )

    def _validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Validate indicator parameters."""
        period = params.get("period", 10)
        multiplier = params.get("multiplier", 3.0)

        if not isinstance(period, int) or period < 1:
            raise ValueError("period must be a positive integer")

        if period < 2:
            raise ValueError("period must be at least 2")

        if period > 200:
            raise ValueError("period should not exceed 200 for practical purposes")

        if not isinstance(multiplier, (int, float)) or multiplier <= 0:
            raise ValueError("multiplier must be a positive number")

        if multiplier > 10:
            raise ValueError("multiplier should not exceed 10 for practical purposes")

        return {"period": period, "multiplier": multiplier}

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Compute SuperTrend indicator.

        Args:
            data: DataFrame containing OHLC data

        Returns:
            DataFrame with SuperTrend values

        Raises:
            DataError: If required columns are missing or insufficient data
        """
        # Get parameters from self.params
        period = self.params.get("period", 10)
        multiplier = self.params.get("multiplier", 3.0)

        # Check required columns
        required_columns = ["high", "low", "close"]
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            raise DataError(
                message=f"SuperTrend requires columns: {', '.join(missing_columns)}",
                error_code="DATA-MissingColumn",
                details={
                    "missing_columns": missing_columns,
                    "required_columns": required_columns,
                    "available_columns": list(data.columns),
                },
            )

        # Check for sufficient data
        min_required = period + 1
        if len(data) < min_required:
            raise DataError(
                message=f"SuperTrend requires at least {min_required} data points",
                error_code="DATA-InsufficientData",
                details={
                    "required": min_required,
                    "provided": len(data),
                    "period": period,
                },
            )

        # Extract OHLC data
        high = data["high"]
        low = data["low"]
        close = data["close"]
        prev_close = close.shift(1)

        # Calculate True Range (TR)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # Calculate ATR using simple moving average
        atr = tr.rolling(window=period, min_periods=period).mean()

        # Calculate median price (HL2)
        median_price = (high + low) / 2

        # Calculate basic bands
        upper_band = median_price + (multiplier * atr)
        lower_band = median_price - (multiplier * atr)

        # Initialize final bands
        final_upper_band = pd.Series(index=data.index, dtype=float)
        final_lower_band = pd.Series(index=data.index, dtype=float)

        # Calculate final bands with trend rules
        for i in range(len(data)):
            if i == 0:
                final_upper_band.iloc[i] = upper_band.iloc[i]
                final_lower_band.iloc[i] = lower_band.iloc[i]
            else:
                # Final Upper Band
                if (
                    upper_band.iloc[i] < final_upper_band.iloc[i - 1]
                    or close.iloc[i - 1] > final_upper_band.iloc[i - 1]
                ):
                    final_upper_band.iloc[i] = upper_band.iloc[i]
                else:
                    final_upper_band.iloc[i] = final_upper_band.iloc[i - 1]

                # Final Lower Band
                if (
                    lower_band.iloc[i] > final_lower_band.iloc[i - 1]
                    or close.iloc[i - 1] < final_lower_band.iloc[i - 1]
                ):
                    final_lower_band.iloc[i] = lower_band.iloc[i]
                else:
                    final_lower_band.iloc[i] = final_lower_band.iloc[i - 1]

        # Initialize SuperTrend and direction
        supertrend = pd.Series(index=data.index, dtype=float)
        trend_direction = pd.Series(
            index=data.index, dtype=int
        )  # 1 for up, -1 for down

        # Calculate SuperTrend
        for i in range(len(data)):
            if i == 0:
                if close.iloc[i] <= final_lower_band.iloc[i]:
                    supertrend.iloc[i] = final_upper_band.iloc[i]
                    trend_direction.iloc[i] = -1
                else:
                    supertrend.iloc[i] = final_lower_band.iloc[i]
                    trend_direction.iloc[i] = 1
            else:
                if trend_direction.iloc[i - 1] == 1:
                    if close.iloc[i] <= final_lower_band.iloc[i]:
                        supertrend.iloc[i] = final_upper_band.iloc[i]
                        trend_direction.iloc[i] = -1
                    else:
                        supertrend.iloc[i] = final_lower_band.iloc[i]
                        trend_direction.iloc[i] = 1
                else:  # trend_direction.iloc[i-1] == -1
                    if close.iloc[i] >= final_upper_band.iloc[i]:
                        supertrend.iloc[i] = final_lower_band.iloc[i]
                        trend_direction.iloc[i] = 1
                    else:
                        supertrend.iloc[i] = final_upper_band.iloc[i]
                        trend_direction.iloc[i] = -1

        # M3b: Return semantic column names only (engine handles prefixing)
        result = pd.DataFrame(
            {
                "trend": supertrend,
                "direction": trend_direction,
            },
            index=data.index,
        )

        logger.debug(
            f"Computed SuperTrend with period={period}, multiplier={multiplier}"
        )

        return result

    def get_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Generate trading signals based on SuperTrend.

        Args:
            data: DataFrame with calculated SuperTrend

        Returns:
            DataFrame with signal columns added
        """
        result = pd.DataFrame(
            index=data.index
        )  # CRITICAL FIX: Only return computed columns

        period = self.params.get("period", 10)
        multiplier = self.params.get("multiplier", 3.0)
        suffix = f"{period}_{multiplier}"

        st_col = f"SuperTrend_{suffix}"
        direction_col = f"ST_Direction_{suffix}"
        strength_col = f"ST_Strength_{suffix}"
        distance_col = f"ST_Distance_{suffix}"

        if st_col not in data.columns:
            result = self.compute(data)

        st_values = result[st_col]
        direction = result[direction_col]
        strength = result[strength_col]
        distance = result[distance_col]
        close = result["close"]

        # Basic trend signals
        bullish_trend = direction == 1
        bearish_trend = direction == -1
        result[f"ST_Bullish_{suffix}"] = bullish_trend
        result[f"ST_Bearish_{suffix}"] = bearish_trend

        # Trend change signals
        trend_change_up = (direction == 1) & (direction.shift(1) == -1)
        trend_change_down = (direction == -1) & (direction.shift(1) == 1)
        result[f"ST_Buy_Signal_{suffix}"] = trend_change_up
        result[f"ST_Sell_Signal_{suffix}"] = trend_change_down

        # Trend strength signals
        strong_uptrend = bullish_trend & (strength >= 5)
        strong_downtrend = bearish_trend & (strength >= 5)
        result[f"ST_Strong_Uptrend_{suffix}"] = strong_uptrend
        result[f"ST_Strong_Downtrend_{suffix}"] = strong_downtrend

        # Early trend signals (shorter strength requirement)
        early_uptrend = bullish_trend & (strength >= 2)
        early_downtrend = bearish_trend & (strength >= 2)
        result[f"ST_Early_Uptrend_{suffix}"] = early_uptrend
        result[f"ST_Early_Downtrend_{suffix}"] = early_downtrend

        # Distance-based signals
        far_above_st = distance > 5  # Price > 5% above SuperTrend
        far_below_st = distance < -5  # Price > 5% below SuperTrend
        result[f"ST_Far_Above_{suffix}"] = far_above_st
        result[f"ST_Far_Below_{suffix}"] = far_below_st

        # Pullback signals (price near SuperTrend in trending market)
        bullish_pullback = bullish_trend & (distance < 2) & (distance > -1)
        bearish_pullback = bearish_trend & (distance > -2) & (distance < 1)
        result[f"ST_Bullish_Pullback_{suffix}"] = bullish_pullback
        result[f"ST_Bearish_Pullback_{suffix}"] = bearish_pullback

        # Momentum signals based on SuperTrend slope
        if f"ST_Slope_{suffix}" in result.columns:
            st_slope = result[f"ST_Slope_{suffix}"]
            accelerating_up = bullish_trend & (st_slope > 0.5)
            accelerating_down = bearish_trend & (st_slope < -0.5)
            result[f"ST_Accelerating_Up_{suffix}"] = accelerating_up
            result[f"ST_Accelerating_Down_{suffix}"] = accelerating_down

        # Consolidation signals (weak trend)
        weak_trend = strength < 3
        result[f"ST_Weak_Trend_{suffix}"] = weak_trend

        # Support/Resistance signals
        price_at_support = bullish_trend & (
            close <= st_values * 1.005
        )  # Within 0.5% of SuperTrend
        price_at_resistance = bearish_trend & (
            close >= st_values * 0.995
        )  # Within 0.5% of SuperTrend
        result[f"ST_At_Support_{suffix}"] = price_at_support
        result[f"ST_At_Resistance_{suffix}"] = price_at_resistance

        return result

    def get_analysis(self, data: pd.DataFrame) -> dict[str, Any]:
        """
        Get comprehensive analysis of SuperTrend.

        Args:
            data: DataFrame with calculated SuperTrend

        Returns:
            Dictionary with analysis results
        """
        period = self.params.get("period", 10)
        multiplier = self.params.get("multiplier", 3.0)
        suffix = f"{period}_{multiplier}"

        st_col = f"SuperTrend_{suffix}"
        direction_col = f"ST_Direction_{suffix}"
        strength_col = f"ST_Strength_{suffix}"
        distance_col = f"ST_Distance_{suffix}"

        if st_col not in data.columns:
            data = self.compute(data)

        # Get recent values (last 30 periods for context)
        recent_data = data.tail(30)
        latest = data.iloc[-1]

        # Current values
        current_st = latest[st_col]
        current_direction = latest[direction_col]
        current_strength = latest[strength_col]
        current_distance = latest[distance_col]
        current_price = latest["close"]

        # Trend analysis
        trend_state = "Uptrend" if current_direction == 1 else "Downtrend"

        # Strength assessment
        if current_strength >= 10:
            strength_level = "Very Strong"
        elif current_strength >= 5:
            strength_level = "Strong"
        elif current_strength >= 2:
            strength_level = "Moderate"
        else:
            strength_level = "Weak"

        # Distance assessment
        if abs(current_distance) > 10:
            distance_level = "Very Far"
        elif abs(current_distance) > 5:
            distance_level = "Far"
        elif abs(current_distance) > 2:
            distance_level = "Moderate"
        else:
            distance_level = "Close"

        # Position assessment
        if current_direction == 1:
            if current_distance > 5:
                position_state = "Strong Bull - Price well above SuperTrend"
            elif current_distance > 0:
                position_state = "Bull - Price above SuperTrend"
            else:
                position_state = "Bull - Price testing SuperTrend support"
        else:
            if current_distance < -5:
                position_state = "Strong Bear - Price well below SuperTrend"
            elif current_distance < 0:
                position_state = "Bear - Price below SuperTrend"
            else:
                position_state = "Bear - Price testing SuperTrend resistance"

        # Historical analysis
        directions = recent_data[direction_col]
        uptrend_days = (directions == 1).sum()
        downtrend_days = (directions == -1).sum()

        # Trend changes in recent period
        trend_changes = (directions != directions.shift(1)).sum()

        # Average distance
        distances = recent_data[distance_col].dropna()
        avg_distance = distances.mean() if len(distances) > 0 else 0

        # SuperTrend slope analysis
        st_slope_col = f"ST_Slope_{suffix}"
        if st_slope_col in recent_data.columns:
            recent_slope = (
                recent_data[st_slope_col].iloc[-1]
                if not pd.isna(recent_data[st_slope_col].iloc[-1])
                else 0
            )
            slope_direction = (
                "Rising"
                if recent_slope > 0.2
                else "Falling" if recent_slope < -0.2 else "Stable"
            )
        else:
            recent_slope = 0
            slope_direction = "Unknown"

        # Signal assessment
        signals_active = {
            "uptrend": current_direction == 1,
            "downtrend": current_direction == -1,
            "strong_trend": current_strength >= 5,
            "trend_developing": current_strength >= 2 and current_strength < 5,
            "price_extended": abs(current_distance) > 5,
            "pullback_opportunity": abs(current_distance) < 2,
            "support_test": current_direction == 1 and current_distance < 1,
            "resistance_test": current_direction == -1 and current_distance > -1,
        }

        # Risk assessment
        if current_direction == 1:
            risk_level = (
                "Low"
                if current_distance > 2
                else "Medium" if current_distance > -1 else "High"
            )
        else:
            risk_level = (
                "Low"
                if current_distance < -2
                else "Medium" if current_distance < 1 else "High"
            )

        return {
            "current_values": {
                "supertrend": round(current_st, 4),
                "current_price": round(current_price, 4),
                "direction": int(current_direction),
                "trend_strength": int(current_strength),
                "distance_percent": round(current_distance, 2),
            },
            "trend_analysis": {
                "state": trend_state,
                "strength": strength_level,
                "duration": int(current_strength),
                "slope_direction": slope_direction,
                "slope_value": round(recent_slope, 2),
            },
            "position_analysis": {
                "state": position_state,
                "distance_level": distance_level,
                "distance_value": round(current_distance, 2),
                "support_resistance": round(current_st, 4),
            },
            "historical_context": {
                "uptrend_days": int(uptrend_days),
                "downtrend_days": int(downtrend_days),
                "trend_changes": int(trend_changes),
                "average_distance": round(avg_distance, 2),
                "trend_consistency": round(
                    (max(uptrend_days, downtrend_days) / len(directions)) * 100, 1
                ),
            },
            "risk_assessment": {
                "level": risk_level,
                "stop_loss_level": round(current_st, 4),
                "trend_reversal_risk": (
                    "High"
                    if current_strength < 3
                    else "Medium" if current_strength < 7 else "Low"
                ),
            },
            "signals": signals_active,
        }


# Create alias for easier access
SuperTrend = SuperTrendIndicator
