"""
Technical indicators module for the KTRDR system.

This module contains implementations of various technical indicators
used for trading analysis and decision making.

Indicators auto-register with INDICATOR_REGISTRY when their modules are imported.
Use ensure_all_registered() to load all indicators for API/validation use cases.

For specific indicator classes, import from their modules directly:
    from ktrdr.indicators.rsi_indicator import RSIIndicator
    from ktrdr.indicators.ma_indicators import SimpleMovingAverage
"""

from ktrdr.indicators.base_indicator import INDICATOR_REGISTRY, BaseIndicator
from ktrdr.indicators.indicator_engine import IndicatorEngine

# List of all indicator modules for lazy loading
_INDICATOR_MODULES = [
    # Momentum
    "ktrdr.indicators.rsi_indicator",
    "ktrdr.indicators.roc_indicator",
    "ktrdr.indicators.momentum_indicator",
    "ktrdr.indicators.cci_indicator",
    "ktrdr.indicators.williams_r_indicator",
    "ktrdr.indicators.stochastic_indicator",
    "ktrdr.indicators.rvi_indicator",
    "ktrdr.indicators.fisher_transform",
    "ktrdr.indicators.aroon_indicator",
    # Volatility
    "ktrdr.indicators.atr_indicator",
    "ktrdr.indicators.bollinger_bands_indicator",
    "ktrdr.indicators.bollinger_band_width_indicator",
    "ktrdr.indicators.keltner_channels",
    "ktrdr.indicators.donchian_channels",
    "ktrdr.indicators.supertrend_indicator",
    # Trend
    "ktrdr.indicators.ma_indicators",
    "ktrdr.indicators.macd_indicator",
    "ktrdr.indicators.adx_indicator",
    "ktrdr.indicators.parabolic_sar_indicator",
    "ktrdr.indicators.ichimoku_indicator",
    # Volume
    "ktrdr.indicators.obv_indicator",
    "ktrdr.indicators.vwap_indicator",
    "ktrdr.indicators.mfi_indicator",
    "ktrdr.indicators.cmf_indicator",
    "ktrdr.indicators.ad_line",
    # Other
    "ktrdr.indicators.volume_ratio_indicator",
    "ktrdr.indicators.distance_from_ma_indicator",
    "ktrdr.indicators.squeeze_intensity_indicator",
    "ktrdr.indicators.zigzag_indicator",
]

_all_loaded = False


def ensure_all_registered() -> int:
    """
    Ensure all indicators are loaded and registered.

    Call this function when you need access to the full indicator registry,
    such as for API endpoints listing all indicators or validation.

    Returns:
        Number of registered indicator types.
    """
    global _all_loaded
    if _all_loaded:
        return len(INDICATOR_REGISTRY.list_types())

    import importlib

    for module_name in _INDICATOR_MODULES:
        importlib.import_module(module_name)

    _all_loaded = True
    return len(INDICATOR_REGISTRY.list_types())


__all__ = [
    # Core
    "BaseIndicator",
    "INDICATOR_REGISTRY",
    "IndicatorEngine",
    "ensure_all_registered",
]
