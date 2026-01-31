"""
Tests for the Stochastic Oscillator indicator.

This module tests the Stochastic indicator implementation including:
- Basic functionality with multi-output DataFrame
- Parameter validation using schema system
- Edge cases and error handling
- Reference value validation
"""

import numpy as np
import pandas as pd
import pytest

from ktrdr.errors import DataError
from ktrdr.indicators.stochastic_indicator import StochasticIndicator
from tests.indicators.validation_utils import create_standard_test_data


class TestStochasticIndicator:
    """Test the Stochastic Oscillator indicator implementation."""

    def test_stochastic_initialization(self):
        """Test Stochastic indicator initialization with parameters."""
        # Test default parameters
        stoch = StochasticIndicator()
        assert stoch.params["k_period"] == 14
        assert stoch.params["d_period"] == 3
        assert stoch.params["smooth_k"] == 3
        assert stoch.name == "Stochastic"
        assert not stoch.display_as_overlay  # Should be in separate panel

        # Test custom parameters
        stoch = StochasticIndicator(k_period=20, d_period=5, smooth_k=1)
        assert stoch.params["k_period"] == 20
        assert stoch.params["d_period"] == 5
        assert stoch.params["smooth_k"] == 1

    def test_stochastic_parameter_validation(self):
        """Test parameter validation at construction time."""
        # Valid parameters
        stoch = StochasticIndicator(k_period=14, d_period=3, smooth_k=3)
        assert stoch.params["k_period"] == 14
        assert stoch.params["d_period"] == 3
        assert stoch.params["smooth_k"] == 3

        # Test defaults
        stoch_default = StochasticIndicator()
        assert stoch_default.params["k_period"] == 14
        assert stoch_default.params["d_period"] == 3
        assert stoch_default.params["smooth_k"] == 3

        # Invalid parameters - below minimum
        with pytest.raises(DataError) as exc_info:
            StochasticIndicator(k_period=0)
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

        # Invalid parameters - above maximum
        with pytest.raises(DataError) as exc_info:
            StochasticIndicator(k_period=101)
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_stochastic_basic_computation(self):
        """Test basic Stochastic computation with simple data."""
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

        stoch = StochasticIndicator(k_period=5, d_period=3, smooth_k=1)
        result = stoch.compute(data)

        # Check that result is a DataFrame
        assert isinstance(result, pd.DataFrame)

        # Check column names
        expected_k_col = "k"
        expected_d_col = "d"
        assert expected_k_col in result.columns
        assert expected_d_col in result.columns
        assert len(result.columns) == 2

        # Check that we have the right number of rows
        assert len(result) == len(data)

        # For rising data, %K should generally increase
        k_values = result[expected_k_col].dropna()
        assert len(k_values) > 0

        # %D should be smoothed version of %K
        d_values = result[expected_d_col].dropna()
        assert len(d_values) > 0

        # All values should be between 0 and 100
        assert (k_values >= 0).all() and (k_values <= 100).all()
        assert (d_values >= 0).all() and (d_values <= 100).all()

    def test_stochastic_with_flat_data(self):
        """Test Stochastic with flat data (no price movement)."""
        # Create flat data
        data = pd.DataFrame(
            {
                "high": [100] * 20,
                "low": [100] * 20,
                "close": [100] * 20,
            }
        )

        stoch = StochasticIndicator(k_period=14, d_period=3, smooth_k=3)
        result = stoch.compute(data)

        # When high == low, %K should be filled with 50.0 (neutral)
        k_col = "k"
        d_col = "d"

        # After sufficient periods, both %K and %D should be 50.0
        k_values = result[k_col].iloc[-5:]  # Last 5 values
        d_values = result[d_col].iloc[-5:]

        assert (k_values == 50.0).all()
        assert (d_values == 50.0).all()

    def test_stochastic_missing_columns(self):
        """Test error handling for missing required columns."""
        # Missing 'high' column
        data = pd.DataFrame(
            {
                "low": [100, 101, 102],
                "close": [101, 102, 103],
            }
        )

        stoch = StochasticIndicator()
        with pytest.raises(DataError, match="Stochastic requires columns: high"):
            stoch.compute(data)

        # Missing multiple columns
        data = pd.DataFrame(
            {
                "open": [100, 101, 102],
            }
        )

        with pytest.raises(DataError, match="Stochastic requires columns"):
            stoch.compute(data)

    def test_stochastic_insufficient_data(self):
        """Test error handling for insufficient data."""
        # Create minimal data that's insufficient
        data = pd.DataFrame(
            {
                "high": [101, 102, 103],
                "low": [100, 101, 102],
                "close": [100.5, 101.5, 102.5],
            }
        )

        # With default parameters (k_period=14, d_period=3, smooth_k=3)
        # minimum required = max(14, 3) + 3 = 17 data points
        stoch = StochasticIndicator()
        with pytest.raises(
            DataError, match="Stochastic requires at least 17 data points"
        ):
            stoch.compute(data)

    def test_stochastic_edge_cases(self):
        """Test Stochastic with various edge cases."""
        # Test with minimum required data
        stoch = StochasticIndicator(k_period=3, d_period=2, smooth_k=1)

        # min_required = max(3, 1) + 2 = 5 data points
        data = pd.DataFrame(
            {
                "high": [105, 104, 106, 103, 107],
                "low": [103, 102, 104, 101, 105],
                "close": [104, 103, 105, 102, 106],
            }
        )

        result = stoch.compute(data)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 5

        # Test with larger smooth_k period
        stoch = StochasticIndicator(k_period=5, d_period=2, smooth_k=5)

        data = pd.DataFrame(
            {
                "high": [105, 104, 106, 103, 107, 102, 108, 101, 109],
                "low": [103, 102, 104, 101, 105, 100, 106, 99, 107],
                "close": [104, 103, 105, 102, 106, 101, 107, 100, 108],
            }
        )

        result = stoch.compute(data)
        assert isinstance(result, pd.DataFrame)

        k_col = "k"
        d_col = "d"
        assert k_col in result.columns
        assert d_col in result.columns

    def test_stochastic_standard_reference_data(self):
        """Test Stochastic with standard reference dataset."""
        # Create reference dataset 1
        patterns = [
            (100, 10, "linear_up"),  # Start at 100, 10 days up
            (110, 10, "constant"),  # Plateau at 110
            (110, 10, "linear_down"),  # 10 days down
            (100, 10, "constant"),  # Plateau at 100
            (100, 10, "linear_up"),  # 10 days up again
        ]
        data = create_standard_test_data(patterns)

        stoch = StochasticIndicator(k_period=14, d_period=3, smooth_k=3)
        result = stoch.compute(data)

        # Verify structure
        assert isinstance(result, pd.DataFrame)
        assert len(result) == len(data)

        k_col = "k"
        d_col = "d"
        assert k_col in result.columns
        assert d_col in result.columns

        # Check some basic properties
        k_values = result[k_col].dropna()
        d_values = result[d_col].dropna()

        # All values should be between 0 and 100
        assert (k_values >= 0).all() and (k_values <= 100).all()
        assert (d_values >= 0).all() and (d_values <= 100).all()

        # %D should be generally smoother than %K (lower volatility)
        k_std = k_values.std()
        d_std = d_values.std()
        assert d_std <= k_std * 1.1  # Allow some tolerance

    def test_stochastic_parameter_edge_values(self):
        """Test Stochastic with edge parameter values."""
        # Test minimum parameters
        stoch = StochasticIndicator(k_period=1, d_period=1, smooth_k=1)

        data = pd.DataFrame(
            {
                "high": [105, 104, 106],
                "low": [103, 102, 104],
                "close": [104, 103, 105],
            }
        )

        result = stoch.compute(data)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3

        # Test maximum reasonable parameters
        stoch = StochasticIndicator(k_period=20, d_period=10, smooth_k=10)

        # Need enough data for these parameters
        np.random.seed(42)  # For reproducible test
        data = pd.DataFrame(
            {
                "high": 100 + np.random.randn(50).cumsum() + 5,
                "low": 100 + np.random.randn(50).cumsum() - 5,
                "close": 100 + np.random.randn(50).cumsum(),
            }
        )

        result = stoch.compute(data)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 50


class TestStochasticParamsValidation:
    """Test Params-based parameter validation for Stochastic."""

    def test_params_comprehensive_validation(self):
        """Test comprehensive Params validation at construction time."""
        # Test all valid parameters
        stoch = StochasticIndicator(k_period=21, d_period=5, smooth_k=7)
        assert stoch.params["k_period"] == 21
        assert stoch.params["d_period"] == 5
        assert stoch.params["smooth_k"] == 7

        # Test partial parameters with defaults
        stoch_partial = StochasticIndicator(k_period=10)
        assert stoch_partial.params["k_period"] == 10
        assert stoch_partial.params["d_period"] == 3  # default
        assert stoch_partial.params["smooth_k"] == 3  # default

        # Test validation errors at construction time
        with pytest.raises(DataError) as exc_info:
            StochasticIndicator(k_period=0)
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

        with pytest.raises(DataError) as exc_info:
            StochasticIndicator(d_period=21)  # Above maximum
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"

    def test_params_error_details(self):
        """Test error information from Params validation."""
        with pytest.raises(DataError) as exc_info:
            StochasticIndicator(k_period=-1)
        assert exc_info.value.error_code == "INDICATOR-InvalidParameters"
        assert "invalid" in str(exc_info.value.message).lower()
