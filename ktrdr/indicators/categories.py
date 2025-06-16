"""
Indicator categorization system.

This module provides categorization for all technical indicators, organizing them
into logical groups that help traders understand their purpose and usage patterns.
"""

from enum import Enum
from typing import Dict, List, Set
from dataclasses import dataclass

class IndicatorCategory(str, Enum):
    """Categories for technical indicators based on their primary purpose."""
    
    TREND = "trend"
    MOMENTUM = "momentum" 
    VOLATILITY = "volatility"
    VOLUME = "volume"
    SUPPORT_RESISTANCE = "support_resistance"
    MULTI_PURPOSE = "multi_purpose"


@dataclass
class CategoryInfo:
    """Information about an indicator category."""
    
    name: str
    description: str
    purpose: str
    typical_usage: str
    common_timeframes: List[str]


# Category descriptions for documentation and API
CATEGORY_DESCRIPTIONS = {
    IndicatorCategory.TREND: CategoryInfo(
        name="Trend Indicators",
        description="Indicators that identify the direction and strength of price trends",
        purpose="Determine if the market is trending up, down, or sideways",
        typical_usage="Entry/exit signals, trend confirmation, support/resistance identification",
        common_timeframes=["1h", "4h", "1d", "1w"]
    ),
    
    IndicatorCategory.MOMENTUM: CategoryInfo(
        name="Momentum Indicators", 
        description="Oscillators that measure the speed and strength of price movements",
        purpose="Identify overbought/oversold conditions and trend reversals",
        typical_usage="Reversal signals, divergence analysis, confirmation of trends",
        common_timeframes=["15m", "1h", "4h", "1d"]
    ),
    
    IndicatorCategory.VOLATILITY: CategoryInfo(
        name="Volatility Indicators",
        description="Indicators that measure the degree of price variation and market uncertainty",
        purpose="Assess market volatility and potential price breakouts",
        typical_usage="Risk management, position sizing, breakout identification",
        common_timeframes=["1h", "4h", "1d"]
    ),
    
    IndicatorCategory.VOLUME: CategoryInfo(
        name="Volume Indicators",
        description="Indicators that analyze trading volume to confirm price movements",
        purpose="Validate price trends through volume analysis",
        typical_usage="Trend confirmation, accumulation/distribution detection",
        common_timeframes=["1h", "4h", "1d"]
    ),
    
    IndicatorCategory.SUPPORT_RESISTANCE: CategoryInfo(
        name="Support & Resistance",
        description="Indicators that identify key price levels and market structure", 
        purpose="Find significant price levels where reversals might occur",
        typical_usage="Entry/exit levels, stop-loss placement, target identification",
        common_timeframes=["4h", "1d", "1w"]
    ),
    
    IndicatorCategory.MULTI_PURPOSE: CategoryInfo(
        name="Multi-Purpose Indicators",
        description="Versatile indicators that can serve multiple analysis purposes",
        purpose="Provide comprehensive market analysis across different dimensions",
        typical_usage="Flexible analysis, confirmation across multiple timeframes",
        common_timeframes=["1h", "4h", "1d"]
    )
}


# Mapping of indicator classes to their primary categories
INDICATOR_CATEGORIES: Dict[str, IndicatorCategory] = {
    # Trend Indicators
    "SimpleMovingAverage": IndicatorCategory.TREND,
    "SMA": IndicatorCategory.TREND,
    "ExponentialMovingAverage": IndicatorCategory.TREND,
    "EMA": IndicatorCategory.TREND,
    "ParabolicSARIndicator": IndicatorCategory.TREND,
    "ParabolicSAR": IndicatorCategory.TREND,
    "IchimokuIndicator": IndicatorCategory.TREND,
    "Ichimoku": IndicatorCategory.TREND,
    "AroonIndicator": IndicatorCategory.TREND,
    "Aroon": IndicatorCategory.TREND,
    "ZigZagIndicator": IndicatorCategory.TREND,
    "ZigZag": IndicatorCategory.TREND,
    "ADXIndicator": IndicatorCategory.TREND,
    "ADX": IndicatorCategory.TREND,
    "AverageDirectionalIndex": IndicatorCategory.TREND,
    "SuperTrendIndicator": IndicatorCategory.TREND,
    "SuperTrend": IndicatorCategory.TREND,
    
    # Momentum Indicators
    "RSIIndicator": IndicatorCategory.MOMENTUM,
    "RSI": IndicatorCategory.MOMENTUM,
    "MACDIndicator": IndicatorCategory.MOMENTUM,
    "MACD": IndicatorCategory.MOMENTUM,
    "StochasticIndicator": IndicatorCategory.MOMENTUM,
    "Stochastic": IndicatorCategory.MOMENTUM,
    "WilliamsRIndicator": IndicatorCategory.MOMENTUM,
    "WilliamsR": IndicatorCategory.MOMENTUM,
    "RVIIndicator": IndicatorCategory.MOMENTUM,
    "RVI": IndicatorCategory.MOMENTUM,
    "MomentumIndicator": IndicatorCategory.MOMENTUM,
    "Momentum": IndicatorCategory.MOMENTUM,
    "ROCIndicator": IndicatorCategory.MOMENTUM,
    "ROC": IndicatorCategory.MOMENTUM,
    "CCIIndicator": IndicatorCategory.MOMENTUM,  # Can also be trend
    "CCI": IndicatorCategory.MOMENTUM,
    "FisherTransformIndicator": IndicatorCategory.MOMENTUM,
    "FisherTransform": IndicatorCategory.MOMENTUM,
    
    # Volatility Indicators
    "ATRIndicator": IndicatorCategory.VOLATILITY,
    "ATR": IndicatorCategory.VOLATILITY,
    "BollingerBandsIndicator": IndicatorCategory.VOLATILITY,
    "BollingerBands": IndicatorCategory.VOLATILITY,
    "DonchianChannelsIndicator": IndicatorCategory.VOLATILITY,
    "DonchianChannels": IndicatorCategory.VOLATILITY,
    "KeltnerChannelsIndicator": IndicatorCategory.VOLATILITY,
    "KeltnerChannels": IndicatorCategory.VOLATILITY,
    
    # Volume Indicators
    "OBVIndicator": IndicatorCategory.VOLUME,
    "OBV": IndicatorCategory.VOLUME,
    "MFIIndicator": IndicatorCategory.VOLUME,
    "MFI": IndicatorCategory.VOLUME,
    "VWAPIndicator": IndicatorCategory.VOLUME,
    "VWAP": IndicatorCategory.VOLUME,
    "ADLineIndicator": IndicatorCategory.VOLUME,
    "ADLine": IndicatorCategory.VOLUME,
    "AccumulationDistribution": IndicatorCategory.VOLUME,
    "CMFIndicator": IndicatorCategory.VOLUME,
    "CMF": IndicatorCategory.VOLUME,
    "ChaikinMoneyFlow": IndicatorCategory.VOLUME,
}


def get_indicator_category(indicator_name: str) -> IndicatorCategory:
    """
    Get the category for a given indicator.
    
    Args:
        indicator_name: Name of the indicator
        
    Returns:
        The category of the indicator
        
    Raises:
        KeyError: If indicator is not found in the mapping
    """
    if indicator_name not in INDICATOR_CATEGORIES:
        # Default to multi-purpose for unknown indicators
        return IndicatorCategory.MULTI_PURPOSE
    
    return INDICATOR_CATEGORIES[indicator_name]


def get_indicators_by_category(category: IndicatorCategory) -> List[str]:
    """
    Get all indicators in a specific category.
    
    Args:
        category: The category to filter by
        
    Returns:
        List of indicator names in the category
    """
    return [
        indicator for indicator, cat in INDICATOR_CATEGORIES.items()
        if cat == category
    ]


def get_all_categories() -> List[IndicatorCategory]:
    """
    Get all available indicator categories.
    
    Returns:
        List of all categories
    """
    return list(IndicatorCategory)


def get_category_info(category: IndicatorCategory) -> CategoryInfo:
    """
    Get detailed information about a category.
    
    Args:
        category: The category to get information for
        
    Returns:
        CategoryInfo object with details about the category
    """
    return CATEGORY_DESCRIPTIONS[category]


def get_category_summary() -> Dict[str, Dict[str, any]]:
    """
    Get a summary of all categories with their indicators.
    
    Returns:
        Dictionary mapping category names to their info and indicators
    """
    summary = {}
    
    for category in IndicatorCategory:
        indicators = get_indicators_by_category(category)
        info = get_category_info(category)
        
        summary[category.value] = {
            "info": {
                "name": info.name,
                "description": info.description,
                "purpose": info.purpose,
                "typical_usage": info.typical_usage,
                "common_timeframes": info.common_timeframes
            },
            "indicators": indicators,
            "count": len(indicators)
        }
    
    return summary