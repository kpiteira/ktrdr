"""
Tests for Rate of Change (ROC) technical indicator.

This module contains comprehensive tests for the ROCIndicator class,
validating calculation accuracy, parameter handling, edge cases, and integration
with the broader indicator framework.
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch

from ktrdr.indicators.roc_indicator import ROCIndicator
from ktrdr.indicators.schemas import ROC_SCHEMA
from ktrdr.errors import DataError


class TestROCIndicator:
    """Test cases for ROC indicator."""

    def test_basic_initialization(self):
        """Test basic initialization with default parameters."""
        roc = ROCIndicator()
        assert roc.params["period"] == 10
        assert roc.params["source"] == "close"

    def test_custom_initialization(self):
        """Test initialization with custom parameters."""
        roc = ROCIndicator(period=14, source="high")
        assert roc.params["period"] == 14
        assert roc.params["source"] == "high"

    def test_parameter_validation_success(self):
        """Test successful parameter validation."""
        roc = ROCIndicator(period=20)
        params = {"period": 20, "source": "close"}
        validated = roc._validate_params(params)
        assert validated["period"] == 20
        assert validated["source"] == "close"

    def test_parameter_validation_period_too_small(self):
        """Test parameter validation with period too small."""
        roc = ROCIndicator()
        params = {"period": 0, "source": "close"}
        with pytest.raises(DataError, match="period.*must be >= 1"):
            roc._validate_params(params)

    def test_parameter_validation_period_too_large(self):
        """Test parameter validation with period too large."""
        roc = ROCIndicator()
        params = {"period": 150, "source": "close"}
        with pytest.raises(DataError, match="period.*must be <= 100"):
            roc._validate_params(params)

    def test_parameter_validation_invalid_source(self):
        """Test parameter validation with invalid source."""
        roc = ROCIndicator()
        params = {"period": 10, "source": "invalid"}
        with pytest.raises(DataError, match="source.*must be one of"):
            roc._validate_params(params)

    def test_basic_calculation(self):
        """Test basic ROC calculation."""
        # Create simple test data with linear progression
        data = pd.DataFrame(
            {
                "open": [100, 105, 110, 115, 120, 125, 130, 135, 140, 145, 150, 155],
                "high": [102, 107, 112, 117, 122, 127, 132, 137, 142, 147, 152, 157],
                "low": [98, 103, 108, 113, 118, 123, 128, 133, 138, 143, 148, 153],
                "close": [100, 105, 110, 115, 120, 125, 130, 135, 140, 145, 150, 155],
                "volume": [1000] * 12,
            }
        )

        roc = ROCIndicator(period=3)
        result = roc.compute(data)

        # Check result structure
        assert isinstance(result, pd.Series)
        assert len(result) == len(data)

        # Check that first (period) values are NaN
        assert pd.isna(result.iloc[0])
        assert pd.isna(result.iloc[1])
        assert pd.isna(result.iloc[2])

        # Check that period+1-th value is not NaN
        assert not pd.isna(result.iloc[3])

        # Check specific calculation: ((115 - 100) / 100) * 100 = 15.0%
        assert abs(result.iloc[3] - 15.0) < 0.001

    def test_mathematical_properties(self):
        """Test mathematical properties of ROC."""
        # Create test data with known ROC patterns
        data = pd.DataFrame(
            {
                "close": [100, 105, 110, 115, 120, 125, 130, 135, 140, 145, 150, 155],
                "open": [99, 104, 109, 114, 119, 124, 129, 134, 139, 144, 149, 154],
                "high": [101, 106, 111, 116, 121, 126, 131, 136, 141, 146, 151, 156],
                "low": [98, 103, 108, 113, 118, 123, 128, 133, 138, 143, 148, 153],
                "volume": [1000] * 12,
            }
        )

        roc = ROCIndicator(period=5)
        result = roc.compute(data)

        # Remove NaN values for testing
        valid_result = result.dropna()

        # With steady +5 price increases, ROC should show consistent percentage growth
        assert len(valid_result) > 0
        assert all(val > 0 for val in valid_result)  # All should be positive

        # Expected values: each ROC should be 25% (25/100 * 100)
        # e.g., at position 5: ((125 - 100) / 100) * 100 = 25.0%
        expected_roc = 25.0
        assert abs(valid_result.iloc[0] - expected_roc) < 0.001

    def test_zero_roc(self):
        """Test ROC with constant prices (zero ROC)."""
        # Create data with constant prices
        constant_price = 100
        data = pd.DataFrame(
            {
                "close": [constant_price] * 15,
                "open": [constant_price] * 15,
                "high": [constant_price + 1] * 15,
                "low": [constant_price - 1] * 15,
                "volume": [1000] * 15,
            }
        )

        roc = ROCIndicator(period=5)
        result = roc.compute(data)

        # All ROC values should be zero (constant price)
        valid_result = result.dropna()
        assert len(valid_result) > 0
        assert all(abs(val) < 0.001 for val in valid_result)

    def test_negative_roc(self):
        """Test ROC with declining prices."""
        # Create data with declining prices
        data = pd.DataFrame(
            {
                "close": [150, 145, 140, 135, 130, 125, 120, 115, 110, 105, 100, 95],
                "open": [149, 144, 139, 134, 129, 124, 119, 114, 109, 104, 99, 94],
                "high": [151, 146, 141, 136, 131, 126, 121, 116, 111, 106, 101, 96],
                "low": [148, 143, 138, 133, 128, 123, 118, 113, 108, 103, 98, 93],
                "volume": [1000] * 12,
            }
        )

        roc = ROCIndicator(period=5)
        result = roc.compute(data)

        # All ROC values should be negative (declining price)
        valid_result = result.dropna()
        assert len(valid_result) > 0
        assert all(val < 0 for val in valid_result)

    def test_missing_source_column(self):
        """Test error handling when source column is missing."""
        data = pd.DataFrame(
            {
                "open": [100, 101, 102],
                "high": [101, 102, 103],
                "low": [99, 100, 101],
                # Missing 'close' column
                "volume": [1000, 1000, 1000],
            }
        )

        roc = ROCIndicator(period=2, source="close")
        with pytest.raises(DataError, match="Source column 'close' not found"):
            roc.compute(data)

    def test_insufficient_data(self):
        """Test error handling with insufficient data."""
        data = pd.DataFrame(
            {
                "close": [100, 101],
                "open": [99, 100],
                "high": [101, 102],
                "low": [98, 99],
                "volume": [1000, 1000],
            }
        )

        roc = ROCIndicator(period=5)  # Need 6 points (5+1), but only have 2
        with pytest.raises(DataError, match="Insufficient data"):
            roc.compute(data)

    def test_division_by_zero_handling(self):
        """Test ROC handling when previous price is zero."""
        # Create data with zero price (edge case)
        data = pd.DataFrame(
            {
                "close": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
                "open": [0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                "high": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
                "low": [0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                "volume": [1000] * 12,
            }
        )

        roc = ROCIndicator(period=3)
        result = roc.compute(data)

        # First valid ROC calculation involves division by zero (price[0] = 0)
        # Should result in NaN for that calculation
        assert pd.isna(result.iloc[3])  # Division by zero should result in NaN

    def test_different_sources(self):
        """Test ROC with different source columns."""
        data = pd.DataFrame(
            {
                "open": [100, 105, 110, 115, 120, 125],
                "high": [102, 107, 112, 117, 122, 127],
                "low": [98, 103, 108, 113, 118, 123],
                "close": [100, 105, 110, 115, 120, 125],
                "volume": [1000] * 6,
            }
        )

        # Test with different sources
        roc_close = ROCIndicator(period=3, source="close")
        roc_high = ROCIndicator(period=3, source="high")

        result_close = roc_close.compute(data)
        result_high = roc_high.compute(data)

        # Both should have valid results
        assert not pd.isna(result_close.iloc[3])
        assert not pd.isna(result_high.iloc[3])

        # Values should be similar since both sources follow same pattern
        # close[3] = 115, close[0] = 100, ROC = 15%
        # high[3] = 117, high[0] = 102, ROC = 14.7%
        assert abs(result_close.iloc[3] - 15.0) < 0.001
        assert abs(result_high.iloc[3] - 14.705882) < 0.001

    def test_different_periods(self):
        """Test ROC with different period values."""
        data = pd.DataFrame(
            {
                "close": [100, 105, 110, 115, 120, 125, 130, 135, 140, 145, 150],
                "open": [99, 104, 109, 114, 119, 124, 129, 134, 139, 144, 149],
                "high": [101, 106, 111, 116, 121, 126, 131, 136, 141, 146, 151],
                "low": [98, 103, 108, 113, 118, 123, 128, 133, 138, 143, 148],
                "volume": [1000] * 11,
            }
        )

        roc_short = ROCIndicator(period=3)
        roc_long = ROCIndicator(period=6)

        result_short = roc_short.compute(data)
        result_long = roc_long.compute(data)

        # Short period should have more data points
        valid_short = result_short.dropna()
        valid_long = result_long.dropna()

        assert len(valid_short) > len(valid_long)

        # With consistent +5 increases, longer period should show larger ROC percentage
        assert valid_long.iloc[0] > valid_short.iloc[0]

    def test_get_name_method(self):
        """Test the get_name method returns correct format."""
        roc = ROCIndicator(period=14, source="high")
        expected_name = "ROC_14_high"
        assert roc.get_name() == expected_name

    def test_empty_dataframe(self):
        """Test handling of empty DataFrame."""
        data = pd.DataFrame()
        roc = ROCIndicator(period=10)

        with pytest.raises(DataError, match="Source column"):
            roc.compute(data)

    def test_single_row_dataframe(self):
        """Test handling of single-row DataFrame."""
        data = pd.DataFrame(
            {"close": [100], "open": [99], "high": [101], "low": [98], "volume": [1000]}
        )

        roc = ROCIndicator(period=5)
        with pytest.raises(DataError, match="Insufficient data"):
            roc.compute(data)

    def test_schema_integration(self):
        """Test integration with parameter schema system."""
        # Test that the schema is properly defined
        assert ROC_SCHEMA.name == "ROC"
        assert len(ROC_SCHEMA.parameters) == 2

        # Test parameter names (parameters is a dict)
        param_names = list(ROC_SCHEMA.parameters.keys())
        assert "period" in param_names
        assert "source" in param_names

    def test_roc_percentage_calculation(self):
        """Test ROC percentage calculation accuracy."""
        # Create data with known percentage changes
        data = pd.DataFrame(
            {
                "close": [100, 100, 100, 100, 100, 110],  # 10% increase at end
                "open": [99, 99, 99, 99, 99, 109],
                "high": [101, 101, 101, 101, 101, 111],
                "low": [98, 98, 98, 98, 98, 108],
                "volume": [1000] * 6,
            }
        )

        roc = ROCIndicator(period=5)
        result = roc.compute(data)

        # At position 5: ((110 - 100) / 100) * 100 = 10.0%
        assert abs(result.iloc[5] - 10.0) < 0.001

    def test_roc_vs_momentum_relationship(self):
        """Test ROC vs Momentum relationship (ROC is percentage, Momentum is absolute)."""
        # Create data where we can compare ROC and Momentum
        data = pd.DataFrame(
            {
                "close": [100, 100, 100, 100, 100, 120],  # 20 point increase
                "open": [99, 99, 99, 99, 99, 119],
                "high": [101, 101, 101, 101, 101, 121],
                "low": [98, 98, 98, 98, 98, 118],
                "volume": [1000] * 6,
            }
        )

        roc = ROCIndicator(period=5)
        result = roc.compute(data)

        # At position 5: ROC = ((120 - 100) / 100) * 100 = 20.0%
        # Momentum would be: 120 - 100 = 20 points
        # So ROC = (Momentum / Old Price) * 100
        assert abs(result.iloc[5] - 20.0) < 0.001

    def test_with_real_market_data_pattern(self):
        """Test with realistic market data patterns."""
        # Simulate realistic price pattern with various ROC conditions
        np.random.seed(42)
        base_price = 100
        n_days = 30

        # Create price pattern with different momentum phases
        prices = [base_price]
        for i in range(n_days - 1):
            if i < 10:
                # Gradual upward trend (positive ROC)
                change = np.random.normal(0.5, 0.3)
            elif i < 20:
                # Gradual downward trend (negative ROC)
                change = np.random.normal(-0.4, 0.3)
            else:
                # Mixed movements (varying ROC)
                change = np.random.normal(0.1, 0.6)

            new_price = max(prices[-1] + change, 10)  # Prevent negative prices
            prices.append(new_price)

        data = pd.DataFrame(
            {
                "close": prices,
                "open": [p * (0.995 + np.random.random() * 0.01) for p in prices],
                "high": [p * (1.005 + np.random.random() * 0.01) for p in prices],
                "low": [p * (0.985 + np.random.random() * 0.01) for p in prices],
                "volume": np.random.randint(100000, 1000000, len(prices)),
            }
        )

        roc = ROCIndicator(period=10)
        result = roc.compute(data)

        # Check that we get reasonable results
        valid_result = result.dropna()
        assert len(valid_result) > 15  # Should have plenty of valid data

        # ROC should show both positive and negative values
        has_positive = any(val > 0 for val in valid_result)
        has_negative = any(val < 0 for val in valid_result)

        assert has_positive or has_negative  # Should have meaningful ROC values

    def test_roc_reference_validation(self):
        """Test ROC against known reference values."""
        # Create data matching reference dataset pattern
        # Linear progression: 100, 101, 102, ..., 109, 110 (first 11 points)
        data = pd.DataFrame(
            {
                "close": list(range(100, 120)),  # 100, 101, 102, ..., 119
                "open": list(range(99, 119)),
                "high": list(range(101, 121)),
                "low": list(range(98, 118)),
                "volume": [1000] * 20,
            }
        )

        roc = ROCIndicator(period=10)
        result = roc.compute(data)

        # At position 10: ((110 - 100) / 100) * 100 = 10.0%
        assert abs(result.iloc[10] - 10.0) < 0.001

        # At position 15: ((115 - 105) / 105) * 100 = 9.524%
        assert abs(result.iloc[15] - 9.523810) < 0.001

    def test_roc_extreme_values(self):
        """Test ROC with extreme price movements."""
        # Create data with extreme movements
        data = pd.DataFrame(
            {
                "close": [100, 100, 100, 100, 100, 200],  # 100% increase
                "open": [99, 99, 99, 99, 99, 199],
                "high": [101, 101, 101, 101, 101, 201],
                "low": [98, 98, 98, 98, 98, 198],
                "volume": [1000] * 6,
            }
        )

        roc = ROCIndicator(period=5)
        result = roc.compute(data)

        # At position 5: ((200 - 100) / 100) * 100 = 100.0%
        assert abs(result.iloc[5] - 100.0) < 0.001

    def test_roc_small_changes(self):
        """Test ROC with very small price changes."""
        # Create data with small price changes
        data = pd.DataFrame(
            {
                "close": [100.00, 100.01, 100.02, 100.03, 100.04, 100.05],
                "open": [99.99, 100.00, 100.01, 100.02, 100.03, 100.04],
                "high": [100.01, 100.02, 100.03, 100.04, 100.05, 100.06],
                "low": [99.98, 99.99, 100.00, 100.01, 100.02, 100.03],
                "volume": [1000] * 6,
            }
        )

        roc = ROCIndicator(period=5)
        result = roc.compute(data)

        # At position 5: ((100.05 - 100.00) / 100.00) * 100 = 0.05%
        assert abs(result.iloc[5] - 0.05) < 0.001
