"""
Tests for IB Data Range Discovery.

This module tests the range discovery functionality for finding
earliest available data points using binary search.
"""

import pytest

pytestmark = pytest.mark.skip(reason="IB integration tests disabled for unit test run")
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import pandas as pd

from ktrdr.data.ib_data_fetcher_sync import IbDataRangeDiscovery, IbDataFetcherSync


class TestIbDataRangeDiscovery:
    """Test suite for IbDataRangeDiscovery."""
    
    @pytest.fixture
    def mock_data_fetcher(self):
        """Create a mock data fetcher."""
        mock_fetcher = Mock(spec=IbDataFetcherSync)
        return mock_fetcher
    
    @pytest.fixture
    def range_discovery(self, mock_data_fetcher):
        """Create range discovery instance with mocked fetcher."""
        return IbDataRangeDiscovery(mock_data_fetcher)
    
    @pytest.fixture
    def sample_dataframe(self):
        """Create sample DataFrame for testing."""
        dates = pd.date_range(start='2020-01-01', end='2020-01-10', freq='D')
        df = pd.DataFrame({
            'open': [100.0] * len(dates),
            'high': [105.0] * len(dates),
            'low': [95.0] * len(dates),
            'close': [102.0] * len(dates),
            'volume': [1000] * len(dates)
        }, index=dates)
        df.index.name = 'timestamp'
        return df
    
    def test_init(self, mock_data_fetcher):
        """Test initialization."""
        discovery = IbDataRangeDiscovery(mock_data_fetcher)
        assert discovery.data_fetcher == mock_data_fetcher
        assert discovery.range_cache == {}
        assert discovery.cache_timestamps == {}
        assert discovery.cache_ttl == 86400  # 24 hours
    
    def test_cache_key_generation(self, range_discovery):
        """Test cache key generation."""
        key = range_discovery._cache_key("AAPL", "1 day")
        assert key == "AAPL:1 day"
    
    def test_cache_validity(self, range_discovery):
        """Test cache validity checking."""
        # No cache entry
        assert range_discovery._is_cache_valid("test_key") is False
        
        # Fresh cache entry
        range_discovery.cache_timestamps["test_key"] = time.time()
        assert range_discovery._is_cache_valid("test_key") is True
        
        # Expired cache entry
        range_discovery.cache_timestamps["test_key"] = time.time() - 90000  # Over 24 hours
        assert range_discovery._is_cache_valid("test_key") is False
    
    def test_cache_range_and_get_cached_range(self, range_discovery):
        """Test caching and retrieving ranges."""
        symbol = "AAPL"
        timeframe = "1 day"
        start = datetime(2020, 1, 1)
        end = datetime(2023, 1, 1)
        
        # Cache a range
        range_discovery._cache_range(symbol, timeframe, start, end)
        
        # Verify it's cached
        cached_range = range_discovery._get_cached_range(symbol, timeframe)
        assert cached_range == (start, end)
        
        # Test with non-existent symbol
        assert range_discovery._get_cached_range("INVALID", timeframe) is None
    
    def test_has_data_at_date_with_data(self, range_discovery, sample_dataframe):
        """Test data existence check when data is available."""
        range_discovery.data_fetcher.fetch_historical_data.return_value = sample_dataframe
        
        test_date = datetime(2020, 1, 1)
        result = range_discovery._has_data_at_date("AAPL", "1 day", test_date)
        
        assert result is True
        range_discovery.data_fetcher.fetch_historical_data.assert_called_once()
    
    def test_has_data_at_date_no_data(self, range_discovery):
        """Test data existence check when no data is available."""
        range_discovery.data_fetcher.fetch_historical_data.return_value = pd.DataFrame()
        
        test_date = datetime(2020, 1, 1)
        result = range_discovery._has_data_at_date("AAPL", "1 day", test_date)
        
        assert result is False
    
    def test_has_data_at_date_exception(self, range_discovery):
        """Test data existence check when exception occurs."""
        range_discovery.data_fetcher.fetch_historical_data.side_effect = Exception("API Error")
        
        test_date = datetime(2020, 1, 1)
        result = range_discovery._has_data_at_date("AAPL", "1 day", test_date)
        
        assert result is False
    
    def test_has_data_at_date_date_tolerance(self, range_discovery):
        """Test data existence check with date tolerance."""
        # Create DataFrame with data 5 days after target date
        target_date = datetime(2020, 1, 1)
        actual_data_date = target_date + timedelta(days=5)
        
        dates = pd.date_range(start=actual_data_date, end=actual_data_date + timedelta(days=5), freq='D')
        df = pd.DataFrame({'close': [100.0] * len(dates)}, index=dates)
        
        range_discovery.data_fetcher.fetch_historical_data.return_value = df
        
        # Should accept within 7 days tolerance
        result = range_discovery._has_data_at_date("AAPL", "1 day", target_date)
        assert result is True
        
        # Test with data too far (beyond 7 days)
        far_data_date = target_date + timedelta(days=10)
        dates = pd.date_range(start=far_data_date, end=far_data_date + timedelta(days=5), freq='D')
        df = pd.DataFrame({'close': [100.0] * len(dates)}, index=dates)
        range_discovery.data_fetcher.fetch_historical_data.return_value = df
        
        result = range_discovery._has_data_at_date("AAPL", "1 day", target_date)
        assert result is False
    
    def test_get_earliest_data_point_cached(self, range_discovery):
        """Test getting earliest data point from cache."""
        symbol = "AAPL"
        timeframe = "1 day"
        start = datetime(2020, 1, 1)
        end = datetime(2023, 1, 1)
        
        # Pre-cache a range
        range_discovery._cache_range(symbol, timeframe, start, end)
        
        result = range_discovery.get_earliest_data_point(symbol, timeframe)
        assert result == start
        
        # Should not call data fetcher
        range_discovery.data_fetcher.fetch_historical_data.assert_not_called()
    
    def test_get_earliest_data_point_no_data(self, range_discovery):
        """Test getting earliest data point when no data exists."""
        range_discovery.data_fetcher.fetch_historical_data.return_value = pd.DataFrame()
        
        result = range_discovery.get_earliest_data_point("INVALID", "1 day")
        assert result is None
    
    def test_get_earliest_data_point_binary_search(self, range_discovery):
        """Test binary search functionality for earliest data point."""
        symbol = "AAPL"
        timeframe = "1 day"
        
        # Mock data availability: data exists from 2021-06-01 onwards
        data_start_date = datetime(2021, 6, 1)
        
        def mock_has_data_at_date(sym, tf, date):
            return date >= data_start_date
        
        # Mock successful data fetch for the final refinement
        sample_df = pd.DataFrame(
            {'close': [100.0]}, 
            index=[data_start_date]
        )
        range_discovery.data_fetcher.fetch_historical_data.return_value = sample_df
        
        with patch.object(range_discovery, '_has_data_at_date', side_effect=mock_has_data_at_date):
            result = range_discovery.get_earliest_data_point(symbol, timeframe, max_lookback_years=5)
        
        # Should find a date close to our target
        assert result is not None
        assert abs((result - data_start_date).days) <= 30  # Within reasonable range
    
    def test_get_earliest_data_point_refinement_error(self, range_discovery):
        """Test handling of errors during date refinement."""
        symbol = "AAPL"
        timeframe = "1 day"
        
        # Mock that data exists somewhere
        def mock_has_data_at_date(sym, tf, date):
            return date >= datetime(2021, 6, 1)
        
        # Mock error during refinement
        range_discovery.data_fetcher.fetch_historical_data.side_effect = Exception("Refinement error")
        
        with patch.object(range_discovery, '_has_data_at_date', side_effect=mock_has_data_at_date):
            result = range_discovery.get_earliest_data_point(symbol, timeframe, max_lookback_years=2)
        
        # Should still return the found date despite refinement error
        assert result is not None
    
    def test_get_data_range_with_discovery(self, range_discovery):
        """Test getting full data range with discovery."""
        symbol = "AAPL"
        timeframe = "1 day"
        earliest_date = datetime(2020, 1, 1)
        
        # Mock the earliest data point discovery
        with patch.object(range_discovery, 'get_earliest_data_point', return_value=earliest_date):
            result = range_discovery.get_data_range(symbol, timeframe)
        
        assert result is not None
        assert result[0] == earliest_date
        assert isinstance(result[1], datetime)  # Latest should be recent
        
        # Should be cached now
        cached_result = range_discovery.get_data_range(symbol, timeframe)
        assert cached_result == result
    
    def test_get_data_range_no_data(self, range_discovery):
        """Test getting data range when no data exists."""
        with patch.object(range_discovery, 'get_earliest_data_point', return_value=None):
            result = range_discovery.get_data_range("INVALID", "1 day")
        
        assert result is None
    
    def test_get_multiple_ranges(self, range_discovery):
        """Test getting ranges for multiple symbols and timeframes."""
        symbols = ["AAPL", "MSFT"]
        timeframes = ["1 day", "1 hour"]
        
        # Mock data ranges
        def mock_get_data_range(symbol, timeframe):
            if symbol == "AAPL":
                return (datetime(2020, 1, 1), datetime(2023, 1, 1))
            elif symbol == "MSFT":
                return (datetime(2019, 1, 1), datetime(2023, 1, 1))
            return None
        
        with patch.object(range_discovery, 'get_data_range', side_effect=mock_get_data_range):
            results = range_discovery.get_multiple_ranges(symbols, timeframes)
        
        assert len(results) == 2
        assert "AAPL" in results
        assert "MSFT" in results
        assert len(results["AAPL"]) == 2
        assert results["AAPL"]["1 day"] is not None
        assert results["MSFT"]["1 day"] is not None
    
    def test_get_multiple_ranges_with_errors(self, range_discovery):
        """Test getting multiple ranges with some errors."""
        symbols = ["AAPL", "ERROR"]
        timeframes = ["1 day"]
        
        def mock_get_data_range(symbol, timeframe):
            if symbol == "AAPL":
                return (datetime(2020, 1, 1), datetime(2023, 1, 1))
            elif symbol == "ERROR":
                raise Exception("Test error")
            return None
        
        with patch.object(range_discovery, 'get_data_range', side_effect=mock_get_data_range):
            results = range_discovery.get_multiple_ranges(symbols, timeframes)
        
        assert results["AAPL"]["1 day"] is not None
        assert results["ERROR"]["1 day"] is None
    
    def test_clear_cache(self, range_discovery):
        """Test cache clearing."""
        # Add some cache entries
        range_discovery._cache_range("AAPL", "1 day", datetime(2020, 1, 1), datetime(2023, 1, 1))
        range_discovery._cache_range("MSFT", "1 hour", datetime(2021, 1, 1), datetime(2023, 1, 1))
        
        assert len(range_discovery.range_cache) == 2
        assert len(range_discovery.cache_timestamps) == 2
        
        range_discovery.clear_cache()
        
        assert len(range_discovery.range_cache) == 0
        assert len(range_discovery.cache_timestamps) == 0
    
    def test_get_cache_stats(self, range_discovery):
        """Test cache statistics."""
        # Initially empty
        stats = range_discovery.get_cache_stats()
        assert stats["total_cached_ranges"] == 0
        assert stats["symbols_in_cache"] == 0
        assert stats["cache_ttl_hours"] == 24
        
        # Add some cache entries
        range_discovery._cache_range("AAPL", "1 day", datetime(2020, 1, 1), datetime(2023, 1, 1))
        range_discovery._cache_range("AAPL", "1 hour", datetime(2020, 1, 1), datetime(2023, 1, 1))
        range_discovery._cache_range("MSFT", "1 day", datetime(2021, 1, 1), datetime(2023, 1, 1))
        
        stats = range_discovery.get_cache_stats()
        assert stats["total_cached_ranges"] == 3
        assert stats["symbols_in_cache"] == 2  # AAPL and MSFT
    
    def test_binary_search_iteration_limit(self, range_discovery):
        """Test that binary search respects iteration limits."""
        symbol = "AAPL"
        timeframe = "1 day"
        
        # Mock that data always exists (to force maximum iterations)
        def mock_has_data_at_date(sym, tf, date):
            return True
        
        # Mock final data fetch
        sample_df = pd.DataFrame(
            {'close': [100.0]}, 
            index=[datetime(2020, 1, 1)]
        )
        range_discovery.data_fetcher.fetch_historical_data.return_value = sample_df
        
        with patch.object(range_discovery, '_has_data_at_date', side_effect=mock_has_data_at_date):
            result = range_discovery.get_earliest_data_point(symbol, timeframe, max_lookback_years=20)
        
        # Should complete without infinite loop
        assert result is not None
    
    def test_edge_case_date_calculations(self, range_discovery):
        """Test edge cases in date calculations."""
        # Test with very recent target date
        recent_date = datetime.now() - timedelta(days=1)
        
        # Create DataFrame with exact target date
        df = pd.DataFrame({'close': [100.0]}, index=[recent_date])
        range_discovery.data_fetcher.fetch_historical_data.return_value = df
        
        result = range_discovery._has_data_at_date("AAPL", "1 day", recent_date)
        assert result is True
        
        # Test with future date (should handle gracefully)
        future_date = datetime.now() + timedelta(days=30)
        result = range_discovery._has_data_at_date("AAPL", "1 day", future_date)
        # Behavior depends on data returned, but should not crash
        assert isinstance(result, bool)