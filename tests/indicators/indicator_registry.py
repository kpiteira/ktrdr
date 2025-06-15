"""
Indicator registry for test validation.

This module maintains a registry of all indicators available for testing,
along with their reference values and test parameters. When new indicators
are added to the system, they should be registered here to ensure they are
automatically validated by the testing framework.
"""

import logging
from typing import Dict, Any, Type, List, Tuple, Optional, Callable

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
        SimpleMovingAverage,
        ExponentialMovingAverage,
        RSIIndicator,
    )
    from ktrdr.indicators.macd_indicator import MACDIndicator
    from ktrdr.indicators.stochastic_indicator import StochasticIndicator
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
        default_params={"fast_period": 12, "slow_period": 26, "signal_period": 9, "source": "close"},
        reference_datasets=["reference_dataset_1"],
        reference_values=REFERENCE_VALUES.get("MACD", {}),
        tolerance=TOLERANCES.get("MACD", 0.01),
        known_edge_cases=[
            # These edge cases test parameter validation during initialization
            # Note: These test __init__ parameter validation, not compute() method
        ]
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

    # Additional indicators would be registered here as they're added to the system


# Automatically register built-in indicators when this module is imported
register_builtin_indicators()
