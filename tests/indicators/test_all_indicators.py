"""
Automated testing for all registered indicators.

This module automatically tests all indicators registered in the indicator_registry.
When new indicators are added to the system and registered properly, they will
be automatically tested without requiring manual test case creation.
"""

import pytest
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Type, List, Callable

from ktrdr.indicators import BaseIndicator
from ktrdr.errors import DataError

from tests.indicators.indicator_registry import get_registered_indicators
from tests.indicators.validation_utils import (
    validate_indicator_against_reference,
    generate_indicator_report,
)
from tests.indicators.reference_datasets import (
    create_reference_dataset_1,
    create_reference_dataset_2,
    create_reference_dataset_3,
    create_reference_dataset_4,
)

# Setup logger
logger = logging.getLogger(__name__)

# Map dataset names to creator functions
DATASET_CREATORS = {
    "reference_dataset_1": create_reference_dataset_1,
    "reference_dataset_2": create_reference_dataset_2,
    "reference_dataset_3": create_reference_dataset_3,
    "reference_dataset_4": create_reference_dataset_4,
}


class TestAutomatedIndicatorValidation:
    """Automated tests for all registered indicators."""

    @pytest.mark.parametrize("indicator_name", get_registered_indicators().keys())
    def test_indicator_against_references(self, indicator_name):
        """Test each registered indicator against its reference values."""
        # Get indicator information from registry
        registry_data = get_registered_indicators()[indicator_name]

        # Create indicator instance with default parameters
        indicator_class = registry_data["class"]
        default_params = registry_data["default_params"]
        indicator = indicator_class(**default_params)

        # Test against each reference dataset
        for dataset_name in registry_data["reference_datasets"]:
            # Skip if no reference values for this dataset
            if dataset_name not in registry_data["reference_values"]:
                logger.info(
                    f"No reference values for {indicator_name} on {dataset_name}, skipping"
                )
                continue

            # Create dataset and get reference values
            dataset_creator = DATASET_CREATORS.get(dataset_name)
            if not dataset_creator:
                logger.warning(
                    f"Dataset creator for {dataset_name} not found, skipping"
                )
                continue

            data = dataset_creator()
            reference_values = registry_data["reference_values"][dataset_name]
            tolerance = registry_data["tolerance"]

            # Validate indicator
            result = validate_indicator_against_reference(
                indicator, data, reference_values, tolerance=tolerance, relative=True
            )

            # Log results
            logger.info(
                f"Validation {result.passed} for {indicator_name} on {dataset_name}: "
                f"{result.comparison_points} points, {result.failed_points} failures"
            )

            if not result.passed:
                logger.warning(result.get_failure_details())

            # Assert validation passed
            assert result.passed, (
                f"{indicator_name} failed validation on {dataset_name} with "
                f"{result.failed_points} points exceeding tolerance {tolerance}"
            )

    @pytest.mark.parametrize("indicator_name", get_registered_indicators().keys())
    def test_indicator_edge_cases(self, indicator_name):
        """Test each registered indicator against common edge cases."""
        # Get indicator information from registry
        registry_data = get_registered_indicators()[indicator_name]

        # Create indicator instance with default parameters
        indicator_class = registry_data["class"]
        default_params = registry_data["default_params"]
        indicator = indicator_class(**default_params)

        # Standard edge cases to test for all indicators
        standard_edge_cases = [
            {
                "name": "empty_df",
                "data": pd.DataFrame(),
                "should_raise": True,
                "error_type": DataError,
            },
            {
                "name": "missing_columns",
                "data": pd.DataFrame({"not_price_data": [1, 2, 3]}),
                "should_raise": True,
                "error_type": DataError,
            },
            {
                "name": "insufficient_data",
                "data": pd.DataFrame({"close": [1, 2]}),
                "should_raise": True,
                "error_type": DataError,
            },
        ]

        # Combine standard edge cases with any indicator-specific edge cases
        edge_cases = standard_edge_cases + registry_data.get("known_edge_cases", [])

        # Test each edge case
        for case in edge_cases:
            if case.get("should_raise", False):
                with pytest.raises(case["error_type"]) as excinfo:
                    indicator.compute(case["data"])
                logger.info(
                    f"{indicator_name} correctly raised {case['error_type'].__name__} "
                    f"for {case['name']}: {str(excinfo.value)}"
                )
            else:
                try:
                    result = indicator.compute(case["data"])
                    logger.info(f"{indicator_name} handled {case['name']} correctly")

                    # If expected values are provided, validate them
                    if "expected_values" in case:
                        for idx, expected in case["expected_values"].items():
                            if isinstance(expected, (int, float)) and not pd.isna(
                                expected
                            ):
                                assert abs(result.iloc[idx] - expected) <= case.get(
                                    "tolerance", 0.01
                                ), f"Expected {expected} at position {idx}, got {result.iloc[idx]}"
                except Exception as e:
                    pytest.fail(
                        f"{indicator_name} should not raise error for {case['name']}: {e}"
                    )

    @pytest.mark.parametrize("indicator_name", get_registered_indicators().keys())
    def test_indicator_basic_properties(self, indicator_name):
        """Test basic properties expected of all indicators."""
        # Get indicator information from registry
        registry_data = get_registered_indicators()[indicator_name]

        # Create indicator instance with default parameters
        indicator_class = registry_data["class"]
        default_params = registry_data["default_params"]
        indicator = indicator_class(**default_params)

        # Use a standard dataset for all indicators
        data = create_reference_dataset_1()

        # Compute the indicator
        result = indicator.compute(data)

        # Check basic properties
        assert isinstance(
            result, pd.Series
        ), f"{indicator_name} should return a pd.Series"
        assert len(result) == len(
            data
        ), f"{indicator_name} output should have same length as input"

        # Check that NaN values only appear at the beginning (warmup period)
        # Find the first non-NaN value
        first_valid_idx = result.first_valid_index()
        if first_valid_idx is not None:
            # Get the position of this index
            pos = data.index.get_loc(first_valid_idx)
            # Check that all values after this position are non-NaN
            assert not pd.isna(
                result.iloc[pos:]
            ).any(), f"{indicator_name} should not have NaN values after warmup period"

        # Generate a report for reference
        report = generate_indicator_report(indicator, data)
        logger.info(f"{indicator_name} basic properties report: {report}")
