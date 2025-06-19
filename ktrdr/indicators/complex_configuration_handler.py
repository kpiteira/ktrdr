"""Handler for complex multi-indicator configurations.

This module provides intelligent handling of indicator configurations that may
require more data than available, with graceful degradation and fallback strategies.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from enum import Enum
import warnings

from ktrdr import get_logger
from ktrdr.indicators.multi_timeframe_indicator_engine import (
    MultiTimeframeIndicatorEngine,
    TimeframeIndicatorConfig,
)
from ktrdr.indicators.indicator_engine import IndicatorEngine
from ktrdr.errors import ProcessingError, ConfigurationError

logger = get_logger(__name__)


class FallbackStrategy(Enum):
    """Strategies for handling insufficient data."""

    SKIP = "skip"  # Skip indicators that need more data
    REDUCE_PERIOD = "reduce_period"  # Reduce indicator periods to fit available data
    PAD_DATA = "pad_data"  # Pad data with synthetic values
    WARN_AND_CONTINUE = "warn_and_continue"  # Warn but compute with available data


@dataclass
class IndicatorRequirement:
    """Requirements for an indicator."""

    indicator_type: str
    minimum_data_points: int
    recommended_data_points: int
    parameters: Dict[str, Any]
    fallback_parameters: Optional[Dict[str, Any]] = None


@dataclass
class DataAvailability:
    """Information about available data."""

    timeframe: str
    total_points: int
    valid_points: int  # Non-NaN points
    date_range: Tuple[pd.Timestamp, pd.Timestamp]


@dataclass
class ConfigurationIssue:
    """Description of a configuration issue."""

    timeframe: str
    indicator_type: str
    issue_type: str
    message: str
    suggested_fix: Optional[str] = None


class ComplexConfigurationHandler:
    """Handles complex multi-indicator configurations with intelligent fallbacks."""

    def __init__(
        self, fallback_strategy: FallbackStrategy = FallbackStrategy.REDUCE_PERIOD
    ):
        """
        Initialize the configuration handler.

        Args:
            fallback_strategy: Strategy to use when indicators need more data than available
        """
        self.fallback_strategy = fallback_strategy
        self.logger = get_logger(__name__)

        # Known indicator requirements
        self.indicator_requirements = {
            "RSI": IndicatorRequirement(
                indicator_type="RSI",
                minimum_data_points=2,
                recommended_data_points=50,  # For reliable RSI
                parameters={"period": 14},
                fallback_parameters={"period": 7},  # Shorter period if needed
            ),
            "SimpleMovingAverage": IndicatorRequirement(
                indicator_type="SimpleMovingAverage",
                minimum_data_points=1,
                recommended_data_points=None,  # Depends on period
                parameters={"period": 20},
                fallback_parameters={"period": 10},
            ),
            "ExponentialMovingAverage": IndicatorRequirement(
                indicator_type="ExponentialMovingAverage",
                minimum_data_points=1,
                recommended_data_points=None,
                parameters={"period": 20},
                fallback_parameters={"period": 10},
            ),
            "MACD": IndicatorRequirement(
                indicator_type="MACD",
                minimum_data_points=26,  # Needs at least slow_period
                recommended_data_points=100,  # For reliable MACD
                parameters={"fast_period": 12, "slow_period": 26, "signal_period": 9},
                fallback_parameters={
                    "fast_period": 6,
                    "slow_period": 13,
                    "signal_period": 5,
                },
            ),
            "BollingerBands": IndicatorRequirement(
                indicator_type="BollingerBands",
                minimum_data_points=2,
                recommended_data_points=None,
                parameters={"period": 20, "std_dev": 2},
                fallback_parameters={"period": 10, "std_dev": 2},
            ),
            "StochasticOscillator": IndicatorRequirement(
                indicator_type="StochasticOscillator",
                minimum_data_points=14,
                recommended_data_points=50,
                parameters={"k_period": 14, "d_period": 3, "smooth_k": 3},
                fallback_parameters={"k_period": 7, "d_period": 3, "smooth_k": 1},
            ),
            "ATR": IndicatorRequirement(
                indicator_type="ATR",
                minimum_data_points=2,
                recommended_data_points=None,
                parameters={"period": 14},
                fallback_parameters={"period": 7},
            ),
        }

    def analyze_data_availability(
        self, data: Dict[str, pd.DataFrame]
    ) -> Dict[str, DataAvailability]:
        """
        Analyze available data for each timeframe.

        Args:
            data: Dictionary of timeframe data

        Returns:
            Dictionary of data availability information
        """
        availability = {}

        for timeframe, df in data.items():
            if df.empty:
                availability[timeframe] = DataAvailability(
                    timeframe=timeframe,
                    total_points=0,
                    valid_points=0,
                    date_range=(pd.Timestamp.min, pd.Timestamp.min),
                )
                continue

            # Count valid data points (non-NaN close prices)
            valid_close = df["close"].notna().sum() if "close" in df.columns else 0

            # Get date range
            if "timestamp" in df.columns:
                timestamps = pd.to_datetime(df["timestamp"])
                date_range = (timestamps.min(), timestamps.max())
            else:
                date_range = (pd.Timestamp.min, pd.Timestamp.min)

            availability[timeframe] = DataAvailability(
                timeframe=timeframe,
                total_points=len(df),
                valid_points=valid_close,
                date_range=date_range,
            )

        return availability

    def validate_configuration(
        self,
        timeframe_configs: List[TimeframeIndicatorConfig],
        data_availability: Dict[str, DataAvailability],
    ) -> Tuple[List[ConfigurationIssue], List[TimeframeIndicatorConfig]]:
        """
        Validate configuration against available data and suggest fixes.

        Args:
            timeframe_configs: List of timeframe configurations
            data_availability: Available data information

        Returns:
            Tuple of (issues found, corrected configurations)
        """
        issues = []
        corrected_configs = []

        for config in timeframe_configs:
            timeframe = config.timeframe

            if timeframe not in data_availability:
                issues.append(
                    ConfigurationIssue(
                        timeframe=timeframe,
                        indicator_type="ALL",
                        issue_type="MISSING_DATA",
                        message=f"No data available for timeframe {timeframe}",
                        suggested_fix="Provide data for this timeframe or remove from configuration",
                    )
                )
                continue

            availability = data_availability[timeframe]
            corrected_indicators = []

            for indicator_config in config.indicators:
                indicator_type = indicator_config.get("type", "Unknown")
                params = indicator_config.get("params", {})

                # Check if we know about this indicator
                if indicator_type not in self.indicator_requirements:
                    self.logger.warning(f"Unknown indicator type: {indicator_type}")
                    corrected_indicators.append(indicator_config)
                    continue

                # Get requirements
                requirements = self.indicator_requirements[indicator_type]

                # Calculate required data points
                required_points = self._calculate_required_points(
                    indicator_type, params
                )

                if required_points > availability.valid_points:
                    # Insufficient data
                    issue = ConfigurationIssue(
                        timeframe=timeframe,
                        indicator_type=indicator_type,
                        issue_type="INSUFFICIENT_DATA",
                        message=f"{indicator_type} needs {required_points} points, "
                        f"but only {availability.valid_points} available",
                        suggested_fix=self._suggest_fix(
                            indicator_type, params, availability.valid_points
                        ),
                    )
                    issues.append(issue)

                    # Apply fallback strategy
                    corrected_config = self._apply_fallback_strategy(
                        indicator_config, availability.valid_points, requirements
                    )

                    if corrected_config:
                        corrected_indicators.append(corrected_config)
                else:
                    # Configuration is fine
                    corrected_indicators.append(indicator_config)

            # Create corrected timeframe config
            corrected_config = TimeframeIndicatorConfig(
                timeframe=config.timeframe,
                indicators=corrected_indicators,
                enabled=config.enabled,
                weight=config.weight,
            )
            corrected_configs.append(corrected_config)

        return issues, corrected_configs

    def _calculate_required_points(
        self, indicator_type: str, params: Dict[str, Any]
    ) -> int:
        """Calculate required data points for an indicator."""

        if indicator_type == "RSI":
            period = params.get("period", 14)
            return max(period * 2, 20)  # Need 2x period for reliable RSI

        elif indicator_type in ["SimpleMovingAverage", "ExponentialMovingAverage"]:
            period = params.get("period", 20)
            return period

        elif indicator_type == "MACD":
            slow_period = params.get("slow_period", 26)
            signal_period = params.get("signal_period", 9)
            return slow_period + signal_period + 10  # Extra buffer for signal line

        elif indicator_type == "BollingerBands":
            period = params.get("period", 20)
            return period

        elif indicator_type == "StochasticOscillator":
            k_period = params.get("k_period", 14)
            d_period = params.get("d_period", 3)
            smooth_k = params.get("smooth_k", 3)
            return k_period + d_period + smooth_k

        elif indicator_type == "ATR":
            period = params.get("period", 14)
            return period + 1  # ATR needs period + 1 for previous close calculation

        else:
            # Default assumption
            return params.get("period", 20)

    def _suggest_fix(
        self, indicator_type: str, params: Dict[str, Any], available_points: int
    ) -> str:
        """Suggest a fix for insufficient data."""

        if indicator_type in ["SimpleMovingAverage", "ExponentialMovingAverage"]:
            max_period = max(1, available_points - 1)
            return f"Reduce period to {max_period} or less"

        elif indicator_type == "RSI":
            max_period = max(2, available_points // 3)
            return f"Reduce period to {max_period} or less"

        elif indicator_type == "MACD":
            max_slow = max(5, available_points // 2)
            max_fast = max(3, max_slow // 2)
            return f"Reduce periods: fast_period={max_fast}, slow_period={max_slow}"

        elif indicator_type == "BollingerBands":
            max_period = max(2, available_points - 1)
            return f"Reduce period to {max_period}"

        else:
            return f"Reduce parameters to fit {available_points} available data points"

    def _apply_fallback_strategy(
        self,
        indicator_config: Dict[str, Any],
        available_points: int,
        requirements: IndicatorRequirement,
    ) -> Optional[Dict[str, Any]]:
        """Apply the configured fallback strategy."""

        if self.fallback_strategy == FallbackStrategy.SKIP:
            self.logger.info(
                f"Skipping {indicator_config['type']} due to insufficient data"
            )
            return None

        elif self.fallback_strategy == FallbackStrategy.REDUCE_PERIOD:
            return self._reduce_indicator_periods(indicator_config, available_points)

        elif self.fallback_strategy == FallbackStrategy.WARN_AND_CONTINUE:
            self.logger.warning(
                f"Computing {indicator_config['type']} with insufficient data"
            )
            return indicator_config

        elif self.fallback_strategy == FallbackStrategy.PAD_DATA:
            # This would require modifying the data, not just the config
            self.logger.warning(
                f"PAD_DATA strategy not implemented, using REDUCE_PERIOD"
            )
            return self._reduce_indicator_periods(indicator_config, available_points)

        else:
            return indicator_config

    def _reduce_indicator_periods(
        self, indicator_config: Dict[str, Any], available_points: int
    ) -> Dict[str, Any]:
        """Reduce indicator periods to fit available data."""

        corrected_config = indicator_config.copy()
        params = corrected_config.get("params", {}).copy()
        indicator_type = indicator_config["type"]

        if indicator_type in ["SimpleMovingAverage", "ExponentialMovingAverage"]:
            original_period = params.get("period", 20)
            max_period = max(1, available_points - 1)
            new_period = min(original_period, max_period)
            params["period"] = new_period

            if new_period != original_period:
                self.logger.info(
                    f"Reduced {indicator_type} period from {original_period} to {new_period}"
                )

        elif indicator_type == "RSI":
            original_period = params.get("period", 14)
            max_period = max(2, available_points // 3)
            new_period = min(original_period, max_period)
            params["period"] = new_period

            if new_period != original_period:
                self.logger.info(
                    f"Reduced RSI period from {original_period} to {new_period}"
                )

        elif indicator_type == "MACD":
            original_fast = params.get("fast_period", 12)
            original_slow = params.get("slow_period", 26)
            original_signal = params.get("signal_period", 9)

            max_slow = max(5, (available_points - 10) // 2)
            max_fast = max(3, max_slow // 2)

            new_slow = min(original_slow, max_slow)
            new_fast = min(original_fast, max_fast)
            new_signal = min(original_signal, available_points - new_slow)

            params.update(
                {
                    "fast_period": new_fast,
                    "slow_period": new_slow,
                    "signal_period": max(1, new_signal),
                }
            )

            if new_slow != original_slow or new_fast != original_fast:
                self.logger.info(
                    f"Reduced MACD periods: {original_fast}/{original_slow}/{original_signal} "
                    f"-> {new_fast}/{new_slow}/{params['signal_period']}"
                )

        elif indicator_type == "BollingerBands":
            original_period = params.get("period", 20)
            max_period = max(2, available_points - 1)
            new_period = min(original_period, max_period)
            params["period"] = new_period

            if new_period != original_period:
                self.logger.info(
                    f"Reduced BollingerBands period from {original_period} to {new_period}"
                )

        elif indicator_type == "StochasticOscillator":
            original_k = params.get("k_period", 14)
            max_k = max(3, available_points // 3)
            new_k = min(original_k, max_k)
            params["k_period"] = new_k

            if new_k != original_k:
                self.logger.info(
                    f"Reduced Stochastic k_period from {original_k} to {new_k}"
                )

        elif indicator_type == "ATR":
            original_period = params.get("period", 14)
            # ATR needs period + 1 data points (for previous close calculation)
            max_period = max(1, available_points - 2)
            new_period = min(original_period, max_period)
            params["period"] = new_period

            if new_period != original_period:
                self.logger.info(
                    f"Reduced ATR period from {original_period} to {new_period}"
                )

        corrected_config["params"] = params
        return corrected_config

    def create_adaptive_configuration(
        self,
        base_configs: List[TimeframeIndicatorConfig],
        data: Dict[str, pd.DataFrame],
    ) -> Tuple[List[TimeframeIndicatorConfig], List[ConfigurationIssue]]:
        """
        Create an adaptive configuration that works with available data.

        Args:
            base_configs: Base configurations to adapt
            data: Available data

        Returns:
            Tuple of (adapted configurations, issues found)
        """
        # Analyze data availability
        availability = self.analyze_data_availability(data)

        # Validate and correct configurations
        issues, corrected_configs = self.validate_configuration(
            base_configs, availability
        )

        # Log summary
        if issues:
            self.logger.warning(f"Found {len(issues)} configuration issues")
            for issue in issues:
                self.logger.warning(
                    f"{issue.timeframe}/{issue.indicator_type}: {issue.message}"
                )

        self.logger.info(
            f"Created adaptive configuration with {len(corrected_configs)} timeframes"
        )

        return corrected_configs, issues

    def suggest_minimum_data_requirements(
        self, timeframe_configs: List[TimeframeIndicatorConfig]
    ) -> Dict[str, int]:
        """
        Suggest minimum data requirements for the given configuration.

        Args:
            timeframe_configs: Timeframe configurations

        Returns:
            Dictionary mapping timeframes to minimum required data points
        """
        requirements = {}

        for config in timeframe_configs:
            timeframe = config.timeframe
            max_required = 0

            for indicator_config in config.indicators:
                indicator_type = indicator_config.get("type", "Unknown")
                params = indicator_config.get("params", {})

                required = self._calculate_required_points(indicator_type, params)
                max_required = max(max_required, required)

            requirements[timeframe] = max_required

        return requirements


def create_robust_configuration(
    base_configs: List[TimeframeIndicatorConfig],
    data: Dict[str, pd.DataFrame],
    fallback_strategy: FallbackStrategy = FallbackStrategy.REDUCE_PERIOD,
) -> Tuple[MultiTimeframeIndicatorEngine, List[ConfigurationIssue]]:
    """
    Create a robust multi-timeframe indicator engine that adapts to available data.

    Args:
        base_configs: Base configurations to adapt
        data: Available data
        fallback_strategy: Strategy for handling insufficient data

    Returns:
        Tuple of (configured engine, issues found)
    """
    handler = ComplexConfigurationHandler(fallback_strategy)

    # Create adaptive configuration
    adapted_configs, issues = handler.create_adaptive_configuration(base_configs, data)

    # Create engine with adapted configuration
    engine = MultiTimeframeIndicatorEngine(adapted_configs)

    return engine, issues


def validate_configuration_feasibility(
    timeframe_configs: List[TimeframeIndicatorConfig], data: Dict[str, pd.DataFrame]
) -> Dict[str, Any]:
    """
    Validate if a configuration is feasible with available data.

    Args:
        timeframe_configs: Configurations to validate
        data: Available data

    Returns:
        Validation report with feasibility assessment
    """
    handler = ComplexConfigurationHandler()

    # Analyze data
    availability = handler.analyze_data_availability(data)

    # Get requirements
    requirements = handler.suggest_minimum_data_requirements(timeframe_configs)

    # Validate
    issues, _ = handler.validate_configuration(timeframe_configs, availability)

    # Create report
    report = {
        "feasible": len(issues) == 0,
        "data_availability": {
            tf: {
                "total_points": avail.total_points,
                "valid_points": avail.valid_points,
                "date_range": f"{avail.date_range[0]} to {avail.date_range[1]}",
            }
            for tf, avail in availability.items()
        },
        "requirements": requirements,
        "issues": [
            {
                "timeframe": issue.timeframe,
                "indicator": issue.indicator_type,
                "type": issue.issue_type,
                "message": issue.message,
                "suggested_fix": issue.suggested_fix,
            }
            for issue in issues
        ],
        "recommendations": [],
    }

    # Add recommendations
    for tf, required in requirements.items():
        if tf in availability:
            available = availability[tf].valid_points
            if available < required:
                report["recommendations"].append(
                    f"Timeframe {tf}: Need {required} points, have {available}. "
                    f"Consider collecting more data or reducing indicator periods."
                )

    return report
