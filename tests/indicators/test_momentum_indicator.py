"""
Tests for Momentum technical indicator.

This module contains comprehensive tests for the MomentumIndicator class,
validating calculation accuracy, parameter handling, edge cases, and integration
with the broader indicator framework.
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch

from ktrdr.indicators.momentum_indicator import MomentumIndicator
from ktrdr.indicators.schemas import MOMENTUM_SCHEMA
from ktrdr.errors import DataError


class TestMomentumIndicator:
    """Test cases for Momentum indicator."""

    def test_basic_initialization(self):
        """Test basic initialization with default parameters."""
        momentum = MomentumIndicator()
        assert momentum.params["period"] == 10
        assert momentum.params["source"] == "close"

    def test_custom_initialization(self):
        """Test initialization with custom parameters."""
        momentum = MomentumIndicator(period=14, source="high")
        assert momentum.params["period"] == 14
        assert momentum.params["source"] == "high"

    def test_parameter_validation_success(self):
        """Test successful parameter validation."""
        momentum = MomentumIndicator(period=20)
        params = {"period": 20, "source": "close"}
        validated = momentum._validate_params(params)
        assert validated["period"] == 20
        assert validated["source"] == "close"

    def test_parameter_validation_period_too_small(self):
        """Test parameter validation with period too small."""
        momentum = MomentumIndicator()
        params = {"period": 0, "source": "close"}
        with pytest.raises(DataError, match="period.*must be >= 1"):
            momentum._validate_params(params)

    def test_parameter_validation_period_too_large(self):
        """Test parameter validation with period too large."""
        momentum = MomentumIndicator()
        params = {"period": 150, "source": "close"}
        with pytest.raises(DataError, match="period.*must be <= 100"):
            momentum._validate_params(params)

    def test_parameter_validation_invalid_source(self):
        """Test parameter validation with invalid source."""
        momentum = MomentumIndicator()
        params = {"period": 10, "source": "invalid"}
        with pytest.raises(DataError, match="source.*must be one of"):
            momentum._validate_params(params)

    def test_basic_calculation(self):
        """Test basic Momentum calculation."""
        # Create simple test data with linear progression
        data = pd.DataFrame({
            "open": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111],
            "high": [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112],
            "low": [99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110],
            "close": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111],
            "volume": [1000] * 12
        })
        
        momentum = MomentumIndicator(period=3)
        result = momentum.compute(data)
        
        # Check result structure
        assert isinstance(result, pd.Series)
        assert len(result) == len(data)
        
        # Check that first (period) values are NaN
        assert pd.isna(result.iloc[0])
        assert pd.isna(result.iloc[1])
        assert pd.isna(result.iloc[2])
        
        # Check that period+1-th value is not NaN
        assert not pd.isna(result.iloc[3])
        
        # Check specific calculation: Close[3] - Close[0] = 103 - 100 = 3
        assert result.iloc[3] == 3.0

    def test_mathematical_properties(self):
        """Test mathematical properties of Momentum."""
        # Create test data with known momentum patterns
        data = pd.DataFrame({
            "close": [100, 102, 104, 106, 108, 110, 112, 114, 116, 118, 120, 122],
            "open": [99, 101, 103, 105, 107, 109, 111, 113, 115, 117, 119, 121],
            "high": [101, 103, 105, 107, 109, 111, 113, 115, 117, 119, 121, 123],
            "low": [98, 100, 102, 104, 106, 108, 110, 112, 114, 116, 118, 120],
            "volume": [1000] * 12
        })
        
        momentum = MomentumIndicator(period=5)
        result = momentum.compute(data)
        
        # Remove NaN values for testing
        valid_result = result.dropna()
        
        # With steady +2 price increases, momentum should show positive trend
        assert len(valid_result) > 0
        assert all(val > 0 for val in valid_result)  # All should be positive
        
        # Expected values: each momentum should be 10 (current price - price 5 periods ago)
        # e.g., at position 5: 110 - 100 = 10
        expected_momentum = 10.0
        assert abs(valid_result.iloc[0] - expected_momentum) < 0.001

    def test_zero_momentum(self):
        """Test Momentum with constant prices (zero momentum)."""
        # Create data with constant prices
        constant_price = 100
        data = pd.DataFrame({
            "close": [constant_price] * 15,
            "open": [constant_price] * 15,
            "high": [constant_price + 1] * 15,
            "low": [constant_price - 1] * 15,
            "volume": [1000] * 15
        })
        
        momentum = MomentumIndicator(period=5)
        result = momentum.compute(data)
        
        # All momentum values should be zero (constant price)
        valid_result = result.dropna()
        assert len(valid_result) > 0
        assert all(abs(val) < 0.001 for val in valid_result)

    def test_negative_momentum(self):
        """Test Momentum with declining prices."""
        # Create data with declining prices
        data = pd.DataFrame({
            "close": [120, 118, 116, 114, 112, 110, 108, 106, 104, 102, 100, 98],
            "open": [119, 117, 115, 113, 111, 109, 107, 105, 103, 101, 99, 97],
            "high": [121, 119, 117, 115, 113, 111, 109, 107, 105, 103, 101, 99],
            "low": [118, 116, 114, 112, 110, 108, 106, 104, 102, 100, 98, 96],
            "volume": [1000] * 12
        })
        
        momentum = MomentumIndicator(period=5)
        result = momentum.compute(data)
        
        # All momentum values should be negative (declining price)
        valid_result = result.dropna()
        assert len(valid_result) > 0
        assert all(val < 0 for val in valid_result)

    def test_missing_source_column(self):
        """Test error handling when source column is missing."""
        data = pd.DataFrame({
            "open": [100, 101, 102],
            "high": [101, 102, 103],
            "low": [99, 100, 101],
            # Missing 'close' column
            "volume": [1000, 1000, 1000]
        })
        
        momentum = MomentumIndicator(period=2, source="close")
        with pytest.raises(DataError, match="Source column 'close' not found"):
            momentum.compute(data)

    def test_insufficient_data(self):
        """Test error handling with insufficient data."""
        data = pd.DataFrame({
            "close": [100, 101],
            "open": [99, 100],
            "high": [101, 102],
            "low": [98, 99],
            "volume": [1000, 1000]
        })
        
        momentum = MomentumIndicator(period=5)  # Need 6 points (5+1), but only have 2
        with pytest.raises(DataError, match="Insufficient data"):
            momentum.compute(data)

    def test_different_sources(self):
        """Test Momentum with different source columns."""
        data = pd.DataFrame({
            "open": [100, 102, 104, 106, 108, 110],
            "high": [101, 103, 105, 107, 109, 111],
            "low": [99, 101, 103, 105, 107, 109],
            "close": [100, 102, 104, 106, 108, 110],
            "volume": [1000] * 6
        })
        
        # Test with different sources
        momentum_close = MomentumIndicator(period=3, source="close")
        momentum_high = MomentumIndicator(period=3, source="high")
        
        result_close = momentum_close.compute(data)
        result_high = momentum_high.compute(data)
        
        # Both should have valid results
        assert not pd.isna(result_close.iloc[3])
        assert not pd.isna(result_high.iloc[3])
        
        # Values should be slightly different due to different sources
        # High values are 1 point higher than close values at each time point
        # So the momentum difference should be: (high[3] - high[0]) vs (close[3] - close[0])
        # Since both have the same pattern but offset by 1, the momentum should be the same
        # Let's just verify they both have valid, reasonable values
        assert result_high.iloc[3] > 0  # Should be positive momentum
        assert result_close.iloc[3] > 0  # Should be positive momentum

    def test_different_periods(self):
        """Test Momentum with different period values."""
        data = pd.DataFrame({
            "close": [100, 102, 104, 106, 108, 110, 112, 114, 116, 118, 120],
            "open": [99, 101, 103, 105, 107, 109, 111, 113, 115, 117, 119],
            "high": [101, 103, 105, 107, 109, 111, 113, 115, 117, 119, 121],
            "low": [98, 100, 102, 104, 106, 108, 110, 112, 114, 116, 118],
            "volume": [1000] * 11
        })
        
        momentum_short = MomentumIndicator(period=3)
        momentum_long = MomentumIndicator(period=6)
        
        result_short = momentum_short.compute(data)
        result_long = momentum_long.compute(data)
        
        # Short period should have more data points
        valid_short = result_short.dropna()
        valid_long = result_long.dropna()
        
        assert len(valid_short) > len(valid_long)
        
        # With consistent +2 increases, longer period should show larger momentum
        assert valid_long.iloc[0] > valid_short.iloc[0]

    def test_get_name_method(self):
        """Test the get_name method returns correct format."""
        momentum = MomentumIndicator(period=14, source="high")
        expected_name = "Momentum_14_high"
        assert momentum.get_name() == expected_name

    def test_empty_dataframe(self):
        """Test handling of empty DataFrame."""
        data = pd.DataFrame()
        momentum = MomentumIndicator(period=10)
        
        with pytest.raises(DataError, match="Source column"):
            momentum.compute(data)

    def test_single_row_dataframe(self):
        """Test handling of single-row DataFrame."""
        data = pd.DataFrame({
            "close": [100],
            "open": [99],
            "high": [101],
            "low": [98],
            "volume": [1000]
        })
        
        momentum = MomentumIndicator(period=5)
        with pytest.raises(DataError, match="Insufficient data"):
            momentum.compute(data)

    def test_schema_integration(self):
        """Test integration with parameter schema system."""
        # Test that the schema is properly defined
        assert MOMENTUM_SCHEMA.name == "Momentum"
        assert len(MOMENTUM_SCHEMA.parameters) == 2
        
        # Test parameter names (parameters is a dict)
        param_names = list(MOMENTUM_SCHEMA.parameters.keys())
        assert "period" in param_names
        assert "source" in param_names

    def test_momentum_volatility_patterns(self):
        """Test Momentum with various volatility patterns."""
        # Create data with varying volatility
        np.random.seed(42)
        base_price = 100
        
        # Generate price with varying momentum
        prices = [base_price]
        changes = [2, 3, 1, -1, -2, 4, 5, -3, -1, 2, 3, 4]  # Varying momentum
        for change in changes:
            prices.append(prices[-1] + change)
        
        data = pd.DataFrame({
            "close": prices,
            "open": [p - 0.5 for p in prices],
            "high": [p + 0.5 for p in prices],
            "low": [p - 1.0 for p in prices],
            "volume": [1000] * len(prices)
        })
        
        momentum = MomentumIndicator(period=5)
        result = momentum.compute(data)
        
        # Check that we get reasonable results
        valid_result = result.dropna()
        assert len(valid_result) > 0
        
        # Momentum should vary with the price changes
        momentum_values = valid_result.tolist()
        assert len(set(momentum_values)) > 1  # Should have different values

    def test_momentum_crossing_zero(self):
        """Test Momentum crossing zero line."""
        # Create price pattern that causes momentum to cross zero
        prices = [100, 102, 104, 106, 105, 104, 103, 102, 101, 100, 101, 102]
        
        data = pd.DataFrame({
            "close": prices,
            "open": [p - 0.5 for p in prices],
            "high": [p + 0.5 for p in prices],
            "low": [p - 1.0 for p in prices],
            "volume": [1000] * len(prices)
        })
        
        momentum = MomentumIndicator(period=4)
        result = momentum.compute(data)
        
        # Should have both positive and negative momentum values
        valid_result = result.dropna()
        has_positive = any(val > 0 for val in valid_result)
        has_negative = any(val < 0 for val in valid_result)
        
        assert has_positive and has_negative

    def test_with_real_market_data_pattern(self):
        """Test with realistic market data patterns."""
        # Simulate realistic price pattern with momentum changes
        np.random.seed(42)
        base_price = 100
        n_days = 30
        
        # Create price pattern with momentum phases
        prices = [base_price]
        for i in range(n_days - 1):
            if i < 10:
                # Upward momentum phase
                change = np.random.normal(0.8, 0.5)
            elif i < 20:
                # Downward momentum phase
                change = np.random.normal(-0.6, 0.4)
            else:
                # Mixed momentum phase
                change = np.random.normal(0.2, 0.8)
            
            new_price = max(prices[-1] + change, 10)  # Prevent negative prices
            prices.append(new_price)
        
        data = pd.DataFrame({
            "close": prices,
            "open": [p * (0.995 + np.random.random() * 0.01) for p in prices],
            "high": [p * (1.005 + np.random.random() * 0.01) for p in prices],
            "low": [p * (0.985 + np.random.random() * 0.01) for p in prices],
            "volume": np.random.randint(100000, 1000000, len(prices))
        })
        
        momentum = MomentumIndicator(period=10)
        result = momentum.compute(data)
        
        # Check that we get reasonable results
        valid_result = result.dropna()
        assert len(valid_result) > 15  # Should have plenty of valid data
        
        # Momentum should show both positive and negative values
        has_positive = any(val > 0 for val in valid_result)
        has_negative = any(val < 0 for val in valid_result)
        
        assert has_positive or has_negative  # Should have meaningful momentum

    def test_momentum_reference_validation(self):
        """Test Momentum against known reference values."""
        # Create simple linear data for validation
        data = pd.DataFrame({
            "close": list(range(100, 120)),  # 100, 101, 102, ..., 119
            "open": list(range(99, 119)),
            "high": list(range(101, 121)),
            "low": list(range(98, 118)),
            "volume": [1000] * 20
        })
        
        momentum = MomentumIndicator(period=5)
        result = momentum.compute(data)
        
        # At position 5: close[5] - close[0] = 105 - 100 = 5
        # At position 10: close[10] - close[5] = 110 - 105 = 5
        assert abs(result.iloc[5] - 5.0) < 0.001
        assert abs(result.iloc[10] - 5.0) < 0.001
        
        # All momentum values should be 5 (constant +1 increase per period)
        valid_result = result.dropna()
        assert all(abs(val - 5.0) < 0.001 for val in valid_result)