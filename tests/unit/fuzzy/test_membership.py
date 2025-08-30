"""
Tests for fuzzy logic membership function implementations.
"""

import numpy as np
import pandas as pd
import pytest

from ktrdr.errors import ConfigurationError
from ktrdr.fuzzy.membership import (
    GaussianMF,
    MembershipFunctionFactory,
    TrapezoidalMF,
    TriangularMF,
)


class TestTriangularMF:
    """Tests for triangular membership function implementation."""

    def test_valid_initialization(self):
        """Test valid initialization of triangular membership function."""
        # Standard case with a < b < c
        mf = TriangularMF([0, 50, 100])
        assert mf.a == 0
        assert mf.b == 50
        assert mf.c == 100

        # Edge case with a = b < c
        mf = TriangularMF([0, 0, 100])
        assert mf.a == 0
        assert mf.b == 0
        assert mf.c == 100

        # Edge case with a < b = c
        mf = TriangularMF([0, 100, 100])
        assert mf.a == 0
        assert mf.b == 100
        assert mf.c == 100

        # Edge case with a = b = c
        mf = TriangularMF([50, 50, 50])
        assert mf.a == 50
        assert mf.b == 50
        assert mf.c == 50

    def test_invalid_initialization(self):
        """Test that initialization fails with invalid parameters."""
        # Wrong number of parameters
        with pytest.raises(ConfigurationError) as exc_info:
            TriangularMF([0, 50])
        assert "requires exactly 3 parameters" in str(exc_info.value)

        with pytest.raises(ConfigurationError) as exc_info:
            TriangularMF([0, 50, 100, 150])
        assert "requires exactly 3 parameters" in str(exc_info.value)

        # Invalid parameter ordering
        with pytest.raises(ConfigurationError) as exc_info:
            TriangularMF([50, 0, 100])  # a > b
        assert "parameters must satisfy: a ≤ b ≤ c" in str(exc_info.value)

        with pytest.raises(ConfigurationError) as exc_info:
            TriangularMF([0, 100, 50])  # b > c
        assert "parameters must satisfy: a ≤ b ≤ c" in str(exc_info.value)

    def test_scalar_evaluation(self):
        """Test evaluation with scalar inputs."""
        # Standard triangular MF [0, 50, 100]
        mf = TriangularMF([0, 50, 100])

        # Values at key points
        assert mf.evaluate(0) == 0.0  # At a
        assert mf.evaluate(50) == 1.0  # At b (peak)
        assert mf.evaluate(100) == 0.0  # At c

        # Values in left slope (a < x < b)
        assert mf.evaluate(25) == 0.5  # Midpoint between a and b

        # Values in right slope (b < x < c)
        assert mf.evaluate(75) == 0.5  # Midpoint between b and c

        # Values outside the range
        assert mf.evaluate(-10) == 0.0  # x < a
        assert mf.evaluate(110) == 0.0  # x > c

        # Test NaN handling
        assert np.isnan(mf.evaluate(np.nan))

        # Test with a = b (left edge case)
        mf = TriangularMF([50, 50, 100])
        assert mf.evaluate(50) == 1.0  # At a = b (peak)
        assert mf.evaluate(75) == 0.5  # Midpoint between b and c
        assert mf.evaluate(100) == 0.0  # At c

        # Test with b = c (right edge case)
        mf = TriangularMF([0, 50, 50])
        assert mf.evaluate(0) == 0.0  # At a
        assert mf.evaluate(25) == 0.5  # Midpoint between a and b
        assert mf.evaluate(50) == 1.0  # At b = c (peak)

        # Test with a = b = c (singleton)
        mf = TriangularMF([50, 50, 50])
        assert mf.evaluate(49) == 0.0  # Just below singleton
        assert mf.evaluate(50) == 1.0  # At singleton
        assert mf.evaluate(51) == 0.0  # Just above singleton

    def test_series_evaluation(self):
        """Test evaluation with pandas Series inputs."""
        mf = TriangularMF([0, 50, 100])

        # Create test series
        x = pd.Series([-10, 0, 25, 50, 75, 100, 110, np.nan])

        # Expected results
        expected = pd.Series([0.0, 0.0, 0.5, 1.0, 0.5, 0.0, 0.0, np.nan])

        # Evaluate series
        result = mf.evaluate(x)

        # Check results
        pd.testing.assert_series_equal(result, expected)

    def test_numpy_evaluation(self):
        """Test evaluation with numpy array inputs."""
        mf = TriangularMF([0, 50, 100])

        # Create test array
        x = np.array([-10, 0, 25, 50, 75, 100, 110, np.nan])

        # Expected results (with NaN handling)
        expected = np.array([0.0, 0.0, 0.5, 1.0, 0.5, 0.0, 0.0, np.nan])

        # Evaluate array
        result = mf.evaluate(x)

        # Check results (accounting for NaN values)
        np.testing.assert_array_equal(np.isnan(result), np.isnan(expected))
        # Check non-NaN values
        mask = ~np.isnan(expected)
        np.testing.assert_array_almost_equal(result[mask], expected[mask])

    def test_repr(self):
        """Test the string representation of the triangular MF."""
        mf = TriangularMF([0, 50, 100])
        assert repr(mf) == "TriangularMF(a=0, b=50, c=100)"

    def test_unsupported_input_type(self):
        """Test that an error is raised for unsupported input types."""
        mf = TriangularMF([0, 50, 100])
        with pytest.raises(TypeError) as exc_info:
            mf.evaluate("not a number")


class TestTrapezoidalMF:
    """Tests for trapezoidal membership function implementation."""

    def test_valid_initialization(self):
        """Test valid initialization of trapezoidal membership function."""
        # Standard case with a < b < c < d
        mf = TrapezoidalMF([0, 25, 75, 100])
        assert mf.a == 0
        assert mf.b == 25
        assert mf.c == 75
        assert mf.d == 100

        # Edge case with a = b < c < d
        mf = TrapezoidalMF([0, 0, 50, 100])
        assert mf.a == 0
        assert mf.b == 0
        assert mf.c == 50
        assert mf.d == 100

        # Edge case with a < b = c < d
        mf = TrapezoidalMF([0, 50, 50, 100])
        assert mf.a == 0
        assert mf.b == 50
        assert mf.c == 50
        assert mf.d == 100

        # Edge case with a < b < c = d
        mf = TrapezoidalMF([0, 25, 100, 100])
        assert mf.a == 0
        assert mf.b == 25
        assert mf.c == 100
        assert mf.d == 100

    def test_invalid_initialization(self):
        """Test that initialization fails with invalid parameters."""
        # Wrong number of parameters
        with pytest.raises(ConfigurationError) as exc_info:
            TrapezoidalMF([0, 25, 75])
        assert "requires exactly 4 parameters" in str(exc_info.value)

        with pytest.raises(ConfigurationError) as exc_info:
            TrapezoidalMF([0, 25, 75, 100, 125])
        assert "requires exactly 4 parameters" in str(exc_info.value)

        # Invalid parameter ordering
        with pytest.raises(ConfigurationError) as exc_info:
            TrapezoidalMF([100, 25, 75, 0])  # a > b
        assert "must satisfy: a ≤ b ≤ c ≤ d" in str(exc_info.value)

        with pytest.raises(ConfigurationError) as exc_info:
            TrapezoidalMF([0, 75, 25, 100])  # b > c
        assert "must satisfy: a ≤ b ≤ c ≤ d" in str(exc_info.value)

        with pytest.raises(ConfigurationError) as exc_info:
            TrapezoidalMF([0, 25, 100, 75])  # c > d
        assert "must satisfy: a ≤ b ≤ c ≤ d" in str(exc_info.value)

    def test_scalar_evaluation(self):
        """Test evaluation with scalar inputs."""
        mf = TrapezoidalMF([0, 25, 75, 100])

        # Test key points
        assert mf.evaluate(-10) == 0.0  # Before start
        assert mf.evaluate(0) == 0.0  # At start
        assert mf.evaluate(12.5) == 0.5  # Rising edge midpoint
        assert mf.evaluate(25) == 1.0  # Plateau start
        assert mf.evaluate(50) == 1.0  # Plateau middle
        assert mf.evaluate(75) == 1.0  # Plateau end
        assert mf.evaluate(87.5) == 0.5  # Falling edge midpoint
        assert mf.evaluate(100) == 0.0  # At end
        assert mf.evaluate(110) == 0.0  # After end

        # Test NaN handling
        result = mf.evaluate(np.nan)
        assert pd.isna(result)

    def test_degenerate_cases(self):
        """Test degenerate cases where parameters are equal."""
        # Triangular case: b = c (no plateau)
        mf = TrapezoidalMF([0, 50, 50, 100])
        assert mf.evaluate(25) == 0.5
        assert mf.evaluate(50) == 1.0
        assert mf.evaluate(75) == 0.5

        # Spike case: a = b = c < d
        # When a = b = c, x at that point is treated as boundary case
        mf = TrapezoidalMF([50, 50, 50, 100])
        assert mf.evaluate(49) == 0.0
        # x=50 falls on boundary (x <= a), so returns 0.0
        assert mf.evaluate(50) == 0.0
        # But x > 50 would fall in the falling edge
        assert abs(mf.evaluate(51) - 0.98) < 0.02  # Close to 1.0 on falling edge
        assert mf.evaluate(75) == 0.5

    def test_series_evaluation(self):
        """Test evaluation with pandas Series inputs."""
        mf = TrapezoidalMF([0, 25, 75, 100])

        # Create test series
        x = pd.Series([-10, 0, 12.5, 25, 50, 75, 87.5, 100, 110, np.nan])

        # Expected results
        expected = pd.Series([0.0, 0.0, 0.5, 1.0, 1.0, 1.0, 0.5, 0.0, 0.0, np.nan])

        # Evaluate series
        result = mf.evaluate(x)

        # Check results
        pd.testing.assert_series_equal(result, expected)

    def test_numpy_evaluation(self):
        """Test evaluation with numpy array inputs."""
        mf = TrapezoidalMF([0, 25, 75, 100])

        # Create test array
        x = np.array([-10, 0, 12.5, 25, 50, 75, 87.5, 100, 110, np.nan])

        # Expected results
        expected = np.array([0.0, 0.0, 0.5, 1.0, 1.0, 1.0, 0.5, 0.0, 0.0, np.nan])

        # Evaluate array
        result = mf.evaluate(x)

        # Check results (accounting for NaN values)
        np.testing.assert_array_equal(np.isnan(result), np.isnan(expected))
        # Check non-NaN values
        mask = ~np.isnan(expected)
        np.testing.assert_array_almost_equal(result[mask], expected[mask])

    def test_repr(self):
        """Test the string representation of the trapezoidal MF."""
        mf = TrapezoidalMF([0, 25, 75, 100])
        assert repr(mf) == "TrapezoidalMF(a=0, b=25, c=75, d=100)"

    def test_unsupported_input_type(self):
        """Test that an error is raised for unsupported input types."""
        mf = TrapezoidalMF([0, 25, 75, 100])
        with pytest.raises(TypeError) as exc_info:
            mf.evaluate("not a number")


class TestGaussianMF:
    """Tests for Gaussian membership function implementation."""

    def test_valid_initialization(self):
        """Test valid initialization of Gaussian membership function."""
        # Standard case
        mf = GaussianMF([50, 10])
        assert mf.mu == 50
        assert mf.sigma == 10

        # Different values
        mf = GaussianMF([0, 1])
        assert mf.mu == 0
        assert mf.sigma == 1

        # Large sigma
        mf = GaussianMF([100, 50])
        assert mf.mu == 100
        assert mf.sigma == 50

    def test_invalid_initialization(self):
        """Test that initialization fails with invalid parameters."""
        # Wrong number of parameters
        with pytest.raises(ConfigurationError) as exc_info:
            GaussianMF([50])
        assert "requires exactly 2 parameters" in str(exc_info.value)

        with pytest.raises(ConfigurationError) as exc_info:
            GaussianMF([50, 10, 5])
        assert "requires exactly 2 parameters" in str(exc_info.value)

        # Invalid sigma (must be > 0)
        with pytest.raises(ConfigurationError) as exc_info:
            GaussianMF([50, 0])
        assert "sigma must be greater than 0" in str(exc_info.value)

        with pytest.raises(ConfigurationError) as exc_info:
            GaussianMF([50, -5])
        assert "sigma must be greater than 0" in str(exc_info.value)

    def test_scalar_evaluation(self):
        """Test evaluation with scalar inputs."""
        mf = GaussianMF([50, 10])

        # Test key points
        assert mf.evaluate(50) == 1.0  # At center
        result_40 = mf.evaluate(40)  # -1 sigma
        result_60 = mf.evaluate(60)  # +1 sigma
        assert abs(result_40 - 0.6065) < 0.001  # exp(-0.5)
        assert abs(result_60 - 0.6065) < 0.001  # exp(-0.5)

        # Symmetry test
        assert abs(mf.evaluate(40) - mf.evaluate(60)) < 1e-10

        # Values further from center should be smaller
        assert mf.evaluate(30) < mf.evaluate(40)
        assert mf.evaluate(70) < mf.evaluate(60)

        # Test NaN handling
        result = mf.evaluate(np.nan)
        assert pd.isna(result)

    def test_gaussian_properties(self):
        """Test mathematical properties of Gaussian function."""
        mf = GaussianMF([0, 1])  # Standard normal

        # Peak at center
        assert mf.evaluate(0) == 1.0

        # Specific values for standard normal
        # At ±1 sigma: exp(-0.5) ≈ 0.6065
        assert abs(mf.evaluate(1) - 0.6065) < 0.001
        assert abs(mf.evaluate(-1) - 0.6065) < 0.001

        # At ±2 sigma: exp(-2) ≈ 0.1353
        assert abs(mf.evaluate(2) - 0.1353) < 0.001
        assert abs(mf.evaluate(-2) - 0.1353) < 0.001

    def test_series_evaluation(self):
        """Test evaluation with pandas Series inputs."""
        mf = GaussianMF([50, 10])

        # Create test series
        x = pd.Series([30, 40, 50, 60, 70, np.nan])

        # Evaluate series
        result = mf.evaluate(x)

        # Check that center has maximum value
        assert result.iloc[2] == 1.0  # x=50
        # Check symmetry
        assert abs(result.iloc[1] - result.iloc[3]) < 1e-10  # x=40 vs x=60
        # Check NaN handling
        assert pd.isna(result.iloc[5])

    def test_numpy_evaluation(self):
        """Test evaluation with numpy array inputs."""
        mf = GaussianMF([50, 10])

        # Create test array
        x = np.array([30, 40, 50, 60, 70, np.nan])

        # Evaluate array
        result = mf.evaluate(x)

        # Check that center has maximum value
        assert result[2] == 1.0
        # Check symmetry
        assert abs(result[1] - result[3]) < 1e-10
        # Check NaN handling
        assert np.isnan(result[5])

    def test_different_widths(self):
        """Test Gaussian functions with different sigma values."""
        narrow = GaussianMF([50, 5])  # Narrow Gaussian
        wide = GaussianMF([50, 20])  # Wide Gaussian

        # Both should have same peak
        assert narrow.evaluate(50) == wide.evaluate(50) == 1.0

        # At same distance from center, narrow should have lower value
        assert narrow.evaluate(40) < wide.evaluate(40)
        assert narrow.evaluate(60) < wide.evaluate(60)

    def test_repr(self):
        """Test the string representation of the Gaussian MF."""
        mf = GaussianMF([50, 10])
        assert repr(mf) == "GaussianMF(μ=50, σ=10)"

    def test_unsupported_input_type(self):
        """Test that an error is raised for unsupported input types."""
        mf = GaussianMF([50, 10])
        with pytest.raises(TypeError) as exc_info:
            mf.evaluate("not a number")


class TestMembershipFunctionFactory:
    """Tests for membership function factory."""

    def test_create_triangular(self):
        """Test creating triangular membership function via factory."""
        mf = MembershipFunctionFactory.create("triangular", [0, 50, 100])
        assert isinstance(mf, TriangularMF)
        assert mf.a == 0
        assert mf.b == 50
        assert mf.c == 100

    def test_create_trapezoidal(self):
        """Test creating trapezoidal membership function via factory."""
        mf = MembershipFunctionFactory.create("trapezoidal", [0, 25, 75, 100])
        assert isinstance(mf, TrapezoidalMF)
        assert mf.a == 0
        assert mf.b == 25
        assert mf.c == 75
        assert mf.d == 100

    def test_create_gaussian(self):
        """Test creating Gaussian membership function via factory."""
        mf = MembershipFunctionFactory.create("gaussian", [50, 10])
        assert isinstance(mf, GaussianMF)
        assert mf.mu == 50
        assert mf.sigma == 10

    def test_case_insensitive(self):
        """Test that factory is case-insensitive."""
        mf1 = MembershipFunctionFactory.create("TRIANGULAR", [0, 50, 100])
        mf2 = MembershipFunctionFactory.create("Triangular", [0, 50, 100])
        mf3 = MembershipFunctionFactory.create("triangular", [0, 50, 100])

        assert all(isinstance(mf, TriangularMF) for mf in [mf1, mf2, mf3])

    def test_unknown_type(self):
        """Test that factory raises error for unknown types."""
        with pytest.raises(ConfigurationError) as exc_info:
            MembershipFunctionFactory.create("unknown", [0, 50, 100])
        assert "Unknown membership function type" in str(exc_info.value)

    def test_get_supported_types(self):
        """Test getting list of supported types."""
        types = MembershipFunctionFactory.get_supported_types()
        expected = ["triangular", "trapezoidal", "gaussian"]
        assert types == expected
