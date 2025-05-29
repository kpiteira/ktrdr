"""
Tests for DataManager IB integration
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch
import pandas as pd

from ktrdr.data.data_manager import DataManager
from ktrdr.data.ib_connection import IbConnectionManager
from ktrdr.data.ib_data_fetcher import IbDataFetcher
from ktrdr.config.ib_config import IbConfig
from ktrdr.errors import DataNotFoundError


class TestDataManagerIbIntegration:
    """Test DataManager with IB integration."""
    
    @pytest.fixture
    def mock_ib_config(self):
        """Create mock IB configuration."""
        return IbConfig(
            host="127.0.0.1",
            port=7497,
            client_id=1,
            rate_limit=50,
            rate_period=60
        )
        
    @pytest.fixture
    def mock_ib_connection(self):
        """Create mock IB connection."""
        connection = Mock(spec=IbConnectionManager)
        connection.is_connected_sync.return_value = True
        connection.ib = Mock()
        return connection
        
    @pytest.fixture
    def mock_ib_fetcher(self):
        """Create mock IB fetcher."""
        fetcher = Mock(spec=IbDataFetcher)
        return fetcher
        
    @pytest.fixture
    def sample_ib_data(self):
        """Create sample IB data."""
        dates = pd.date_range('2024-01-01', periods=10, freq='H', tz='UTC')
        return pd.DataFrame({
            'timestamp': dates,
            'open': [100 + i for i in range(10)],
            'high': [101 + i for i in range(10)],
            'low': [99 + i for i in range(10)],
            'close': [100.5 + i for i in range(10)],
            'volume': [1000 + i*100 for i in range(10)]
        }).set_index('timestamp')
        
    @pytest.fixture
    def sample_local_data(self):
        """Create sample local CSV data."""
        dates = pd.date_range('2024-01-01 05:00:00', periods=15, freq='H', tz='UTC')
        return pd.DataFrame({
            'open': [105 + i for i in range(15)],
            'high': [106 + i for i in range(15)],
            'low': [104 + i for i in range(15)],
            'close': [105.5 + i for i in range(15)],
            'volume': [2000 + i*100 for i in range(15)]
        }, index=dates)
        
    def test_init_with_ib_success(self, mock_ib_config):
        """Test DataManager initialization with successful IB setup."""
        with patch('ktrdr.data.data_manager.get_ib_config', return_value=mock_ib_config), \
             patch('ktrdr.data.data_manager.IbConnectionManager') as mock_conn_class, \
             patch('ktrdr.data.data_manager.IbDataFetcher') as mock_fetcher_class:
            
            mock_conn = Mock()
            mock_fetcher = Mock()
            mock_conn_class.return_value = mock_conn
            mock_fetcher_class.return_value = mock_fetcher
            
            manager = DataManager()
            
            assert manager.ib_connection is mock_conn
            assert manager.ib_fetcher is mock_fetcher
            mock_conn_class.assert_called_once_with(mock_ib_config)
            mock_fetcher_class.assert_called_once_with(mock_conn, mock_ib_config)
            
    def test_init_with_ib_failure(self):
        """Test DataManager initialization with IB setup failure."""
        with patch('ktrdr.data.data_manager.get_ib_config', side_effect=Exception("IB config error")):
            manager = DataManager()
            
            assert manager.ib_connection is None
            assert manager.ib_fetcher is None
            
    def test_load_with_fallback_ib_only(self, sample_ib_data):
        """Test loading data with IB only (no local data)."""
        with patch('ktrdr.data.data_manager.get_ib_config') as mock_config, \
             patch('ktrdr.data.data_manager.IbConnectionManager') as mock_conn_class, \
             patch('ktrdr.data.data_manager.IbDataFetcher') as mock_fetcher_class:
            
            # Setup mocks
            mock_conn = Mock()
            mock_fetcher = Mock()
            mock_conn.is_connected_sync.return_value = True
            mock_fetcher.fetch_historical_data_sync.return_value = sample_ib_data
            mock_conn_class.return_value = mock_conn
            mock_fetcher_class.return_value = mock_fetcher
            
            manager = DataManager()
            
            # Mock local data loader to raise DataNotFoundError
            manager.data_loader.load = Mock(side_effect=DataNotFoundError("No local data"))
            manager.data_loader.save = Mock()
            
            result = manager._load_with_fallback("AAPL", "1h")
            
            assert result is not None
            assert len(result) == len(sample_ib_data)
            mock_fetcher.fetch_historical_data_sync.assert_called_once()
            manager.data_loader.save.assert_called_once()
            
    def test_load_with_fallback_local_only(self, sample_local_data):
        """Test loading data with local CSV only (IB unavailable)."""
        with patch('ktrdr.data.data_manager.get_ib_config') as mock_config, \
             patch('ktrdr.data.data_manager.IbConnectionManager') as mock_conn_class, \
             patch('ktrdr.data.data_manager.IbDataFetcher') as mock_fetcher_class:
            
            # Setup mocks - IB not connected
            mock_conn = Mock()
            mock_fetcher = Mock()
            mock_conn.is_connected_sync.return_value = False
            mock_conn_class.return_value = mock_conn
            mock_fetcher_class.return_value = mock_fetcher
            
            manager = DataManager()
            
            # Mock local data loader to return data
            manager.data_loader.load = Mock(return_value=sample_local_data)
            
            result = manager._load_with_fallback("AAPL", "1h")
            
            assert result is not None
            assert len(result) == len(sample_local_data)
            mock_fetcher.fetch_historical_data_sync.assert_not_called()
            manager.data_loader.load.assert_called_once()
            
    def test_load_with_fallback_merge_data(self, sample_ib_data, sample_local_data):
        """Test loading data with both IB and local data - should merge."""
        with patch('ktrdr.data.data_manager.get_ib_config') as mock_config, \
             patch('ktrdr.data.data_manager.IbConnectionManager') as mock_conn_class, \
             patch('ktrdr.data.data_manager.IbDataFetcher') as mock_fetcher_class:
            
            # Setup mocks
            mock_conn = Mock()
            mock_fetcher = Mock()
            mock_conn.is_connected_sync.return_value = True
            mock_fetcher.fetch_historical_data_sync.return_value = sample_ib_data
            mock_conn_class.return_value = mock_conn
            mock_fetcher_class.return_value = mock_fetcher
            
            manager = DataManager()
            
            # Mock local data loader to return data
            manager.data_loader.load = Mock(return_value=sample_local_data)
            manager.data_loader.save = Mock()
            
            result = manager._load_with_fallback("AAPL", "1h")
            
            assert result is not None
            # Should have data from both sources (merged and deduplicated)
            assert len(result) >= max(len(sample_ib_data), len(sample_local_data))
            mock_fetcher.fetch_historical_data_sync.assert_called_once()
            manager.data_loader.load.assert_called_once()
            manager.data_loader.save.assert_called_once()
            
    def test_load_with_fallback_no_data(self):
        """Test loading data when no data available from any source."""
        with patch('ktrdr.data.data_manager.get_ib_config') as mock_config, \
             patch('ktrdr.data.data_manager.IbConnectionManager') as mock_conn_class, \
             patch('ktrdr.data.data_manager.IbDataFetcher') as mock_fetcher_class:
            
            # Setup mocks - both sources fail
            mock_conn = Mock()
            mock_fetcher = Mock()
            mock_conn.is_connected_sync.return_value = True
            mock_fetcher.fetch_historical_data_sync.side_effect = Exception("IB error")
            mock_conn_class.return_value = mock_conn
            mock_fetcher_class.return_value = mock_fetcher
            
            manager = DataManager()
            
            # Mock local data loader to fail
            manager.data_loader.load = Mock(side_effect=DataNotFoundError("No local data"))
            
            result = manager._load_with_fallback("AAPL", "1h")
            
            assert result is None
            
    def test_merge_and_fill_gaps(self, sample_ib_data, sample_local_data):
        """Test data merging logic."""
        manager = DataManager()
        
        # Make both DataFrames timezone-naive for testing
        ib_data = sample_ib_data.copy()
        local_data = sample_local_data.copy()
        ib_data.index = ib_data.index.tz_localize(None)
        local_data.index = local_data.index.tz_localize(None)
        
        merged = manager._merge_and_fill_gaps(ib_data, local_data)
        
        assert merged is not None
        assert len(merged) >= max(len(ib_data), len(local_data))
        assert merged.index.is_monotonic_increasing
        assert merged.index.tz is not None  # Should be timezone-aware
        
    def test_load_data_integration(self, sample_ib_data):
        """Test full load_data method with IB integration."""
        with patch('ktrdr.data.data_manager.get_ib_config') as mock_config, \
             patch('ktrdr.data.data_manager.IbConnectionManager') as mock_conn_class, \
             patch('ktrdr.data.data_manager.IbDataFetcher') as mock_fetcher_class:
            
            # Setup mocks
            mock_conn = Mock()
            mock_fetcher = Mock()
            mock_conn.is_connected_sync.return_value = True
            mock_fetcher.fetch_historical_data_sync.return_value = sample_ib_data
            mock_conn_class.return_value = mock_conn
            mock_fetcher_class.return_value = mock_fetcher
            
            manager = DataManager()
            
            # Mock local data loader
            manager.data_loader.load = Mock(side_effect=DataNotFoundError("No local data"))
            manager.data_loader.save = Mock()
            
            result = manager.load_data("AAPL", "1h", validate=False)
            
            assert result is not None
            assert len(result) == len(sample_ib_data)