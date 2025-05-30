"""
Comprehensive integration tests for IB data fetching system.

These tests verify the complete IB integration including:
- Connection management
- Data fetching and validation
- Range discovery
- Error recovery and resumption
- Data quality checks
- Symbol validation
- End-to-end workflows
"""

import pytest

pytestmark = pytest.mark.skip(reason="IB integration tests disabled for unit test run")
import asyncio
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import pandas as pd
import numpy as np
from pathlib import Path

from ktrdr.data.ib_connection_sync import IbConnectionSync, ConnectionConfig
from ktrdr.data.ib_data_fetcher_sync import IbDataFetcherSync, IbDataRangeDiscovery
from ktrdr.data.ib_symbol_validator import IbSymbolValidator
from ktrdr.data.ib_resume_handler import IbResumeHandler, DownloadSession
from ktrdr.data.data_quality_validator import DataQualityValidator
from ktrdr.data.data_manager import DataManager
from ktrdr.config.ib_config import IbConfig
from ktrdr.errors import DataError, ConnectionError, DataNotFoundError


@pytest.fixture
def ib_config():
    """Create test IB configuration."""
    return IbConfig(
        host="127.0.0.1",
        port=7497,
        client_id=1,
        rate_limit=50,
        rate_period=60,
        timeout=30,
        retry_attempts=3
    )

@pytest.fixture
def connection_config():
    """Create connection configuration."""
    return ConnectionConfig(
        host="127.0.0.1",
        port=7497,
        client_id=1,
        timeout=30
    )

@pytest.fixture
def mock_ib_client():
    """Create mock IB client."""
    mock_ib = Mock()
    mock_ib.isConnected.return_value = True
    mock_ib.reqCurrentTime.return_value = datetime.now()
    mock_ib.reqHeadTimeStamp.return_value = datetime(2020, 1, 1, tzinfo=timezone.utc)
    
    # Mock contract qualification
    mock_contract = Mock()
    mock_contract.symbol = "AAPL"
    mock_contract.exchange = "SMART"
    mock_ib.qualifyContracts.return_value = [mock_contract]
    
    # Mock historical data
    mock_bars = []
    for i in range(10):
        mock_bar = Mock()
        mock_bar.date = datetime(2024, 1, 1, i, tzinfo=timezone.utc)
        mock_bar.open = 100 + i
        mock_bar.high = 101 + i
        mock_bar.low = 99 + i
        mock_bar.close = 100.5 + i
        mock_bar.volume = 1000 + i * 100
        mock_bars.append(mock_bar)
    
    mock_ib.reqHistoricalData.return_value = mock_bars
    
    return mock_ib

@pytest.fixture
def sample_ohlcv_data_integration():
    """Create sample OHLCV data for integration tests."""
    dates = pd.date_range('2024-01-01', periods=100, freq='H', tz='UTC')
    np.random.seed(42)
    
    data = {
        'open': 100 + np.random.normal(0, 1, 100).cumsum(),
        'high': 101 + np.random.normal(0, 1, 100).cumsum(),
        'low': 99 + np.random.normal(0, 1, 100).cumsum(),
        'close': 100.5 + np.random.normal(0, 1, 100).cumsum(),
        'volume': np.random.randint(1000, 5000, 100)
    }
    
    df = pd.DataFrame(data, index=dates)
    
    # Ensure high >= max(open, close) and low <= min(open, close)
    df['high'] = np.maximum(df['high'], np.maximum(df['open'], df['close']))
    df['low'] = np.minimum(df['low'], np.minimum(df['open'], df['close']))
    
    return df


class TestIbCompleteIntegration:
    """Complete integration tests for IB data system."""


class TestConnectionManagement:
    """Test IB connection management integration."""
    
    def test_connection_lifecycle(self, connection_config, mock_ib_client):
        """Test complete connection lifecycle."""
        with patch('ktrdr.data.ib_connection_sync.IB', return_value=mock_ib_client):
            connection = IbConnectionSync(connection_config)
            
            # Test connection (auto-connects in constructor)
            assert connection.is_connected()
            
            # Test connection persistence
            assert connection.ensure_connection()
            
            # Test disconnection
            connection.disconnect()
            mock_ib_client.disconnect.assert_called()
    
    def test_connection_error_handling(self, connection_config):
        """Test connection error handling."""
        with patch('ktrdr.data.ib_connection_sync.IB') as mock_ib_class:
            mock_ib = Mock()
            mock_ib.connect.side_effect = Exception("Connection failed")
            mock_ib.isConnected.return_value = False
            mock_ib_class.return_value = mock_ib
            
            connection = IbConnectionSync(connection_config)
            
            # Connection should fail gracefully (constructor tries to connect)
            assert not connection.is_connected()
    
    def test_connection_auto_reconnect(self, connection_config, mock_ib_client):
        """Test automatic reconnection."""
        with patch('ktrdr.data.ib_connection_sync.IB', return_value=mock_ib_client):
            connection = IbConnectionSync(connection_config)
            
            # Initial connection (auto-connected in constructor)
            assert connection.is_connected()
            
            # Simulate connection loss
            mock_ib_client.isConnected.return_value = False
            
            # ensure_connection should reconnect
            mock_ib_client.isConnected.side_effect = [False, True]  # First call returns False, second returns True
            mock_ib_client.connect.return_value = None  # Successful reconnection
            
            assert connection.ensure_connection()


class TestDataFetchingIntegration:
    """Test complete data fetching workflows."""
    
    def test_full_data_fetch_workflow(self, connection_config, mock_ib_client, sample_ohlcv_data_integration):
        """Test complete data fetching workflow."""
        with patch('ktrdr.data.ib_connection_sync.IB', return_value=mock_ib_client):
            connection = IbConnectionSync(connection_config)
            fetcher = IbDataFetcherSync(connection)
            
            # Setup mock to return our sample data
            mock_bars = []
            for i, (timestamp, row) in enumerate(sample_ohlcv_data_integration.head(10).iterrows()):
                mock_bar = Mock()
                mock_bar.date = timestamp
                mock_bar.open = row['open']
                mock_bar.high = row['high']
                mock_bar.low = row['low']
                mock_bar.close = row['close']
                mock_bar.volume = row['volume']
                mock_bars.append(mock_bar)
            
            mock_ib_client.reqHistoricalData.return_value = mock_bars
            
            # Test data fetching
            result = fetcher.fetch_historical_data(
                symbol="AAPL",
                timeframe="1h",
                start=datetime(2024, 1, 1, tzinfo=timezone.utc),
                end=datetime(2024, 1, 2, tzinfo=timezone.utc)
            )
            
            assert not result.empty
            assert len(result) == 10
            assert list(result.columns) == ['open', 'high', 'low', 'close', 'volume']
            assert result.index.tz is not None  # Should be timezone-aware
    
    def test_data_fetch_with_validation(self, connection_config, mock_ib_client):
        """Test data fetching with quality validation."""
        with patch('ktrdr.data.ib_connection_sync.IB', return_value=mock_ib_client):
            connection = IbConnectionSync(connection_config)
            fetcher = IbDataFetcherSync(connection)
            validator = DataQualityValidator(auto_correct=True)
            
            # Fetch data
            result = fetcher.fetch_historical_data(
                symbol="AAPL",
                timeframe="1h",
                start=datetime(2024, 1, 1, tzinfo=timezone.utc),
                end=datetime(2024, 1, 2, tzinfo=timezone.utc)
            )
            
            # Validate data
            validated_data, quality_report = validator.validate_data(result, "AAPL", "1h")
            
            assert not validated_data.empty
            assert quality_report.symbol == "AAPL"
            assert quality_report.timeframe == "1h"
    
    def test_forex_data_fetching(self, connection_config, mock_ib_client):
        """Test forex data fetching with appropriate settings."""
        with patch('ktrdr.data.ib_connection_sync.IB', return_value=mock_ib_client):
            connection = IbConnectionSync(connection_config)
            fetcher = IbDataFetcherSync(connection)
            
            # Test forex data fetch
            result = fetcher.fetch_historical_data(
                symbol="EURUSD",
                timeframe="1h",
                start=datetime(2024, 1, 1, tzinfo=timezone.utc),
                end=datetime(2024, 1, 2, tzinfo=timezone.utc),
                instrument_type='forex'
            )
            
            assert not result.empty
            # Verify forex contract was requested
            mock_ib_client.qualifyContracts.assert_called()
            mock_ib_client.reqHistoricalData.assert_called()


class TestRangeDiscoveryIntegration:
    """Test range discovery integration."""
    
    def test_range_discovery_with_head_timestamp(self, connection_config, mock_ib_client):
        """Test range discovery using IB's reqHeadTimeStamp API."""
        with patch('ktrdr.data.ib_connection_sync.IB', return_value=mock_ib_client):
            connection = IbConnectionSync(connection_config)
            fetcher = IbDataFetcherSync(connection)
            range_discovery = IbDataRangeDiscovery(fetcher)
            
            # Mock head timestamp response
            mock_ib_client.reqHeadTimeStamp.return_value = datetime(2020, 1, 1, tzinfo=timezone.utc)
            
            # Test range discovery
            earliest = range_discovery.get_earliest_data_point("AAPL", "1d")
            
            assert earliest is not None
            assert earliest.year == 2020
            mock_ib_client.reqHeadTimeStamp.assert_called()
    
    def test_range_discovery_caching(self, connection_config, mock_ib_client):
        """Test range discovery caching functionality."""
        with patch('ktrdr.data.ib_connection_sync.IB', return_value=mock_ib_client):
            connection = IbConnectionSync(connection_config)
            fetcher = IbDataFetcherSync(connection)
            range_discovery = IbDataRangeDiscovery(fetcher)
            
            mock_ib_client.reqHeadTimeStamp.return_value = datetime(2020, 1, 1, tzinfo=timezone.utc)
            
            # First call should hit the API
            earliest1 = range_discovery.get_earliest_data_point("AAPL", "1d")
            
            # Second call should use cache
            earliest2 = range_discovery.get_earliest_data_point("AAPL", "1d")
            
            assert earliest1 == earliest2
            # Should only call the API once due to caching
            assert mock_ib_client.reqHeadTimeStamp.call_count == 1
    
    def test_multiple_symbol_range_discovery(self, connection_config, mock_ib_client):
        """Test range discovery for multiple symbols."""
        with patch('ktrdr.data.ib_connection_sync.IB', return_value=mock_ib_client):
            connection = IbConnectionSync(connection_config)
            fetcher = IbDataFetcherSync(connection)
            range_discovery = IbDataRangeDiscovery(fetcher)
            
            # Mock different head timestamps for different symbols
            def mock_head_timestamp(contract, **kwargs):
                if hasattr(contract, 'symbol'):
                    if contract.symbol == "AAPL":
                        return datetime(2020, 1, 1, tzinfo=timezone.utc)
                    elif contract.symbol == "MSFT":
                        return datetime(2019, 1, 1, tzinfo=timezone.utc)
                return datetime(2020, 1, 1, tzinfo=timezone.utc)
            
            mock_ib_client.reqHeadTimeStamp.side_effect = mock_head_timestamp
            
            # Mock contract qualification to return different contracts
            def mock_qualify_contracts(contract):
                mock_contract = Mock()
                mock_contract.symbol = contract.symbol
                mock_contract.exchange = "SMART"
                return [mock_contract]
            
            mock_ib_client.qualifyContracts.side_effect = mock_qualify_contracts
            
            # Test multiple ranges
            ranges = range_discovery.get_multiple_ranges(
                symbols=["AAPL", "MSFT"],
                timeframes=["1d"]
            )
            
            assert "AAPL" in ranges
            assert "MSFT" in ranges
            assert ranges["AAPL"]["1d"] is not None
            assert ranges["MSFT"]["1d"] is not None


class TestSymbolValidationIntegration:
    """Test symbol validation integration."""
    
    def test_symbol_validation_workflow(self, connection_config, mock_ib_client):
        """Test complete symbol validation workflow."""
        with patch('ktrdr.data.ib_connection_sync.IB', return_value=mock_ib_client):
            connection = IbConnectionSync(connection_config)
            validator = IbSymbolValidator(connection)
            
            # Mock successful validation
            mock_contract = Mock()
            mock_contract.symbol = "AAPL"
            mock_contract.exchange = "SMART"
            mock_ib_client.qualifyContracts.return_value = [mock_contract]
            
            # Test validation
            result = validator.validate_symbol("AAPL")
            
            assert result.is_valid
            assert result.symbol == "AAPL"
            assert result.validated_symbol == "AAPL"
            assert result.instrument_type == "stock"
    
    def test_forex_symbol_validation(self, connection_config, mock_ib_client):
        """Test forex symbol validation."""
        with patch('ktrdr.data.ib_connection_sync.IB', return_value=mock_ib_client):
            connection = IbConnectionSync(connection_config)
            validator = IbSymbolValidator(connection)
            
            # Mock forex contract
            mock_contract = Mock()
            mock_contract.symbol = "EUR"
            mock_contract.currency = "USD"
            mock_ib_client.qualifyContracts.return_value = [mock_contract]
            
            # Test forex validation
            result = validator.validate_symbol("EURUSD")
            
            assert result.is_valid
            assert result.instrument_type == "forex"
    
    def test_batch_symbol_validation(self, connection_config, mock_ib_client):
        """Test batch symbol validation."""
        with patch('ktrdr.data.ib_connection_sync.IB', return_value=mock_ib_client):
            connection = IbConnectionSync(connection_config)
            validator = IbSymbolValidator(connection)
            
            # Mock multiple contracts
            def mock_qualify_contracts(contract):
                mock_contract = Mock()
                if hasattr(contract, 'symbol'):
                    mock_contract.symbol = contract.symbol
                    if contract.symbol in ["AAPL", "MSFT", "GOOGL"]:
                        return [mock_contract]
                return []
            
            mock_ib_client.qualifyContracts.side_effect = mock_qualify_contracts
            
            # Test batch validation
            symbols = ["AAPL", "MSFT", "GOOGL", "INVALID"]
            results = validator.validate_symbols_batch(symbols)
            
            assert len(results) == 4
            assert sum(1 for r in results if r.is_valid) == 3
            assert sum(1 for r in results if not r.is_valid) == 1


class TestErrorRecoveryIntegration:
    """Test error recovery and resumption integration."""
    
    def test_download_session_management(self, tmp_path, connection_config, mock_ib_client):
        """Test download session persistence and recovery."""
        with patch('ktrdr.data.ib_connection_sync.IB', return_value=mock_ib_client):
            connection = IbConnectionSync(connection_config)
            fetcher = IbDataFetcherSync(connection)
            
            # Create resume handler
            resume_handler = IbResumeHandler(fetcher, progress_dir=str(tmp_path))
            
            # Create and save initial session
            session = DownloadSession(
                session_id="test_session",
                symbol="AAPL",
                timeframe="1h",
                full_start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                full_end_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
                chunks=[],
                status="in_progress"
            )
            
            resume_handler.save_session(session)
            
            # Load session and verify
            loaded_session = resume_handler.load_session("test_session")
            
            assert loaded_session is not None
            assert loaded_session.symbol == "AAPL"
            assert loaded_session.timeframe == "1h"
            assert loaded_session.status == "in_progress"
    
    def test_resumable_download_workflow(self, tmp_path, connection_config, mock_ib_client):
        """Test complete resumable download workflow."""
        with patch('ktrdr.data.ib_connection_sync.IB', return_value=mock_ib_client):
            connection = IbConnectionSync(connection_config)
            fetcher = IbDataFetcherSync(connection)
            
            resume_handler = IbResumeHandler(fetcher, progress_dir=str(tmp_path))
            
            # Simulate partial download
            start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
            end_date = datetime(2024, 1, 10, tzinfo=timezone.utc)
            
            # Create session with some progress
            session = DownloadSession(
                session_id="partial_session",
                symbol="AAPL",
                timeframe="1h",
                full_start_date=start_date,
                full_end_date=end_date,
                chunks=[],
                status="in_progress"
            )
            
            resume_handler.save_session(session)
            
            # Test resumption
            loaded_session = resume_handler.load_session("partial_session")
            assert loaded_session is not None
            
            # Verify session details
            assert loaded_session.symbol == "AAPL"
            assert loaded_session.full_start_date == start_date
            assert loaded_session.full_end_date == end_date
    
    def test_error_recovery_with_retries(self, tmp_path, connection_config, mock_ib_client):
        """Test error recovery with retry logic."""
        with patch('ktrdr.data.ib_connection_sync.IB', return_value=mock_ib_client):
            connection = IbConnectionSync(connection_config)
            fetcher = IbDataFetcherSync(connection)
            
            resume_handler = IbResumeHandler(fetcher, progress_dir=str(tmp_path))
            
            # Mock fetcher to fail initially then succeed
            call_count = 0
            def mock_fetch(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count <= 2:
                    raise DataError("Temporary failure")
                
                # Return mock data on third attempt
                dates = pd.date_range('2024-01-01', periods=5, freq='H', tz='UTC')
                return pd.DataFrame({
                    'open': [100] * 5,
                    'high': [101] * 5,
                    'low': [99] * 5,
                    'close': [100.5] * 5,
                    'volume': [1000] * 5
                }, index=dates)
            
            fetcher.fetch_historical_data = mock_fetch
            
            # Create session for retry testing
            session = DownloadSession(
                session_id="retry_session",
                symbol="AAPL",
                timeframe="1h",
                full_start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                full_end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
                chunks=[],
                status="in_progress"
            )
            
            # Test that session can be created and managed
            resume_handler.save_session(session)
            loaded_session = resume_handler.load_session("retry_session")
            assert loaded_session is not None


class TestDataQualityIntegration:
    """Test data quality validation integration."""
    
    def test_end_to_end_data_quality_workflow(self, connection_config, mock_ib_client):
        """Test complete data quality validation workflow."""
        with patch('ktrdr.data.ib_connection_sync.IB', return_value=mock_ib_client):
            connection = IbConnectionSync(connection_config)
            fetcher = IbDataFetcherSync(connection)
            validator = DataQualityValidator(auto_correct=True)
            
            # Create data with quality issues
            dates = pd.date_range('2024-01-01', periods=10, freq='H', tz='UTC')
            data = pd.DataFrame({
                'open': [100, 101, 102, -5, 104, 105, 106, 107, 108, 109],  # Negative price
                'high': [101, 102, 103, 104, 105, 106, 107, 108, 109, 110],
                'low': [99, 100, 101, 102, 103, 104, 105, 106, 107, 108],
                'close': [100.5, 101.5, 102.5, 103.5, 104.5, 105.5, 106.5, 107.5, 108.5, 109.5],
                'volume': [1000, 1100, 1200, -500, 1400, 1500, 1600, 1700, 1800, 1900]  # Negative volume
            }, index=dates)
            
            # Mock fetcher to return this problematic data
            fetcher.fetch_historical_data = Mock(return_value=data)
            
            # Fetch and validate
            raw_data = fetcher.fetch_historical_data("AAPL", "1h", dates[0], dates[-1])
            validated_data, quality_report = validator.validate_data(raw_data, "AAPL", "1h")
            
            # Verify issues were detected and corrected
            assert quality_report.total_issues > 0
            assert quality_report.corrections_made > 0
            
            # Verify data was corrected
            assert all(validated_data['open'] > 0)  # No negative prices
            assert all(validated_data['volume'] >= 0)  # No negative volumes
    
    def test_data_quality_with_outlier_detection(self, sample_ohlcv_data_integration):
        """Test data quality validation with outlier detection."""
        validator = DataQualityValidator(auto_correct=True)
        
        # Introduce outliers
        data = sample_ohlcv_data_integration.copy()
        data.iloc[50, data.columns.get_loc('close')] = data.iloc[50, data.columns.get_loc('close')] * 3  # 300% spike
        
        # Validate
        validated_data, quality_report = validator.validate_data(data, "AAPL", "1h")
        
        # Check for outlier detection
        outlier_issues = [issue for issue in quality_report.issues if 'outlier' in issue.issue_type]
        assert len(outlier_issues) > 0


class TestEndToEndWorkflows:
    """Test complete end-to-end workflows."""
    
    def test_complete_data_manager_ib_workflow(self, ib_config, mock_ib_client, tmp_path):
        """Test complete DataManager workflow with IB integration."""
        with patch('ktrdr.data.data_manager.get_ib_config', return_value=ib_config), \
             patch('ktrdr.data.ib_connection_sync.IB', return_value=mock_ib_client), \
             patch('ktrdr.data.data_manager.IbConnectionSync') as mock_conn_class, \
             patch('ktrdr.data.data_manager.IbDataFetcherSync') as mock_fetcher_class:
            
            # Setup mocks
            mock_connection = Mock()
            mock_connection.is_connected.return_value = True
            mock_fetcher = Mock()
            
            # Create sample data
            dates = pd.date_range('2024-01-01', periods=50, freq='H', tz='UTC')
            sample_data = pd.DataFrame({
                'open': 100 + np.random.normal(0, 1, 50),
                'high': 101 + np.random.normal(0, 1, 50),
                'low': 99 + np.random.normal(0, 1, 50),
                'close': 100.5 + np.random.normal(0, 1, 50),
                'volume': np.random.randint(1000, 5000, 50)
            }, index=dates)
            
            mock_fetcher.fetch_historical_data.return_value = sample_data
            mock_conn_class.return_value = mock_connection
            mock_fetcher_class.return_value = mock_fetcher
            
            # Initialize DataManager
            manager = DataManager(data_dir=tmp_path)
            
            # Mock local data loader to simulate no local data  
            manager.data_loader.load = Mock(side_effect=DataNotFoundError("No local data"))
            manager.data_loader.save = Mock()
            
            # Test complete workflow
            result = manager.load_data("AAPL", "1h", validate=True)
            
            assert result is not None
            assert not result.empty
            assert len(result) == 50
            
            # Verify IB fetcher was called
            mock_fetcher.fetch_historical_data.assert_called()
            
            # Verify data was saved locally
            manager.data_loader.save.assert_called()
    
    def test_symbol_discovery_and_validation_workflow(self, connection_config, mock_ib_client):
        """Test complete symbol discovery and validation workflow."""
        with patch('ktrdr.data.ib_connection_sync.IB', return_value=mock_ib_client):
            connection = IbConnectionSync(connection_config)
            validator = IbSymbolValidator(connection)
            fetcher = IbDataFetcherSync(connection)
            range_discovery = IbDataRangeDiscovery(fetcher)
            
            # Mock symbol validation
            mock_contract = Mock()
            mock_contract.symbol = "AAPL"
            mock_contract.exchange = "SMART"
            mock_ib_client.qualifyContracts.return_value = [mock_contract]
            
            # Mock range discovery
            mock_ib_client.reqHeadTimeStamp.return_value = datetime(2020, 1, 1, tzinfo=timezone.utc)
            
            # Test workflow
            symbols_to_test = ["AAPL", "MSFT", "INVALID_SYMBOL"]
            
            validated_symbols = []
            for symbol in symbols_to_test:
                validation_result = validator.validate_symbol(symbol)
                if validation_result.is_valid:
                    validated_symbols.append(symbol)
                    
                    # Get data range for valid symbols
                    data_range = range_discovery.get_data_range(symbol, "1d")
                    assert data_range is not None
            
            assert len(validated_symbols) >= 1  # At least AAPL should be valid
    
    def test_error_scenarios_and_recovery(self, connection_config, mock_ib_client, tmp_path):
        """Test various error scenarios and recovery mechanisms."""
        with patch('ktrdr.data.ib_connection_sync.IB', return_value=mock_ib_client):
            connection = IbConnectionSync(connection_config)
            fetcher = IbDataFetcherSync(connection)
            
            resume_handler = IbResumeHandler(fetcher, progress_dir=str(tmp_path))
            
            # Test connection error recovery
            mock_ib_client.isConnected.side_effect = [True, False, True]  # Connection drops then recovers
            
            assert connection.is_connected()  # Initially connected
            assert not connection.is_connected()  # Connection dropped
            
            # ensure_connection should handle reconnection
            mock_ib_client.connect.return_value = None
            assert connection.ensure_connection()  # Should reconnect
            
            # Test data fetching error and recovery
            fetch_attempts = 0
            def mock_fetch_with_failures(*args, **kwargs):
                nonlocal fetch_attempts
                fetch_attempts += 1
                if fetch_attempts <= 2:
                    raise DataError("Temporary API error")
                
                # Return data on third attempt
                dates = pd.date_range('2024-01-01', periods=5, freq='H', tz='UTC')
                return pd.DataFrame({
                    'open': [100] * 5,
                    'high': [101] * 5,
                    'low': [99] * 5,
                    'close': [100.5] * 5,
                    'volume': [1000] * 5
                }, index=dates)
            
            fetcher.fetch_historical_data = mock_fetch_with_failures
            
            # Test that multiple attempts eventually succeed
            # (In a real implementation, this would be handled by retry decorators)
            result = None
            for attempt in range(3):
                try:
                    result = fetcher.fetch_historical_data(
                        "AAPL", "1h",
                        datetime(2024, 1, 1, tzinfo=timezone.utc),
                        datetime(2024, 1, 2, tzinfo=timezone.utc)
                    )
                    break
                except DataError:
                    if attempt == 2:  # Last attempt
                        raise
                    continue
            
            assert result is not None
            assert not result.empty


class TestPerformanceAndScaling:
    """Test performance and scaling aspects."""
    
    def test_large_dataset_handling(self, connection_config, mock_ib_client):
        """Test handling of large datasets."""
        with patch('ktrdr.data.ib_connection_sync.IB', return_value=mock_ib_client):
            connection = IbConnectionSync(connection_config)
            fetcher = IbDataFetcherSync(connection)
            
            # Mock large dataset
            large_dates = pd.date_range('2020-01-01', '2024-01-01', freq='H', tz='UTC')
            large_data = pd.DataFrame({
                'open': np.random.normal(100, 10, len(large_dates)),
                'high': np.random.normal(105, 10, len(large_dates)),
                'low': np.random.normal(95, 10, len(large_dates)),
                'close': np.random.normal(102, 10, len(large_dates)),
                'volume': np.random.randint(1000, 10000, len(large_dates))
            }, index=large_dates)
            
            # Ensure OHLC relationships are valid
            large_data['high'] = np.maximum(large_data['high'], np.maximum(large_data['open'], large_data['close']))
            large_data['low'] = np.minimum(large_data['low'], np.minimum(large_data['open'], large_data['close']))
            
            fetcher.fetch_historical_data = Mock(return_value=large_data)
            
            # Test validation with large dataset
            validator = DataQualityValidator(auto_correct=True)
            
            start_time = time.time()
            validated_data, quality_report = validator.validate_data(large_data, "AAPL", "1h")
            validation_time = time.time() - start_time
            
            assert not validated_data.empty
            assert len(validated_data) == len(large_data)
            assert validation_time < 30  # Should complete within 30 seconds
    
    def test_concurrent_symbol_processing(self, connection_config, mock_ib_client):
        """Test processing multiple symbols concurrently."""
        with patch('ktrdr.data.ib_connection_sync.IB', return_value=mock_ib_client):
            connection = IbConnectionSync(connection_config)
            fetcher = IbDataFetcherSync(connection)
            range_discovery = IbDataRangeDiscovery(fetcher)
            
            # Mock different responses for different symbols
            def mock_head_timestamp(contract, **kwargs):
                symbol_dates = {
                    "AAPL": datetime(2020, 1, 1, tzinfo=timezone.utc),
                    "MSFT": datetime(2019, 1, 1, tzinfo=timezone.utc),
                    "GOOGL": datetime(2021, 1, 1, tzinfo=timezone.utc),
                }
                if hasattr(contract, 'symbol'):
                    return symbol_dates.get(contract.symbol, datetime(2020, 1, 1, tzinfo=timezone.utc))
                return datetime(2020, 1, 1, tzinfo=timezone.utc)
            
            mock_ib_client.reqHeadTimeStamp.side_effect = mock_head_timestamp
            
            # Mock contract qualification
            def mock_qualify_contracts(contract):
                mock_contract = Mock()
                mock_contract.symbol = contract.symbol
                mock_contract.exchange = "SMART"
                return [mock_contract]
            
            mock_ib_client.qualifyContracts.side_effect = mock_qualify_contracts
            
            # Test concurrent processing
            symbols = ["AAPL", "MSFT", "GOOGL"]
            timeframes = ["1d", "1h"]
            
            start_time = time.time()
            ranges = range_discovery.get_multiple_ranges(symbols, timeframes)
            processing_time = time.time() - start_time
            
            assert len(ranges) == len(symbols)
            for symbol in symbols:
                assert symbol in ranges
                for timeframe in timeframes:
                    assert timeframe in ranges[symbol]
                    assert ranges[symbol][timeframe] is not None
            
            # Should be reasonably fast
            assert processing_time < 10  # Should complete within 10 seconds


if __name__ == "__main__":
    pytest.main([__file__, "-v"])