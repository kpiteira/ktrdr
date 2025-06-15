"""
Tests for the Williams %R indicator.

This module tests the Williams %R indicator implementation including:
- Basic functionality with Series output
- Parameter validation using schema system
- Edge cases and error handling
- Reference value validation
"""

import pytest
import pandas as pd
import numpy as np
from typing import Dict, Any

from ktrdr.indicators.williams_r_indicator import WilliamsRIndicator
from ktrdr.indicators.schemas import WILLIAMS_R_SCHEMA
from ktrdr.errors import DataError
from tests.indicators.validation_utils import create_standard_test_data


class TestWilliamsRIndicator:
    """Test the Williams %R indicator implementation."""

    def test_williams_r_initialization(self):
        """Test Williams %R indicator initialization with parameters."""
        # Test default parameters
        wr = WilliamsRIndicator()
        assert wr.params["period"] == 14
        assert wr.name == "WilliamsR"
        assert not wr.display_as_overlay  # Should be in separate panel

        # Test custom parameters
        wr = WilliamsRIndicator(period=21)
        assert wr.params["period"] == 21

    def test_williams_r_parameter_validation(self):
        """Test parameter validation using schema system."""
        # Valid parameters
        params = {"period": 14}
        validated = WILLIAMS_R_SCHEMA.validate(params)
        assert validated == params

        # Test defaults
        defaults = WILLIAMS_R_SCHEMA.validate({})
        assert defaults["period"] == 14

        # Invalid parameters - below minimum
        with pytest.raises(DataError):
            WILLIAMS_R_SCHEMA.validate({"period": 0})

        # Invalid parameters - above maximum
        with pytest.raises(DataError):
            WILLIAMS_R_SCHEMA.validate({"period": 101})

    def test_williams_r_basic_computation(self):
        """Test basic Williams %R computation with simple data."""
        # Create simple rising data
        data = pd.DataFrame(
            {
                "high": [
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
                "low": [
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
                "close": [
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
            }
        )

        wr = WilliamsRIndicator(period=5)
        result = wr.compute(data)

        # Check that result is a Series
        assert isinstance(result, pd.Series)
        assert result.name == "WilliamsR_5"

        # Check that we have the right number of rows
        assert len(result) == len(data)

        # For rising data where close is at the high, Williams %R should be close to 0
        wr_values = result.dropna()
        assert len(wr_values) > 0

        # All values should be between -100 and 0
        assert (wr_values >= -100).all() and (wr_values <= 0).all()

        # For this rising data where close is 1 below high with 2-point range:
        # %R = ((High - Close) / (High - Low)) × -100 = (1 / 2) × -100 = -50
        # But with rolling window, we get different ranges
        final_values = wr_values.iloc[-5:]  # Last 5 values
        # Expected value: ((116-115)/(116-110)) * -100 = -16.67
        assert abs(final_values.iloc[-1] - (-16.666667)) < 0.1

    def test_williams_r_with_falling_data(self):
        """Test Williams %R with falling data."""
        # Create falling data where close is at the low
        data = pd.DataFrame(
            {
                "high": [
                    116,
                    115,
                    114,
                    113,
                    112,
                    111,
                    110,
                    109,
                    108,
                    107,
                    106,
                    105,
                    104,
                    103,
                    102,
                ],
                "low": [
                    114,
                    113,
                    112,
                    111,
                    110,
                    109,
                    108,
                    107,
                    106,
                    105,
                    104,
                    103,
                    102,
                    101,
                    100,
                ],
                "close": [
                    114,
                    113,
                    112,
                    111,
                    110,
                    109,
                    108,
                    107,
                    106,
                    105,
                    104,
                    103,
                    102,
                    101,
                    100,
                ],
            }
        )

        wr = WilliamsRIndicator(period=5)
        result = wr.compute(data)

        wr_values = result.dropna()

        # For falling data where close = low, Williams %R should be close to -100
        # %R = ((High - Close) / (High - Low)) × -100 = (range / range) × -100 = -100
        final_values = wr_values.iloc[-5:]  # Last 5 values
        assert (final_values <= -90).all()  # Should be close to -100

    def test_williams_r_with_flat_data(self):
        """Test Williams %R with flat data (no price movement)."""
        # Create flat data
        data = pd.DataFrame(
            {
                "high": [100] * 20,
                "low": [100] * 20,
                "close": [100] * 20,
            }
        )

        wr = WilliamsRIndicator(period=14)
        result = wr.compute(data)

        # When high == low, %R should be filled with -50.0 (neutral)
        wr_values = result.iloc[-5:]  # Last 5 values
        assert (wr_values == -50.0).all()

    def test_williams_r_overbought_oversold_levels(self):
        """Test Williams %R with typical overbought and oversold scenarios."""
        # Create data that should trigger overbought conditions
        # High volatility with close near highs
        data = pd.DataFrame(
            {
                "high": [
                    100,
                    105,
                    110,
                    115,
                    120,
                    125,
                    130,
                    135,
                    140,
                    145,
                    150,
                    155,
                    160,
                    165,
                    170,
                ],
                "low": [
                    95,
                    100,
                    105,
                    110,
                    115,
                    120,
                    125,
                    130,
                    135,
                    140,
                    145,
                    150,
                    155,
                    160,
                    165,
                ],
                "close": [
                    99,
                    104,
                    109,
                    114,
                    119,
                    124,
                    129,
                    134,
                    139,
                    144,
                    149,
                    154,
                    159,
                    164,
                    169,
                ],  # Close near high
            }
        )

        wr = WilliamsRIndicator(period=10)
        result = wr.compute(data)

        wr_values = result.dropna()

        # With close consistently near high, should be in overbought territory (> -20)
        final_values = wr_values.iloc[-3:]  # Last 3 values
        assert (final_values > -30).all()  # Should be overbought

    def test_williams_r_missing_columns(self):
        """Test error handling for missing required columns."""
        # Missing 'high' column
        data = pd.DataFrame(
            {
                "low": [100, 101, 102],
                "close": [101, 102, 103],
            }
        )

        wr = WilliamsRIndicator()
        with pytest.raises(DataError, match="Williams %R requires columns: high"):
            wr.compute(data)

        # Missing multiple columns
        data = pd.DataFrame(
            {
                "open": [100, 101, 102],
            }
        )

        with pytest.raises(DataError, match="Williams %R requires columns"):
            wr.compute(data)

    def test_williams_r_insufficient_data(self):
        """Test error handling for insufficient data."""
        # Create minimal data that's insufficient
        data = pd.DataFrame(
            {
                "high": [101, 102, 103],
                "low": [100, 101, 102],
                "close": [100.5, 101.5, 102.5],
            }
        )

        # With default period=14, need at least 14 data points
        wr = WilliamsRIndicator()
        with pytest.raises(
            DataError, match="Williams %R requires at least 14 data points"
        ):
            wr.compute(data)

        # Test with custom period
        wr = WilliamsRIndicator(period=5)
        with pytest.raises(
            DataError, match="Williams %R requires at least 5 data points"
        ):
            wr.compute(data)

    def test_williams_r_edge_cases(self):
        """Test Williams %R with various edge cases."""
        # Test with minimum required data
        wr = WilliamsRIndicator(period=3)

        data = pd.DataFrame(
            {
                "high": [105, 104, 106],
                "low": [103, 102, 104],
                "close": [104, 103, 105],
            }
        )

        result = wr.compute(data)
        assert isinstance(result, pd.Series)
        assert len(result) == 3
        assert result.name == "WilliamsR_3"

        # Test with period=1 (minimum possible)
        wr = WilliamsRIndicator(period=1)

        data = pd.DataFrame(
            {
                "high": [105, 104, 106],
                "low": [103, 102, 104],
                "close": [104, 103, 105],
            }
        )

        result = wr.compute(data)
        assert isinstance(result, pd.Series)
        assert len(result) == 3

        # For period=1, %R = ((High - Close) / (High - Low)) × -100
        # First point: ((105 - 104) / (105 - 103)) × -100 = (1/2) × -100 = -50
        assert abs(result.iloc[0] - (-50.0)) < 1e-10

    def test_williams_r_standard_reference_data(self):
        """Test Williams %R with standard reference dataset."""
        # Create reference dataset 1
        patterns = [
            (100, 10, "linear_up"),  # Start at 100, 10 days up
            (110, 10, "constant"),  # Plateau at 110
            (110, 10, "linear_down"),  # 10 days down
            (100, 10, "constant"),  # Plateau at 100
            (100, 10, "linear_up"),  # 10 days up again
        ]
        data = create_standard_test_data(patterns)

        wr = WilliamsRIndicator(period=14)
        result = wr.compute(data)

        # Verify structure
        assert isinstance(result, pd.Series)
        assert len(result) == len(data)
        assert result.name == "WilliamsR_14"

        # Check some basic properties
        wr_values = result.dropna()

        # All values should be between -100 and 0
        assert (wr_values >= -100).all() and (wr_values <= 0).all()

        # During uptrend periods, %R should generally be less negative (closer to 0)
        # During downtrend periods, %R should be more negative (closer to -100)
        uptrend_values = wr_values.iloc[15:25]  # During plateau/early downtrend
        downtrend_values = wr_values.iloc[25:35]  # During downtrend

        # Mean of uptrend should be higher (less negative) than downtrend
        assert uptrend_values.mean() > downtrend_values.mean()

    def test_williams_r_parameter_edge_values(self):
        """Test Williams %R with edge parameter values."""
        # Test minimum period
        wr = WilliamsRIndicator(period=1)

        data = pd.DataFrame(
            {
                "high": [105, 104, 106],
                "low": [103, 102, 104],
                "close": [104, 103, 105],
            }
        )

        result = wr.compute(data)
        assert isinstance(result, pd.Series)
        assert len(result) == 3

        # Test maximum reasonable period
        wr = WilliamsRIndicator(period=50)

        # Need enough data for this period
        np.random.seed(42)  # For reproducible test
        data = pd.DataFrame(
            {
                "high": 100 + np.random.randn(60).cumsum() + 5,
                "low": 100 + np.random.randn(60).cumsum() - 5,
                "close": 100 + np.random.randn(60).cumsum(),
            }
        )

        result = wr.compute(data)
        assert isinstance(result, pd.Series)
        assert len(result) == 60
        assert result.name == "WilliamsR_50"

    def test_williams_r_mathematical_accuracy(self):
        """Test Williams %R mathematical accuracy with known values."""
        # Create specific data with known Williams %R values
        data = pd.DataFrame(
            {
                "high": [110, 110, 110, 110, 110],  # Constant high
                "low": [100, 100, 100, 100, 100],  # Constant low
                "close": [105, 102, 108, 101, 109],  # Various closes
            }
        )

        wr = WilliamsRIndicator(period=5)
        result = wr.compute(data)

        # For the last point (index 4):
        # Highest High = 110, Lowest Low = 100, Close = 109
        # %R = ((110 - 109) / (110 - 100)) × -100 = (1/10) × -100 = -10
        expected_last = -10.0
        assert abs(result.iloc[-1] - expected_last) < 1e-10

        # For points before the full window (index 3), we get -50.0 (NaN fill)
        # because min_periods=period, so only the last point (index 4) has a real value
        assert result.iloc[3] == -50.0  # NaN filled with neutral value

        # The last point (index 4) should have the correct calculation
        # Only the last point has 5 full periods for calculation


class TestWilliamsRSchemaValidation:
    """Test schema-based parameter validation for Williams %R."""

    def test_schema_comprehensive_validation(self):
        """Test comprehensive schema validation."""
        # Test valid parameters
        valid_params = {"period": 21}
        validated = WILLIAMS_R_SCHEMA.validate(valid_params)
        assert validated == valid_params

        # Test defaults
        defaults = WILLIAMS_R_SCHEMA.validate({})
        assert defaults["period"] == 14

        # Test string to int conversion
        string_params = {"period": "20"}
        validated = WILLIAMS_R_SCHEMA.validate(string_params)
        assert validated["period"] == 20

        # Test validation errors
        with pytest.raises(DataError):
            WILLIAMS_R_SCHEMA.validate({"period": "invalid"})

        with pytest.raises(DataError):
            WILLIAMS_R_SCHEMA.validate({"period": 0})

        with pytest.raises(DataError):
            WILLIAMS_R_SCHEMA.validate({"period": 101})

        with pytest.raises(DataError):
            WILLIAMS_R_SCHEMA.validate({"unknown_param": 123})

    def test_schema_error_details(self):
        """Test detailed error information from schema validation."""
        try:
            WILLIAMS_R_SCHEMA.validate({"period": -1})
            assert False, "Should have raised DataError"
        except DataError as e:
            assert e.error_code == "PARAM-BelowMinimum"
            assert "period" in str(e.message)
            assert "minimum" in e.details
            assert "received" in e.details

        try:
            WILLIAMS_R_SCHEMA.validate({"period": "not_a_number"})
            assert False, "Should have raised DataError"
        except DataError as e:
            assert e.error_code == "PARAM-InvalidType"
            assert "period" in e.details["parameter"]
