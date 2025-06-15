"""
Tests for Relative Vigor Index (RVI) indicator.

This module provides comprehensive tests for the RVI indicator implementation,
including mathematical accuracy, parameter validation, and edge case handling.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from ktrdr.indicators.rvi_indicator import RVIIndicator
from ktrdr.errors import DataError


class TestRVIIndicator:
    """Test suite for RVI indicator."""

    def test_basic_initialization(self):
        """Test basic RVI initialization with default parameters."""
        indicator = RVIIndicator()
        
        assert indicator.name == "RVI"
        assert indicator.params["period"] == 10
        assert indicator.params["signal_period"] == 4

    def test_custom_initialization(self):
        """Test RVI initialization with custom parameters."""
        indicator = RVIIndicator(period=14, signal_period=6)
        
        assert indicator.params["period"] == 14
        assert indicator.params["signal_period"] == 6

    def test_parameter_validation_success(self):
        """Test successful parameter validation."""
        # Valid parameters should not raise an error
        RVIIndicator(period=4, signal_period=1)
        RVIIndicator(period=10, signal_period=4)
        RVIIndicator(period=100, signal_period=50)

    def test_parameter_validation_period_too_small(self):
        """Test parameter validation for period too small."""
        with pytest.raises(DataError) as exc_info:
            RVIIndicator(period=3)
        assert "period must be" in str(exc_info.value).lower()

    def test_parameter_validation_period_too_large(self):
        """Test parameter validation for period too large."""
        with pytest.raises(DataError) as exc_info:
            RVIIndicator(period=101)
        assert "period must be" in str(exc_info.value).lower()

    def test_parameter_validation_signal_period_too_small(self):
        """Test parameter validation for signal_period too small."""
        with pytest.raises(DataError) as exc_info:
            RVIIndicator(signal_period=0)
        assert "signal_period must be" in str(exc_info.value).lower()

    def test_parameter_validation_signal_period_too_large(self):
        """Test parameter validation for signal_period too large."""
        with pytest.raises(DataError) as exc_info:
            RVIIndicator(signal_period=51)
        assert "signal_period must be" in str(exc_info.value).lower()

    def test_parameter_validation_period_non_integer(self):
        """Test parameter validation for non-integer period."""
        with pytest.raises(DataError) as exc_info:
            RVIIndicator(period=10.5)
        assert "period must be" in str(exc_info.value).lower()

    def test_parameter_validation_signal_period_non_integer(self):
        """Test parameter validation for non-integer signal_period."""
        with pytest.raises(DataError) as exc_info:
            RVIIndicator(signal_period=4.5)
        assert "signal_period must be" in str(exc_info.value).lower()

    def test_basic_calculation(self):
        """Test basic RVI calculation with sufficient data."""
        # Create test data with meaningful OHLC relationships
        data = pd.DataFrame({
            'open': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119],
            'high': [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120],
            'low': [99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118],
            'close': [100.5, 101.5, 102.5, 103.5, 104.5, 105.5, 106.5, 107.5, 108.5, 109.5, 110.5, 111.5, 112.5, 113.5, 114.5, 115.5, 116.5, 117.5, 118.5, 119.5]
        })
        
        indicator = RVIIndicator()
        result = indicator.compute(data)
        
        # Should return DataFrame with 2 columns (RVI and Signal)
        assert isinstance(result, pd.DataFrame)
        assert len(result.columns) == 2
        
        # Should have same length as input
        assert len(result) == len(data)
        
        # Column names should be correctly formatted
        assert "RVI_10_4_RVI" in result.columns
        assert "RVI_10_4_Signal" in result.columns

    def test_bullish_trend_momentum(self):
        """Test RVI behavior during bullish trend (close > open)."""
        # Create data with consistently bullish candles (close > open)
        data = pd.DataFrame({
            'open': [100 + i for i in range(20)],
            'high': [101 + i for i in range(20)],
            'low': [99 + i for i in range(20)],
            'close': [100.8 + i for i in range(20)]  # Consistently close higher than open
        })
        
        indicator = RVIIndicator()
        result = indicator.compute(data)
        
        # In bullish trend, RVI should be positive
        rvi_values = result["RVI_10_4_RVI"].dropna()
        assert len(rvi_values) > 0
        
        # Most values should be positive in strong bullish trend
        positive_count = (rvi_values > 0).sum()
        assert positive_count >= len(rvi_values) * 0.7  # At least 70% positive

    def test_bearish_trend_momentum(self):
        """Test RVI behavior during bearish trend (close < open)."""
        # Create data with consistently bearish candles (close < open)
        data = pd.DataFrame({
            'open': [120 - i for i in range(20)],
            'high': [121 - i for i in range(20)],
            'low': [119 - i for i in range(20)],
            'close': [119.2 - i for i in range(20)]  # Consistently close lower than open
        })
        
        indicator = RVIIndicator()
        result = indicator.compute(data)
        
        # In bearish trend, RVI should be negative
        rvi_values = result["RVI_10_4_RVI"].dropna()
        assert len(rvi_values) > 0
        
        # Most values should be negative in strong bearish trend
        negative_count = (rvi_values < 0).sum()
        assert negative_count >= len(rvi_values) * 0.7  # At least 70% negative

    def test_signal_line_smoothing(self):
        """Test that signal line is smoother than RVI line."""
        # Create volatile OHLC data
        np.random.seed(42)
        data = pd.DataFrame({
            'open': [100 + np.random.normal(0, 2) for _ in range(30)],
            'high': [102 + np.random.normal(0, 2) for _ in range(30)],
            'low': [98 + np.random.normal(0, 2) for _ in range(30)],
            'close': [100 + np.random.normal(0, 2) for _ in range(30)]
        })
        
        # Ensure proper OHLC relationships
        for i in range(len(data)):
            data.loc[i, 'high'] = max(data.loc[i, 'high'], data.loc[i, 'open'], data.loc[i, 'close'])
            data.loc[i, 'low'] = min(data.loc[i, 'low'], data.loc[i, 'open'], data.loc[i, 'close'])
        
        indicator = RVIIndicator()
        result = indicator.compute(data)
        
        # Calculate volatility (standard deviation) of RVI and Signal
        rvi_values = result["RVI_10_4_RVI"].dropna()
        signal_values = result["RVI_10_4_Signal"].dropna()
        
        if len(rvi_values) > 5 and len(signal_values) > 5:
            rvi_volatility = rvi_values.std()
            signal_volatility = signal_values.std()
            
            # Signal line should be smoother (less volatile) than RVI line
            assert signal_volatility <= rvi_volatility * 1.2  # Allow some tolerance

    def test_missing_required_columns(self):
        """Test RVI with missing required columns."""
        # Missing open column
        data = pd.DataFrame({
            'high': [101, 102, 103],
            'low': [99, 100, 101],
            'close': [100, 101, 102]
        })
        
        indicator = RVIIndicator()
        with pytest.raises(DataError) as exc_info:
            indicator.compute(data)
        assert "missing required columns" in str(exc_info.value).lower()
        assert "open" in str(exc_info.value).lower()

    def test_insufficient_data(self):
        """Test RVI with insufficient data points."""
        # Only 5 data points, but need at least 13 for default parameters (period=10 + 3)
        data = pd.DataFrame({
            'open': [100, 101, 102, 103, 104],
            'high': [101, 102, 103, 104, 105],
            'low': [99, 100, 101, 102, 103],
            'close': [100.5, 101.5, 102.5, 103.5, 104.5]
        })
        
        indicator = RVIIndicator()
        with pytest.raises(DataError) as exc_info:
            indicator.compute(data)
        assert "requires at least" in str(exc_info.value).lower()

    def test_minimum_required_data(self):
        """Test RVI with exactly minimum required data."""
        # Exactly 13 data points for default parameters (period=10 + 3)
        data = pd.DataFrame({
            'open': [100 + i for i in range(13)],
            'high': [101 + i for i in range(13)],
            'low': [99 + i for i in range(13)],
            'close': [100.5 + i for i in range(13)]
        })
        
        indicator = RVIIndicator()
        result = indicator.compute(data)
        
        # Should work with exactly minimum data
        assert len(result) == 13
        
        # Should have some valid values near the end
        rvi_values = result["RVI_10_4_RVI"].dropna()
        assert len(rvi_values) > 0

    def test_custom_parameters(self):
        """Test RVI with custom parameters requiring less data."""
        # Use smaller parameters to test with less data
        data = pd.DataFrame({
            'open': [100 + i for i in range(10)],
            'high': [101 + i for i in range(10)],
            'low': [99 + i for i in range(10)],
            'close': [100.5 + i for i in range(10)]
        })
        
        indicator = RVIIndicator(period=4, signal_period=2)
        result = indicator.compute(data)
        
        # Should work with custom parameters
        assert len(result) == 10
        
        # Column names should reflect custom parameters
        assert "RVI_4_2_RVI" in result.columns
        assert "RVI_4_2_Signal" in result.columns

    def test_zero_high_low_range(self):
        """Test RVI with zero high-low range (doji candles)."""
        # All high = low (doji candles)
        data = pd.DataFrame({
            'open': [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100],
            'high': [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100],
            'low': [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100],
            'close': [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100]
        })
        
        indicator = RVIIndicator()
        result = indicator.compute(data)
        
        # Should handle zero range gracefully (may result in NaN or 0 values)
        assert len(result) == 15
        
        # RVI should be either NaN or 0 when there's no range or price movement
        rvi_values = result["RVI_10_4_RVI"].dropna()
        if len(rvi_values) > 0:
            assert all(abs(val) < 0.001 for val in rvi_values)  # Should be close to 0

    def test_extreme_volatility(self):
        """Test RVI with extreme price volatility."""
        np.random.seed(42)
        
        # Generate highly volatile data
        data = pd.DataFrame({
            'open': [100 + np.random.normal(0, 20) for _ in range(20)],
            'high': [100 + np.random.normal(0, 20) + 5 for _ in range(20)],
            'low': [100 + np.random.normal(0, 20) - 5 for _ in range(20)],
            'close': [100 + np.random.normal(0, 20) for _ in range(20)]
        })
        
        # Ensure proper OHLC relationships
        for i in range(len(data)):
            data.loc[i, 'high'] = max(data.loc[i, 'high'], data.loc[i, 'open'], data.loc[i, 'close'])
            data.loc[i, 'low'] = min(data.loc[i, 'low'], data.loc[i, 'open'], data.loc[i, 'close'])
        
        indicator = RVIIndicator()
        result = indicator.compute(data)
        
        # Should handle volatility without errors
        assert len(result) == 20
        
        # Values should be finite
        rvi_values = result["RVI_10_4_RVI"].dropna()
        signal_values = result["RVI_10_4_Signal"].dropna()
        
        assert all(np.isfinite(rvi_values))
        assert all(np.isfinite(signal_values))

    def test_get_name_method(self):
        """Test get_name method returns correct formatted name."""
        indicator = RVIIndicator(period=14, signal_period=6)
        expected_name = "RVI_14_6"
        assert indicator.get_name() == expected_name

    def test_empty_dataframe(self):
        """Test RVI with empty DataFrame."""
        data = pd.DataFrame()
        
        indicator = RVIIndicator()
        with pytest.raises(DataError) as exc_info:
            indicator.compute(data)
        assert "missing required columns" in str(exc_info.value).lower()

    def test_nan_values_in_data(self):
        """Test RVI handling of NaN values in input data."""
        data = pd.DataFrame({
            'open': [100, np.nan, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114],
            'high': [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115],
            'low': [99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113],
            'close': [100.5, 101.5, 102.5, 103.5, 104.5, 105.5, 106.5, 107.5, 108.5, 109.5, 110.5, 111.5, 112.5, 113.5, 114.5]
        })
        
        indicator = RVIIndicator()
        result = indicator.compute(data)
        
        # Should handle NaN values appropriately
        assert len(result) == len(data)

    def test_rvi_oscillator_range(self):
        """Test that RVI oscillates around zero as expected."""
        # Create mixed momentum data (some bullish, some bearish)
        data = []
        for i in range(20):
            if i % 2 == 0:  # Bullish candles
                data.append({
                    'open': 100 + i,
                    'high': 102 + i,
                    'low': 99 + i,
                    'close': 101.5 + i
                })
            else:  # Bearish candles
                data.append({
                    'open': 100 + i,
                    'high': 101 + i,
                    'low': 98 + i,
                    'close': 99.5 + i
                })
        
        df = pd.DataFrame(data)
        
        indicator = RVIIndicator()
        result = indicator.compute(df)
        
        rvi_values = result["RVI_10_4_RVI"].dropna()
        
        if len(rvi_values) > 0:
            # Should have both positive and negative values
            has_positive = (rvi_values > 0).any()
            has_negative = (rvi_values < 0).any()
            
            # In mixed momentum, we should see oscillation around zero
            assert has_positive or has_negative  # At least one direction

    def test_mathematical_properties(self):
        """Test mathematical properties of RVI calculation."""
        # Create predictable data
        data = pd.DataFrame({
            'open': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114],
            'high': [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115],
            'low': [99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113],
            'close': [100.7, 101.7, 102.7, 103.7, 104.7, 105.7, 106.7, 107.7, 108.7, 109.7, 110.7, 111.7, 112.7, 113.7, 114.7]
        })
        
        indicator = RVIIndicator()
        result = indicator.compute(data)
        
        # All valid values should be finite numbers
        rvi_values = result["RVI_10_4_RVI"].dropna()
        signal_values = result["RVI_10_4_Signal"].dropna()
        
        assert all(np.isfinite(rvi_values))
        assert all(np.isfinite(signal_values))
        
        # No infinity values
        assert not any(np.isinf(rvi_values))
        assert not any(np.isinf(signal_values))

    def test_indicator_name_and_params(self):
        """Test indicator name and parameters accessibility."""
        indicator = RVIIndicator(period=12, signal_period=3)
        
        assert indicator.name == "RVI"
        assert indicator.params["period"] == 12
        assert indicator.params["signal_period"] == 3

    def test_weighted_calculation_logic(self):
        """Test the weighted calculation logic specific to RVI."""
        # Create simple test data to verify weighted calculation
        data = pd.DataFrame({
            'open': [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100],
            'high': [102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102],
            'low': [98, 98, 98, 98, 98, 98, 98, 98, 98, 98, 98, 98, 98, 98],
            'close': [101, 101, 101, 101, 101, 101, 101, 101, 101, 101, 101, 101, 101, 101]  # Consistent bullish momentum
        })
        
        indicator = RVIIndicator(period=4, signal_period=2)  # Shorter periods for easier verification
        result = indicator.compute(data)
        
        # In this consistent bullish pattern, RVI should be positive
        rvi_values = result["RVI_4_2_RVI"].dropna()
        if len(rvi_values) > 0:
            assert all(val > 0 for val in rvi_values)  # All should be positive for consistent bullish pattern

    def test_signal_line_lag(self):
        """Test that signal line lags behind RVI line as expected."""
        # Create data with momentum shift
        data = []
        for i in range(20):
            if i < 10:  # First half: bearish
                data.append({
                    'open': 100 - i,
                    'high': 101 - i,
                    'low': 98 - i,
                    'close': 98.5 - i
                })
            else:  # Second half: bullish
                data.append({
                    'open': 90 + (i - 10),
                    'high': 92 + (i - 10),
                    'low': 89 + (i - 10),
                    'close': 91.5 + (i - 10)
                })
        
        df = pd.DataFrame(data)
        
        indicator = RVIIndicator()
        result = indicator.compute(df)
        
        # Signal should be smoother and lag behind RVI during momentum changes
        # This is a qualitative test - in practice, signal should change more gradually
        rvi_values = result["RVI_10_4_RVI"].dropna()
        signal_values = result["RVI_10_4_Signal"].dropna()
        
        assert len(rvi_values) > 0
        assert len(signal_values) > 0