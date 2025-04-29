"""
Tests for fuzzy logic membership function implementations.
"""

import pytest
import numpy as np
import pandas as pd

from ktrdr.fuzzy.membership import MembershipFunction, TriangularMF
from ktrdr.errors import ConfigurationError


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
        assert mf.evaluate(0) == 0.0    # At a
        assert mf.evaluate(50) == 1.0   # At b (peak)
        assert mf.evaluate(100) == 0.0  # At c
        
        # Values in left slope (a < x < b)
        assert mf.evaluate(25) == 0.5   # Midpoint between a and b
        
        # Values in right slope (b < x < c)
        assert mf.evaluate(75) == 0.5   # Midpoint between b and c
        
        # Values outside the range
        assert mf.evaluate(-10) == 0.0  # x < a
        assert mf.evaluate(110) == 0.0  # x > c
        
        # Test NaN handling
        assert np.isnan(mf.evaluate(np.nan))
        
        # Test with a = b (left edge case)
        mf = TriangularMF([50, 50, 100])
        assert mf.evaluate(50) == 1.0   # At a = b (peak)
        assert mf.evaluate(75) == 0.5   # Midpoint between b and c
        assert mf.evaluate(100) == 0.0  # At c
        
        # Test with b = c (right edge case)
        mf = TriangularMF([0, 50, 50])
        assert mf.evaluate(0) == 0.0    # At a
        assert mf.evaluate(25) == 0.5   # Midpoint between a and b
        assert mf.evaluate(50) == 1.0   # At b = c (peak)
        
        # Test with a = b = c (singleton)
        mf = TriangularMF([50, 50, 50])
        assert mf.evaluate(49) == 0.0   # Just below singleton
        assert mf.evaluate(50) == 1.0   # At singleton
        assert mf.evaluate(51) == 0.0   # Just above singleton

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
        np.testing.assert_array_equal(
            np.isnan(result), 
            np.isnan(expected)
        )
        # Check non-NaN values
        mask = ~np.isnan(expected)
        np.testing.assert_array_almost_equal(
            result[mask], 
            expected[mask]
        )
    
    def test_repr(self):
        """Test the string representation of the triangular MF."""
        mf = TriangularMF([0, 50, 100])
        assert repr(mf) == "TriangularMF(a=0, b=50, c=100)"
    
    def test_unsupported_input_type(self):
        """Test that an error is raised for unsupported input types."""
        mf = TriangularMF([0, 50, 100])
        with pytest.raises(TypeError) as exc_info:
            mf.evaluate("not a number")
        assert "Unsupported input type" in str(exc_info.value)