"""
Fisher Transform Indicator.

The Fisher Transform is a technical indicator that converts price data to a near-normal
distribution to improve signal clarity. It helps identify price reversals by highlighting
extreme price movements and generating clearer buy/sell signals.

Author: KTRDR
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Union

from ktrdr import get_logger
from ktrdr.indicators.base_indicator import BaseIndicator
from ktrdr.errors import DataError

logger = get_logger(__name__)


class FisherTransformIndicator(BaseIndicator):
    """
    Fisher Transform indicator implementation.
    
    The Fisher Transform calculation involves these steps:
    
    1. Calculate the median price: (High + Low) / 2
    2. Normalize the median price to a range between -1 and +1 using the highest high
       and lowest low over the specified period
    3. Apply the Fisher Transform formula:
       Fisher = 0.5 * ln((1 + normalized_price) / (1 - normalized_price))
    4. Smooth the result using exponential moving average
    
    The indicator helps identify:
    - Price reversals at extreme levels
    - Trend changes and momentum shifts
    - Overbought/oversold conditions
    - Divergences between price and momentum
    
    Key characteristics:
    - Oscillates around zero line
    - Values above +2 indicate overbought conditions
    - Values below -2 indicate oversold conditions
    - Zero line crossings suggest trend changes
    - Extreme readings often precede reversals
    
    Typical Parameters:
    - period: 10 (lookback period for normalization)
    - smoothing: 3 (EMA smoothing period)
    """
    
    def __init__(self, period: int = 10, smoothing: int = 3):
        """
        Initialize Fisher Transform indicator.
        
        Args:
            period: Lookback period for price normalization (default: 10)
            smoothing: EMA smoothing period for the Fisher Transform (default: 3)
        """
        # Call parent constructor - Fisher Transform is typically displayed in separate panel
        super().__init__(
            name="FisherTransform",
            display_as_overlay=False,
            period=period,
            smoothing=smoothing
        )
    
    def _validate_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate indicator parameters."""
        period = params.get("period", 10)
        smoothing = params.get("smoothing", 3)
        
        if not isinstance(period, int) or period < 1:
            raise ValueError("period must be a positive integer")
        
        if period < 2:
            raise ValueError("period must be at least 2")
        
        if period > 100:
            raise ValueError("period should not exceed 100 for practical purposes")
            
        if not isinstance(smoothing, int) or smoothing < 1:
            raise ValueError("smoothing must be a positive integer")
            
        if smoothing > 20:
            raise ValueError("smoothing should not exceed 20 for practical purposes")
            
        return {"period": period, "smoothing": smoothing}
    
    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Compute Fisher Transform.
        
        Args:
            data: DataFrame containing OHLC data
        
        Returns:
            DataFrame with Fisher Transform values
            
        Raises:
            DataError: If required columns are missing or insufficient data
        """
        # Get parameters from self.params
        period = self.params.get("period", 10)
        smoothing = self.params.get("smoothing", 3)
        
        # Check required columns
        required_columns = ["high", "low"]
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            raise DataError(
                message=f"Fisher Transform requires columns: {', '.join(missing_columns)}",
                error_code="DATA-MissingColumn",
                details={
                    "missing_columns": missing_columns,
                    "required_columns": required_columns,
                    "available_columns": list(data.columns),
                },
            )
        
        # Check for sufficient data
        min_required = period + smoothing
        if len(data) < min_required:
            raise DataError(
                message=f"Fisher Transform requires at least {min_required} data points",
                error_code="DATA-InsufficientData",
                details={
                    "required": min_required,
                    "provided": len(data),
                    "period": period,
                    "smoothing": smoothing,
                },
            )
        
        # Calculate median price (typical price without close)
        median_price = (data["high"] + data["low"]) / 2
        
        # Calculate rolling highest high and lowest low
        highest_high = data["high"].rolling(window=period, min_periods=period).max()
        lowest_low = data["low"].rolling(window=period, min_periods=period).min()
        
        # Normalize price to range [-1, +1]
        # Avoid division by zero
        price_range = highest_high - lowest_low
        normalized_price = pd.Series(index=data.index, dtype=float)
        
        valid_range = price_range != 0
        normalized_price[valid_range] = 2 * ((median_price[valid_range] - lowest_low[valid_range]) / 
                                           price_range[valid_range]) - 1
        normalized_price[~valid_range] = 0
        
        # Clamp values to prevent numerical issues with ln function
        # Fisher Transform requires values to be in range (-1, 1) exclusive
        normalized_price = normalized_price.clip(-0.999, 0.999)
        
        # Apply Fisher Transform formula
        # Fisher = 0.5 * ln((1 + x) / (1 - x))
        fisher_raw = 0.5 * np.log((1 + normalized_price) / (1 - normalized_price))
        
        # Apply exponential smoothing
        fisher_smooth = fisher_raw.ewm(span=smoothing, adjust=False).mean()
        
        # Calculate trigger line (previous Fisher Transform value)
        fisher_trigger = fisher_smooth.shift(1)
        
        # Create result DataFrame
        result = data.copy()
        suffix = f"{period}_{smoothing}"
        result[f"Fisher_{suffix}"] = fisher_smooth
        result[f"Fisher_Trigger_{suffix}"] = fisher_trigger
        result[f"Fisher_Raw_{suffix}"] = fisher_raw
        result[f"Fisher_Normalized_{suffix}"] = normalized_price
        
        # Calculate additional analysis metrics
        # Fisher Transform momentum (rate of change)
        fisher_momentum = fisher_smooth - fisher_smooth.shift(3)
        result[f"Fisher_Momentum_{suffix}"] = fisher_momentum
        
        # Fisher Transform histogram (difference from trigger)
        fisher_histogram = fisher_smooth - fisher_trigger
        result[f"Fisher_Histogram_{suffix}"] = fisher_histogram
        
        # Zero line crossings
        fisher_above_zero = fisher_smooth > 0
        fisher_below_zero = fisher_smooth < 0
        result[f"Fisher_Above_Zero_{suffix}"] = fisher_above_zero
        result[f"Fisher_Below_Zero_{suffix}"] = fisher_below_zero
        
        # Extreme readings
        fisher_overbought = fisher_smooth > 2
        fisher_oversold = fisher_smooth < -2
        result[f"Fisher_Overbought_{suffix}"] = fisher_overbought
        result[f"Fisher_Oversold_{suffix}"] = fisher_oversold
        
        logger.debug(f"Computed Fisher Transform with period={period}, smoothing={smoothing}")
        
        return result
    
    def get_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Generate trading signals based on Fisher Transform.
        
        Args:
            data: DataFrame with calculated Fisher Transform
        
        Returns:
            DataFrame with signal columns added
        """
        result = data.copy()
        
        period = self.params.get("period", 10)
        smoothing = self.params.get("smoothing", 3)
        suffix = f"{period}_{smoothing}"
        
        fisher_col = f"Fisher_{suffix}"
        trigger_col = f"Fisher_Trigger_{suffix}"
        momentum_col = f"Fisher_Momentum_{suffix}"
        histogram_col = f"Fisher_Histogram_{suffix}"
        
        if fisher_col not in data.columns:
            result = self.compute(data)
        
        fisher = result[fisher_col]
        trigger = result[trigger_col]
        momentum = result[momentum_col]
        histogram = result[histogram_col]
        
        # Zero line crossing signals
        zero_cross_up = (fisher > 0) & (fisher.shift(1) <= 0)
        zero_cross_down = (fisher < 0) & (fisher.shift(1) >= 0)
        result[f"Fisher_Zero_Cross_Up_{suffix}"] = zero_cross_up
        result[f"Fisher_Zero_Cross_Down_{suffix}"] = zero_cross_down
        
        # Trigger line crossing signals
        trigger_cross_up = (fisher > trigger) & (fisher.shift(1) <= trigger.shift(1))
        trigger_cross_down = (fisher < trigger) & (fisher.shift(1) >= trigger.shift(1))
        result[f"Fisher_Trigger_Cross_Up_{suffix}"] = trigger_cross_up
        result[f"Fisher_Trigger_Cross_Down_{suffix}"] = trigger_cross_down
        
        # Extreme level signals
        extreme_overbought = fisher > 3
        extreme_oversold = fisher < -3
        result[f"Fisher_Extreme_Overbought_{suffix}"] = extreme_overbought
        result[f"Fisher_Extreme_Oversold_{suffix}"] = extreme_oversold
        
        # Reversal signals from extreme levels
        reversal_from_high = (fisher < 2) & (fisher.shift(1) >= 2)
        reversal_from_low = (fisher > -2) & (fisher.shift(1) <= -2)
        result[f"Fisher_Reversal_From_High_{suffix}"] = reversal_from_high
        result[f"Fisher_Reversal_From_Low_{suffix}"] = reversal_from_low
        
        # Momentum signals
        momentum_up = momentum > 0
        momentum_down = momentum < 0
        result[f"Fisher_Momentum_Up_{suffix}"] = momentum_up
        result[f"Fisher_Momentum_Down_{suffix}"] = momentum_down
        
        # Strong momentum signals
        strong_momentum_up = momentum > 0.5
        strong_momentum_down = momentum < -0.5
        result[f"Fisher_Strong_Momentum_Up_{suffix}"] = strong_momentum_up
        result[f"Fisher_Strong_Momentum_Down_{suffix}"] = strong_momentum_down
        
        # Histogram signals (Fisher vs Trigger)
        histogram_positive = histogram > 0
        histogram_negative = histogram < 0
        result[f"Fisher_Above_Trigger_{suffix}"] = histogram_positive
        result[f"Fisher_Below_Trigger_{suffix}"] = histogram_negative
        
        # Trend signals based on Fisher position
        bullish_trend = (fisher > 0) & (fisher > trigger)
        bearish_trend = (fisher < 0) & (fisher < trigger)
        result[f"Fisher_Bullish_Trend_{suffix}"] = bullish_trend
        result[f"Fisher_Bearish_Trend_{suffix}"] = bearish_trend
        
        # Divergence detection (requires price data)
        if "close" in result.columns:
            # Price momentum for divergence analysis
            price_momentum = result["close"] - result["close"].shift(period)
            
            # Bullish divergence: Price declining but Fisher improving
            price_declining = price_momentum < 0
            fisher_improving = momentum > 0
            result[f"Fisher_Bullish_Divergence_{suffix}"] = price_declining & fisher_improving
            
            # Bearish divergence: Price rising but Fisher weakening
            price_rising = price_momentum > 0
            fisher_weakening = momentum < 0
            result[f"Fisher_Bearish_Divergence_{suffix}"] = price_rising & fisher_weakening
        
        # Consolidation signals (Fisher near zero with low momentum)
        consolidation = (fisher.abs() < 0.5) & (momentum.abs() < 0.2)
        result[f"Fisher_Consolidation_{suffix}"] = consolidation
        
        return result
    
    def get_analysis(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Get comprehensive analysis of Fisher Transform.
        
        Args:
            data: DataFrame with calculated Fisher Transform
        
        Returns:
            Dictionary with analysis results
        """
        period = self.params.get("period", 10)
        smoothing = self.params.get("smoothing", 3)
        suffix = f"{period}_{smoothing}"
        
        fisher_col = f"Fisher_{suffix}"
        trigger_col = f"Fisher_Trigger_{suffix}"
        momentum_col = f"Fisher_Momentum_{suffix}"
        
        if fisher_col not in data.columns:
            data = self.compute(data)
        
        # Get recent values (last 30 periods for context)
        recent_data = data.tail(30)
        latest = data.iloc[-1]
        
        # Current values
        current_fisher = latest[fisher_col]
        current_trigger = latest[trigger_col]
        current_momentum = latest[momentum_col]
        current_price = latest["close"] if "close" in latest else latest["high"]
        
        # Historical analysis
        fisher_values = recent_data[fisher_col].dropna()
        fisher_max = fisher_values.max() if len(fisher_values) > 0 else 0
        fisher_min = fisher_values.min() if len(fisher_values) > 0 else 0
        fisher_avg = fisher_values.mean() if len(fisher_values) > 0 else 0
        
        # Level assessment
        if current_fisher > 3:
            level_state = "Extremely Overbought"
        elif current_fisher > 2:
            level_state = "Overbought"
        elif current_fisher > 0.5:
            level_state = "Bullish"
        elif current_fisher > -0.5:
            level_state = "Neutral"
        elif current_fisher > -2:
            level_state = "Bearish"
        elif current_fisher > -3:
            level_state = "Oversold"
        else:
            level_state = "Extremely Oversold"
        
        # Momentum assessment
        if current_momentum > 0.5:
            momentum_state = "Strong Bullish Momentum"
        elif current_momentum > 0.1:
            momentum_state = "Bullish Momentum"
        elif current_momentum > -0.1:
            momentum_state = "Neutral Momentum"
        elif current_momentum > -0.5:
            momentum_state = "Bearish Momentum"
        else:
            momentum_state = "Strong Bearish Momentum"
        
        # Position relative to trigger
        trigger_relation = "Above Trigger" if current_fisher > current_trigger else "Below Trigger"
        
        # Zero line analysis
        zero_line_state = "Above Zero (Bullish Bias)" if current_fisher > 0 else "Below Zero (Bearish Bias)"
        
        # Extreme analysis
        days_in_extreme = 0
        extreme_threshold = 2 if current_fisher > 0 else -2
        for i in range(len(fisher_values)):
            if current_fisher > 0:
                if fisher_values.iloc[-(i+1)] > extreme_threshold:
                    days_in_extreme += 1
                else:
                    break
            else:
                if fisher_values.iloc[-(i+1)] < extreme_threshold:
                    days_in_extreme += 1
                else:
                    break
        
        # Trend consistency
        bullish_periods = (fisher_values > 0).sum()
        bearish_periods = (fisher_values < 0).sum()
        trend_consistency = max(bullish_periods, bearish_periods) / len(fisher_values) * 100 if len(fisher_values) > 0 else 50
        
        # Reversal probability
        if abs(current_fisher) > 2.5:
            reversal_probability = "High"
        elif abs(current_fisher) > 1.5:
            reversal_probability = "Medium"
        else:
            reversal_probability = "Low"
        
        # Signal strength
        signal_strength = "Strong" if abs(current_momentum) > 0.3 else "Moderate" if abs(current_momentum) > 0.1 else "Weak"
        
        # Divergence analysis (if price data available)
        divergence_state = "None"
        if "close" in recent_data.columns:
            price_change = recent_data["close"].iloc[-1] - recent_data["close"].iloc[0]
            fisher_change = fisher_values.iloc[-1] - fisher_values.iloc[0] if len(fisher_values) >= period else 0
            
            if price_change > 0 and fisher_change < 0:
                divergence_state = "Bearish Divergence"
            elif price_change < 0 and fisher_change > 0:
                divergence_state = "Bullish Divergence"
            elif (price_change > 0 and fisher_change > 0) or (price_change < 0 and fisher_change < 0):
                divergence_state = "Confirmation"
        
        return {
            "current_values": {
                "fisher": round(current_fisher, 4),
                "trigger": round(current_trigger, 4),
                "momentum": round(current_momentum, 4),
                "current_price": round(current_price, 4)
            },
            "level_analysis": {
                "state": level_state,
                "zero_line_state": zero_line_state,
                "extreme_reading": abs(current_fisher) > 2,
                "days_in_extreme": days_in_extreme
            },
            "momentum_analysis": {
                "state": momentum_state,
                "strength": signal_strength,
                "direction": "Up" if current_momentum > 0 else "Down",
                "acceleration": abs(current_momentum)
            },
            "position_analysis": {
                "trigger_relation": trigger_relation,
                "range_position": round(((current_fisher - fisher_min) / (fisher_max - fisher_min) * 100), 1) if fisher_max != fisher_min else 50,
                "historical_max": round(fisher_max, 4),
                "historical_min": round(fisher_min, 4),
                "historical_avg": round(fisher_avg, 4)
            },
            "trend_analysis": {
                "consistency": round(trend_consistency, 1),
                "dominant_bias": "Bullish" if bullish_periods > bearish_periods else "Bearish",
                "bullish_periods": int(bullish_periods),
                "bearish_periods": int(bearish_periods)
            },
            "reversal_analysis": {
                "probability": reversal_probability,
                "extreme_exhaustion": abs(current_fisher) > 3,
                "momentum_divergence": (current_fisher > 2 and current_momentum < 0) or (current_fisher < -2 and current_momentum > 0)
            },
            "divergence_analysis": {
                "state": divergence_state,
                "warning": divergence_state in ["Bullish Divergence", "Bearish Divergence"]
            },
            "signals": {
                "overbought": current_fisher > 2,
                "oversold": current_fisher < -2,
                "extreme_overbought": current_fisher > 3,
                "extreme_oversold": current_fisher < -3,
                "bullish_bias": current_fisher > 0,
                "bearish_bias": current_fisher < 0,
                "above_trigger": current_fisher > current_trigger,
                "momentum_bullish": current_momentum > 0.1,
                "momentum_bearish": current_momentum < -0.1,
                "reversal_warning": abs(current_fisher) > 2.5
            }
        }


# Create alias for easier access
FisherTransform = FisherTransformIndicator