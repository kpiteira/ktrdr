"""
Tests for numerical validation of fuzzy logic implementation.

This module contains tests that verify the fuzzy logic system produces
expected membership values for known indicator inputs.
"""

import pytest
import numpy as np
import pandas as pd

from ktrdr.fuzzy import FuzzyEngine, FuzzyConfig, TriangularMF
from ktrdr.errors import ProcessingError, ConfigurationError


class FuzzyValidationResult:
    """
    Container for fuzzy validation results.

    Holds information about the validation of fuzzy membership degrees
    against expected values.
    """

    def __init__(
        self,
        passed: bool = True,
        indicator: str = "",
        fuzzy_set: str = "",
        comparison_points: int = 0,
        failed_points: int = 0,
        max_deviation: float = 0.0,
        avg_deviation: float = 0.0,
        details: dict = None,
    ):
        """
        Initialize a FuzzyValidationResult.

        Args:
            passed: Whether all comparison points passed validation
            indicator: Name of the indicator being validated
            fuzzy_set: Name of the fuzzy set being validated
            comparison_points: Number of points compared
            failed_points: Number of points that failed validation
            max_deviation: Maximum deviation found
            avg_deviation: Average deviation
            details: Detailed information about comparison points
        """
        self.passed = passed
        self.indicator = indicator
        self.fuzzy_set = fuzzy_set
        self.comparison_points = comparison_points
        self.failed_points = failed_points
        self.max_deviation = max_deviation
        self.avg_deviation = avg_deviation
        self.details = details or {}

    def __str__(self) -> str:
        """String representation of the validation result."""
        status = "PASSED" if self.passed else "FAILED"
        return (
            f"Fuzzy validation {status} for {self.indicator}.{self.fuzzy_set}: "
            f"{self.comparison_points} points compared, "
            f"{self.failed_points} failed. "
            f"Max deviation: {self.max_deviation:.4f}, "
            f"Avg deviation: {self.avg_deviation:.4f}"
        )

    def get_failure_details(self) -> str:
        """Get detailed information about validation failures."""
        if self.passed:
            return "No failures"

        details_str = f"Failures for {self.indicator}.{self.fuzzy_set}:\n"
        for idx, detail in sorted(self.details.items()):
            if not detail.get("passed", True) and not detail.get("skipped", False):
                details_str += (
                    f"  Index {idx}: "
                    f"Expected {detail['expected']:.4f}, "
                    f"Got {detail['actual']:.4f}, "
                    f"Deviation: {detail['deviation']:.4f}\n"
                )
        return details_str


def validate_fuzzy_output(
    engine: FuzzyEngine,
    indicator: str,
    values: pd.Series,
    fuzzy_set: str,
    expected_values: dict,
    tolerance: float = 0.01,
) -> FuzzyValidationResult:
    """
    Validate fuzzy membership values against expected results.

    Args:
        engine: The FuzzyEngine to use for validation
        indicator: Name of the indicator being validated
        values: Series of indicator values
        fuzzy_set: Name of the fuzzy set to validate
        expected_values: Dictionary mapping index positions to expected membership values
        tolerance: Maximum allowed deviation from expected values

    Returns:
        A FuzzyValidationResult object with validation results
    """
    # Fuzzify the inputs
    output_name = f"{indicator}_{fuzzy_set}"
    result = engine.fuzzify(indicator, values)

    # Get the output column for the specified fuzzy set
    if output_name not in result.columns:
        raise ProcessingError(
            message=f"Fuzzy set output not found: {output_name}",
            error_code="VALIDATION-MissingOutput",
            details={"available_outputs": list(result.columns)},
        )

    output = result[output_name]

    # Perform validation
    passed = True
    failed_points = 0
    deviations = []
    details = {}

    # Check each reference value
    for idx, expected in expected_values.items():
        if idx >= len(output):
            raise ProcessingError(
                message=f"Reference index {idx} is out of bounds for result with length {len(output)}",
                error_code="VALIDATION-IndexOutOfBounds",
                details={"max_index": len(output) - 1},
            )

        actual = output.iloc[idx]

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
        deviations.append(deviation)

        # Check if within tolerance
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

    return FuzzyValidationResult(
        passed=passed,
        indicator=indicator,
        fuzzy_set=fuzzy_set,
        comparison_points=len(expected_values),
        failed_points=failed_points,
        max_deviation=max_deviation,
        avg_deviation=avg_deviation,
        details=details,
    )


# Reference test data for RSI values and expected membership degrees
RSI_TEST_VALUES = pd.Series(
    [
        0.0,  # Very low RSI
        20.0,  # Low RSI
        30.0,  # Medium-low RSI (boundary)
        40.0,  # Medium RSI
        50.0,  # Neutral RSI
        60.0,  # Medium-high RSI
        70.0,  # High RSI (boundary)
        80.0,  # High RSI
        100.0,  # Very high RSI
    ]
)

# Expected membership degrees for standard fuzzy sets (RSI)
# Updated based on actual implementation behavior observed in validation
RSI_EXPECTED = {
    "low": {
        0: 0.0,  # 0.0 -> no low membership (at boundary)
        1: 0.667,  # 20.0 -> strong low membership
        2: 1.0,  # 30.0 -> full low membership (peak)
        3: 0.5,  # 40.0 -> medium low membership
        4: 0.0,  # 50.0 -> no low membership
        5: 0.0,  # 60.0 -> no low membership
        6: 0.0,  # 70.0 -> no low membership
        7: 0.0,  # 80.0 -> no low membership
        8: 0.0,  # 100.0 -> no low membership
    },
    "medium": {
        0: 0.0,  # 0.0 -> no medium membership
        1: 0.0,  # 20.0 -> no medium membership
        2: 0.0,  # 30.0 -> no medium membership (boundary)
        3: 0.5,  # 40.0 -> medium membership
        4: 1.0,  # 50.0 -> full medium membership (peak)
        5: 0.5,  # 60.0 -> medium membership
        6: 0.0,  # 70.0 -> no medium membership (boundary)
        7: 0.0,  # 80.0 -> no medium membership
        8: 0.0,  # 100.0 -> no medium membership
    },
    "high": {
        0: 0.0,  # 0.0 -> no high membership
        1: 0.0,  # 20.0 -> no high membership
        2: 0.0,  # 30.0 -> no high membership
        3: 0.0,  # 40.0 -> no high membership
        4: 0.0,  # 50.0 -> no high membership (boundary)
        5: 0.5,  # 60.0 -> medium high membership
        6: 1.0,  # 70.0 -> full high membership (peak)
        7: 0.667,  # 80.0 -> strong high membership
        8: 0.0,  # 100.0 -> no high membership (at boundary)
    },
}

# Reference test data for MACD values and expected membership degrees
MACD_TEST_VALUES = pd.Series(
    [
        -10.0,  # Very negative
        -5.0,  # Strongly negative (peak)
        -2.0,  # Negative
        -1.0,  # Slightly negative
        0.0,  # Neutral
        1.0,  # Slightly positive
        2.0,  # Positive
        5.0,  # Strongly positive (peak)
        10.0,  # Very positive
    ]
)

# Expected membership degrees for standard fuzzy sets (MACD)
# Updated based on actual implementation behavior observed in validation
MACD_EXPECTED = {
    "negative": {
        0: 0.0,  # -10.0 -> no negative membership (at boundary)
        1: 1.0,  # -5.0 -> full negative membership (peak)
        2: 0.4,  # -2.0 -> moderate negative membership
        3: 0.2,  # -1.0 -> weak negative membership
        4: 0.0,  # 0.0 -> no negative membership
        5: 0.0,  # 1.0 -> no negative membership
        6: 0.0,  # 2.0 -> no negative membership
        7: 0.0,  # 5.0 -> no negative membership
        8: 0.0,  # 10.0 -> no negative membership
    },
    "neutral": {
        0: 0.0,  # -10.0 -> no neutral membership
        1: 0.0,  # -5.0 -> no neutral membership
        2: 0.0,  # -2.0 -> no neutral membership (boundary)
        3: 0.5,  # -1.0 -> medium neutral membership
        4: 1.0,  # 0.0 -> full neutral membership (peak)
        5: 0.5,  # 1.0 -> medium neutral membership
        6: 0.0,  # 2.0 -> no neutral membership (boundary)
        7: 0.0,  # 5.0 -> no neutral membership
        8: 0.0,  # 10.0 -> no neutral membership
    },
    "positive": {
        0: 0.0,  # -10.0 -> no positive membership
        1: 0.0,  # -5.0 -> no positive membership
        2: 0.0,  # -2.0 -> no positive membership
        3: 0.0,  # -1.0 -> no positive membership
        4: 0.0,  # 0.0 -> no positive membership
        5: 0.2,  # 1.0 -> weak positive membership
        6: 0.4,  # 2.0 -> moderate positive membership
        7: 1.0,  # 5.0 -> full positive membership (peak)
        8: 0.0,  # 10.0 -> no positive membership (at boundary)
    },
}


class TestFuzzyNumericalValidation:
    """Test suite for numerical validation of fuzzy logic implementation."""

    @pytest.fixture
    def standard_fuzzy_config(self):
        """Fixture for a standard fuzzy configuration with known parameters."""
        config_dict = {
            "rsi": {
                "low": {"type": "triangular", "parameters": [0.0, 30.0, 50.0]},
                "medium": {"type": "triangular", "parameters": [30.0, 50.0, 70.0]},
                "high": {"type": "triangular", "parameters": [50.0, 70.0, 100.0]},
            },
            "macd": {
                "negative": {"type": "triangular", "parameters": [-10.0, -5.0, 0.0]},
                "neutral": {"type": "triangular", "parameters": [-2.0, 0.0, 2.0]},
                "positive": {"type": "triangular", "parameters": [0.0, 5.0, 10.0]},
            },
        }
        return FuzzyConfig.model_validate(config_dict)

    @pytest.fixture
    def standard_fuzzy_engine(self, standard_fuzzy_config):
        """Fixture for a FuzzyEngine with standardized configuration."""
        return FuzzyEngine(standard_fuzzy_config)

    def test_rsi_low_membership(self, standard_fuzzy_engine):
        """Test that RSI low membership values match expected results."""
        result = validate_fuzzy_output(
            engine=standard_fuzzy_engine,
            indicator="rsi",
            values=RSI_TEST_VALUES,
            fuzzy_set="low",
            expected_values=RSI_EXPECTED["low"],
            tolerance=0.05,  # Allow 5% deviation
        )

        # Log detailed results
        print(str(result))
        if not result.passed:
            print(result.get_failure_details())

        # Assert all points pass validation
        assert (
            result.passed
        ), f"RSI low membership validation failed: {result.failed_points} points"

    def test_rsi_medium_membership(self, standard_fuzzy_engine):
        """Test that RSI medium membership values match expected results."""
        result = validate_fuzzy_output(
            engine=standard_fuzzy_engine,
            indicator="rsi",
            values=RSI_TEST_VALUES,
            fuzzy_set="medium",
            expected_values=RSI_EXPECTED["medium"],
            tolerance=0.05,  # Allow 5% deviation
        )

        print(str(result))
        if not result.passed:
            print(result.get_failure_details())

        assert (
            result.passed
        ), f"RSI medium membership validation failed: {result.failed_points} points"

    def test_rsi_high_membership(self, standard_fuzzy_engine):
        """Test that RSI high membership values match expected results."""
        result = validate_fuzzy_output(
            engine=standard_fuzzy_engine,
            indicator="rsi",
            values=RSI_TEST_VALUES,
            fuzzy_set="high",
            expected_values=RSI_EXPECTED["high"],
            tolerance=0.05,  # Allow 5% deviation
        )

        print(str(result))
        if not result.passed:
            print(result.get_failure_details())

        assert (
            result.passed
        ), f"RSI high membership validation failed: {result.failed_points} points"

    def test_macd_negative_membership(self, standard_fuzzy_engine):
        """Test that MACD negative membership values match expected results."""
        result = validate_fuzzy_output(
            engine=standard_fuzzy_engine,
            indicator="macd",
            values=MACD_TEST_VALUES,
            fuzzy_set="negative",
            expected_values=MACD_EXPECTED["negative"],
            tolerance=0.05,  # Allow 5% deviation
        )

        print(str(result))
        if not result.passed:
            print(result.get_failure_details())

        assert (
            result.passed
        ), f"MACD negative membership validation failed: {result.failed_points} points"

    def test_macd_neutral_membership(self, standard_fuzzy_engine):
        """Test that MACD neutral membership values match expected results."""
        result = validate_fuzzy_output(
            engine=standard_fuzzy_engine,
            indicator="macd",
            values=MACD_TEST_VALUES,
            fuzzy_set="neutral",
            expected_values=MACD_EXPECTED["neutral"],
            tolerance=0.05,  # Allow 5% deviation
        )

        print(str(result))
        if not result.passed:
            print(result.get_failure_details())

        assert (
            result.passed
        ), f"MACD neutral membership validation failed: {result.failed_points} points"

    def test_macd_positive_membership(self, standard_fuzzy_engine):
        """Test that MACD positive membership values match expected results."""
        result = validate_fuzzy_output(
            engine=standard_fuzzy_engine,
            indicator="macd",
            values=MACD_TEST_VALUES,
            fuzzy_set="positive",
            expected_values=MACD_EXPECTED["positive"],
            tolerance=0.05,  # Allow 5% deviation
        )

        print(str(result))
        if not result.passed:
            print(result.get_failure_details())

        assert (
            result.passed
        ), f"MACD positive membership validation failed: {result.failed_points} points"
