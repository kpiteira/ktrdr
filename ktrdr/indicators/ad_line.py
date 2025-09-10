"""
Accumulation/Distribution Line (A/D Line) Indicator.

The Accumulation/Distribution Line is a volume-based indicator that attempts to gauge
supply and demand by determining whether investors are generally accumulating (buying)
or distributing (selling) a particular stock by identifying divergences between
stock price and volume flow.

Author: KTRDR
"""

from typing import Any

import pandas as pd

from ktrdr import get_logger
from ktrdr.errors import DataError
from ktrdr.indicators.base_indicator import BaseIndicator

logger = get_logger(__name__)


class ADLineIndicator(BaseIndicator):
    """
    Accumulation/Distribution Line indicator implementation.

    The A/D Line is calculated by first determining the Money Flow Multiplier:

    Money Flow Multiplier = [(Close - Low) - (High - Close)] / (High - Low)

    Then the Money Flow Volume:
    Money Flow Volume = Money Flow Multiplier × Volume

    Finally, the A/D Line is the cumulative sum of Money Flow Volume:
    A/D Line = Previous A/D Line + Current Period's Money Flow Volume

    The A/D Line helps identify:
    - Accumulation (buying pressure) when line is rising
    - Distribution (selling pressure) when line is falling
    - Divergences between price and volume flow
    - Trend confirmations or warnings

    Key characteristics:
    - Ranges from -1 to +1 for the Money Flow Multiplier
    - A/D Line is cumulative and can trend indefinitely
    - More effective when combined with price action analysis
    """

    def __init__(self, use_sma_smoothing: bool = False, smoothing_period: int = 21):
        """
        Initialize A/D Line indicator.

        Args:
            use_sma_smoothing: Whether to apply SMA smoothing to the A/D Line (default: False)
            smoothing_period: Period for SMA smoothing if enabled (default: 21)
        """
        # Call parent constructor - A/D Line is typically displayed in separate panel
        super().__init__(
            name="ADLine",
            display_as_overlay=False,
            use_sma_smoothing=use_sma_smoothing,
            smoothing_period=smoothing_period,
        )

    def _validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Validate indicator parameters."""
        use_sma_smoothing = params.get("use_sma_smoothing", False)
        smoothing_period = params.get("smoothing_period", 21)

        if not isinstance(use_sma_smoothing, bool):
            raise ValueError("use_sma_smoothing must be a boolean")

        if not isinstance(smoothing_period, int) or smoothing_period < 1:
            raise ValueError("smoothing_period must be a positive integer")

        if smoothing_period < 2:
            raise ValueError("smoothing_period must be at least 2")

        if smoothing_period > 200:
            raise ValueError(
                "smoothing_period should not exceed 200 for practical purposes"
            )

        return {
            "use_sma_smoothing": use_sma_smoothing,
            "smoothing_period": smoothing_period,
        }

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Compute Accumulation/Distribution Line.

        Args:
            data: DataFrame containing OHLCV data

        Returns:
            DataFrame with A/D Line values

        Raises:
            DataError: If required columns are missing or insufficient data
        """
        # Get parameters from self.params
        use_sma_smoothing = self.params.get("use_sma_smoothing", False)
        smoothing_period = self.params.get("smoothing_period", 21)

        # Check required columns
        required_columns = ["high", "low", "close", "volume"]
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            raise DataError(
                message=f"A/D Line requires columns: {', '.join(missing_columns)}",
                error_code="DATA-MissingColumn",
                details={
                    "missing_columns": missing_columns,
                    "required_columns": required_columns,
                    "available_columns": list(data.columns),
                },
            )

        # Check for sufficient data
        min_required = smoothing_period if use_sma_smoothing else 1
        if len(data) < min_required:
            raise DataError(
                message=f"A/D Line requires at least {min_required} data points",
                error_code="DATA-InsufficientData",
                details={
                    "required": min_required,
                    "provided": len(data),
                    "use_sma_smoothing": use_sma_smoothing,
                    "smoothing_period": smoothing_period,
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

        # Calculate cumulative A/D Line
        ad_line = money_flow_volume.cumsum()

        # Create result DataFrame
        result = data.copy()
        result["AD_Line"] = ad_line
        result["AD_MF_Multiplier"] = money_flow_multiplier
        result["AD_MF_Volume"] = money_flow_volume

        # Apply smoothing if requested
        if use_sma_smoothing:
            ad_line_smooth = ad_line.rolling(
                window=smoothing_period, min_periods=smoothing_period
            ).mean()
            result[f"AD_Line_SMA_{smoothing_period}"] = ad_line_smooth

        # Calculate rate of change for trend analysis
        ad_roc = ad_line.pct_change(periods=10) * 100  # 10-period rate of change
        result["AD_ROC_10"] = ad_roc

        # Calculate momentum (difference between current and N periods ago)
        ad_momentum = ad_line - ad_line.shift(21)  # 21-period momentum
        result["AD_Momentum_21"] = ad_momentum

        # Calculate relative strength (current A/D vs recent average)
        ad_recent_avg = ad_line.rolling(window=50, min_periods=20).mean()
        ad_relative_strength = (ad_line / ad_recent_avg - 1) * 100
        result["AD_Relative_Strength"] = ad_relative_strength

        logger.debug(f"Computed A/D Line with smoothing={use_sma_smoothing}")

        return result

    def get_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Generate trading signals based on A/D Line.

        Args:
            data: DataFrame with calculated A/D Line

        Returns:
            DataFrame with signal columns added
        """
        result = data.copy()

        use_sma_smoothing = self.params.get("use_sma_smoothing", False)
        smoothing_period = self.params.get("smoothing_period", 21)

        ad_col = f"AD_Line_SMA_{smoothing_period}" if use_sma_smoothing else "AD_Line"

        if ad_col not in data.columns:
            result = self.compute(data)

        # Trend signals based on A/D Line direction
        ad_values = result[ad_col]
        ad_rising = ad_values > ad_values.shift(1)
        ad_falling = ad_values < ad_values.shift(1)

        result["AD_Rising"] = ad_rising
        result["AD_Falling"] = ad_falling

        # Momentum signals
        ad_momentum = result["AD_Momentum_21"]
        result["AD_Strong_Accumulation"] = (
            ad_momentum > ad_momentum.rolling(window=10).mean()
        )
        result["AD_Strong_Distribution"] = (
            ad_momentum < ad_momentum.rolling(window=10).mean()
        )

        # Rate of change signals
        ad_roc = result["AD_ROC_10"]
        result["AD_Accelerating_Up"] = (
            ad_roc > 5
        )  # A/D Line growing faster than 5% per 10 periods
        result["AD_Accelerating_Down"] = (
            ad_roc < -5
        )  # A/D Line declining faster than 5% per 10 periods

        # Divergence signals (requires price comparison)
        if "close" in result.columns:
            # Price momentum for divergence detection
            price_momentum = result["close"] - result["close"].shift(21)

            # Bullish divergence: Price falling but A/D Line rising
            price_falling = price_momentum < 0
            ad_momentum_rising = ad_momentum > 0
            result["AD_Bullish_Divergence"] = price_falling & ad_momentum_rising

            # Bearish divergence: Price rising but A/D Line falling
            price_rising = price_momentum > 0
            ad_momentum_falling = ad_momentum < 0
            result["AD_Bearish_Divergence"] = price_rising & ad_momentum_falling

        # Extreme values signals
        ad_rel_strength = result["AD_Relative_Strength"]
        result["AD_Extremely_Strong"] = (
            ad_rel_strength > 20
        )  # A/D Line 20% above recent average
        result["AD_Extremely_Weak"] = (
            ad_rel_strength < -20
        )  # A/D Line 20% below recent average

        # Money Flow signals
        mf_multiplier = result["AD_MF_Multiplier"]
        result["AD_Strong_Buying_Pressure"] = mf_multiplier > 0.5
        result["AD_Strong_Selling_Pressure"] = mf_multiplier < -0.5
        result["AD_Neutral_Flow"] = (mf_multiplier >= -0.2) & (mf_multiplier <= 0.2)

        return result

    def get_analysis(self, data: pd.DataFrame) -> dict[str, Any]:
        """
        Get comprehensive analysis of A/D Line.

        Args:
            data: DataFrame with calculated A/D Line

        Returns:
            Dictionary with analysis results
        """
        use_sma_smoothing = self.params.get("use_sma_smoothing", False)
        smoothing_period = self.params.get("smoothing_period", 21)

        ad_col = f"AD_Line_SMA_{smoothing_period}" if use_sma_smoothing else "AD_Line"

        if ad_col not in data.columns:
            data = self.compute(data)

        # Get recent values (last 50 periods for more context)
        recent_data = data.tail(50)
        latest = data.iloc[-1]

        # Current values
        current_ad = latest[ad_col]
        current_mf_multiplier = latest["AD_MF_Multiplier"]
        current_mf_volume = latest["AD_MF_Volume"]
        current_roc = latest["AD_ROC_10"]
        current_momentum = latest["AD_Momentum_21"]
        current_rel_strength = latest["AD_Relative_Strength"]
        current_price = latest["close"]

        # Trend analysis
        ad_values = recent_data[ad_col].dropna()
        if len(ad_values) >= 2:
            recent_slope = (
                (ad_values.iloc[-1] - ad_values.iloc[-5]) / 4
                if len(ad_values) >= 5
                else (ad_values.iloc[-1] - ad_values.iloc[-2])
            )
            trend_direction = (
                "Accumulation"
                if recent_slope > 0
                else "Distribution"
                if recent_slope < 0
                else "Neutral"
            )
        else:
            recent_slope = 0
            trend_direction = "Insufficient Data"

        # Momentum analysis
        momentum_values = recent_data["AD_Momentum_21"].dropna()
        avg_momentum = momentum_values.mean() if len(momentum_values) > 0 else 0
        momentum_strength = (
            "Strong"
            if abs(current_momentum) > abs(avg_momentum) * 1.5
            else (
                "Moderate"
                if abs(current_momentum) > abs(avg_momentum) * 0.5
                else "Weak"
            )
        )

        # Volume flow analysis
        mf_multiplier_values = recent_data["AD_MF_Multiplier"].dropna()
        avg_mf_multiplier = (
            mf_multiplier_values.mean() if len(mf_multiplier_values) > 0 else 0
        )

        # Determine money flow state
        if current_mf_multiplier > 0.5:
            money_flow_state = "Strong Buying Pressure"
        elif current_mf_multiplier > 0.2:
            money_flow_state = "Moderate Buying Pressure"
        elif current_mf_multiplier > -0.2:
            money_flow_state = "Neutral Flow"
        elif current_mf_multiplier > -0.5:
            money_flow_state = "Moderate Selling Pressure"
        else:
            money_flow_state = "Strong Selling Pressure"

        # Divergence analysis (last 21 periods)
        recent_short = recent_data.tail(21)
        price_change = (
            recent_short["close"].iloc[-1] - recent_short["close"].iloc[0]
            if len(recent_short) >= 21
            else 0
        )
        ad_change = (
            recent_short[ad_col].iloc[-1] - recent_short[ad_col].iloc[0]
            if len(recent_short) >= 21
            else 0
        )

        divergence_state = "None"
        if price_change > 0 and ad_change < 0:
            divergence_state = "Bearish Divergence (Price up, A/D down)"
        elif price_change < 0 and ad_change > 0:
            divergence_state = "Bullish Divergence (Price down, A/D up)"
        elif (price_change > 0 and ad_change > 0) or (
            price_change < 0 and ad_change < 0
        ):
            divergence_state = "Confirmation (Price and A/D aligned)"

        # Strength assessment
        if current_rel_strength > 20:
            strength_state = "Extremely Strong"
        elif current_rel_strength > 10:
            strength_state = "Strong"
        elif current_rel_strength > -10:
            strength_state = "Normal"
        elif current_rel_strength > -20:
            strength_state = "Weak"
        else:
            strength_state = "Extremely Weak"

        return {
            "current_values": {
                "ad_line": round(current_ad, 2),
                "mf_multiplier": round(current_mf_multiplier, 4),
                "mf_volume": round(current_mf_volume, 2),
                "rate_of_change": round(current_roc, 2),
                "momentum": round(current_momentum, 2),
                "relative_strength": round(current_rel_strength, 2),
                "current_price": round(current_price, 4),
            },
            "trend_analysis": {
                "direction": trend_direction,
                "slope": round(recent_slope, 2),
                "strength": momentum_strength,
                "is_accelerating": abs(current_roc) > 5,
            },
            "money_flow_analysis": {
                "state": money_flow_state,
                "current_multiplier": round(current_mf_multiplier, 4),
                "average_multiplier": round(avg_mf_multiplier, 4),
                "volume_weighted": round(current_mf_volume, 2),
            },
            "divergence_analysis": {
                "state": divergence_state,
                "price_change_21d": round(price_change, 4),
                "ad_change_21d": round(ad_change, 2),
                "alignment": (
                    "Aligned" if (price_change * ad_change) >= 0 else "Diverging"
                ),
            },
            "strength_assessment": {
                "state": strength_state,
                "relative_strength": round(current_rel_strength, 2),
                "momentum": round(current_momentum, 2),
                "momentum_vs_average": (
                    round((current_momentum / avg_momentum - 1) * 100, 1)
                    if avg_momentum != 0
                    else 0
                ),
            },
            "signals": {
                "accumulation": trend_direction == "Accumulation",
                "distribution": trend_direction == "Distribution",
                "strong_buying": current_mf_multiplier > 0.5,
                "strong_selling": current_mf_multiplier < -0.5,
                "bullish_divergence": price_change < 0 and ad_change > 0,
                "bearish_divergence": price_change > 0 and ad_change < 0,
                "accelerating": abs(current_roc) > 5,
                "extreme_strength": abs(current_rel_strength) > 20,
            },
        }


# Create alias for easier access
ADLine = ADLineIndicator
AccumulationDistribution = ADLineIndicator
