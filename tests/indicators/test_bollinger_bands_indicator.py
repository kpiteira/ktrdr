"""
Tests for Bollinger Bands technical indicator.

This module contains comprehensive tests for the BollingerBandsIndicator class,
validating calculation accuracy, parameter handling, edge cases, and integration
with the broader indicator framework.
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch

from ktrdr.indicators.bollinger_bands_indicator import BollingerBandsIndicator
from ktrdr.indicators.schemas import BOLLINGER_BANDS_SCHEMA
from ktrdr.errors import DataError


class TestBollingerBandsIndicator:
    """Test cases for Bollinger Bands indicator."""

    def test_basic_initialization(self):
        """Test basic initialization with default parameters."""
        bb = BollingerBandsIndicator()
        assert bb.params["period"] == 20
        assert bb.params["multiplier"] == 2.0
        assert bb.params["source"] == "close"

    def test_custom_initialization(self):
        """Test initialization with custom parameters."""
        bb = BollingerBandsIndicator(period=14, multiplier=1.5, source="high")
        assert bb.params["period"] == 14
        assert bb.params["multiplier"] == 1.5
        assert bb.params["source"] == "high"

    def test_parameter_validation_success(self):
        """Test successful parameter validation."""
        bb = BollingerBandsIndicator(period=10, multiplier=2.5, source="low")
        params = {"period": 10, "multiplier": 2.5, "source": "low"}
        validated = bb._validate_params(params)
        assert validated["period"] == 10
        assert validated["multiplier"] == 2.5
        assert validated["source"] == "low"

    def test_parameter_validation_period_too_small(self):
        """Test parameter validation with period too small."""
        bb = BollingerBandsIndicator()
        params = {"period": 1, "multiplier": 2.0, "source": "close"}
        with pytest.raises(DataError, match="period.*must be >= 2"):
            bb._validate_params(params)

    def test_parameter_validation_period_too_large(self):
        """Test parameter validation with period too large."""
        bb = BollingerBandsIndicator()
        params = {"period": 150, "multiplier": 2.0, "source": "close"}
        with pytest.raises(DataError, match="period.*must be <= 100"):
            bb._validate_params(params)

    def test_parameter_validation_multiplier_too_small(self):
        """Test parameter validation with multiplier too small."""
        bb = BollingerBandsIndicator()
        params = {"period": 20, "multiplier": 0.05, "source": "close"}
        with pytest.raises(DataError, match="multiplier.*must be >= 0.1"):
            bb._validate_params(params)

    def test_parameter_validation_multiplier_too_large(self):
        """Test parameter validation with multiplier too large."""
        bb = BollingerBandsIndicator()
        params = {"period": 20, "multiplier": 6.0, "source": "close"}
        with pytest.raises(DataError, match="multiplier.*must be <= 5.0"):
            bb._validate_params(params)

    def test_parameter_validation_invalid_source(self):
        """Test parameter validation with invalid source."""
        bb = BollingerBandsIndicator()
        params = {"period": 20, "multiplier": 2.0, "source": "invalid"}
        with pytest.raises(DataError, match="source.*must be one of"):
            bb._validate_params(params)

    def test_basic_calculation(self):
        """Test basic Bollinger Bands calculation."""
        # Create simple test data
        data = pd.DataFrame({
            "open": [100, 101, 102, 103, 104],
            "high": [101, 102, 103, 104, 105],
            "low": [99, 100, 101, 102, 103],
            "close": [100, 101, 102, 103, 104],
            "volume": [1000, 1000, 1000, 1000, 1000]
        })
        
        bb = BollingerBandsIndicator(period=3, multiplier=2.0)
        result = bb.compute(data)
        
        # Check result structure
        assert isinstance(result, pd.DataFrame)
        assert len(result.columns) == 3
        assert "upper" in result.columns
        assert "middle" in result.columns
        assert "lower" in result.columns
        assert len(result) == len(data)
        
        # Check that first (period-1) values are NaN
        assert pd.isna(result.iloc[0]["upper"])
        assert pd.isna(result.iloc[1]["upper"])
        
        # Check that period-th value is not NaN
        assert not pd.isna(result.iloc[2]["upper"])
        assert not pd.isna(result.iloc[2]["middle"])
        assert not pd.isna(result.iloc[2]["lower"])

    def test_mathematical_properties(self):
        """Test mathematical properties of Bollinger Bands."""
        # Create test data
        data = pd.DataFrame({
            "open": range(50, 100),
            "high": range(51, 101),
            "low": range(49, 99),
            "close": range(50, 100),
            "volume": [1000] * 50
        })
        
        bb = BollingerBandsIndicator(period=20, multiplier=2.0)
        result = bb.compute(data)
        
        # Remove NaN values for testing
        valid_result = result.dropna()
        
        # Upper band should always be >= middle band
        assert all(valid_result["upper"] >= valid_result["middle"])
        
        # Middle band should always be >= lower band
        assert all(valid_result["middle"] >= valid_result["lower"])
        
        # For trending data, bands should generally widen
        # (though this can vary based on local volatility)
        assert len(valid_result) > 10  # Ensure we have enough data

    def test_constant_prices(self):
        """Test Bollinger Bands with constant prices."""
        # Create data with constant prices
        data = pd.DataFrame({
            "open": [100] * 30,
            "high": [100] * 30,
            "low": [100] * 30,
            "close": [100] * 30,
            "volume": [1000] * 30
        })
        
        bb = BollingerBandsIndicator(period=10, multiplier=2.0)
        result = bb.compute(data)
        
        # With constant prices, standard deviation should be 0
        # So upper, middle, and lower bands should all equal the constant price
        valid_result = result.dropna()
        
        # All bands should be equal to the constant price
        assert all(abs(valid_result["upper"] - 100.0) < 1e-10)
        assert all(abs(valid_result["middle"] - 100.0) < 1e-10)
        assert all(abs(valid_result["lower"] - 100.0) < 1e-10)

    def test_missing_source_column(self):
        """Test error handling when source column is missing."""
        data = pd.DataFrame({
            "open": [100, 101, 102],
            "high": [101, 102, 103],
            "low": [99, 100, 101],
            # Missing 'close' column
            "volume": [1000, 1000, 1000]
        })
        
        bb = BollingerBandsIndicator(period=2, source="close")
        with pytest.raises(DataError, match="Source column 'close' not found"):
            bb.compute(data)

    def test_insufficient_data(self):
        """Test error handling with insufficient data."""
        data = pd.DataFrame({
            "open": [100, 101],
            "high": [101, 102],
            "low": [99, 100],
            "close": [100, 101],
            "volume": [1000, 1000]
        })
        
        bb = BollingerBandsIndicator(period=5)  # Need 5 points, but only have 2
        with pytest.raises(DataError, match="Insufficient data"):
            bb.compute(data)

    def test_different_sources(self):
        """Test Bollinger Bands calculation with different price sources."""
        data = pd.DataFrame({
            "open": [100, 105, 110, 115, 120],
            "high": [105, 110, 115, 120, 125],
            "low": [95, 100, 105, 110, 115],
            "close": [102, 107, 112, 117, 122],
            "volume": [1000, 1000, 1000, 1000, 1000]
        })
        
        # Test with different sources
        bb_close = BollingerBandsIndicator(period=3, source="close")
        bb_high = BollingerBandsIndicator(period=3, source="high")
        bb_low = BollingerBandsIndicator(period=3, source="low")
        
        result_close = bb_close.compute(data)
        result_high = bb_high.compute(data)
        result_low = bb_low.compute(data)
        
        # Results should be different for different sources
        valid_close = result_close.dropna()
        valid_high = result_high.dropna()
        valid_low = result_low.dropna()
        
        # High source should generally produce higher values
        assert valid_high["middle"].iloc[-1] > valid_close["middle"].iloc[-1]
        assert valid_close["middle"].iloc[-1] > valid_low["middle"].iloc[-1]

    def test_different_multipliers(self):
        """Test Bollinger Bands with different standard deviation multipliers."""
        data = pd.DataFrame({
            "close": [100, 102, 98, 105, 95, 108, 92, 110, 90, 112],
            "open": [99, 101, 97, 104, 94, 107, 91, 109, 89, 111],
            "high": [101, 103, 99, 106, 96, 109, 93, 111, 91, 113],
            "low": [98, 100, 96, 103, 93, 106, 90, 108, 88, 110],
            "volume": [1000] * 10
        })
        
        bb_1 = BollingerBandsIndicator(period=5, multiplier=1.0)
        bb_2 = BollingerBandsIndicator(period=5, multiplier=2.0)
        bb_3 = BollingerBandsIndicator(period=5, multiplier=3.0)
        
        result_1 = bb_1.compute(data)
        result_2 = bb_2.compute(data)
        result_3 = bb_3.compute(data)
        
        # Larger multipliers should produce wider bands
        valid_1 = result_1.dropna()
        valid_2 = result_2.dropna()
        valid_3 = result_3.dropna()
        
        # Middle bands should be identical
        assert all(abs(valid_1["middle"] - valid_2["middle"]) < 1e-10)
        assert all(abs(valid_2["middle"] - valid_3["middle"]) < 1e-10)
        
        # Band widths should increase with multiplier
        width_1 = valid_1["upper"] - valid_1["lower"]
        width_2 = valid_2["upper"] - valid_2["lower"]
        width_3 = valid_3["upper"] - valid_3["lower"]
        
        assert all(width_2 > width_1)
        assert all(width_3 > width_2)

    def test_get_name_method(self):
        """Test the get_name method returns correct format."""
        bb = BollingerBandsIndicator(period=15, multiplier=1.8)
        expected_name = "BollingerBands_15_1.8"
        assert bb.get_name() == expected_name

    def test_empty_dataframe(self):
        """Test handling of empty DataFrame."""
        data = pd.DataFrame()
        bb = BollingerBandsIndicator(period=10)
        
        with pytest.raises(DataError, match="Source column 'close' not found"):
            bb.compute(data)

    def test_single_row_dataframe(self):
        """Test handling of single-row DataFrame."""
        data = pd.DataFrame({
            "close": [100],
            "open": [99],
            "high": [101],
            "low": [98],
            "volume": [1000]
        })
        
        bb = BollingerBandsIndicator(period=5)
        with pytest.raises(DataError, match="Insufficient data"):
            bb.compute(data)

    def test_schema_integration(self):
        """Test integration with parameter schema system."""
        # Test that the schema is properly defined
        assert BOLLINGER_BANDS_SCHEMA.name == "BollingerBands"
        assert len(BOLLINGER_BANDS_SCHEMA.parameters) == 3
        
        # Test parameter names (parameters is a dict)
        param_names = list(BOLLINGER_BANDS_SCHEMA.parameters.keys())
        assert "period" in param_names
        assert "multiplier" in param_names
        assert "source" in param_names

    def test_with_real_market_data_pattern(self):
        """Test with realistic market data patterns."""
        # Simulate a realistic price pattern
        np.random.seed(42)
        base_price = 100
        n_days = 50
        
        # Generate price series with trend and volatility
        price_changes = np.random.normal(0.1, 2.0, n_days)  # Slight upward trend with volatility
        prices = [base_price]
        for change in price_changes[:-1]:
            prices.append(max(prices[-1] + change, 10))  # Prevent negative prices
        
        data = pd.DataFrame({
            "close": prices,
            "open": [p * 0.998 for p in prices],  # Slight gap between open and close
            "high": [p * 1.01 for p in prices],
            "low": [p * 0.99 for p in prices],
            "volume": np.random.randint(100000, 1000000, len(prices))
        })
        
        bb = BollingerBandsIndicator(period=20, multiplier=2.0)
        result = bb.compute(data)
        
        # Check that we get reasonable results
        valid_result = result.dropna()
        assert len(valid_result) > 20  # Should have plenty of valid data
        
        # Bands should be properly ordered
        assert all(valid_result["upper"] >= valid_result["middle"])
        assert all(valid_result["middle"] >= valid_result["lower"])
        
        # Bands should generally contain the prices (though price can break out)
        price_in_bands = (data["close"].iloc[-len(valid_result):] >= valid_result["lower"]) & \
                        (data["close"].iloc[-len(valid_result):] <= valid_result["upper"])
        # Most prices should be within bands (Bollinger Bands theory)
        assert price_in_bands.sum() / len(price_in_bands) > 0.8  # 80%+ within bands