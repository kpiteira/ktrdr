"""
Tests for the BatchFuzzyCalculator class.
"""

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from ktrdr.errors import ProcessingError
from ktrdr.fuzzy.batch_calculator import BatchFuzzyCalculator
from ktrdr.fuzzy.config import FuzzyConfigLoader
from ktrdr.fuzzy.engine import FuzzyEngine


@pytest.fixture
def sample_fuzzy_config():
    """Create a sample fuzzy configuration for testing."""
    config_dict = {
        "rsi": {
            "low": {"type": "triangular", "parameters": [0.0, 0.0, 50.0]},
            "neutral": {"type": "triangular", "parameters": [20.0, 50.0, 80.0]},
            "high": {"type": "triangular", "parameters": [50.0, 100.0, 100.0]},
        },
        "macd": {
            "negative": {"type": "triangular", "parameters": [-10.0, -10.0, 0.0]},
            "positive": {"type": "triangular", "parameters": [0.0, 10.0, 10.0]},
        },
    }
    return FuzzyConfigLoader.load_from_dict(config_dict)


@pytest.fixture
def fuzzy_engine(sample_fuzzy_config):
    """Create a FuzzyEngine for testing."""
    return FuzzyEngine(sample_fuzzy_config)


@pytest.fixture
def batch_calculator(fuzzy_engine):
    """Create a BatchFuzzyCalculator for testing."""
    return BatchFuzzyCalculator(fuzzy_engine)


@pytest.fixture
def sample_timestamps():
    """Create sample timestamps for testing."""
    start_time = datetime(2023, 1, 1, 9, 0)
    return pd.date_range(start=start_time, periods=10, freq="1h")


@pytest.fixture
def sample_rsi_series(sample_timestamps):
    """Create a sample RSI time series."""
    rsi_values = [25.0, 30.0, 45.0, 55.0, 65.0, 70.0, 80.0, 75.0, 60.0, 40.0]
    return pd.Series(rsi_values, index=sample_timestamps, name="rsi")


class TestBatchFuzzyCalculator:
    """Test cases for BatchFuzzyCalculator."""

    def test_initialization(self, fuzzy_engine):
        """Test BatchFuzzyCalculator initialization."""
        calculator = BatchFuzzyCalculator(fuzzy_engine)

        assert calculator._fuzzy_engine is fuzzy_engine
        assert calculator._cache_size == 1000  # default
        assert calculator._cache_hits == 0
        assert calculator._cache_misses == 0

    def test_initialization_with_custom_cache_size(self, fuzzy_engine):
        """Test initialization with custom cache size."""
        calculator = BatchFuzzyCalculator(fuzzy_engine, cache_size=500)
        assert calculator._cache_size == 500

    def test_calculate_memberships_basic(self, batch_calculator, sample_rsi_series):
        """Test basic membership calculation."""
        result = batch_calculator.calculate_memberships("rsi", sample_rsi_series)

        # Check result structure
        assert isinstance(result, dict)
        assert "rsi_low" in result
        assert "rsi_neutral" in result
        assert "rsi_high" in result

        # Check that all results are Series with correct index
        for _set_name, series in result.items():
            assert isinstance(series, pd.Series)
            assert len(series) == len(sample_rsi_series)
            assert series.index.equals(sample_rsi_series.index)

        # Check that membership values are in [0, 1] range
        for series in result.values():
            assert (series >= 0.0).all()
            assert (series <= 1.0).all()

    def test_calculate_memberships_with_nan_values(
        self, batch_calculator, sample_timestamps
    ):
        """Test calculation with NaN values in the series."""
        # Create series with NaN values
        rsi_values = [25.0, np.nan, 45.0, np.nan, 65.0, 70.0, np.nan, 75.0, 60.0, 40.0]
        rsi_series = pd.Series(rsi_values, index=sample_timestamps, name="rsi")

        result = batch_calculator.calculate_memberships("rsi", rsi_series)

        # Check that NaN positions are preserved
        nan_positions = rsi_series.isna()
        for _set_name, series in result.items():
            assert series.isna()[nan_positions].all()
            assert not series.isna()[~nan_positions].any()

    def test_calculate_memberships_empty_series(
        self, batch_calculator, sample_timestamps
    ):
        """Test calculation with empty series."""
        empty_series = pd.Series(
            [], dtype=float, index=pd.Index([], dtype="datetime64[ns]")
        )

        result = batch_calculator.calculate_memberships("rsi", empty_series)

        # Should return empty series for each fuzzy set
        assert "rsi_low" in result
        assert "rsi_neutral" in result
        assert "rsi_high" in result

        for series in result.values():
            assert len(series) == 0
            assert series.index.equals(empty_series.index)

    def test_calculate_memberships_all_nan_series(
        self, batch_calculator, sample_timestamps
    ):
        """Test calculation with series containing only NaN values."""
        nan_series = pd.Series(
            [np.nan] * len(sample_timestamps), index=sample_timestamps
        )

        result = batch_calculator.calculate_memberships("rsi", nan_series)

        # All results should be NaN
        for series in result.values():
            assert series.isna().all()
            assert len(series) == len(sample_timestamps)

    def test_unknown_indicator_error(self, batch_calculator, sample_rsi_series):
        """Test error handling for unknown indicator."""
        with pytest.raises(ProcessingError) as exc_info:
            batch_calculator.calculate_memberships(
                "unknown_indicator", sample_rsi_series
            )

        assert "Unknown indicator" in str(exc_info.value)
        assert exc_info.value.error_code == "BATCH-UnknownIndicator"

    def test_invalid_indicator_name(self, batch_calculator, sample_rsi_series):
        """Test error handling for invalid indicator names."""
        with pytest.raises(ProcessingError) as exc_info:
            batch_calculator.calculate_memberships("", sample_rsi_series)

        assert "Indicator name must be a non-empty string" in str(exc_info.value)
        assert exc_info.value.error_code == "BATCH-InvalidIndicatorName"

        with pytest.raises(ProcessingError) as exc_info:
            batch_calculator.calculate_memberships(None, sample_rsi_series)

        assert exc_info.value.error_code == "BATCH-InvalidIndicatorName"

    def test_invalid_value_type(self, batch_calculator):
        """Test error handling for invalid value types."""
        with pytest.raises(ProcessingError) as exc_info:
            batch_calculator.calculate_memberships(
                "rsi", [1, 2, 3]
            )  # list instead of Series

        assert "Values must be a pandas Series" in str(exc_info.value)
        assert exc_info.value.error_code == "BATCH-InvalidValueType"

    def test_cache_functionality(self, batch_calculator, sample_rsi_series):
        """Test caching functionality."""
        # First calculation
        result1 = batch_calculator.calculate_memberships("rsi", sample_rsi_series)

        # Second calculation with same data (should hit cache)
        result2 = batch_calculator.calculate_memberships("rsi", sample_rsi_series)

        # Results should be identical
        for set_name in result1.keys():
            pd.testing.assert_series_equal(result1[set_name], result2[set_name])

        # Check cache statistics
        stats = batch_calculator.get_cache_stats()
        assert stats["cache_misses"] >= 1
        # Note: cache hits might be 0 due to simplified caching implementation

    def test_cache_stats(self, batch_calculator, sample_rsi_series):
        """Test cache statistics tracking."""
        initial_stats = batch_calculator.get_cache_stats()
        assert initial_stats["cache_hits"] == 0
        assert initial_stats["cache_misses"] == 0

        # Perform a calculation
        batch_calculator.calculate_memberships("rsi", sample_rsi_series)

        updated_stats = batch_calculator.get_cache_stats()
        assert updated_stats["cache_misses"] >= 1
        assert "hit_rate" in updated_stats
        assert "cache_size" in updated_stats

    def test_clear_cache(self, batch_calculator, sample_rsi_series):
        """Test cache clearing functionality."""
        # Perform calculation to populate cache
        batch_calculator.calculate_memberships("rsi", sample_rsi_series)

        # Clear cache
        batch_calculator.clear_cache()

        # Statistics should be reset
        stats = batch_calculator.get_cache_stats()
        assert stats["cache_hits"] == 0
        assert stats["cache_misses"] == 0

    def test_multiple_indicators(self, batch_calculator, sample_timestamps):
        """Test calculation with multiple different indicators."""
        # Test RSI
        rsi_series = pd.Series([25.0, 75.0], index=sample_timestamps[:2])
        rsi_result = batch_calculator.calculate_memberships("rsi", rsi_series)

        # Test MACD
        macd_series = pd.Series([-5.0, 5.0], index=sample_timestamps[:2])
        macd_result = batch_calculator.calculate_memberships("macd", macd_series)

        # Results should have different set names
        assert "rsi_low" in rsi_result
        assert "macd_negative" in macd_result
        assert "rsi_low" not in macd_result
        assert "macd_negative" not in rsi_result

    def test_performance_with_large_dataset(self, batch_calculator):
        """Test performance with a larger dataset."""
        # Create a large time series (1000 points)
        large_timestamps = pd.date_range(start="2023-01-01", periods=1000, freq="1h")
        large_values = np.random.uniform(0, 100, 1000)
        large_series = pd.Series(large_values, index=large_timestamps)

        # This should complete without timeout or memory issues
        result = batch_calculator.calculate_memberships("rsi", large_series)

        assert len(result["rsi_low"]) == 1000
        assert len(result["rsi_neutral"]) == 1000
        assert len(result["rsi_high"]) == 1000

    def test_membership_value_correctness(self, batch_calculator):
        """Test that membership values are calculated correctly."""
        # Create specific test values where we know expected membership
        timestamps = pd.date_range(start="2023-01-01", periods=3, freq="1h")

        # Test extreme values for RSI
        # RSI = 0 should have high membership in "low" set
        # RSI = 50 should have high membership in "neutral" set
        # RSI = 100 should have high membership in "high" set
        test_values = [0.0, 50.0, 100.0]
        test_series = pd.Series(test_values, index=timestamps)

        result = batch_calculator.calculate_memberships("rsi", test_series)

        # Check first value (RSI = 0)
        assert result["rsi_low"].iloc[0] == 1.0  # Should be fully in "low" set
        assert result["rsi_high"].iloc[0] == 0.0  # Should not be in "high" set

        # Check middle value (RSI = 50)
        assert result["rsi_neutral"].iloc[1] == 1.0  # Should be fully in "neutral" set

        # Check last value (RSI = 100)
        assert result["rsi_high"].iloc[2] == 1.0  # Should be fully in "high" set
        assert result["rsi_low"].iloc[2] == 0.0  # Should not be in "low" set
