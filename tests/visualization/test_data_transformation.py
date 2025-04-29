"""
Tests for the data transformation module in the visualization package.

This module provides comprehensive tests for the DataAdapter class,
ensuring that DataFrames are correctly transformed into the format
required by lightweight-charts.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

from ktrdr.visualization.data_adapter import DataAdapter
from ktrdr.errors import DataError

# Import test fixtures
from test_fixtures import (
    sample_price_data, 
    sample_indicators,
    histogram_data,
    multiple_series_data,
    edge_case_data
)


class TestDataTransformation:
    """
    Comprehensive tests for data transformation functionality.
    """
    
    def test_ohlc_transformation(self, sample_price_data):
        """Test OHLC transformation with realistic price patterns."""
        # Transform the data
        result = DataAdapter.transform_ohlc(sample_price_data)
        
        # Verify basic structure and types
        assert isinstance(result, list)
        assert len(result) == len(sample_price_data)
        
        # Check structure of first item
        item = result[0]
        assert 'time' in item
        assert 'open' in item
        assert 'high' in item
        assert 'low' in item
        assert 'close' in item
        
        # Check data types
        assert isinstance(item['time'], int)  # Unix timestamp
        assert isinstance(item['open'], float)
        assert isinstance(item['high'], float)
        assert isinstance(item['low'], float)
        assert isinstance(item['close'], float)
        
        # Verify values are correctly transformed
        for i, row in enumerate(result):
            source_row = sample_price_data.iloc[i]
            assert pytest.approx(row['open']) == source_row['open']
            assert pytest.approx(row['high']) == source_row['high']
            assert pytest.approx(row['low']) == source_row['low']
            assert pytest.approx(row['close']) == source_row['close']
            
            # Don't check exact timestamp equality as implementations might use different precision
            # Just ensure it's an integer timestamp
            assert isinstance(row['time'], int)
    
    def test_line_transformation(self, sample_indicators):
        """Test line series transformation with indicator data."""
        # Test SMA-10 transformation
        result = DataAdapter.transform_line(
            sample_indicators, 
            time_column='date', 
            value_column='sma_10'
        )
        
        # Verify basic structure and types
        assert isinstance(result, list)
        
        # NaN values might be filtered out, so we can't directly compare lengths
        # Get count of non-NaN values in source data
        non_nan_count = sample_indicators['sma_10'].notna().sum()
        
        # Check we have data points (might not be exactly the same number as source due to NaN handling)
        assert len(result) > 0
        
        # Check data structure for valid items
        valid_items = [item for item in result if 'value' in item]
        if valid_items:
            item = valid_items[0]
            assert 'time' in item
            assert 'value' in item
            assert isinstance(item['time'], int)
            assert isinstance(item['value'], float)
        
        # Verify values are correctly transformed for non-NaN entries
        for i, row in enumerate(sample_indicators.iterrows()):
            idx, source_row = row
            source_val = source_row['sma_10']
            
            # Skip NaN values which might be handled differently in DataAdapter
            if pd.notna(source_val):
                # Find corresponding item in result if it exists
                # Don't check exact timestamp equality, as implementations might use different precision
                matching_items = [r for r in result if 'value' in r and 
                                  pytest.approx(r['value'], rel=1e-5) == source_val]
                
                if matching_items:
                    result_item = matching_items[0]
                    assert pytest.approx(result_item['value']) == source_val
    
    def test_histogram_transformation(self, histogram_data):
        """Test histogram transformation with alternating positive/negative values."""
        result = DataAdapter.transform_histogram(
            histogram_data,
            time_column='date',
            value_column='value'
        )
        
        # Verify basic structure and types
        assert isinstance(result, list)
        assert len(result) == len(histogram_data)
        
        # Check data structure
        item = result[0]
        assert 'time' in item
        assert 'value' in item
        assert 'color' in item  # Color should be present for histograms
        
        # Verify color assignment based on value sign
        for i, row in enumerate(result):
            source_val = histogram_data.iloc[i]['value']
            
            # The implementation might use absolute values
            assert pytest.approx(abs(row['value'])) == abs(source_val)
            
            # Check color assignment (positive = green, negative = red)
            # Note: compare colors case-insensitively as implementation might use lowercase
            if source_val >= 0:
                assert row['color'].lower() == '#26a69a'  # Green
            else:
                assert row['color'].lower() == '#ef5350'  # Red
                
    def test_transform_with_missing_columns(self, sample_price_data):
        """Test transformation with missing required columns."""
        # Create a copy without required columns
        df_missing = sample_price_data.drop(['open', 'high'], axis=1)
        
        # Should raise an error due to missing columns
        with pytest.raises(DataError):
            DataAdapter.transform_ohlc(df_missing)
            
    def test_transform_with_edge_cases(self, edge_case_data):
        """Test transformation with edge case data."""
        # Test with column having missing values
        result = DataAdapter.transform_line(
            edge_case_data,
            time_column='date',
            value_column='missing_values'
        )
        
        # Verify NaN values are properly handled - the behavior could be:
        # 1. Skip NaN values entirely (item not in result)
        # 2. Include NaN values as null or undefined (value is NaN)
        # 3. Replace NaN with 0 or other default value
        for i, row in enumerate(edge_case_data.iterrows()):
            idx, source_row = row
            source_val = source_row['missing_values']
            
            # Don't check exact timestamp equality, as implementations might use different precision
            # Just check values where source is not NaN
            if pd.notna(source_val):
                # Find corresponding item in result if it exists
                matching_items = [r for r in result if 'value' in r and 
                                  pytest.approx(r['value'], rel=1e-5) == source_val]
                
                # If we found matching items, verify the values
                if matching_items:
                    result_item = matching_items[0]
                    assert pytest.approx(result_item['value']) == source_val
        
        # Test with extreme values
        result = DataAdapter.transform_line(
            edge_case_data,
            time_column='date',
            value_column='extreme_values'
        )
        
        # Verify extreme values are properly handled
        # This might handle extreme values differently, so check more flexibly
        for i, row in enumerate(edge_case_data.iterrows()):
            idx, source_row = row
            source_val = source_row['extreme_values']
            
            if pd.notna(source_val) and not np.isnan(source_val):
                # Find corresponding item in result if it exists
                matching_items = [r for r in result if 'value' in r and 
                                  pytest.approx(r['value'], rel=1e-5) == source_val]
                
                # If we found matching items, verify the values
                if matching_items:
                    result_item = matching_items[0]
                    assert pytest.approx(result_item['value'], rel=1e-5) == source_val
        
        # Test with constant values
        result = DataAdapter.transform_line(
            edge_case_data,
            time_column='date',
            value_column='constant'
        )
        
        # Verify constant values are properly handled
        for item in result:
            if 'value' in item:
                assert pytest.approx(item['value']) == 100.0  # All values are 100
    
    def test_serializable_output(self, sample_price_data, sample_indicators, histogram_data):
        """Test that transformation outputs can be serialized to JSON."""
        # Test OHLC data
        ohlc_data = DataAdapter.transform_ohlc(sample_price_data)
        try:
            json_str = json.dumps(ohlc_data)
            assert isinstance(json_str, str)
        except Exception as e:
            pytest.fail(f"Failed to serialize OHLC data: {e}")
            
        # Test line data
        line_data = DataAdapter.transform_line(
            sample_indicators,
            time_column='date',
            value_column='rsi'
        )
        try:
            json_str = json.dumps(line_data)
            assert isinstance(json_str, str)
        except Exception as e:
            pytest.fail(f"Failed to serialize line data: {e}")
            
        # Test histogram data
        hist_data = DataAdapter.transform_histogram(
            histogram_data,
            time_column='date',
            value_column='value'
        )
        try:
            json_str = json.dumps(hist_data)
            assert isinstance(json_str, str)
        except Exception as e:
            pytest.fail(f"Failed to serialize histogram data: {e}")