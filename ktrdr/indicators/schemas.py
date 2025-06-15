"""
Parameter schemas for all technical indicators.

This module defines the parameter schemas for each indicator, including
type definitions, constraints, and validation rules.
"""

from typing import Dict
from ktrdr.indicators.parameter_schema import (
    ParameterSchema,
    ParameterDefinition,
    ParameterConstraint,
    ParameterType,
    less_than,
    greater_than,
)


# RSI Parameter Schema
RSI_SCHEMA = ParameterSchema(
    name="RSI",
    description="Relative Strength Index momentum oscillator",
    parameters=[
        ParameterDefinition(
            name="period",
            param_type=ParameterType.INT,
            description="Number of periods for RSI calculation",
            default=14,
            min_value=2,
            max_value=100,
        ),
        ParameterDefinition(
            name="source",
            param_type=ParameterType.STRING,
            description="Price column to use for calculation",
            default="close",
            options=["open", "high", "low", "close"],
        ),
    ],
)


# Simple Moving Average Parameter Schema
SMA_SCHEMA = ParameterSchema(
    name="SMA",
    description="Simple Moving Average trend indicator",
    parameters=[
        ParameterDefinition(
            name="period",
            param_type=ParameterType.INT,
            description="Number of periods for moving average",
            default=20,
            min_value=1,
            max_value=200,
        ),
        ParameterDefinition(
            name="source",
            param_type=ParameterType.STRING,
            description="Price column to use for calculation",
            default="close",
            options=["open", "high", "low", "close"],
        ),
    ],
)


# Exponential Moving Average Parameter Schema
EMA_SCHEMA = ParameterSchema(
    name="EMA",
    description="Exponential Moving Average trend indicator",
    parameters=[
        ParameterDefinition(
            name="period",
            param_type=ParameterType.INT,
            description="Number of periods for exponential moving average",
            default=20,
            min_value=1,
            max_value=200,
        ),
        ParameterDefinition(
            name="source",
            param_type=ParameterType.STRING,
            description="Price column to use for calculation",
            default="close",
            options=["open", "high", "low", "close"],
        ),
        ParameterDefinition(
            name="adjust",
            param_type=ParameterType.BOOL,
            description="Use adjustment for bias correction",
            default=True,
        ),
    ],
)


# MACD Parameter Schema
MACD_SCHEMA = ParameterSchema(
    name="MACD",
    description="Moving Average Convergence Divergence momentum indicator",
    parameters=[
        ParameterDefinition(
            name="fast_period",
            param_type=ParameterType.INT,
            description="Period for fast EMA",
            default=12,
            min_value=1,
            max_value=50,
        ),
        ParameterDefinition(
            name="slow_period",
            param_type=ParameterType.INT,
            description="Period for slow EMA",
            default=26,
            min_value=2,
            max_value=100,
        ),
        ParameterDefinition(
            name="signal_period",
            param_type=ParameterType.INT,
            description="Period for signal line EMA",
            default=9,
            min_value=1,
            max_value=50,
        ),
        ParameterDefinition(
            name="source",
            param_type=ParameterType.STRING,
            description="Price column to use for calculation",
            default="close",
            options=["open", "high", "low", "close"],
        ),
    ],
    constraints=[
        ParameterConstraint(
            name="fast_less_than_slow",
            description="Fast period must be less than slow period",
            validator=less_than("fast_period", "slow_period"),
            error_message="Fast period must be less than slow period for meaningful MACD calculation",
        )
    ],
)


# Stochastic Oscillator Parameter Schema (for upcoming implementation)
STOCHASTIC_SCHEMA = ParameterSchema(
    name="Stochastic",
    description="Stochastic Oscillator momentum indicator",
    parameters=[
        ParameterDefinition(
            name="k_period",
            param_type=ParameterType.INT,
            description="Period for %K calculation",
            default=14,
            min_value=1,
            max_value=100,
        ),
        ParameterDefinition(
            name="d_period",
            param_type=ParameterType.INT,
            description="Period for %D smoothing",
            default=3,
            min_value=1,
            max_value=20,
        ),
        ParameterDefinition(
            name="smooth_k",
            param_type=ParameterType.INT,
            description="Period for %K smoothing",
            default=3,
            min_value=1,
            max_value=20,
        ),
    ],
)


# Williams %R Parameter Schema (for upcoming implementation)
WILLIAMS_R_SCHEMA = ParameterSchema(
    name="WilliamsR",
    description="Williams %R momentum oscillator",
    parameters=[
        ParameterDefinition(
            name="period",
            param_type=ParameterType.INT,
            description="Lookback period for Williams %R",
            default=14,
            min_value=1,
            max_value=100,
        )
    ],
)


# Average True Range Parameter Schema (for upcoming implementation)
ATR_SCHEMA = ParameterSchema(
    name="ATR",
    description="Average True Range volatility indicator",
    parameters=[
        ParameterDefinition(
            name="period",
            param_type=ParameterType.INT,
            description="Period for ATR calculation",
            default=14,
            min_value=1,
            max_value=100,
        )
    ],
)


# On-Balance Volume Parameter Schema (for upcoming implementation)
OBV_SCHEMA = ParameterSchema(
    name="OBV",
    description="On-Balance Volume indicator",
    parameters=[
        # OBV typically doesn't have parameters besides source data
    ],
)


# Bollinger Bands Parameter Schema (for Phase 2)
BOLLINGER_BANDS_SCHEMA = ParameterSchema(
    name="BollingerBands",
    description="Bollinger Bands volatility indicator",
    parameters=[
        ParameterDefinition(
            name="period",
            param_type=ParameterType.INT,
            description="Period for moving average and standard deviation",
            default=20,
            min_value=2,
            max_value=100,
        ),
        ParameterDefinition(
            name="multiplier",
            param_type=ParameterType.FLOAT,
            description="Number of standard deviations for bands",
            default=2.0,
            min_value=0.1,
            max_value=5.0,
        ),
        ParameterDefinition(
            name="source",
            param_type=ParameterType.STRING,
            description="Price column to use for calculation",
            default="close",
            options=["open", "high", "low", "close"],
        ),
    ],
)


# Commodity Channel Index Parameter Schema (for Phase 2)
CCI_SCHEMA = ParameterSchema(
    name="CCI",
    description="Commodity Channel Index momentum oscillator",
    parameters=[
        ParameterDefinition(
            name="period",
            param_type=ParameterType.INT,
            description="Period for CCI calculation",
            default=20,
            min_value=2,
            max_value=100,
        )
    ],
)


# Momentum Parameter Schema (for Phase 2)
MOMENTUM_SCHEMA = ParameterSchema(
    name="Momentum",
    description="Momentum oscillator",
    parameters=[
        ParameterDefinition(
            name="period",
            param_type=ParameterType.INT,
            description="Lookback period for momentum calculation",
            default=10,
            min_value=1,
            max_value=100,
        ),
        ParameterDefinition(
            name="source",
            param_type=ParameterType.STRING,
            description="Price column to use for calculation",
            default="close",
            options=["open", "high", "low", "close"],
        ),
    ],
)


# Rate of Change Parameter Schema (for Phase 2)
ROC_SCHEMA = ParameterSchema(
    name="ROC",
    description="Rate of Change momentum oscillator",
    parameters=[
        ParameterDefinition(
            name="period",
            param_type=ParameterType.INT,
            description="Lookback period for ROC calculation",
            default=10,
            min_value=1,
            max_value=100,
        ),
        ParameterDefinition(
            name="source",
            param_type=ParameterType.STRING,
            description="Price column to use for calculation",
            default="close",
            options=["open", "high", "low", "close"],
        ),
    ],
)


# Volume Weighted Average Price Parameter Schema (for Phase 2)
VWAP_SCHEMA = ParameterSchema(
    name="VWAP",
    description="Volume Weighted Average Price indicator",
    parameters=[
        ParameterDefinition(
            name="period",
            param_type=ParameterType.INT,
            description="Period for rolling VWAP (0 for cumulative)",
            default=20,
            min_value=0,
            max_value=200,
        ),
        ParameterDefinition(
            name="use_typical_price",
            param_type=ParameterType.BOOL,
            description="Use typical price (H+L+C)/3 vs close price",
            default=True,
        ),
    ],
)


# Parabolic SAR Parameter Schema (for Phase 3)
PARABOLIC_SAR_SCHEMA = ParameterSchema(
    name="ParabolicSAR",
    description="Parabolic Stop and Reverse trend-following indicator",
    parameters=[
        ParameterDefinition(
            name="initial_af",
            param_type=ParameterType.FLOAT,
            description="Initial acceleration factor",
            default=0.02,
            min_value=0.001,
            max_value=0.1,
        ),
        ParameterDefinition(
            name="step_af",
            param_type=ParameterType.FLOAT,
            description="Acceleration factor increment",
            default=0.02,
            min_value=0.001,
            max_value=0.1,
        ),
        ParameterDefinition(
            name="max_af",
            param_type=ParameterType.FLOAT,
            description="Maximum acceleration factor",
            default=0.20,
            min_value=0.01,
            max_value=1.0,
        ),
    ],
)


# Ichimoku Cloud Parameter Schema (for Phase 3)
ICHIMOKU_SCHEMA = ParameterSchema(
    name="Ichimoku",
    description="Ichimoku Cloud comprehensive trend analysis system",
    parameters=[
        ParameterDefinition(
            name="tenkan_period",
            param_type=ParameterType.INT,
            description="Period for Tenkan-sen (Conversion Line)",
            default=9,
            min_value=1,
            max_value=50,
        ),
        ParameterDefinition(
            name="kijun_period",
            param_type=ParameterType.INT,
            description="Period for Kijun-sen (Base Line)",
            default=26,
            min_value=1,
            max_value=100,
        ),
        ParameterDefinition(
            name="senkou_b_period",
            param_type=ParameterType.INT,
            description="Period for Senkou Span B (Leading Span B)",
            default=52,
            min_value=1,
            max_value=200,
        ),
        ParameterDefinition(
            name="displacement",
            param_type=ParameterType.INT,
            description="Displacement for Senkou spans and Chikou span",
            default=26,
            min_value=1,
            max_value=100,
        ),
    ],
)


# RVI Parameter Schema
RVI_SCHEMA = ParameterSchema(
    name="RVI",
    description="Relative Vigor Index momentum oscillator",
    parameters=[
        ParameterDefinition(
            name="period",
            param_type=ParameterType.INT,
            description="Period for RVI calculation",
            default=10,
            min_value=4,
            max_value=100,
        ),
        ParameterDefinition(
            name="signal_period",
            param_type=ParameterType.INT,
            description="Period for signal line calculation",
            default=4,
            min_value=1,
            max_value=50,
        ),
    ],
)


# MFI Parameter Schema
MFI_SCHEMA = ParameterSchema(
    name="MFI",
    description="Money Flow Index volume-weighted momentum oscillator",
    parameters=[
        ParameterDefinition(
            name="period",
            param_type=ParameterType.INT,
            description="Period for MFI calculation",
            default=14,
            min_value=1,
            max_value=100,
        ),
    ],
)


# Registry of all parameter schemas
PARAMETER_SCHEMAS = {
    "RSI": RSI_SCHEMA,
    "SMA": SMA_SCHEMA,
    "EMA": EMA_SCHEMA,
    "MACD": MACD_SCHEMA,
    "Stochastic": STOCHASTIC_SCHEMA,
    "WilliamsR": WILLIAMS_R_SCHEMA,
    "ATR": ATR_SCHEMA,
    "OBV": OBV_SCHEMA,
    "BollingerBands": BOLLINGER_BANDS_SCHEMA,
    "CCI": CCI_SCHEMA,
    "Momentum": MOMENTUM_SCHEMA,
    "ROC": ROC_SCHEMA,
    "VWAP": VWAP_SCHEMA,
    "ParabolicSAR": PARABOLIC_SAR_SCHEMA,
    "Ichimoku": ICHIMOKU_SCHEMA,
    "RVI": RVI_SCHEMA,
    "MFI": MFI_SCHEMA,
}


def get_schema(indicator_name: str) -> ParameterSchema:
    """
    Get parameter schema for an indicator.

    Args:
        indicator_name: Name of the indicator

    Returns:
        Parameter schema for the indicator

    Raises:
        KeyError: If indicator schema not found
    """
    if indicator_name not in PARAMETER_SCHEMAS:
        raise KeyError(f"No parameter schema found for indicator '{indicator_name}'")

    return PARAMETER_SCHEMAS[indicator_name]


def list_schemas() -> Dict[str, str]:
    """
    List all available parameter schemas.

    Returns:
        Dictionary mapping indicator names to descriptions
    """
    return {name: schema.description for name, schema in PARAMETER_SCHEMAS.items()}
