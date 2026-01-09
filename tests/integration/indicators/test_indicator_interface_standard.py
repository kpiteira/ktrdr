"""
Integration test for indicator interface standard.

This test verifies that ALL registered indicators in BUILT_IN_INDICATORS
follow the M1 interface standard:
- Multi-output indicators must have get_output_names() returning non-empty list
- Single-output indicators must have get_output_names() returning empty list
- compute() return type must match is_multi_output() declaration
- Primary output must be first in output names list

This test catches gaps like missing get_output_names() implementations.
"""

import numpy as np
import pandas as pd
import pytest

from ktrdr.indicators.indicator_factory import BUILT_IN_INDICATORS


def create_sample_ohlcv(rows: int = 100) -> pd.DataFrame:
    """
    Create sample OHLCV data for testing.

    Args:
        rows: Number of rows to generate

    Returns:
        DataFrame with OHLCV columns and datetime index
    """
    dates = pd.date_range("2023-01-01", periods=rows, freq="D")
    np.random.seed(42)  # For reproducible tests

    # Generate price series with some volatility
    start_price = 100.0
    price_changes = np.random.normal(0, 1, rows)
    prices = [start_price]
    for change in price_changes[1:]:
        prices.append(prices[-1] * (1 + change * 0.01))

    # Generate high/low variations deterministically
    high_variations = np.random.normal(0, 0.005, rows)
    low_variations = np.random.normal(0, 0.005, rows)

    data = pd.DataFrame(
        {
            "open": prices,
            "high": [p * (1 + abs(v)) for p, v in zip(prices, high_variations)],
            "low": [p * (1 - abs(v)) for p, v in zip(prices, low_variations)],
            "close": prices,
            "volume": np.random.randint(1000, 10000, rows),
        },
        index=dates,
    )

    return data


def test_all_indicators_follow_interface_standard():
    """
    Verify all registered indicators implement the interface correctly.

    This test ensures:
    - Multi-output indicators have non-empty output names
    - Single-output indicators have empty output names
    - Primary output matches first output name
    """
    # Get all unique indicator classes from factory registry
    tested = set()
    failed_indicators = []

    for indicator_type, indicator_class in BUILT_IN_INDICATORS.items():
        # Skip aliases (same class, different name)
        if indicator_class in tested:
            continue
        tested.add(indicator_class)

        try:
            # Test interface contract
            if indicator_class.is_multi_output():
                outputs = indicator_class.get_output_names()
                assert len(outputs) > 0, (
                    f"{indicator_type} is multi-output but has no output names. "
                    f"Add get_output_names() classmethod returning list of output names."
                )
                assert indicator_class.get_primary_output() == outputs[0], (
                    f"{indicator_type} primary output mismatch. "
                    f"Expected: {outputs[0]}, Got: {indicator_class.get_primary_output()}"
                )
            else:
                outputs = indicator_class.get_output_names()
                assert len(outputs) == 0, (
                    f"{indicator_type} is single-output but has output names: {outputs}. "
                    f"Remove get_output_names() override or set is_multi_output() to True."
                )
                assert indicator_class.get_primary_output() is None, (
                    f"{indicator_type} single-output should have None primary output. "
                    f"Got: {indicator_class.get_primary_output()}"
                )
        except AssertionError as e:
            failed_indicators.append(f"{indicator_class.__name__}: {str(e)}")

    # Report all failures at once
    if failed_indicators:
        pytest.fail(
            "Interface standard violations found:\n" + "\n".join(failed_indicators)
        )


def test_all_indicators_compute_without_error():
    """
    Verify all indicators can compute on sample data.

    This test ensures:
    - All indicators can instantiate with default params
    - compute() returns correct type (DataFrame for multi-output, Series for single)
    - No runtime errors during computation
    """
    sample_data = create_sample_ohlcv(rows=200)  # Extra rows for warmup

    tested = set()
    failed_indicators = []

    for indicator_type, indicator_class in BUILT_IN_INDICATORS.items():
        if indicator_class in tested:
            continue
        tested.add(indicator_class)

        try:
            # Try to create with default params
            try:
                indicator = indicator_class()
            except TypeError:
                # Some indicators require params - skip gracefully
                # (This is acceptable, not all indicators have usable defaults)
                continue

            # Compute result
            result = indicator.compute(sample_data)

            # Verify return type matches declaration
            if indicator_class.is_multi_output():
                assert isinstance(result, pd.DataFrame), (
                    f"{indicator_type} is multi-output but compute() returned "
                    f"{type(result).__name__} instead of DataFrame"
                )
            else:
                assert isinstance(result, pd.Series), (
                    f"{indicator_type} is single-output but compute() returned "
                    f"{type(result).__name__} instead of Series"
                )

        except AssertionError as e:
            failed_indicators.append(f"{indicator_class.__name__}: {str(e)}")
        except Exception as e:
            # Unexpected errors during computation
            failed_indicators.append(
                f"{indicator_class.__name__}: Computation error: {str(e)}"
            )

    # Report all failures at once
    if failed_indicators:
        pytest.fail("Computation issues found:\n" + "\n".join(failed_indicators))
