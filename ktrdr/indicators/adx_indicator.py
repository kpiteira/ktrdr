"""
Average Directional Index (ADX) Indicator.

The Average Directional Index is a trend strength indicator that measures the strength
of a trend without regard to its direction. It consists of three lines:
- ADX: Trend strength (0-100 scale)
- +DI: Positive directional indicator (upward trend strength)
- -DI: Negative directional indicator (downward trend strength)

Author: KTRDR
"""

from typing import Any, Optional

import pandas as pd

from ktrdr import get_logger
from ktrdr.errors import DataError
from ktrdr.indicators.base_indicator import BaseIndicator

logger = get_logger(__name__)


class ADXIndicator(BaseIndicator):
    """
    Average Directional Index (ADX) indicator implementation.

    The ADX calculation involves several steps:

    1. Calculate True Range (TR)
    2. Calculate Directional Movement (DM+ and DM-)
    3. Smooth TR, DM+, and DM- using Wilder's smoothing
    4. Calculate Directional Indicators (DI+ and DI-)
    5. Calculate Directional Index (DX)
    6. Smooth DX to get ADX

    The indicator helps identify:
    - Trend strength (regardless of direction)
    - Whether a market is trending or ranging
    - Potential trend reversals
    - Entry and exit points when combined with directional indicators

    Key characteristics:
    - ADX values above 25 indicate strong trend
    - ADX values below 20 indicate weak trend or ranging market
    - ADX values above 50 indicate very strong trend
    - +DI above -DI suggests uptrend
    - -DI above +DI suggests downtrend

    Typical Parameters:
    - period: 14 (most common), 21, 28
    """

    @classmethod
    def is_multi_output(cls) -> bool:
        """ADX produces multiple outputs (ADX, DI_Plus, DI_Minus, DX, TR, ADX_Slope)."""
        return True

    @classmethod
    def get_output_names(cls) -> list[str]:
        """Return semantic output names for ADX."""
        return ["adx", "plus_di", "minus_di"]

    @classmethod
    def get_primary_output_suffix(cls) -> None:
        """Primary output is ADX with no suffix."""
        return None

    def get_column_name(self, suffix: Optional[str] = None) -> str:
        """
        Generate column name matching what compute() actually produces.

        ADX format:
        - ADX: "ADX_{period}"
        - DI_Plus: "DI_Plus_{period}"
        - DI_Minus: "DI_Minus_{period}"
        - DX: "DX_{period}"
        - TR: "TR_{period}"
        - ADX_Slope: "ADX_Slope_{period}"

        Args:
            suffix: Optional suffix (None, "DI_Plus", "DI_Minus", "DX", "TR", "ADX_Slope")

        Returns:
            Column name matching compute() output format
        """
        period = self.params.get("period", 14)

        if suffix == "DI_Plus":
            return f"DI_Plus_{period}"
        elif suffix == "DI_Minus":
            return f"DI_Minus_{period}"
        elif suffix == "DX":
            return f"DX_{period}"
        elif suffix == "TR":
            return f"TR_{period}"
        elif suffix == "ADX_Slope":
            return f"ADX_Slope_{period}"
        else:
            # Default to ADX (primary)
            return f"ADX_{period}"

    def __init__(self, period: int = 14):
        """
        Initialize ADX indicator.

        Args:
            period: Period for ADX calculation (default: 14)
        """
        # Call parent constructor - ADX is typically displayed in separate panel
        super().__init__(name="ADX", display_as_overlay=False, period=period)

    def _validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Validate indicator parameters."""
        period = params.get("period", 14)

        if not isinstance(period, int) or period < 1:
            raise ValueError("period must be a positive integer")

        if period < 2:
            raise ValueError("period must be at least 2")

        if period > 200:
            raise ValueError("period should not exceed 200 for practical purposes")

        return {"period": period}

    def _wilder_smoothing(self, series: pd.Series, period: int) -> pd.Series:
        """
        Apply Wilder's smoothing method.

        Wilder's smoothing is similar to EMA but uses a different alpha calculation:
        alpha = 1 / period
        """
        alpha = 1.0 / period
        return series.ewm(alpha=alpha, adjust=False).mean()

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Compute Average Directional Index (ADX).

        Args:
            data: DataFrame containing OHLC data

        Returns:
            DataFrame with ADX values

        Raises:
            DataError: If required columns are missing or insufficient data
        """
        # Get parameters from self.params
        period = self.params.get("period", 14)

        # Check required columns
        required_columns = ["high", "low", "close"]
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            raise DataError(
                message=f"ADX requires columns: {', '.join(missing_columns)}",
                error_code="DATA-MissingColumn",
                details={
                    "missing_columns": missing_columns,
                    "required_columns": required_columns,
                    "available_columns": list(data.columns),
                },
            )

        # Check for sufficient data (need extra periods for smoothing)
        min_required = period * 2 + 1
        if len(data) < min_required:
            raise DataError(
                message=f"ADX requires at least {min_required} data points for accurate calculation",
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

        # Calculate Directional Movement
        high_diff = high - high.shift(1)
        low_diff = low.shift(1) - low

        # Positive Directional Movement (+DM)
        dm_plus = pd.Series(index=data.index, dtype=float)
        dm_plus[(high_diff > low_diff) & (high_diff > 0)] = high_diff
        dm_plus.fillna(0, inplace=True)

        # Negative Directional Movement (-DM)
        dm_minus = pd.Series(index=data.index, dtype=float)
        dm_minus[(low_diff > high_diff) & (low_diff > 0)] = low_diff
        dm_minus.fillna(0, inplace=True)

        # Apply Wilder's smoothing to TR, +DM, and -DM
        tr_smooth = self._wilder_smoothing(tr, period)
        dm_plus_smooth = self._wilder_smoothing(dm_plus, period)
        dm_minus_smooth = self._wilder_smoothing(dm_minus, period)

        # Calculate Directional Indicators
        # Avoid division by zero
        di_plus = pd.Series(index=data.index, dtype=float)
        di_minus = pd.Series(index=data.index, dtype=float)

        valid_tr = tr_smooth != 0
        di_plus[valid_tr] = (dm_plus_smooth[valid_tr] / tr_smooth[valid_tr]) * 100
        di_minus[valid_tr] = (dm_minus_smooth[valid_tr] / tr_smooth[valid_tr]) * 100

        di_plus.fillna(0, inplace=True)
        di_minus.fillna(0, inplace=True)

        # Calculate Directional Index (DX)
        di_sum = di_plus + di_minus
        di_diff = (di_plus - di_minus).abs()

        dx = pd.Series(index=data.index, dtype=float)
        valid_sum = di_sum != 0
        dx[valid_sum] = (di_diff[valid_sum] / di_sum[valid_sum]) * 100
        dx.fillna(0, inplace=True)

        # Calculate ADX (smoothed DX)
        adx = self._wilder_smoothing(dx, period)

        # Create result DataFrame
        result = pd.DataFrame(
            index=data.index
        )  # CRITICAL FIX: Only return computed columns
        result[f"ADX_{period}"] = adx
        result[f"DI_Plus_{period}"] = di_plus
        result[f"DI_Minus_{period}"] = di_minus
        result[f"DX_{period}"] = dx
        result[f"TR_{period}"] = tr

        # Calculate additional analysis metrics
        # ADX trend (rising/falling ADX)
        adx_slope = adx - adx.shift(3)  # 3-period slope
        result[f"ADX_Slope_{period}"] = adx_slope

        # Directional spread (difference between +DI and -DI)
        di_spread = di_plus - di_minus
        result[f"DI_Spread_{period}"] = di_spread

        # ADX momentum (rate of change)
        adx_momentum = adx.pct_change(periods=5) * 100
        result[f"ADX_Momentum_{period}"] = adx_momentum

        logger.debug(f"Computed ADX with period={period}")

        return result

    def get_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Generate trading signals based on ADX.

        Args:
            data: DataFrame with calculated ADX

        Returns:
            DataFrame with signal columns added
        """
        result = pd.DataFrame(
            index=data.index
        )  # CRITICAL FIX: Only return computed columns

        period = self.params.get("period", 14)
        adx_col = f"ADX_{period}"
        di_plus_col = f"DI_Plus_{period}"
        di_minus_col = f"DI_Minus_{period}"
        slope_col = f"ADX_Slope_{period}"
        spread_col = f"DI_Spread_{period}"

        if adx_col not in data.columns:
            result = self.compute(data)

        adx_values = result[adx_col]
        di_plus = result[di_plus_col]
        di_minus = result[di_minus_col]
        adx_slope = result[slope_col]
        di_spread = result[spread_col]

        # Trend strength signals
        strong_trend = adx_values > 25
        very_strong_trend = adx_values > 50
        weak_trend = adx_values < 20
        result[f"ADX_Strong_Trend_{period}"] = strong_trend
        result[f"ADX_Very_Strong_Trend_{period}"] = very_strong_trend
        result[f"ADX_Weak_Trend_{period}"] = weak_trend

        # ADX direction signals
        adx_rising = adx_slope > 0
        adx_falling = adx_slope < 0
        result[f"ADX_Rising_{period}"] = adx_rising
        result[f"ADX_Falling_{period}"] = adx_falling

        # Directional signals
        bullish_direction = di_plus > di_minus
        bearish_direction = di_minus > di_plus
        result[f"ADX_Bullish_Direction_{period}"] = bullish_direction
        result[f"ADX_Bearish_Direction_{period}"] = bearish_direction

        # Directional crossover signals
        di_bullish_cross = (di_plus > di_minus) & (
            di_plus.shift(1) <= di_minus.shift(1)
        )
        di_bearish_cross = (di_minus > di_plus) & (
            di_minus.shift(1) <= di_plus.shift(1)
        )
        result[f"ADX_DI_Bullish_Cross_{period}"] = di_bullish_cross
        result[f"ADX_DI_Bearish_Cross_{period}"] = di_bearish_cross

        # Combined trend and direction signals
        strong_uptrend = strong_trend & bullish_direction
        strong_downtrend = strong_trend & bearish_direction
        result[f"ADX_Strong_Uptrend_{period}"] = strong_uptrend
        result[f"ADX_Strong_Downtrend_{period}"] = strong_downtrend

        # Trend development signals
        trend_developing = (adx_values > 20) & adx_rising
        trend_weakening = (adx_values > 20) & adx_falling
        result[f"ADX_Trend_Developing_{period}"] = trend_developing
        result[f"ADX_Trend_Weakening_{period}"] = trend_weakening

        # Extreme readings
        extremely_strong = adx_values > 70
        result[f"ADX_Extremely_Strong_{period}"] = extremely_strong

        # Directional strength signals
        strong_directional_bias = di_spread.abs() > 10
        weak_directional_bias = di_spread.abs() < 5
        result[f"ADX_Strong_Direction_{period}"] = strong_directional_bias
        result[f"ADX_Weak_Direction_{period}"] = weak_directional_bias

        # Ranging market signals
        ranging_market = weak_trend & weak_directional_bias
        result[f"ADX_Ranging_Market_{period}"] = ranging_market

        # Trend reversal warning signals
        # ADX falling from high levels
        trend_exhaustion = (adx_values > 40) & adx_falling
        result[f"ADX_Trend_Exhaustion_{period}"] = trend_exhaustion

        return result

    def get_analysis(self, data: pd.DataFrame) -> dict[str, Any]:
        """
        Get comprehensive analysis of ADX.

        Args:
            data: DataFrame with calculated ADX

        Returns:
            Dictionary with analysis results
        """
        period = self.params.get("period", 14)
        adx_col = f"ADX_{period}"
        di_plus_col = f"DI_Plus_{period}"
        di_minus_col = f"DI_Minus_{period}"
        slope_col = f"ADX_Slope_{period}"
        spread_col = f"DI_Spread_{period}"

        if adx_col not in data.columns:
            data = self.compute(data)

        # Get recent values (last 30 periods for context)
        recent_data = data.tail(30)
        latest = data.iloc[-1]

        # Current values
        current_adx = latest[adx_col]
        current_di_plus = latest[di_plus_col]
        current_di_minus = latest[di_minus_col]
        current_slope = latest[slope_col]
        current_spread = latest[spread_col]
        current_price = latest["close"]

        # Historical analysis
        adx_values = recent_data[adx_col].dropna()
        adx_max = adx_values.max() if len(adx_values) > 0 else 0
        adx_min = adx_values.min() if len(adx_values) > 0 else 0
        adx_avg = adx_values.mean() if len(adx_values) > 0 else 0

        # Trend strength assessment
        if current_adx > 70:
            trend_strength = "Extremely Strong"
        elif current_adx > 50:
            trend_strength = "Very Strong"
        elif current_adx > 25:
            trend_strength = "Strong"
        elif current_adx > 20:
            trend_strength = "Moderate"
        else:
            trend_strength = "Weak/Ranging"

        # Trend direction assessment
        if current_di_plus > current_di_minus:
            if current_spread > 10:
                direction_state = "Strong Uptrend"
            elif current_spread > 5:
                direction_state = "Moderate Uptrend"
            else:
                direction_state = "Weak Uptrend"
        elif current_di_minus > current_di_plus:
            if abs(current_spread) > 10:
                direction_state = "Strong Downtrend"
            elif abs(current_spread) > 5:
                direction_state = "Moderate Downtrend"
            else:
                direction_state = "Weak Downtrend"
        else:
            direction_state = "Neutral/Sideways"

        # ADX momentum assessment
        if current_slope > 2:
            adx_momentum = "Rising Strongly"
        elif current_slope > 0:
            adx_momentum = "Rising"
        elif current_slope > -2:
            adx_momentum = "Stable"
        else:
            adx_momentum = "Falling"

        # Market state assessment
        if current_adx < 20 and abs(current_spread) < 5:
            market_state = "Ranging/Consolidating"
        elif current_adx > 25 and current_slope > 0:
            market_state = "Trending (Developing)"
        elif current_adx > 25 and current_slope < -2:
            market_state = "Trending (Weakening)"
        elif current_adx > 50:
            market_state = "Strong Trend"
        else:
            market_state = "Transitional"

        # Position within recent range
        if adx_max != adx_min:
            adx_position = (current_adx - adx_min) / (adx_max - adx_min) * 100
        else:
            adx_position = 50

        # Trend reliability
        di_values = recent_data[di_plus_col] - recent_data[di_minus_col]
        direction_consistency = (
            (di_values > 0).sum() / len(di_values) * 100 if len(di_values) > 0 else 50
        )

        # Time analysis
        days_above_25 = (adx_values > 25).sum()
        days_below_20 = (adx_values < 20).sum()

        # Extreme analysis
        days_since_peak = 0
        for i in range(len(adx_values)):
            if adx_values.iloc[-(i + 1)] == adx_max:
                days_since_peak = i
                break

        # Signal assessment
        signals_active = {
            "strong_trend": current_adx > 25,
            "very_strong_trend": current_adx > 50,
            "trending_up": current_di_plus > current_di_minus and current_adx > 20,
            "trending_down": current_di_minus > current_di_plus and current_adx > 20,
            "trend_developing": current_adx > 20 and current_slope > 0,
            "trend_weakening": current_adx > 25 and current_slope < -1,
            "ranging_market": current_adx < 20 and abs(current_spread) < 5,
            "extreme_reading": current_adx > 70,
        }

        return {
            "current_values": {
                "adx": round(current_adx, 2),
                "di_plus": round(current_di_plus, 2),
                "di_minus": round(current_di_minus, 2),
                "di_spread": round(current_spread, 2),
                "adx_slope": round(current_slope, 2),
                "current_price": round(current_price, 4),
            },
            "trend_analysis": {
                "strength": trend_strength,
                "direction": direction_state,
                "momentum": adx_momentum,
                "market_state": market_state,
                "reliability": round(direction_consistency, 1),
            },
            "historical_context": {
                "position_in_range": round(adx_position, 1),
                "recent_max": round(adx_max, 2),
                "recent_min": round(adx_min, 2),
                "recent_average": round(adx_avg, 2),
                "days_since_peak": days_since_peak,
            },
            "market_character": {
                "days_trending": days_above_25,
                "days_ranging": days_below_20,
                "trend_consistency": round(direction_consistency, 1),
                "volatility": (
                    "High"
                    if adx_max - adx_min > 30
                    else "Medium" if adx_max - adx_min > 15 else "Low"
                ),
            },
            "directional_analysis": {
                "dominant_force": (
                    "+DI" if current_di_plus > current_di_minus else "-DI"
                ),
                "spread_magnitude": round(abs(current_spread), 2),
                "directional_strength": (
                    "Strong"
                    if abs(current_spread) > 10
                    else "Moderate" if abs(current_spread) > 5 else "Weak"
                ),
            },
            "signals": signals_active,
        }


# Create alias for easier access
ADX = ADXIndicator
AverageDirectionalIndex = ADXIndicator
