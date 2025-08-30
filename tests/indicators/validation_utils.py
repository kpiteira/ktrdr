"""
Validation utilities for testing indicator implementations.

This module provides utilities for:
1. Validating indicator results against reference values
2. Creating reference datasets with known indicator values
3. Generating comprehensive reports for validation failures
"""

import logging
from typing import Any

import pandas as pd

from ktrdr.errors import DataError
from ktrdr.indicators import BaseIndicator

# Setup logger
logger = logging.getLogger(__name__)


class IndicatorValidationResult:
    """Stores the results of an indicator validation run."""

    def __init__(
        self,
        indicator_name: str,
        passed: bool,
        comparison_points: int,
        failed_points: int,
        max_deviation: float,
        avg_deviation: float,
        details: dict[int, dict[str, Any]] = None,
    ):
        """
        Initialize the validation result.

        Args:
            indicator_name: Name of the indicator being validated
            passed: Whether all validation points passed
            comparison_points: Total number of comparison points
            failed_points: Number of failed comparison points
            max_deviation: Maximum deviation found between actual and reference
            avg_deviation: Average deviation across all comparison points
            details: Detailed results for each comparison point
        """
        self.indicator_name = indicator_name
        self.passed = passed
        self.comparison_points = comparison_points
        self.failed_points = failed_points
        self.max_deviation = max_deviation
        self.avg_deviation = avg_deviation
        self.details = details or {}

    def __str__(self) -> str:
        """Return a string representation of the validation result."""
        status = "PASSED" if self.passed else "FAILED"
        return (
            f"Validation {status} for {self.indicator_name}: "
            f"{self.comparison_points} comparison points, "
            f"{self.failed_points} failures, "
            f"max deviation: {self.max_deviation:.4f}, "
            f"avg deviation: {self.avg_deviation:.4f}"
        )

    def get_failure_details(self) -> str:
        """Return a formatted string with details about failures."""
        if not self.details or self.passed:
            return "No failures detected."

        result = [f"Failures for {self.indicator_name}:"]
        for idx, detail in self.details.items():
            if not detail.get("passed", True):
                if detail.get("skipped", False):
                    result.append(
                        f"  At position {idx}: skipped - {detail.get('reason', 'unknown reason')}"
                    )
                else:
                    expected = detail.get("expected", "N/A")
                    actual = detail.get("actual", "N/A")
                    deviation = detail.get("deviation", "N/A")

                    # Handle formatting based on value type
                    if isinstance(expected, (int, float)) and expected is not None:
                        expected_str = f"{expected:.4f}"
                    else:
                        expected_str = str(expected)

                    if isinstance(actual, (int, float)) and actual is not None:
                        actual_str = f"{actual:.4f}"
                    else:
                        actual_str = str(actual)

                    if isinstance(deviation, (int, float)) and deviation is not None:
                        deviation_str = f"{deviation:.4f}"
                    else:
                        deviation_str = str(deviation)

                    result.append(
                        f"  At position {idx}: "
                        f"expected {expected_str}, "
                        f"got {actual_str}, "
                        f"deviation: {deviation_str}"
                    )
        return "\n".join(result)


def validate_indicator_against_reference(
    indicator: BaseIndicator,
    data: pd.DataFrame,
    reference_values: dict[int, float],
    tolerance: float = 0.01,
    relative: bool = False,
) -> IndicatorValidationResult:
    """
    Validate an indicator's output against reference values.

    Args:
        indicator: The indicator to validate
        data: DataFrame to compute the indicator on
        reference_values: Dictionary mapping positions to expected values
        tolerance: Maximum allowed deviation (absolute or relative)
        relative: If True, tolerance is treated as relative percentage
                 If False, tolerance is treated as absolute difference

    Returns:
        IndicatorValidationResult object containing validation statistics
    """
    # Compute the indicator
    try:
        result = indicator.compute(data)
    except Exception as e:
        raise DataError(
            message=f"Error computing indicator: {str(e)}",
            error_code="DATA-ComputationError",
            details={"indicator": indicator.name},
        ) from e

    # Prepare result variables
    passed = True
    failed_points = 0
    deviations = []
    details = {}

    # Check each reference value
    for idx, expected in reference_values.items():
        if idx >= len(result):
            raise DataError(
                message=f"Reference index {idx} is out of bounds for result with length {len(result)}",
                error_code="DATA-ValidationIndexError",
                details={"max_index": len(result) - 1},
            )

        actual = result.iloc[idx]

        # Skip NaN values
        if pd.isna(actual) or pd.isna(expected):
            details[idx] = {
                "expected": expected if not pd.isna(expected) else None,
                "actual": actual if not pd.isna(actual) else None,
                "passed": False,
                "deviation": None,
                "skipped": True,
                "reason": "NaN value encountered",
            }
            continue

        # Calculate deviation
        deviation = abs(actual - expected)
        if relative:
            # For relative tolerance, use percentage of expected value
            if expected != 0:  # Avoid division by zero
                deviation = deviation / abs(expected)
            else:
                # If expected is zero, use absolute tolerance
                pass

        deviations.append(deviation)
        point_passed = deviation <= tolerance

        # Record result for this point
        details[idx] = {
            "expected": expected,
            "actual": actual,
            "passed": point_passed,
            "deviation": deviation,
        }

        # Update overall passed status
        if not point_passed:
            passed = False
            failed_points += 1

    # Calculate statistics
    max_deviation = max(deviations) if deviations else 0
    avg_deviation = sum(deviations) / len(deviations) if deviations else 0

    # Log detailed results
    if not passed:
        logger.warning(
            f"Validation failed for indicator {indicator.name} "
            f"with {failed_points} points exceeding tolerance {tolerance}"
        )
        for idx, detail in details.items():
            if not detail.get("passed", True) and not detail.get("skipped", False):
                logger.debug(
                    f"  Failed at index {idx}: "
                    f"expected {detail['expected']}, got {detail['actual']}, "
                    f"deviation: {detail['deviation']}"
                )

    return IndicatorValidationResult(
        indicator_name=indicator.name,
        passed=passed,
        comparison_points=len(reference_values),
        failed_points=failed_points,
        max_deviation=max_deviation,
        avg_deviation=avg_deviation,
        details=details,
    )


def create_standard_test_data(
    patterns: list[tuple[float, int, str]],
    start_date: str = "2023-01-01",
    include_ohlcv: bool = True,
) -> pd.DataFrame:
    """
    Create a standard test dataset with predictable patterns.

    Args:
        patterns: List of tuples (start_value, length, pattern_type)
            pattern_type can be 'constant', 'linear_up', 'linear_down',
            'exponential_up', or 'exponential_down'
        start_date: Starting date for the DataFrame index
        include_ohlcv: If True, creates a DataFrame with OHLCV columns

    Returns:
        DataFrame with the specified patterns
    """
    # Initialize empty list for values
    values = []

    # Create each pattern
    for start_value, length, pattern_type in patterns:
        if pattern_type == "constant":
            segment = [start_value] * length
        elif pattern_type == "linear_up":
            segment = [start_value + i for i in range(length)]
        elif pattern_type == "linear_down":
            segment = [start_value - i for i in range(length)]
        elif pattern_type == "exponential_up":
            segment = [start_value * (1.05**i) for i in range(length)]
        elif pattern_type == "exponential_down":
            segment = [start_value * (0.95**i) for i in range(length)]
        else:
            raise ValueError(f"Unknown pattern type: {pattern_type}")

        values.extend(segment)

    # Create date range index
    dates = pd.date_range(start=start_date, periods=len(values), freq="D")

    # Create DataFrame
    if include_ohlcv:
        df = pd.DataFrame(
            {
                "open": values,
                "high": [v * 1.01 for v in values],
                "low": [v * 0.99 for v in values],
                "close": values,
                "volume": [1000000] * len(values),
            },
            index=dates,
        )
    else:
        df = pd.DataFrame({"close": values}, index=dates)

    return df


def generate_indicator_report(
    indicator: BaseIndicator,
    data: pd.DataFrame,
    expected_values: dict[int, float] = None,
    key_points: list[int] = None,
    full: bool = False,
) -> dict[str, Any]:
    """
    Generate a comprehensive report about an indicator's behavior.

    Args:
        indicator: The indicator to analyze
        data: DataFrame to compute the indicator on
        expected_values: Optional reference values for validation
        key_points: Optional list of positions to analyze in detail
        full: If True, include the full result series in the report

    Returns:
        Dictionary containing the indicator report
    """
    try:
        result = indicator.compute(data)
    except Exception as e:
        return {
            "indicator": indicator.name,
            "success": False,
            "error": str(e),
            "params": indicator.params,
        }

    # Basic statistics about the result
    stats = {
        "min": result.min() if not result.empty else None,
        "max": result.max() if not result.empty else None,
        "mean": result.mean() if not result.empty else None,
        "std": result.std() if not result.empty else None,
        "nan_count": result.isna().sum(),
        "nan_percentage": result.isna().mean() * 100,
    }

    # Validation results if reference values provided
    validation = None
    if expected_values:
        try:
            validation = validate_indicator_against_reference(
                indicator, data, expected_values
            )
            validation = {
                "passed": validation.passed,
                "failed_points": validation.failed_points,
                "max_deviation": validation.max_deviation,
                "avg_deviation": validation.avg_deviation,
            }
        except Exception as e:
            validation = {"passed": False, "error": str(e)}

    # Key points analysis
    key_points_values = {}
    if key_points:
        for idx in key_points:
            if 0 <= idx < len(result):
                key_points_values[idx] = result.iloc[idx]

    # Create report
    report = {
        "indicator": indicator.name,
        "success": True,
        "params": indicator.params,
        "length": len(result),
        "stats": stats,
        "validation": validation,
        "key_points": key_points_values,
    }

    # Include full result if requested
    if full:
        report["values"] = result.tolist()

    return report
