"""
Indicator registry for test validation.

This module maintains a registry of all indicators available for testing,
along with their reference values and test parameters. When new indicators
are added to the system, they should be registered here to ensure they are
automatically validated by the testing framework.
"""

import logging
from typing import Any, Dict, List, Type

from ktrdr.indicators import BaseIndicator

# Setup logger
logger = logging.getLogger(__name__)

# Global registry for indicators and their validation data
INDICATOR_REGISTRY = {}


def register_indicator(
    indicator_class: Type[BaseIndicator],
    default_params: Dict[str, Any] = None,
    reference_datasets: List[str] = None,
    reference_values: Dict[str, Dict[int, float]] = None,
    tolerance: float = 0.01,
    known_edge_cases: List[Dict[str, Any]] = None,
):
    """
    Register an indicator for automated validation.

    Args:
        indicator_class: The indicator class to register
        default_params: Default parameters for testing the indicator
        reference_datasets: Names of datasets to use for testing this indicator
        reference_values: Reference values for each dataset indexed by position
        tolerance: Default tolerance for validation
        known_edge_cases: List of edge cases to test specifically for this indicator
    """
    indicator_name = indicator_class.__name__

    if indicator_name in INDICATOR_REGISTRY:
        logger.warning(f"Indicator {indicator_name} already registered, overwriting")

    INDICATOR_REGISTRY[indicator_name] = {
        "class": indicator_class,
        "default_params": default_params or {},
        "reference_datasets": reference_datasets or ["reference_dataset_1"],
        "reference_values": reference_values or {},
        "tolerance": tolerance,
        "known_edge_cases": known_edge_cases or [],
    }

    logger.info(f"Registered indicator {indicator_name} for automated validation")


def get_registered_indicators() -> Dict[str, Dict[str, Any]]:
    """
    Get all registered indicators and their validation data.

    Returns:
        Dictionary of registered indicators
    """
    return INDICATOR_REGISTRY


def is_indicator_registered(indicator_name: str) -> bool:
    """
    Check if an indicator is registered.

    Args:
        indicator_name: Name of the indicator class

    Returns:
        True if the indicator is registered, False otherwise
    """
    return indicator_name in INDICATOR_REGISTRY


def register_builtin_indicators():
    """
    Register all built-in indicators with their validation parameters.
    This function should be updated whenever a new indicator is added to the system.
    """
    from ktrdr.indicators import (
        ExponentialMovingAverage,
        RSIIndicator,
        SimpleMovingAverage,
    )
    from ktrdr.indicators.aroon_indicator import AroonIndicator
    from ktrdr.indicators.atr_indicator import ATRIndicator
    from ktrdr.indicators.bollinger_bands_indicator import BollingerBandsIndicator
    from ktrdr.indicators.cci_indicator import CCIIndicator
    from ktrdr.indicators.ichimoku_indicator import IchimokuIndicator
    from ktrdr.indicators.macd_indicator import MACDIndicator
    from ktrdr.indicators.mfi_indicator import MFIIndicator
    from ktrdr.indicators.momentum_indicator import MomentumIndicator
    from ktrdr.indicators.obv_indicator import OBVIndicator
    from ktrdr.indicators.parabolic_sar_indicator import ParabolicSARIndicator
    from ktrdr.indicators.roc_indicator import ROCIndicator
    from ktrdr.indicators.rvi_indicator import RVIIndicator
    from ktrdr.indicators.stochastic_indicator import StochasticIndicator
    from ktrdr.indicators.vwap_indicator import VWAPIndicator
    from ktrdr.indicators.williams_r_indicator import WilliamsRIndicator

    from .reference_datasets import REFERENCE_VALUES, TOLERANCES

    # Register Simple Moving Average
    register_indicator(
        indicator_class=SimpleMovingAverage,
        default_params={"period": 10, "source": "close"},
        reference_datasets=["reference_dataset_1", "reference_dataset_2"],
        reference_values=REFERENCE_VALUES.get("SMA", {}),
        tolerance=TOLERANCES.get("SMA", 0.5),
    )

    # Register Exponential Moving Average
    register_indicator(
        indicator_class=ExponentialMovingAverage,
        default_params={"period": 10, "source": "close", "adjust": True},
        reference_datasets=["reference_dataset_1", "reference_dataset_2"],
        reference_values=REFERENCE_VALUES.get("EMA", {}),
        tolerance=TOLERANCES.get("EMA", 5.0),
    )

    # Register RSI Indicator
    register_indicator(
        indicator_class=RSIIndicator,
        default_params={"period": 14, "source": "close"},
        reference_datasets=["reference_dataset_3"],
        reference_values=REFERENCE_VALUES.get("RSI", {}),
        tolerance=TOLERANCES.get("RSI", 5.0),
    )

    # Register MACD Indicator
    register_indicator(
        indicator_class=MACDIndicator,
        default_params={
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "source": "close",
        },
        reference_datasets=["reference_dataset_1"],
        reference_values=REFERENCE_VALUES.get("MACD", {}),
        tolerance=TOLERANCES.get("MACD", 0.01),
        known_edge_cases=[
            # These edge cases test parameter validation during initialization
            # Note: These test __init__ parameter validation, not compute() method
        ],
    )

    # Register Stochastic Oscillator
    register_indicator(
        indicator_class=StochasticIndicator,
        default_params={"k_period": 14, "d_period": 3, "smooth_k": 3},
        reference_datasets=["reference_dataset_1"],
        reference_values=REFERENCE_VALUES.get("Stochastic", {}),
        tolerance=TOLERANCES.get("Stochastic", 0.1),
    )

    # Register Williams %R
    register_indicator(
        indicator_class=WilliamsRIndicator,
        default_params={"period": 14},
        reference_datasets=["reference_dataset_1"],
        reference_values=REFERENCE_VALUES.get("WilliamsR", {}),
        tolerance=TOLERANCES.get("WilliamsR", 0.1),
    )

    # Register ATR
    register_indicator(
        indicator_class=ATRIndicator,
        default_params={"period": 14},
        reference_datasets=["reference_dataset_1"],
        reference_values=REFERENCE_VALUES.get("ATR", {}),
        tolerance=TOLERANCES.get("ATR", 0.1),
    )

    # Register OBV
    register_indicator(
        indicator_class=OBVIndicator,
        default_params={},  # OBV has no parameters
        reference_datasets=["reference_dataset_obv"],
        reference_values=REFERENCE_VALUES.get("OBV", {}),
        tolerance=TOLERANCES.get("OBV", 0.01),
    )

    # Register Bollinger Bands
    register_indicator(
        indicator_class=BollingerBandsIndicator,
        default_params={"period": 20, "multiplier": 2.0, "source": "close"},
        reference_datasets=["reference_dataset_1"],
        reference_values=REFERENCE_VALUES.get("BollingerBands", {}),
        tolerance=TOLERANCES.get("BollingerBands", 0.1),
    )

    # Register CCI
    register_indicator(
        indicator_class=CCIIndicator,
        default_params={"period": 20},
        reference_datasets=["reference_dataset_1"],
        reference_values=REFERENCE_VALUES.get("CCI", {}),
        tolerance=TOLERANCES.get("CCI", 0.1),
    )

    # Register Momentum
    register_indicator(
        indicator_class=MomentumIndicator,
        default_params={"period": 10, "source": "close"},
        reference_datasets=["reference_dataset_1"],
        reference_values=REFERENCE_VALUES.get("Momentum", {}),
        tolerance=TOLERANCES.get("Momentum", 0.01),
    )

    # Register ROC (Rate of Change)
    register_indicator(
        indicator_class=ROCIndicator,
        default_params={"period": 10, "source": "close"},
        reference_datasets=["reference_dataset_1"],
        reference_values=REFERENCE_VALUES.get("ROC", {}),
        tolerance=TOLERANCES.get("ROC", 0.01),
    )

    # Register VWAP (Volume Weighted Average Price)
    register_indicator(
        indicator_class=VWAPIndicator,
        default_params={"period": 20, "use_typical_price": True},
        reference_datasets=["reference_dataset_1"],
        reference_values=REFERENCE_VALUES.get("VWAP", {}),
        tolerance=TOLERANCES.get("VWAP", 0.01),
    )

    # Register Parabolic SAR (Stop and Reverse)
    register_indicator(
        indicator_class=ParabolicSARIndicator,
        default_params={"initial_af": 0.02, "step_af": 0.02, "max_af": 0.20},
        reference_datasets=["reference_dataset_1"],
        reference_values=REFERENCE_VALUES.get("ParabolicSAR", {}),
        tolerance=TOLERANCES.get("ParabolicSAR", 0.01),
    )

    # Register Ichimoku Cloud
    register_indicator(
        indicator_class=IchimokuIndicator,
        default_params={
            "tenkan_period": 9,
            "kijun_period": 26,
            "senkou_b_period": 52,
            "displacement": 26,
        },
        reference_datasets=["reference_dataset_ichimoku"],
        reference_values=REFERENCE_VALUES.get("Ichimoku", {}),
        tolerance=TOLERANCES.get("Ichimoku", 0.01),
    )

    # Register RVI (Relative Vigor Index)
    register_indicator(
        indicator_class=RVIIndicator,
        default_params={"period": 10, "signal_period": 4},
        reference_datasets=["reference_dataset_rvi"],
        reference_values=REFERENCE_VALUES.get("RVI", {}),
        tolerance=TOLERANCES.get("RVI", 0.01),
    )

    # Register MFI (Money Flow Index)
    register_indicator(
        indicator_class=MFIIndicator,
        default_params={"period": 14},
        reference_datasets=["reference_dataset_mfi"],
        reference_values=REFERENCE_VALUES.get("MFI", {}),
        tolerance=TOLERANCES.get("MFI", 0.01),
    )

    # Register Aroon Indicator
    register_indicator(
        indicator_class=AroonIndicator,
        default_params={"period": 14, "include_oscillator": False},
        reference_datasets=["reference_dataset_aroon"],
        reference_values=REFERENCE_VALUES.get("Aroon", {}),
        tolerance=TOLERANCES.get("Aroon", 0.01),
    )

    # Additional indicators would be registered here as they're added to the system


# Automatically register built-in indicators when this module is imported
register_builtin_indicators()
