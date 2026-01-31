"""
Tests for the Average True Range (ATR) indicator.

This module tests the ATR indicator implementation including:
- Basic functionality with Series output
- Parameter validation using schema system
- Edge cases and error handling
- Reference value validation
"""

import numpy as np
import pandas as pd
import pytest

from ktrdr.errors import DataError
from ktrdr.indicators.atr_indicator import ATRIndicator
from tests.indicators.validation_utils import create_standard_test_data


class TestATRIndicator:
    """Test the ATR indicator implementation."""

    def test_atr_initialization(self):
        """Test ATR indicator initialization with parameters."""
        # Test default parameters
        atr = ATRIndicator()
        assert atr.params["period"] == 14
        assert atr.name == "ATR"
        assert not atr.display_as_overlay  # Should be in separate panel

        # Test custom parameters
        atr = ATRIndicator(period=21)
        assert atr.params["period"] == 21

    def test_atr_parameter_validation(self):
        """Test parameter validation at construction time."""
        # Valid parameters
        atr = ATRIndicator(period=14)
        assert atr.params["period"] == 14

        # Test defaults
        atr_default = ATRIndicator()
        assert atr_default.params["period"] == 14

        # Invalid parameters - below minimum
        with pytest.raises(DataError) as exc_info:
            ATRIndicator(period=0)
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

        # Invalid parameters - above maximum
        with pytest.raises(DataError) as exc_info:
            ATRIndicator(period=101)
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_atr_basic_computation(self):
        """Test basic ATR computation with simple data."""
        # Create data with increasing volatility
        data = pd.DataFrame(
            {
                "high": [
                    102,
                    104,
                    108,
                    106,
                    110,
                    109,
                    115,
                    112,
                    118,
                    120,
                    125,
                    122,
                    130,
                    128,
                    135,
                ],
                "low": [
                    100,
                    101,
                    105,
                    103,
                    107,
                    106,
                    112,
                    109,
                    115,
                    117,
                    122,
                    119,
                    127,
                    125,
                    132,
                ],
                "close": [
                    101,
                    103,
                    107,
                    104,
                    109,
                    108,
                    114,
                    111,
                    117,
                    119,
                    124,
                    121,
                    129,
                    127,
                    134,
                ],
            }
        )

        atr = ATRIndicator(period=5)
        result = atr.compute(data)

        # Check that result is a Series
        assert isinstance(result, pd.Series)
        # M3a: ATR returns unnamed Series (engine handles naming)
        assert result.name is None

        # Check that we have the right number of rows
        assert len(result) == len(data)

        # ATR values should always be positive
        atr_values = result.dropna()
        assert len(atr_values) > 0
        assert (atr_values > 0).all()

        # ATR should reflect increasing volatility in this data
        # Later values should generally be higher than earlier ones
        early_atr = atr_values.iloc[:3].mean()
        late_atr = atr_values.iloc[-3:].mean()
        assert late_atr > early_atr

    def test_atr_with_constant_data(self):
        """Test ATR with constant data (no volatility)."""
        # Create flat data
        data = pd.DataFrame(
            {
                "high": [100] * 20,
                "low": [100] * 20,
                "close": [100] * 20,
            }
        )

        atr = ATRIndicator(period=14)
        result = atr.compute(data)

        # With no volatility, ATR should be 0
        atr_values = result.dropna()
        assert (atr_values == 0.0).all()

    def test_atr_with_gaps(self):
        """Test ATR with price gaps between periods."""
        # Create data with significant gaps
        data = pd.DataFrame(
            {
                "high": [
                    102,
                    104,
                    130,
                    132,
                    105,
                    107,
                    109,
                    111,
                    113,
                    115,
                    117,
                    119,
                    121,
                    123,
                    125,
                ],
                "low": [
                    100,
                    102,
                    128,
                    130,
                    103,
                    105,
                    107,
                    109,
                    111,
                    113,
                    115,
                    117,
                    119,
                    121,
                    123,
                ],
                "close": [
                    101,
                    103,
                    129,
                    131,
                    104,
                    106,
                    108,
                    110,
                    112,
                    114,
                    116,
                    118,
                    120,
                    122,
                    124,
                ],
            }
        )

        atr = ATRIndicator(period=5)
        result = atr.compute(data)

        atr_values = result.dropna()

        # ATR should be positive and reflect the volatility from gaps
        assert (atr_values > 0).all()

        # The period with the gap (around index 2-3) should show higher ATR
        # when it appears in the rolling window
        gap_period_atr = result.iloc[6]  # Should include the gap in calculation
        normal_period_atr = result.iloc[-1]  # Later period without gaps
        assert gap_period_atr > normal_period_atr

    def test_atr_missing_columns(self):
        """Test error handling for missing required columns."""
        # Missing 'high' column
        data = pd.DataFrame(
            {
                "low": [100, 101, 102],
                "close": [101, 102, 103],
            }
        )

        atr = ATRIndicator()
        with pytest.raises(DataError, match="ATR requires columns: high"):
            atr.compute(data)

        # Missing multiple columns
        data = pd.DataFrame(
            {
                "open": [100, 101, 102],
            }
        )

        with pytest.raises(DataError, match="ATR requires columns"):
            atr.compute(data)

    def test_atr_insufficient_data(self):
        """Test error handling for insufficient data."""
        # Create minimal data that's insufficient
        data = pd.DataFrame(
            {
                "high": [101, 102, 103],
                "low": [100, 101, 102],
                "close": [100.5, 101.5, 102.5],
            }
        )

        # With default period=14, need at least 15 data points (period+1)
        atr = ATRIndicator()
        with pytest.raises(DataError, match="ATR requires at least 15 data points"):
            atr.compute(data)

        # Test with custom period
        atr = ATRIndicator(period=5)
        with pytest.raises(DataError, match="ATR requires at least 6 data points"):
            atr.compute(data)

    def test_atr_edge_cases(self):
        """Test ATR with various edge cases."""
        # Test with minimum required data
        atr = ATRIndicator(period=3)

        data = pd.DataFrame(
            {
                "high": [105, 104, 106, 108],
                "low": [103, 102, 104, 105],
                "close": [104, 103, 105, 107],
            }
        )

        result = atr.compute(data)
        assert isinstance(result, pd.Series)
        assert len(result) == 4
        # M3a: ATR returns unnamed Series (engine handles naming)
        assert result.name is None

        # First two values should be NaN (not enough data for period=3)
        # Values starting from index 2 should have ATR values
        assert pd.isna(result.iloc[0])
        assert pd.isna(result.iloc[1])
        assert not pd.isna(result.iloc[2])
        assert not pd.isna(result.iloc[3])
        assert result.iloc[2] > 0
        assert result.iloc[3] > 0

    def test_atr_true_range_calculation(self):
        """Test ATR True Range calculation accuracy."""
        # Create specific data to test True Range calculation
        data = pd.DataFrame(
            {
                "high": [110, 108, 112, 115],
                "low": [105, 103, 107, 110],
                "close": [108, 106, 111, 113],
            }
        )

        atr = ATRIndicator(period=3)
        result = atr.compute(data)

        # Manual calculation of True Range for verification:
        # Index 0: TR = 110 - 105 = 5 (no previous close)
        # Index 1: TR = max(108-103=5, |108-108|=0, |103-108|=5) = 5
        # Index 2: TR = max(112-107=5, |112-106|=6, |107-106|=1) = 6
        # Index 3: TR = max(115-110=5, |115-111|=4, |110-111|=1) = 5
        # ATR at index 3 = (5 + 6 + 5) / 3 = 5.333...

        expected_atr = (5 + 6 + 5) / 3
        assert abs(result.iloc[3] - expected_atr) < 1e-10

    def test_atr_with_extreme_volatility(self):
        """Test ATR with extreme volatility scenarios."""
        # Create data with very high volatility
        data = pd.DataFrame(
            {
                "high": [
                    100,
                    150,
                    80,
                    200,
                    50,
                    180,
                    70,
                    160,
                    90,
                    140,
                    110,
                    130,
                    120,
                    125,
                    122,
                ],
                "low": [
                    95,
                    140,
                    70,
                    190,
                    40,
                    170,
                    60,
                    150,
                    80,
                    130,
                    100,
                    120,
                    110,
                    115,
                    112,
                ],
                "close": [
                    98,
                    145,
                    75,
                    195,
                    45,
                    175,
                    65,
                    155,
                    85,
                    135,
                    105,
                    125,
                    115,
                    120,
                    117,
                ],
            }
        )

        atr = ATRIndicator(period=5)
        result = atr.compute(data)

        atr_values = result.dropna()

        # With extreme volatility, ATR should be quite high
        assert (atr_values > 10).all()  # Should be significant

        # All values should still be positive
        assert (atr_values > 0).all()

    def test_atr_standard_reference_data(self):
        """Test ATR with standard reference dataset."""
        # Create reference dataset 1
        patterns = [
            (100, 10, "linear_up"),  # Start at 100, 10 days up
            (110, 10, "constant"),  # Plateau at 110
            (110, 10, "linear_down"),  # 10 days down
            (100, 10, "constant"),  # Plateau at 100
            (100, 10, "linear_up"),  # 10 days up again
        ]
        data = create_standard_test_data(patterns)

        atr = ATRIndicator(period=14)
        result = atr.compute(data)

        # Verify structure
        assert isinstance(result, pd.Series)
        assert len(result) == len(data)
        # M3a: ATR returns unnamed Series (engine handles naming)
        assert result.name is None

        # Check some basic properties
        atr_values = result.dropna()

        # All values should be positive
        assert (atr_values > 0).all()

        # ATR should be relatively stable during constant periods
        # and higher during transition periods
        plateau_atr = result.iloc[20:25].mean()  # During plateau
        transition_atr = result.iloc[30:35].mean()  # During transition

        # Transition periods might have slightly higher volatility
        # but this data is quite smooth, so differences may be small
        assert plateau_atr > 0
        assert transition_atr > 0

    def test_atr_parameter_edge_values(self):
        """Test ATR with edge parameter values."""
        # Test minimum period
        atr = ATRIndicator(period=1)

        data = pd.DataFrame(
            {
                "high": [105, 104, 106],
                "low": [103, 102, 104],
                "close": [104, 103, 105],
            }
        )

        result = atr.compute(data)
        assert isinstance(result, pd.Series)
        assert len(result) == 3
        # M3a: ATR returns unnamed Series (engine handles naming)
        assert result.name is None

        # With period=1, ATR is just the True Range itself
        # First value: TR = 105 - 103 = 2
        # Second value: TR = max(104-102=2, |104-104|=0, |102-104|=2) = 2
        assert result.iloc[1] == 2.0

        # Test larger period
        atr = ATRIndicator(period=20)

        # Need enough data for this period
        np.random.seed(42)  # For reproducible test
        high_vals = 100 + np.random.randn(25).cumsum() + 5
        low_vals = 100 + np.random.randn(25).cumsum() - 5
        close_vals = 100 + np.random.randn(25).cumsum()

        data = pd.DataFrame(
            {
                "high": high_vals,
                "low": low_vals,
                "close": close_vals,
            }
        )

        result = atr.compute(data)
        assert isinstance(result, pd.Series)
        assert len(result) == 25
        # M3a: ATR returns unnamed Series (engine handles naming)
        assert result.name is None

    def test_atr_mathematical_accuracy(self):
        """Test ATR mathematical accuracy with known values."""
        # Create simple data for precise calculation verification
        data = pd.DataFrame(
            {
                "high": [12, 11, 13, 14, 12],
                "low": [10, 9, 11, 12, 10],
                "close": [11, 10, 12, 13, 11],
            }
        )

        atr = ATRIndicator(period=4)
        result = atr.compute(data)

        # Manual True Range calculations:
        # Index 0: TR = 12 - 10 = 2 (no previous close)
        # Index 1: TR = max(11-9=2, |11-11|=0, |9-11|=2) = 2
        # Index 2: TR = max(13-11=2, |13-10|=3, |11-10|=1) = 3
        # Index 3: TR = max(14-12=2, |14-12|=2, |12-12|=0) = 2
        # Index 4: TR = max(12-10=2, |12-13|=1, |10-13|=3) = 3
        # ATR at index 4 = (2 + 3 + 2 + 3) / 4 = 2.5

        expected_atr = (2 + 3 + 2 + 3) / 4
        assert abs(result.iloc[4] - expected_atr) < 1e-10


class TestATRParamsValidation:
    """Test Params-based parameter validation for ATR."""

    def test_params_comprehensive_validation(self):
        """Test comprehensive Params validation at construction time."""
        # Test valid parameters
        atr = ATRIndicator(period=21)
        assert atr.params["period"] == 21

        # Test defaults
        atr_default = ATRIndicator()
        assert atr_default.params["period"] == 14

        # Test validation errors at construction time
        with pytest.raises(DataError) as exc_info:
            ATRIndicator(period=0)
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

        with pytest.raises(DataError) as exc_info:
            ATRIndicator(period=101)
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_params_error_details(self):
        """Test error information from Params validation."""
        with pytest.raises(DataError) as exc_info:
            ATRIndicator(period=-1)
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"
        # The error message contains "Invalid parameters" and the details contain validation info
        assert "invalid" in str(exc_info.value.message).lower()
