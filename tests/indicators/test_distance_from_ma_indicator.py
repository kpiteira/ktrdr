"""
Tests for the Distance from Moving Average indicator.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from ktrdr.indicators.distance_from_ma_indicator import DistanceFromMAIndicator
from ktrdr.errors import DataError


def create_test_data():
    """Create price data for testing distance from MA calculations."""
    # Create a date range for index
    start_date = datetime(2023, 1, 1)
    dates = [start_date + timedelta(days=i) for i in range(30)]

    # Create price series with known moving average behavior
    # Simple increasing prices for predictable calculations
    close_prices = [100 + i for i in range(30)]  # 100, 101, 102, ..., 129

    data = pd.DataFrame({
        'open': [price - 0.5 for price in close_prices],
        'high': [price + 1.0 for price in close_prices],
        'low': [price - 1.0 for price in close_prices],
        'close': close_prices,
        'volume': [1000 + i * 10 for i in range(30)]
    }, index=dates)

    return data


class TestDistanceFromMAIndicator:
    """Test cases for Distance from Moving Average indicator."""

    def test_initialization_default_params(self):
        """Test indicator initialization with default parameters."""
        indicator = DistanceFromMAIndicator()
        assert indicator.name == "DistanceFromMA"
        assert indicator.params["period"] == 20
        assert indicator.params["ma_type"] == "SMA"
        assert indicator.params["source"] == "close"
        assert not indicator.display_as_overlay

    def test_initialization_custom_params(self):
        """Test indicator initialization with custom parameters."""
        indicator = DistanceFromMAIndicator(period=14, ma_type="EMA", source="open")
        assert indicator.params["period"] == 14
        assert indicator.params["ma_type"] == "EMA"
        assert indicator.params["source"] == "open"

    def test_get_name(self):
        """Test the get_name method returns proper indicator names."""
        indicator_sma = DistanceFromMAIndicator(period=20, ma_type="SMA")
        assert indicator_sma.get_name() == "DistanceFromMA_SMA_20"

        indicator_ema = DistanceFromMAIndicator(period=14, ma_type="EMA")
        assert indicator_ema.get_name() == "DistanceFromMA_EMA_14"

    def test_compute_sma_distance(self):
        """Test distance calculation with SMA."""
        data = create_test_data()
        indicator = DistanceFromMAIndicator(period=5, ma_type="SMA")
        
        result = indicator.compute(data)
        
        # Verify return type and length
        assert isinstance(result, pd.Series)
        assert len(result) == len(data)
        
        # First 4 values should be NaN due to min_periods
        assert pd.isna(result.iloc[:4]).all()
        
        # For period=5, SMA at index 4 should be (100+101+102+103+104)/5 = 102
        # Distance = (104 - 102) / 102 * 100 = 1.96%
        expected_distance_idx4 = (104 - 102) / 102 * 100
        assert result.iloc[4] == pytest.approx(expected_distance_idx4, rel=0.01)

    def test_compute_ema_distance(self):
        """Test distance calculation with EMA."""
        data = create_test_data()
        indicator = DistanceFromMAIndicator(period=5, ma_type="EMA")
        
        result = indicator.compute(data)
        
        # Verify return type and length
        assert isinstance(result, pd.Series)
        assert len(result) == len(data)
        
        # Should have results starting from the first period
        assert not pd.isna(result.iloc[4:]).any()

    def test_compute_different_source(self):
        """Test distance calculation with different price source."""
        data = create_test_data()
        indicator = DistanceFromMAIndicator(period=5, source="high")
        
        result = indicator.compute(data)
        
        # Should use 'high' prices instead of 'close'
        assert isinstance(result, pd.Series)
        assert len(result) == len(data)

    def test_insufficient_data_error(self):
        """Test error handling for insufficient data."""
        data = create_test_data().iloc[:5]  # Only 5 rows
        indicator = DistanceFromMAIndicator(period=10)  # Needs 10 periods
        
        with pytest.raises(DataError) as exc_info:
            indicator.compute(data)
        
        assert "Insufficient data" in str(exc_info.value)
        assert exc_info.value.error_code == "DATA-InsufficientData"

    def test_missing_column_error(self):
        """Test error handling for missing required columns."""
        data = create_test_data().drop(columns=['close'])
        indicator = DistanceFromMAIndicator(source="close")
        
        with pytest.raises(DataError) as exc_info:
            indicator.compute(data)
        
        assert "Source column 'close' not found" in str(exc_info.value)
        assert exc_info.value.error_code == "DATA-MissingColumn"

    def test_invalid_ma_type_error(self):
        """Test error handling for invalid moving average type."""
        data = create_test_data()
        # Create indicator with invalid MA type by directly setting params
        indicator = DistanceFromMAIndicator()
        indicator.params["ma_type"] = "INVALID"
        
        with pytest.raises(DataError) as exc_info:
            indicator.compute(data)
        
        # The error message comes from schema validation
        assert "Parameter 'ma_type' must be one of" in str(exc_info.value)
        assert exc_info.value.error_code == "PARAM-InvalidOption"

    def test_zero_ma_values_handling(self):
        """Test handling of zero or near-zero moving average values."""
        # Create data with very small prices near zero
        dates = [datetime(2023, 1, 1) + timedelta(days=i) for i in range(10)]
        data = pd.DataFrame({
            'open': [1e-12] * 10,
            'high': [1e-12] * 10,
            'low': [1e-12] * 10,
            'close': [1e-12] * 10,
            'volume': [1000] * 10
        }, index=dates)
        
        indicator = DistanceFromMAIndicator(period=5)
        result = indicator.compute(data)
        
        # Should handle division by near-zero gracefully
        # Values should be 0.0 for near-zero denominators
        assert not pd.isna(result.iloc[4:]).any()
        assert all(result.iloc[4:] == 0.0)

    @pytest.mark.parametrize("period,ma_type", [
        (5, "SMA"),
        (10, "SMA"),
        (5, "EMA"),
        (10, "EMA"),
    ])
    def test_different_periods_and_types(self, period, ma_type):
        """Test distance calculation with different periods and MA types."""
        data = create_test_data()
        indicator = DistanceFromMAIndicator(period=period, ma_type=ma_type)
        
        result = indicator.compute(data)
        
        assert isinstance(result, pd.Series)
        assert len(result) == len(data)
        # Should have valid results after the warm-up period
        assert not pd.isna(result.iloc[period-1:]).any()

    def test_column_name_generation(self):
        """Test proper column name generation."""
        indicator = DistanceFromMAIndicator(period=20, ma_type="SMA")
        column_name = indicator.get_column_name()
        expected_name = "distancefromma_20_SMA"  # MA type is not lowercased
        assert column_name == expected_name

    def test_positive_negative_distances(self):
        """Test that distances are correctly positive/negative."""
        # Create data where price moves above and below MA
        dates = [datetime(2023, 1, 1) + timedelta(days=i) for i in range(20)]
        
        # Create oscillating price pattern around 100
        close_prices = [100 + 5 * np.sin(i * 0.5) for i in range(20)]
        
        data = pd.DataFrame({
            'open': close_prices,
            'high': close_prices,
            'low': close_prices,
            'close': close_prices,
            'volume': [1000] * 20
        }, index=dates)
        
        indicator = DistanceFromMAIndicator(period=5)
        result = indicator.compute(data)
        
        # Should have both positive and negative distances
        valid_results = result.dropna()
        assert (valid_results > 0).any()
        assert (valid_results < 0).any()

    def test_parameter_validation(self):
        """Test parameter validation through schema."""
        # Valid parameters should work
        indicator = DistanceFromMAIndicator(period=20, ma_type="SMA", source="close")
        validated = indicator._validate_params(indicator.params)
        assert validated["period"] == 20
        assert validated["ma_type"] == "SMA"
        assert validated["source"] == "close"

    def test_extreme_values_handling(self):
        """Test handling of extreme price movements."""
        dates = [datetime(2023, 1, 1) + timedelta(days=i) for i in range(10)]
        
        # Create data with extreme price spike - gradual then spike
        close_prices = [100, 101, 102, 103, 104, 200, 201, 202, 203, 204]  # 100% price spike at position 5
        
        data = pd.DataFrame({
            'open': close_prices,
            'high': close_prices,
            'low': close_prices,
            'close': close_prices,
            'volume': [1000] * 10
        }, index=dates)
        
        indicator = DistanceFromMAIndicator(period=5)
        result = indicator.compute(data)
        
        # Should handle extreme values without errors
        assert not pd.isna(result.iloc[4:]).any()
        # Distance should be large positive right after the spike (index 5)
        # At index 5: price=200, MA=(101+102+103+104+200)/5=122, distance=(200-122)/122*100=64%
        assert result.iloc[5] > 60  # Should be >60% above MA
        # Distance should still be positive but decreasing as MA adapts
        assert result.iloc[6] > 20  # Should still be significantly above MA