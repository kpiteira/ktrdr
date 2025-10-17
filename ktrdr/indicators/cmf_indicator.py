"""
Chaikin Money Flow (CMF) Indicator.

The Chaikin Money Flow oscillator is a volume-weighted average of the
Accumulation/Distribution Line over a specific period. It oscillates between +1 and -1,
with values closer to +1 indicating buying pressure and values closer to -1 indicating
selling pressure.

Author: KTRDR
"""

from typing import Any

import pandas as pd

from ktrdr import get_logger
from ktrdr.errors import DataError
from ktrdr.indicators.base_indicator import BaseIndicator

logger = get_logger(__name__)


class CMFIndicator(BaseIndicator):
    """
    Chaikin Money Flow (CMF) indicator implementation.

    CMF is calculated using the following steps:

    1. Money Flow Multiplier = [(Close - Low) - (High - Close)] / (High - Low)
    2. Money Flow Volume = Money Flow Multiplier × Volume
    3. CMF = Sum(Money Flow Volume, period) / Sum(Volume, period)

    The indicator helps identify:
    - Money flow direction (buying vs selling pressure)
    - Potential trend reversals when crossing zero line
    - Overbought/oversold conditions at extreme values
    - Divergences between price and money flow

    Key characteristics:
    - Oscillates between -1 and +1
    - Values above 0.1 suggest buying pressure
    - Values below -0.1 suggest selling pressure
    - Zero line crossings indicate potential trend changes

    Typical Parameters:
    - period: 21 (most common), 10, 14, 20
    """

    def __init__(self, period: int = 21):
        """
        Initialize CMF indicator.

        Args:
            period: Period for CMF calculation (default: 21)
        """
        # Call parent constructor - CMF is typically displayed in separate panel
        super().__init__(name="CMF", display_as_overlay=False, period=period)

    def _validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Validate indicator parameters."""
        period = params.get("period", 21)

        if not isinstance(period, int) or period < 1:
            raise ValueError("period must be a positive integer")

        if period < 2:
            raise ValueError("period must be at least 2")

        if period > 500:
            raise ValueError("period should not exceed 500 for practical purposes")

        return {"period": period}

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Compute Chaikin Money Flow.

        Args:
            data: DataFrame containing OHLCV data

        Returns:
            DataFrame with CMF values

        Raises:
            DataError: If required columns are missing or insufficient data
        """
        # Get parameters from self.params
        period = self.params.get("period", 21)

        # Check required columns
        required_columns = ["high", "low", "close", "volume"]
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            raise DataError(
                message=f"CMF requires columns: {', '.join(missing_columns)}",
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
                message=f"CMF requires at least {period} data points",
                error_code="DATA-InsufficientData",
                details={
                    "required": period,
                    "provided": len(data),
                    "period": period,
                },
            )

        # Extract OHLCV data
        high = data["high"]
        low = data["low"]
        close = data["close"]
        volume = data["volume"]

        # Calculate Money Flow Multiplier
        # Handle cases where high == low (no price range)
        price_range = high - low
        close_location = (close - low) - (high - close)

        # Avoid division by zero
        money_flow_multiplier = pd.Series(index=data.index, dtype=float)

        # When high == low, set multiplier to 0 (no clear direction)
        money_flow_multiplier[price_range == 0] = 0

        # Normal calculation when there's a price range
        valid_range = price_range != 0
        money_flow_multiplier[valid_range] = (
            close_location[valid_range] / price_range[valid_range]
        )

        # Calculate Money Flow Volume
        money_flow_volume = money_flow_multiplier * volume

        # Calculate CMF (rolling sum of MFV divided by rolling sum of volume)
        mfv_sum = money_flow_volume.rolling(window=period, min_periods=period).sum()
        volume_sum = volume.rolling(window=period, min_periods=period).sum()

        # Avoid division by zero
        cmf = pd.Series(index=data.index, dtype=float)
        valid_volume = volume_sum != 0
        cmf[valid_volume] = mfv_sum[valid_volume] / volume_sum[valid_volume]
        cmf[~valid_volume] = 0

        # Create result DataFrame
        result = pd.DataFrame(
            index=data.index
        )  # CRITICAL FIX: Only return computed columns
        result[f"CMF_{period}"] = cmf
        result[f"CMF_MF_Multiplier_{period}"] = money_flow_multiplier
        result[f"CMF_MF_Volume_{period}"] = money_flow_volume

        # Calculate additional analysis metrics
        # CMF momentum (rate of change)
        cmf_momentum = cmf - cmf.shift(5)  # 5-period momentum
        result[f"CMF_Momentum_{period}"] = cmf_momentum

        # CMF signal line (EMA of CMF for smoothing)
        cmf_signal = cmf.ewm(span=9, adjust=False).mean()
        result[f"CMF_Signal_{period}"] = cmf_signal

        # CMF histogram (difference between CMF and signal)
        cmf_histogram = cmf - cmf_signal
        result[f"CMF_Histogram_{period}"] = cmf_histogram

        # Zero-line crossings
        cmf_above_zero = cmf > 0
        cmf_below_zero = cmf < 0
        result[f"CMF_Above_Zero_{period}"] = cmf_above_zero
        result[f"CMF_Below_Zero_{period}"] = cmf_below_zero

        logger.debug(f"Computed CMF with period={period}")

        return result

    def get_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Generate trading signals based on CMF.

        Args:
            data: DataFrame with calculated CMF

        Returns:
            DataFrame with signal columns added
        """
        result = pd.DataFrame(
            index=data.index
        )  # CRITICAL FIX: Only return computed columns

        period = self.params.get("period", 21)
        cmf_col = f"CMF_{period}"
        signal_col = f"CMF_Signal_{period}"
        histogram_col = f"CMF_Histogram_{period}"
        momentum_col = f"CMF_Momentum_{period}"

        if cmf_col not in data.columns:
            result = self.compute(data)

        cmf_values = result[cmf_col]
        cmf_signal = result[signal_col]
        cmf_histogram = result[histogram_col]
        cmf_momentum = result[momentum_col]

        # Zero line crossing signals
        cmf_crossing_up = (cmf_values > 0) & (cmf_values.shift(1) <= 0)
        cmf_crossing_down = (cmf_values < 0) & (cmf_values.shift(1) >= 0)
        result[f"CMF_Zero_Cross_Up_{period}"] = cmf_crossing_up
        result[f"CMF_Zero_Cross_Down_{period}"] = cmf_crossing_down

        # Signal line crossings
        cmf_signal_cross_up = (cmf_values > cmf_signal) & (
            cmf_values.shift(1) <= cmf_signal.shift(1)
        )
        cmf_signal_cross_down = (cmf_values < cmf_signal) & (
            cmf_values.shift(1) >= cmf_signal.shift(1)
        )
        result[f"CMF_Signal_Cross_Up_{period}"] = cmf_signal_cross_up
        result[f"CMF_Signal_Cross_Down_{period}"] = cmf_signal_cross_down

        # Strength signals
        strong_buying = cmf_values > 0.1
        strong_selling = cmf_values < -0.1
        result[f"CMF_Strong_Buying_{period}"] = strong_buying
        result[f"CMF_Strong_Selling_{period}"] = strong_selling

        # Extreme signals
        extremely_strong_buying = cmf_values > 0.25
        extremely_strong_selling = cmf_values < -0.25
        result[f"CMF_Extreme_Buying_{period}"] = extremely_strong_buying
        result[f"CMF_Extreme_Selling_{period}"] = extremely_strong_selling

        # Momentum signals
        momentum_increasing = cmf_momentum > 0
        momentum_decreasing = cmf_momentum < 0
        result[f"CMF_Momentum_Up_{period}"] = momentum_increasing
        result[f"CMF_Momentum_Down_{period}"] = momentum_decreasing

        # Histogram signals (CMF vs signal line)
        histogram_positive = cmf_histogram > 0
        histogram_negative = cmf_histogram < 0
        result[f"CMF_Above_Signal_{period}"] = histogram_positive
        result[f"CMF_Below_Signal_{period}"] = histogram_negative

        # Divergence detection (requires price data)
        if "close" in result.columns:
            # Price momentum for divergence analysis
            price_momentum = result["close"] - result["close"].shift(period)

            # Bullish divergence: Price declining but CMF improving
            price_declining = price_momentum < 0
            cmf_improving = cmf_momentum > 0
            result[f"CMF_Bullish_Divergence_{period}"] = price_declining & cmf_improving

            # Bearish divergence: Price rising but CMF weakening
            price_rising = price_momentum > 0
            cmf_weakening = cmf_momentum < 0
            result[f"CMF_Bearish_Divergence_{period}"] = price_rising & cmf_weakening

        # Consolidation/range signals
        cmf_range_bound = (cmf_values > -0.05) & (cmf_values < 0.05)
        result[f"CMF_Range_Bound_{period}"] = cmf_range_bound

        return result

    def get_analysis(self, data: pd.DataFrame) -> dict[str, Any]:
        """
        Get comprehensive analysis of CMF.

        Args:
            data: DataFrame with calculated CMF

        Returns:
            Dictionary with analysis results
        """
        period = self.params.get("period", 21)
        cmf_col = f"CMF_{period}"
        signal_col = f"CMF_Signal_{period}"
        momentum_col = f"CMF_Momentum_{period}"

        if cmf_col not in data.columns:
            data = self.compute(data)

        # Get recent values (last 50 periods for context)
        recent_data = data.tail(50)
        latest = data.iloc[-1]

        # Current values
        current_cmf = latest[cmf_col]
        current_signal = latest[signal_col]
        current_momentum = latest[momentum_col]
        current_price = latest["close"]

        # Historical analysis
        cmf_values = recent_data[cmf_col].dropna()
        cmf_max = cmf_values.max() if len(cmf_values) > 0 else 0
        cmf_min = cmf_values.min() if len(cmf_values) > 0 else 0
        cmf_avg = cmf_values.mean() if len(cmf_values) > 0 else 0

        # Trend analysis
        if len(cmf_values) >= 5:
            recent_trend = (cmf_values.iloc[-1] - cmf_values.iloc[-5]) / 4
            trend_direction = (
                "Improving"
                if recent_trend > 0
                else "Deteriorating" if recent_trend < 0 else "Stable"
            )
        else:
            recent_trend = 0
            trend_direction = "Insufficient Data"

        # Strength assessment
        if current_cmf > 0.25:
            strength_state = "Extremely Strong Buying"
        elif current_cmf > 0.1:
            strength_state = "Strong Buying"
        elif current_cmf > 0:
            strength_state = "Moderate Buying"
        elif current_cmf > -0.1:
            strength_state = "Weak/Neutral"
        elif current_cmf > -0.25:
            strength_state = "Strong Selling"
        else:
            strength_state = "Extremely Strong Selling"

        # Position within recent range
        if cmf_max != cmf_min:
            position_in_range = (current_cmf - cmf_min) / (cmf_max - cmf_min) * 100
        else:
            position_in_range = 50

        # Signal analysis
        signal_state = (
            "Above Signal" if current_cmf > current_signal else "Below Signal"
        )

        # Zero line analysis
        zero_line_state = (
            "Above Zero (Buying Pressure)"
            if current_cmf > 0
            else "Below Zero (Selling Pressure)"
        )

        # Divergence analysis (compare with price trend)
        price_change = (
            recent_data["close"].iloc[-1] - recent_data["close"].iloc[0]
            if len(recent_data) >= period
            else 0
        )
        cmf_change = (
            cmf_values.iloc[-1] - cmf_values.iloc[0] if len(cmf_values) >= period else 0
        )

        divergence_state = "None"
        if price_change > 0 and cmf_change < 0:
            divergence_state = "Bearish Divergence"
        elif price_change < 0 and cmf_change > 0:
            divergence_state = "Bullish Divergence"
        elif (price_change > 0 and cmf_change > 0) or (
            price_change < 0 and cmf_change < 0
        ):
            divergence_state = "Confirmation"

        # Volatility analysis
        cmf_volatility = cmf_values.std() if len(cmf_values) > 1 else 0
        volatility_state = (
            "High"
            if cmf_volatility > 0.15
            else "Medium" if cmf_volatility > 0.05 else "Low"
        )

        # Time since extremes
        days_since_high = 0
        days_since_low = 0

        for i in range(len(cmf_values)):
            if cmf_values.iloc[-(i + 1)] == cmf_max:
                days_since_high = i
                break

        for i in range(len(cmf_values)):
            if cmf_values.iloc[-(i + 1)] == cmf_min:
                days_since_low = i
                break

        return {
            "current_values": {
                "cmf": round(current_cmf, 4),
                "signal_line": round(current_signal, 4),
                "momentum": round(current_momentum, 4),
                "current_price": round(current_price, 4),
            },
            "strength_analysis": {
                "state": strength_state,
                "value": round(current_cmf, 4),
                "intensity": (
                    "Extreme"
                    if abs(current_cmf) > 0.25
                    else "Strong" if abs(current_cmf) > 0.1 else "Moderate"
                ),
            },
            "trend_analysis": {
                "direction": trend_direction,
                "momentum": round(current_momentum, 4),
                "trend_slope": round(recent_trend, 4),
                "consistency": "High" if abs(recent_trend) > 0.01 else "Low",
            },
            "position_analysis": {
                "zero_line_state": zero_line_state,
                "signal_state": signal_state,
                "range_position": round(position_in_range, 1),
                "historical_max": round(cmf_max, 4),
                "historical_min": round(cmf_min, 4),
                "historical_avg": round(cmf_avg, 4),
            },
            "divergence_analysis": {
                "state": divergence_state,
                "price_change": round(price_change, 4),
                "cmf_change": round(cmf_change, 4),
                "alignment": (
                    "Aligned" if (price_change * cmf_change) >= 0 else "Diverging"
                ),
            },
            "volatility_analysis": {
                "state": volatility_state,
                "value": round(cmf_volatility, 4),
                "days_since_high": days_since_high,
                "days_since_low": days_since_low,
            },
            "signals": {
                "buying_pressure": current_cmf > 0.1,
                "selling_pressure": current_cmf < -0.1,
                "extreme_reading": abs(current_cmf) > 0.25,
                "zero_cross_potential": abs(current_cmf) < 0.05,
                "bullish_momentum": current_momentum > 0,
                "bearish_momentum": current_momentum < 0,
                "above_signal": current_cmf > current_signal,
                "divergence_warning": divergence_state
                in ["Bullish Divergence", "Bearish Divergence"],
            },
        }


# Create alias for easier access
CMF = CMFIndicator
ChaikinMoneyFlow = CMFIndicator
