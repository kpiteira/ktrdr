"""
Tests for Aroon indicator.

This module provides comprehensive tests for the Aroon indicator implementation,
including mathematical accuracy, parameter validation, and edge case handling.
"""

import numpy as np
import pandas as pd
import pytest

from ktrdr.errors import DataError
from ktrdr.indicators.aroon_indicator import AroonIndicator


class TestAroonIndicator:
    """Test suite for Aroon indicator."""

    def test_basic_initialization(self):
        """Test basic Aroon initialization with default parameters."""
        indicator = AroonIndicator()

        assert indicator.name == "Aroon"
        assert indicator.params["period"] == 14
        assert not indicator.params["include_oscillator"]

    def test_custom_initialization(self):
        """Test Aroon initialization with custom parameters."""
        indicator = AroonIndicator(period=20, include_oscillator=True)

        assert indicator.params["period"] == 20
        assert indicator.params["include_oscillator"]

    def test_parameter_validation_success(self):
        """Test successful parameter validation."""
        # Valid parameters should not raise an error
        AroonIndicator(period=1)
        AroonIndicator(period=14, include_oscillator=False)
        AroonIndicator(period=200, include_oscillator=True)

    def test_parameter_validation_period_too_small(self):
        """Test parameter validation for period too small."""
        with pytest.raises(DataError) as exc_info:
            AroonIndicator(period=0)
        # New Params pattern raises DataError with INDICATOR-InvalidParameters code
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_parameter_validation_period_too_large(self):
        """Test parameter validation for period too large."""
        with pytest.raises(DataError) as exc_info:
            AroonIndicator(period=201)
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_parameter_validation_period_non_integer(self):
        """Test parameter validation for non-integer period."""
        with pytest.raises(DataError) as exc_info:
            AroonIndicator(period=14.5)
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_parameter_validation_include_oscillator_non_boolean(self):
        """Test parameter validation for non-boolean include_oscillator."""
        with pytest.raises(DataError) as exc_info:
            AroonIndicator(include_oscillator="true")
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_basic_calculation(self):
        """Test basic Aroon calculation with sufficient data."""
        # Create test data with clear trend patterns
        data = pd.DataFrame(
            {
                "open": [
                    100,
                    101,
                    102,
                    103,
                    104,
                    105,
                    106,
                    107,
                    108,
                    109,
                    110,
                    111,
                    112,
                    113,
                    114,
                    115,
                    116,
                ],
                "high": [
                    101,
                    102,
                    103,
                    104,
                    105,
                    106,
                    107,
                    108,
                    109,
                    110,
                    111,
                    112,
                    113,
                    114,
                    115,
                    116,
                    117,
                ],
                "low": [
                    99,
                    100,
                    101,
                    102,
                    103,
                    104,
                    105,
                    106,
                    107,
                    108,
                    109,
                    110,
                    111,
                    112,
                    113,
                    114,
                    115,
                ],
                "close": [
                    100.5,
                    101.5,
                    102.5,
                    103.5,
                    104.5,
                    105.5,
                    106.5,
                    107.5,
                    108.5,
                    109.5,
                    110.5,
                    111.5,
                    112.5,
                    113.5,
                    114.5,
                    115.5,
                    116.5,
                ],
            }
        )

        indicator = AroonIndicator(period=10)
        result = indicator.compute(data)

        # M3b: Should always return DataFrame with 3 columns (Up, Down, Oscillator)
        # to match get_output_names()
        assert isinstance(result, pd.DataFrame)
        assert len(result.columns) == 3

        # Should have same length as input
        assert len(result) == len(data)

        # Column names should be correctly formatted
        # M3b: Now returns semantic column names
        assert "up" in result.columns
        assert "down" in result.columns
        assert "oscillator" in result.columns

    def test_aroon_with_oscillator(self):
        """Test Aroon calculation with oscillator included."""
        data = pd.DataFrame(
            {
                "high": [
                    101,
                    102,
                    103,
                    104,
                    105,
                    106,
                    107,
                    108,
                    109,
                    110,
                    111,
                    112,
                    113,
                    114,
                    115,
                ],
                "low": [
                    99,
                    100,
                    101,
                    102,
                    103,
                    104,
                    105,
                    106,
                    107,
                    108,
                    109,
                    110,
                    111,
                    112,
                    113,
                ],
            }
        )

        indicator = AroonIndicator(period=10, include_oscillator=True)
        result = indicator.compute(data)

        # Should return DataFrame with 3 columns (Up, Down, Oscillator)
        assert len(result.columns) == 3
        # M3b: Now returns semantic column names
        assert "up" in result.columns
        assert "down" in result.columns
        # M3b: Now returns semantic column name
        assert "oscillator" in result.columns

    def test_uptrend_aroon_behavior(self):
        """Test Aroon behavior during strong uptrend."""
        # Create strong uptrend data (new highs frequently)
        data = pd.DataFrame(
            {
                "high": [100 + i * 2 for i in range(20)],  # Consistent new highs
                "low": [99 + i * 2 for i in range(20)],
            }
        )

        indicator = AroonIndicator(period=10)
        result = indicator.compute(data)

        # In strong uptrend, Aroon Up should be high, Aroon Down should be low
        valid_up = result["up"].dropna()
        valid_down = result["down"].dropna()

        if len(valid_up) > 0 and len(valid_down) > 0:
            # Most recent values should show strong uptrend
            recent_up = valid_up.iloc[-3:]  # Last 3 values
            recent_down = valid_down.iloc[-3:]

            # Aroon Up should be high (new highs recently)
            assert (recent_up > 70).any(), "Aroon Up should be high during uptrend"
            # Aroon Down should be relatively low (no recent lows)
            assert (recent_down < 30).any(), "Aroon Down should be low during uptrend"

    def test_downtrend_aroon_behavior(self):
        """Test Aroon behavior during strong downtrend."""
        # Create strong downtrend data (new lows frequently)
        data = pd.DataFrame(
            {
                "high": [120 - i * 2 for i in range(20)],
                "low": [118 - i * 2 for i in range(20)],  # Consistent new lows
            }
        )

        indicator = AroonIndicator(period=10)
        result = indicator.compute(data)

        # In strong downtrend, Aroon Down should be high, Aroon Up should be low
        valid_up = result["up"].dropna()
        valid_down = result["down"].dropna()

        if len(valid_up) > 0 and len(valid_down) > 0:
            # Most recent values should show strong downtrend
            recent_up = valid_up.iloc[-3:]  # Last 3 values
            recent_down = valid_down.iloc[-3:]

            # Aroon Down should be high (new lows recently)
            assert (
                recent_down > 70
            ).any(), "Aroon Down should be high during downtrend"
            # Aroon Up should be relatively low (no recent highs)
            assert (recent_up < 30).any(), "Aroon Up should be low during downtrend"

    def test_consolidation_aroon_behavior(self):
        """Test Aroon behavior during consolidation/sideways movement."""
        # Create sideways data (no clear new highs or lows)
        base = 100
        data = pd.DataFrame(
            {
                "high": [base + np.sin(i * 0.5) * 2 for i in range(20)],
                "low": [base + np.sin(i * 0.5) * 2 - 3 for i in range(20)],
            }
        )

        indicator = AroonIndicator(period=10)
        result = indicator.compute(data)

        # In consolidation, both Aroon Up and Down should be moderate
        valid_up = result["up"].dropna()
        valid_down = result["down"].dropna()

        if len(valid_up) > 0 and len(valid_down) > 0:
            # Values should be neither extremely high nor low
            avg_up = valid_up.mean()
            avg_down = valid_down.mean()

            # During consolidation, neither should dominate consistently
            assert (
                20 <= avg_up <= 80
            ), "Aroon Up should be moderate during consolidation"
            assert (
                20 <= avg_down <= 80
            ), "Aroon Down should be moderate during consolidation"

    def test_aroon_oscillator_calculation(self):
        """Test Aroon Oscillator calculation (Up - Down)."""
        data = pd.DataFrame(
            {
                "high": [
                    100,
                    102,
                    101,
                    103,
                    102,
                    104,
                    103,
                    105,
                    104,
                    106,
                    105,
                    107,
                    106,
                    108,
                    107,
                ],
                "low": [
                    98,
                    100,
                    99,
                    101,
                    100,
                    102,
                    101,
                    103,
                    102,
                    104,
                    103,
                    105,
                    104,
                    106,
                    105,
                ],
            }
        )

        indicator = AroonIndicator(period=10, include_oscillator=True)
        result = indicator.compute(data)

        # Verify oscillator calculation
        valid_indices = ~(pd.isna(result["up"]) | pd.isna(result["down"]))

        for idx in result.index[valid_indices]:
            expected_oscillator = result["up"][idx] - result["down"][idx]
            actual_oscillator = result["oscillator"][idx]
            assert abs(actual_oscillator - expected_oscillator) < 0.001

    def test_missing_required_columns(self):
        """Test Aroon with missing required columns."""
        # Missing low column
        data = pd.DataFrame({"high": [101, 102, 103], "close": [100, 101, 102]})

        indicator = AroonIndicator()
        with pytest.raises(DataError) as exc_info:
            indicator.compute(data)
        assert "missing required columns" in str(exc_info.value).lower()
        assert "low" in str(exc_info.value).lower()

    def test_insufficient_data(self):
        """Test Aroon with insufficient data points."""
        # Only 5 data points, but need at least 14 for default parameters
        data = pd.DataFrame(
            {"high": [101, 102, 103, 104, 105], "low": [99, 100, 101, 102, 103]}
        )

        indicator = AroonIndicator()
        with pytest.raises(DataError) as exc_info:
            indicator.compute(data)
        assert "requires at least" in str(exc_info.value).lower()

    def test_minimum_required_data(self):
        """Test Aroon with exactly minimum required data."""
        # Exactly 14 data points for default parameters
        data = pd.DataFrame(
            {"high": [100 + i for i in range(14)], "low": [99 + i for i in range(14)]}
        )

        indicator = AroonIndicator()
        result = indicator.compute(data)

        # Should work with exactly minimum data
        assert len(result) == 14

        # Should have exactly one valid value at the end
        valid_up = result["up"].dropna()
        valid_down = result["down"].dropna()
        assert len(valid_up) == 1
        assert len(valid_down) == 1

    def test_custom_period_parameters(self):
        """Test Aroon with custom period parameter."""
        # Use smaller period to test with less data
        data = pd.DataFrame(
            {"high": [100 + i for i in range(8)], "low": [99 + i for i in range(8)]}
        )

        indicator = AroonIndicator(period=5)
        result = indicator.compute(data)

        # Should work with custom parameters
        assert len(result) == 8

        # Column names should reflect custom parameters
        # M3b: Now returns semantic column names
        assert "up" in result.columns
        assert "down" in result.columns

    def test_extreme_values(self):
        """Test Aroon with extreme high/low values."""
        # Create data with extreme values
        data = pd.DataFrame(
            {
                "high": [
                    100,
                    1000,
                    101,
                    102,
                    103,
                    104,
                    105,
                    106,
                    107,
                    108,
                    109,
                    110,
                    111,
                    112,
                    113,
                    114,
                ],
                "low": [
                    99,
                    1,
                    100,
                    101,
                    102,
                    103,
                    104,
                    105,
                    106,
                    107,
                    108,
                    109,
                    110,
                    111,
                    112,
                    113,
                ],
            }
        )

        indicator = AroonIndicator()
        result = indicator.compute(data)

        # Should handle extreme values without errors
        assert len(result) == 16

        # Values should still be between 0 and 100
        valid_up = result["up"].dropna()
        valid_down = result["down"].dropna()

        assert all(0 <= val <= 100 for val in valid_up)
        assert all(0 <= val <= 100 for val in valid_down)

    def test_get_name_method(self):
        """Test get_name method returns correct formatted name."""
        indicator1 = AroonIndicator(period=20)
        expected_name1 = "Aroon_20"
        assert indicator1.get_name() == expected_name1

        indicator2 = AroonIndicator(period=20, include_oscillator=True)
        expected_name2 = "Aroon_20_with_Oscillator"
        assert indicator2.get_name() == expected_name2

    def test_empty_dataframe(self):
        """Test Aroon with empty DataFrame."""
        data = pd.DataFrame()

        indicator = AroonIndicator()
        with pytest.raises(DataError) as exc_info:
            indicator.compute(data)
        assert "missing required columns" in str(exc_info.value).lower()

    def test_nan_values_in_data(self):
        """Test Aroon handling of NaN values in input data."""
        data = pd.DataFrame(
            {
                "high": [
                    101,
                    np.nan,
                    103,
                    104,
                    105,
                    106,
                    107,
                    108,
                    109,
                    110,
                    111,
                    112,
                    113,
                    114,
                    115,
                ],
                "low": [
                    99,
                    100,
                    101,
                    102,
                    103,
                    104,
                    105,
                    106,
                    107,
                    108,
                    109,
                    110,
                    111,
                    112,
                    113,
                ],
            }
        )

        indicator = AroonIndicator()
        result = indicator.compute(data)

        # Should handle NaN values appropriately
        assert len(result) == len(data)

    def test_mathematical_properties(self):
        """Test mathematical properties of Aroon calculation."""
        # Create predictable data
        data = pd.DataFrame(
            {
                "high": [
                    100,
                    101,
                    102,
                    103,
                    104,
                    105,
                    106,
                    107,
                    108,
                    109,
                    110,
                    111,
                    112,
                    113,
                    114,
                    115,
                ],
                "low": [
                    99,
                    100,
                    101,
                    102,
                    103,
                    104,
                    105,
                    106,
                    107,
                    108,
                    109,
                    110,
                    111,
                    112,
                    113,
                    114,
                ],
            }
        )

        indicator = AroonIndicator()
        result = indicator.compute(data)

        # All valid values should be finite numbers between 0 and 100
        valid_up = result["up"].dropna()
        valid_down = result["down"].dropna()

        assert all(np.isfinite(valid_up))
        assert all(np.isfinite(valid_down))
        assert all(0 <= val <= 100 for val in valid_up)
        assert all(0 <= val <= 100 for val in valid_down)

        # No infinity values
        assert not any(np.isinf(valid_up))
        assert not any(np.isinf(valid_down))

    def test_indicator_name_and_params(self):
        """Test indicator name and parameters accessibility."""
        indicator = AroonIndicator(period=20, include_oscillator=True)

        assert indicator.name == "Aroon"
        assert indicator.params["period"] == 20
        assert indicator.params["include_oscillator"]

    def test_aroon_boundary_values(self):
        """Test Aroon calculation with boundary scenarios."""
        # Scenario 1: New high on current period
        data = pd.DataFrame(
            {
                "high": [
                    100,
                    101,
                    102,
                    103,
                    104,
                    105,
                    106,
                    107,
                    108,
                    109,
                    110,
                    111,
                    112,
                    113,
                    120,
                ],  # New high at end
                "low": [
                    99,
                    100,
                    101,
                    102,
                    103,
                    104,
                    105,
                    106,
                    107,
                    108,
                    109,
                    110,
                    111,
                    112,
                    119,
                ],
            }
        )

        indicator = AroonIndicator(period=10)
        result = indicator.compute(data)

        # Last Aroon Up should be 100 (new high at position 0 of lookback)
        assert result["up"].iloc[-1] == 100.0

    def test_aroon_time_calculation(self):
        """Test the time-based calculation logic of Aroon."""
        # Create data where we know exactly when highs and lows occurred
        data = pd.DataFrame(
            {
                "high": [
                    100,
                    110,
                    102,
                    103,
                    104,
                    105,
                    106,
                    107,
                    108,
                    109,
                ],  # High at position 9 (last)
                "low": [
                    99,
                    109,
                    95,
                    102,
                    103,
                    104,
                    105,
                    106,
                    107,
                    108,
                ],  # Low at position 2
            }
        )

        indicator = AroonIndicator(period=8)
        result = indicator.compute(data)

        # At index 9 (last position), the 8-period window covers indices 2-9:
        # - Highest high (109) is at position 9 (current position), so periods_since_high = 0
        # - Lowest low (95) is at position 2, so periods_since_low = 7 (positions from current)

        aroon_up_last = result["up"].iloc[-1]
        aroon_down_last = result["down"].iloc[-1]

        # Aroon Up = ((8 - 0) / 8) * 100 = 100.0 (high was 0 periods ago - current)
        # Aroon Down = ((8 - 7) / 8) * 100 = 12.5 (low was 7 periods ago)
        expected_up = ((8 - 0) / 8) * 100  # periods_since_high = 0
        expected_down = ((8 - 7) / 8) * 100  # periods_since_low = 7

        assert abs(aroon_up_last - expected_up) < 0.1
        assert abs(aroon_down_last - expected_down) < 0.1

    def test_aroon_equal_highs_lows(self):
        """Test Aroon with equal consecutive highs/lows."""
        # Create data with equal highs/lows
        data = pd.DataFrame(
            {
                "high": [
                    100,
                    100,
                    100,
                    101,
                    101,
                    101,
                    102,
                    102,
                    102,
                    103,
                    103,
                    103,
                    104,
                    104,
                    104,
                ],
                "low": [
                    99,
                    99,
                    99,
                    100,
                    100,
                    100,
                    101,
                    101,
                    101,
                    102,
                    102,
                    102,
                    103,
                    103,
                    103,
                ],
            }
        )

        indicator = AroonIndicator(period=10)
        result = indicator.compute(data)

        # Should handle equal values appropriately
        assert len(result) == 15

        # Values should still be valid
        valid_up = result["up"].dropna()
        valid_down = result["down"].dropna()

        assert all(0 <= val <= 100 for val in valid_up)
        assert all(0 <= val <= 100 for val in valid_down)
