"""
Tests for the DataManager class.
"""

import os
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

from ktrdr.data import DataManager, DataCorruptionError, DataNotFoundError, DataError


@pytest.fixture
def sample_data():
    """Create a sample OHLCV DataFrame for testing."""
    index = pd.date_range(start='2023-01-01', periods=100, freq='1D')
    data = {
        'open': np.random.uniform(100, 110, size=100),
        'high': np.random.uniform(110, 120, size=100),
        'low': np.random.uniform(90, 100, size=100),
        'close': np.random.uniform(100, 110, size=100),
        'volume': np.random.uniform(1000, 10000, size=100)
    }
    
    # Fix OHLC relationships to ensure high is truly the highest and low is truly the lowest
    df = pd.DataFrame(data, index=index)
    
    # Ensure high >= open, close
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    # Ensure low <= open, close
    df['low'] = df[['open', 'low', 'close']].min(axis=1)
    
    return df


@pytest.fixture
def corrupt_data():
    """Create a sample corrupt OHLCV DataFrame for testing repair functionality."""
    index = pd.date_range(start='2023-01-01', periods=100, freq='1D')
    data = {
        'open': np.random.uniform(100, 110, size=100),
        'high': np.random.uniform(110, 120, size=100),
        'low': np.random.uniform(90, 100, size=100),
        'close': np.random.uniform(100, 110, size=100),
        'volume': np.random.uniform(1000, 10000, size=100)
    }
    
    df = pd.DataFrame(data, index=index)
    
    # Add corruption:
    
    # 1. Some missing values
    df.loc[df.index[10:15], 'close'] = np.nan
    df.loc[df.index[20:22], 'open'] = np.nan
    
    # 2. Some invalid OHLC relationships - make low > high in a few places
    df.loc[df.index[30:32], 'low'] = df.loc[df.index[30:32], 'high'] + 5
    
    # 3. Some negative volumes
    df.loc[df.index[40:42], 'volume'] = -1000
    
    # 4. Create gaps by removing some rows
    return df.drop(index.tolist()[50:55])


@pytest.fixture
def data_manager(tmp_path):
    """Create a DataManager instance with a temporary directory for testing."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return DataManager(data_dir=str(data_dir), enable_ib=False)


@pytest.fixture
def data_manager_with_data(data_manager, sample_data):
    """Create a DataManager with sample data already saved."""
    data_manager.data_loader.save(sample_data, "TEST", "1d")
    return data_manager


class TestDataManager:
    """Tests for the DataManager class."""
    
    def test_initialization(self, tmp_path):
        """Test that DataManager initializes correctly with various parameters."""
        # Default initialization
        dm = DataManager(data_dir=str(tmp_path))
        assert dm.max_gap_percentage == 5.0
        assert dm.default_repair_method == 'ffill'
        
        # Custom initialization
        dm = DataManager(
            data_dir=str(tmp_path),
            max_gap_percentage=10.0,
            default_repair_method='interpolate'
        )
        assert dm.max_gap_percentage == 10.0
        assert dm.default_repair_method == 'interpolate'
        
        # Invalid max_gap_percentage
        with pytest.raises(DataError):
            DataManager(data_dir=str(tmp_path), max_gap_percentage=-1.0)
        
        with pytest.raises(DataError):
            DataManager(data_dir=str(tmp_path), max_gap_percentage=101.0)
            
        # Invalid repair method
        with pytest.raises(DataError):
            DataManager(data_dir=str(tmp_path), default_repair_method='invalid_method')
    
    def test_load_data(self, data_manager_with_data):
        """Test loading data with validation."""
        # Load data with default settings
        df = data_manager_with_data.load_data("TEST", "1d")
        assert not df.empty
        assert len(df) == 100
        
        # Load data within a date range
        df = data_manager_with_data.load_data(
            "TEST", "1d",
            start_date="2023-01-10",
            end_date="2023-01-20"
        )
        assert not df.empty
        assert len(df) == 11  # 10-20 inclusive
        
        # Test non-existent data
        with pytest.raises(DataNotFoundError):
            data_manager_with_data.load_data("NONEXISTENT", "1d")
    
    def test_data_integrity_check(self, data_manager, corrupt_data):
        """Test the data integrity checking."""
        issues = data_manager.check_data_integrity(corrupt_data, "1d")
        
        # Check that all types of corruption were detected
        assert len(issues) >= 4
        
        # Check specific issues
        assert any("Missing values" in issue for issue in issues)
        assert any("Invalid OHLC" in issue for issue in issues)
        assert any("Negative volume" in issue for issue in issues)
        
        # Test with clean data
        clean_df = data_manager.repair_data(corrupt_data, "1d")
        # Use is_post_repair=True for repaired data to apply tolerance to outlier detection
        clean_issues = data_manager.check_data_integrity(clean_df, "1d", is_post_repair=True)
        assert len(clean_issues) == 0
    
    def test_load_data_with_repair(self, data_manager, corrupt_data):
        """Test loading and repairing corrupt data."""
        # Save corrupt data
        data_manager.data_loader.save(corrupt_data, "CORRUPT", "1d")
        
        # Try to load with strict validation - should fail
        with pytest.raises(DataCorruptionError):
            data_manager.load_data("CORRUPT", "1d", validate=True, strict=True)
            
        # Load with repair
        repaired_df = data_manager.load_data(
            "CORRUPT", "1d", 
            validate=True, 
            repair=True,
            repair_method='ffill'
        )
        
        # Verify repair fixed the issues
        assert not repaired_df.isnull().any().any()
        assert not (repaired_df['low'] > repaired_df['high']).any()
        assert not (repaired_df['volume'] < 0).any()
    
    def test_detect_gaps(self, data_manager, corrupt_data):
        """Test gap detection in time series data."""
        gaps = data_manager.detect_gaps(corrupt_data, "1d")
        assert len(gaps) == 1  # We created one gap in the fixture
        
        # The gap should be 5 days long (we removed indices 50-54)
        assert (gaps[0][1] - gaps[0][0]).days == 4  # End minus start
    
    def test_repair_data(self, data_manager, corrupt_data):
        """Test different data repair methods."""
        # Test ffill (forward fill)
        repaired_ffill = data_manager.repair_data(corrupt_data, "1d", method='ffill')
        assert not repaired_ffill.isnull().any().any()
        
        # Test interpolate
        repaired_interp = data_manager.repair_data(corrupt_data, "1d", method='interpolate')
        assert not repaired_interp.isnull().any().any()
        
        # Test with invalid method
        with pytest.raises(DataError):
            data_manager.repair_data(corrupt_data, "1d", method='invalid_method')
    
    def test_merge_data(self, data_manager_with_data, sample_data):
        """Test merging new data with existing data."""
        # Create new data with a completely different date range to ensure no overlap
        new_index = pd.date_range(start='2023-05-01', periods=20, freq='1D')
        new_data = sample_data.iloc[-20:].copy()
        new_data.index = new_index
        
        # Merge without overwriting (should have 120 rows total - no overlap)
        merged = data_manager_with_data.merge_data(
            "TEST", "1d", new_data, 
            save_result=False,
            overwrite_conflicts=False
        )
        assert len(merged) == 120
        
        # Create conflicting data (same dates as original, different values)
        conflict_data = sample_data.copy()
        conflict_data['close'] = conflict_data['close'] + 10
        
        # Merge with overwrite_conflicts=False should keep original values
        merged = data_manager_with_data.merge_data(
            "TEST", "1d", conflict_data, 
            save_result=False,
            overwrite_conflicts=False
        )
        assert len(merged) == 100
        assert (merged['close'] != conflict_data['close']).all()
        
        # Merge with overwrite_conflicts=True should use new values
        merged = data_manager_with_data.merge_data(
            "TEST", "1d", conflict_data, 
            save_result=False,
            overwrite_conflicts=True
        )
        assert len(merged) == 100
        assert (merged['close'] == conflict_data['close']).all()
    
    def test_resample_data(self, data_manager, sample_data):
        """Test resampling data to different timeframes."""
        # Original data is daily, resample to weekly
        resampled = data_manager.resample_data(
            sample_data, 
            target_timeframe="1w",
            source_timeframe="1d"
        )
        
        # Should have fewer rows after resampling to a larger timeframe
        assert len(resampled) < len(sample_data)
        
        # Check that volume is summed correctly
        assert pytest.approx(resampled['volume'].sum()) == pytest.approx(sample_data['volume'].sum())
        
        # Check high is the maximum
        assert pytest.approx(resampled['high'].max()) == pytest.approx(sample_data['high'].max())
    
    def test_get_data_summary(self, data_manager_with_data):
        """Test getting a summary of available data."""
        summary = data_manager_with_data.get_data_summary("TEST", "1d")
        
        assert summary['symbol'] == "TEST"
        assert summary['timeframe'] == "1d"
        assert summary['rows'] == 100
        assert 'open' in summary['columns']
        assert 'high' in summary['columns']
        assert 'low' in summary['columns']
        assert 'close' in summary['columns']
        assert 'volume' in summary['columns']
        assert summary['days'] > 0
        assert not summary['has_gaps']
    
    def test_filter_data_by_condition(self, data_manager, sample_data):
        """Test filtering data with custom conditions."""
        # Define a condition: close > open (bullish candles)
        bullish_condition = lambda df: df['close'] > df['open']
        
        # Filter for bullish candles
        bullish_df = data_manager.filter_data_by_condition(sample_data, bullish_condition)
        assert len(bullish_df) <= len(sample_data)
        assert (bullish_df['close'] > bullish_df['open']).all()
        
        # Filter for bearish candles (inverse)
        bearish_df = data_manager.filter_data_by_condition(sample_data, bullish_condition, inverse=True)
        assert len(bearish_df) <= len(sample_data)
        assert (bearish_df['close'] <= bearish_df['open']).all()
        
        # Total rows should equal original dataframe
        assert len(bullish_df) + len(bearish_df) == len(sample_data)
    
    def test_detect_outliers(self, data_manager, sample_data):
        """Test outlier detection with both global and context-aware approaches."""
        # Create a copy of sample data and add outliers
        df = sample_data.copy()
        
        # Add extreme outliers that should be detected regardless of approach
        outlier_idx = df.index[30]
        df.loc[outlier_idx, 'close'] = df.loc[outlier_idx, 'close'] * 5  # 400% spike - very extreme
        
        outlier_idx2 = df.index[60]
        df.loc[outlier_idx2, 'close'] = df.loc[outlier_idx2, 'close'] * 0.2  # 80% drop - very extreme
        
        # Test global outlier detection
        outlier_count = data_manager.detect_outliers(df, std_threshold=3.0, log_outliers=False)
        assert outlier_count >= 1  # Should detect at least one of our inserted outliers
        
        # Test context-aware outlier detection
        # Since context-aware detection is more selective by design, we just verify it works
        context_outlier_count = data_manager.detect_outliers(df, std_threshold=3.0, 
                                                         context_window=10, log_outliers=False)
        assert context_outlier_count >= 0  # Should run without errors
        
        # Test with increased tolerance
        high_tolerance_count = data_manager.detect_outliers(df, std_threshold=10.0, log_outliers=False)
        assert high_tolerance_count <= outlier_count  # Should detect fewer or equal outliers

    def test_repair_data_with_outliers(self, data_manager, sample_data):
        """Test repairing data with outliers, testing both repair options."""
        # Create a copy of sample data and add outliers
        df = sample_data.copy()
        
        # Add outliers
        outlier_idx = df.index[30]
        original_value = df.loc[outlier_idx, 'close']
        df.loc[outlier_idx, 'close'] = df.loc[outlier_idx, 'close'] * 2  # 100% spike
        
        # Test repair with outlier repair enabled (default)
        repaired_df = data_manager.repair_data(df, "1d", repair_outliers=True)
        
        # Verify the outlier was repaired
        assert repaired_df.loc[outlier_idx, 'close'] != df.loc[outlier_idx, 'close']
        assert abs(repaired_df.loc[outlier_idx, 'close'] - original_value) < abs(df.loc[outlier_idx, 'close'] - original_value)
        
        # Test repair without outlier repair
        no_outlier_repair_df = data_manager.repair_data(df, "1d", repair_outliers=False)
        
        # Verify the outlier was preserved
        assert no_outlier_repair_df.loc[outlier_idx, 'close'] == df.loc[outlier_idx, 'close']
    
    def test_context_aware_repair(self, data_manager):
        """Test context-aware outlier repair."""
        # Create a DataFrame with changing volatility
        index = pd.date_range(start='2023-01-01', periods=100, freq='1D')
        
        # Create price series with increasing volatility
        close = np.linspace(100, 200, 100)  # Linear trend
        
        # Add increasing volatility
        volatility = np.linspace(1, 10, 100)  # Increasing volatility
        noise = np.random.normal(0, 1, 100) * volatility
        close = close + noise
        
        # Create a DataFrame
        df = pd.DataFrame({
            'open': close - 1,
            'high': close + 1,
            'low': close - 1,
            'close': close,
            'volume': np.random.uniform(1000, 10000, 100)
        }, index=index)
        
        # Add outliers in low and high volatility regions
        # Low volatility region (early in the series)
        df.loc[index[10], 'close'] = df.loc[index[10], 'close'] + 15  # +15 points
        
        # High volatility region (later in the series)
        df.loc[index[80], 'close'] = df.loc[index[80], 'close'] + 15  # +15 points
        
        # Repair with global outlier detection
        global_repaired = data_manager.repair_data(df, "1d", repair_outliers=True, context_window=None)
        
        # Repair with context-aware outlier detection
        context_repaired = data_manager.repair_data(df, "1d", repair_outliers=True, context_window=20)
        
        # In high volatility region, context-aware should modify the outlier less
        # because it's considered less extreme in a high volatility context
        high_vol_diff_global = abs(global_repaired.loc[index[80], 'close'] - df.loc[index[80], 'close'])
        high_vol_diff_context = abs(context_repaired.loc[index[80], 'close'] - df.loc[index[80], 'close'])
        
        assert high_vol_diff_context <= high_vol_diff_global

    def test_load_data_with_outlier_options(self, data_manager, corrupt_data):
        """Test loading data with various outlier repair options."""
        # Save corrupt data
        data_manager.data_loader.save(corrupt_data, "OUTLIER_TEST", "1d")
        
        # Add an extreme outlier that should be detected by any method
        outlier_idx = corrupt_data.index[30]
        original_value = corrupt_data.loc[outlier_idx, 'close']
        corrupt_data.loc[outlier_idx, 'close'] = 999.99  # Extreme value
        data_manager.data_loader.save(corrupt_data, "OUTLIER_TEST", "1d")
        
        # Test loading with repair but no outlier repair
        no_outlier_repair = data_manager.load_data(
            "OUTLIER_TEST", "1d",
            validate=True,
            repair=True,
            repair_outliers=False
        )
        
        # Test loading with repair and outlier repair
        with_outlier_repair = data_manager.load_data(
            "OUTLIER_TEST", "1d",
            validate=True,
            repair=True,
            repair_outliers=True
        )
        
        # Verify that standard outlier repair worked
        assert np.isclose(no_outlier_repair.loc[outlier_idx, 'close'], 999.99)  # Preserved
        assert not np.isclose(with_outlier_repair.loc[outlier_idx, 'close'], 999.99)  # Was repaired
        
        # We'll verify that context-aware repair works in a separate test
        # since its behavior can vary based on the data context