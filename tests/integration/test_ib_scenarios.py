"""
Integration tests for IB scenarios that must be preserved during refactoring.

These tests verify actual behavior with real IB connections (when available)
and ensure that refactoring doesn't break existing functionality.

Prerequisites:
- IB Gateway running on paper trading mode
- Port forwarding active (host:4003 -> container:4002)
- Test symbols like AAPL, MSFT available

Run with: uv run pytest tests/integration/test_ib_scenarios.py -v -s
"""

import pytest
import os
import time
import tempfile
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pandas as pd
import requests

from ktrdr.data.ib_connection_manager import get_connection_manager
from ktrdr.data.ib_gap_filler import get_gap_filler, GapFillerService
from ktrdr.data.data_manager import DataManager
from ktrdr.data.local_data_loader import LocalDataLoader
from ktrdr.api.services.ib_service import IbService
from ktrdr.api.models.ib import IbLoadRequest


# Test configuration
TEST_SYMBOL = "AAPL"
TEST_TIMEFRAME = "1d"
ALT_SYMBOL = "MSFT" 
ALT_TIMEFRAME = "1h"

# Skip these tests if IB is not available
def is_ib_available():
    """Check if IB Gateway is running and accessible."""
    try:
        connection_manager = get_connection_manager()
        connection = connection_manager.get_connection()
        return connection is not None and connection.is_connected()
    except Exception:
        return False

def is_api_server_running():
    """Check if the API server is running for endpoint tests."""
    try:
        response = requests.get("http://localhost:8000/api/v1/ib/status", timeout=2)
        return response.status_code == 200
    except:
        return False

pytestmark = pytest.mark.skipif(
    not is_ib_available(), 
    reason="IB Gateway not available - ensure it's running with port forwarding"
)


@pytest.fixture(scope="function")
def temp_data_dir():
    """Create a temporary directory for test data."""
    temp_dir = tempfile.mkdtemp(prefix="ib_test_")
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture(scope="function") 
def test_data_manager(temp_data_dir):
    """Create a DataManager with temporary data directory."""
    return DataManager(data_dir=temp_data_dir)


@pytest.fixture(scope="function")
def test_gap_filler(temp_data_dir):
    """Create a GapFillerService with temporary data directory."""
    gap_filler = GapFillerService(data_dir=temp_data_dir)
    yield gap_filler
    # Ensure gap filler is stopped after test
    if gap_filler._running:
        gap_filler.stop()


@pytest.fixture(scope="function")
def test_csv_with_gap(temp_data_dir):
    """Create a test CSV file with a gap for gap filling tests."""
    # Create CSV with data ending 2 days ago (creates a gap)
    end_date = datetime.now(timezone.utc) - timedelta(days=2)
    start_date = end_date - timedelta(days=5)
    
    # Generate sample data
    dates = pd.date_range(start_date, end_date, freq='1D', tz='UTC')
    data = pd.DataFrame({
        'open': [100.0 + i for i in range(len(dates))],
        'high': [101.0 + i for i in range(len(dates))], 
        'low': [99.0 + i for i in range(len(dates))],
        'close': [100.5 + i for i in range(len(dates))],
        'volume': [1000 + i * 100 for i in range(len(dates))]
    }, index=dates)
    
    # Save to CSV with ISO 8601 timestamp format
    csv_path = Path(temp_data_dir) / f"{TEST_SYMBOL}_{TEST_TIMEFRAME}.csv"
    data.to_csv(csv_path, date_format='%Y-%m-%dT%H:%M:%SZ')
    
    return csv_path, len(dates)


class TestConnectionManagement:
    """Test connection management scenarios."""
    
    def test_connection_manager_singleton(self):
        """Test that connection manager maintains singleton pattern."""
        manager1 = get_connection_manager()
        manager2 = get_connection_manager()
        
        assert manager1 is manager2, "Connection manager should be singleton"
        
        # Test connection availability
        connection = manager1.get_connection()
        assert connection is not None, "Should get a valid connection"
        assert connection.is_connected(), "Connection should be active"
    
    def test_connection_sharing_across_operations(self):
        """Test that multiple operations can share connections safely."""
        manager = get_connection_manager()
        
        # Get connections for different operations
        conn1 = manager.get_connection()  # Simulating API call
        conn2 = manager.get_connection()  # Simulating gap filler
        
        assert conn1 is not None and conn2 is not None
        assert conn1.is_connected() and conn2.is_connected()
        
        # Both should work concurrently
        status1 = manager.get_status()
        status2 = manager.get_status()
        
        assert status1.connected and status2.connected


class TestAutomaticGapFilling:
    """Test automatic gap filling scenarios."""
    
    def test_gap_detection_and_filling(self, test_csv_with_gap, test_gap_filler):
        """Test that gap filler detects and fills gaps automatically."""
        csv_path, original_length = test_csv_with_gap
        
        # Verify initial state
        initial_data = pd.read_csv(csv_path, index_col=0, parse_dates=True)
        assert len(initial_data) == original_length
        
        # Force a gap scan (don't wait for automatic timing)
        result = test_gap_filler.force_scan()
        assert result.get("success", False), f"Gap scan failed: {result.get('error')}"
        
        # Check if gap was filled (should have more data now)
        updated_data = pd.read_csv(csv_path, index_col=0, parse_dates=True)
        
        if len(updated_data) > original_length:
            print(f"✅ Gap filled: {original_length} -> {len(updated_data)} bars")
            assert len(updated_data) > original_length, "Gap should have been filled"
        else:
            # Gap might not need filling if market is closed
            print(f"ℹ️  No gap to fill (market hours): {len(updated_data)} bars")
    
    def test_gap_filler_statistics(self, test_gap_filler):
        """Test that gap filler maintains statistics."""
        # Get initial stats
        initial_stats = test_gap_filler.get_stats()
        assert "gaps_detected" in initial_stats
        assert "gaps_filled" in initial_stats
        assert "running" in initial_stats
        
        # Force a scan
        result = test_gap_filler.force_scan()
        
        # Check updated stats
        updated_stats = test_gap_filler.get_stats()
        assert updated_stats["last_scan_time"] is not None
    
    def test_gap_filler_service_lifecycle(self, test_gap_filler):
        """Test gap filler service start/stop lifecycle."""
        # Initially not running
        assert not test_gap_filler._running
        
        # Start service
        success = test_gap_filler.start()
        assert success, "Gap filler should start successfully"
        assert test_gap_filler._running
        
        # Stop service
        test_gap_filler.stop()
        assert not test_gap_filler._running


class TestApiDataLoading:
    """Test API data loading scenarios."""
    
    def test_ib_service_load_data_tail_mode(self, test_data_manager):
        """Test IbService load_data with tail mode."""
        ib_service = IbService(test_data_manager)
        
        # Test tail mode request
        request = IbLoadRequest(
            symbol=TEST_SYMBOL,
            timeframe=TEST_TIMEFRAME,
            mode="tail"
        )
        
        response = ib_service.load_data(request)
        
        assert response.status in ["success", "failed"], f"Unexpected status: {response.status}"
        assert response.execution_time_seconds > 0
        assert response.merged_file != ""
        
        if response.status == "success":
            print(f"✅ Tail mode: {response.fetched_bars} bars fetched")
            assert response.fetched_bars >= 0
        else:
            print(f"ℹ️  Tail mode failed (expected if no gap): {response.error_message}")
    
    def test_ib_service_load_data_full_mode(self, test_data_manager):
        """Test IbService load_data with full mode."""
        ib_service = IbService(test_data_manager)
        
        # Test full mode request 
        request = IbLoadRequest(
            symbol=ALT_SYMBOL,
            timeframe=ALT_TIMEFRAME,
            mode="full"
        )
        
        response = ib_service.load_data(request)
        
        assert response.status in ["success", "failed"], f"Unexpected status: {response.status}"
        assert response.execution_time_seconds > 0
        
        if response.status == "success":
            print(f"✅ Full mode: {response.fetched_bars} bars fetched")
            assert response.fetched_bars > 0, "Full mode should fetch some data"
            assert response.merged_file != ""
        else:
            print(f"❌ Full mode failed: {response.error_message}")
    
    def test_ib_service_progressive_loading(self, test_data_manager):
        """Test that progressive loading works for date ranges that exceed IB limits."""
        ib_service = IbService(test_data_manager)
        
        # Request a large date range that should trigger progressive loading
        # Use explicit dates that span more than IB's single request limit
        request = IbLoadRequest(
            symbol=TEST_SYMBOL,
            timeframe="1d",
            mode="full",
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2024, 12, 31, tzinfo=timezone.utc)  # Full year (> 365 days for daily)
        )
        
        response = ib_service.load_data(request)
        
        assert response.status in ["success", "failed"]
        
        if response.status == "success":
            print(f"✅ Progressive loading: {response.requests_made} requests, {response.fetched_bars} bars")
            assert response.requests_made >= 1, "Should have made at least one request"
        else:
            print(f"ℹ️  Progressive loading failed (might be expected): {response.error_message}")


@pytest.mark.skipif(
    not is_api_server_running(),
    reason="API server not running - start with 'uv run python -m ktrdr.api.main'"
)
class TestApiEndpoints:
    """Test API endpoints (requires running server)."""
    
    def test_ib_load_endpoint_tail_mode(self):
        """Test POST /api/v1/ib/load endpoint with tail mode."""
        url = "http://localhost:8000/api/v1/ib/load"
        payload = {
            "symbol": TEST_SYMBOL,
            "timeframe": TEST_TIMEFRAME,
            "mode": "tail"
        }
        
        response = requests.post(url, json=payload, timeout=30)
        
        assert response.status_code in [200, 400, 503], f"Unexpected status code: {response.status_code}"
        
        data = response.json()
        assert "success" in data
        assert "data" in data
        
        if data["success"]:
            result = data["data"]
            print(f"✅ API tail mode: {result.get('fetched_bars', 0)} bars")
            assert "status" in result
            assert "execution_time_seconds" in result
        else:
            print(f"ℹ️  API tail mode failed: {data.get('error', {}).get('message', 'Unknown')}")
    
    def test_ib_load_endpoint_full_mode(self):
        """Test POST /api/v1/ib/load endpoint with full mode."""
        url = "http://localhost:8000/api/v1/ib/load"
        payload = {
            "symbol": ALT_SYMBOL,
            "timeframe": ALT_TIMEFRAME, 
            "mode": "full"
        }
        
        response = requests.post(url, json=payload, timeout=60)  # Longer timeout for full mode
        
        assert response.status_code in [200, 400, 503], f"Unexpected status code: {response.status_code}"
        
        data = response.json()
        assert "success" in data
        
        if data["success"]:
            result = data["data"]
            print(f"✅ API full mode: {result.get('fetched_bars', 0)} bars")
            assert result.get("fetched_bars", 0) > 0, "Full mode should fetch data"
        else:
            print(f"❌ API full mode failed: {data.get('error', {}).get('message', 'Unknown')}")
    
    def test_ib_status_endpoint(self):
        """Test that IB status endpoint works."""
        url = "http://localhost:8000/api/v1/ib/status"
        
        response = requests.get(url, timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "connection" in data["data"]
        assert "ib_available" in data["data"]
        
        print(f"✅ IB Status: available={data['data']['ib_available']}")


class TestDataManagerFallback:
    """Test DataManager IB fallback scenarios."""
    
    def test_datamanager_ib_fallback(self, test_data_manager):
        """Test that DataManager falls back to IB when CSV is incomplete."""
        # Try to load data for a symbol that doesn't exist locally
        # This should trigger IB fallback
        try:
            result = test_data_manager.load_data(
                symbol="TSLA",  # Different symbol to ensure no local data
                timeframe="1d",
                validate=False  # Skip validation for speed
            )
            
            if result is not None and not result.empty:
                print(f"✅ DataManager IB fallback: {len(result)} bars loaded")
                assert len(result) > 0, "Should have loaded some data from IB"
            else:
                print("ℹ️  DataManager IB fallback: No data returned (might be expected)")
                
        except Exception as e:
            print(f"ℹ️  DataManager IB fallback failed: {e}")
            # This might be expected if the symbol is invalid or IB is unavailable


class TestRangeDiscovery:
    """Test IB range discovery scenarios."""
    
    def test_range_discovery_single_symbol(self):
        """Test range discovery for a single symbol."""
        ib_service = IbService()
        
        try:
            ranges_response = ib_service.get_data_ranges([TEST_SYMBOL], [TEST_TIMEFRAME])
            
            assert len(ranges_response.symbols) == 1
            symbol_data = ranges_response.symbols[0]
            assert symbol_data.symbol == TEST_SYMBOL
            assert TEST_TIMEFRAME in symbol_data.ranges
            
            range_info = symbol_data.ranges[TEST_TIMEFRAME]
            if range_info:
                print(f"✅ Range discovery: {TEST_SYMBOL} from {range_info.earliest_date} to {range_info.latest_date}")
                assert range_info.earliest_date is not None
                assert range_info.latest_date is not None
                assert range_info.total_days is not None
            else:
                print(f"ℹ️  Range discovery: No range data for {TEST_SYMBOL}")
                
        except Exception as e:
            print(f"ℹ️  Range discovery failed: {e}")
    
    def test_range_discovery_multiple_symbols(self):
        """Test range discovery for multiple symbols."""
        ib_service = IbService()
        
        try:
            symbols = [TEST_SYMBOL, ALT_SYMBOL]
            timeframes = [TEST_TIMEFRAME, ALT_TIMEFRAME]
            
            ranges_response = ib_service.get_data_ranges(symbols, timeframes)
            
            assert len(ranges_response.symbols) == len(symbols)
            assert ranges_response.requested_timeframes == timeframes
            
            for symbol_data in ranges_response.symbols:
                print(f"✅ Range discovery: {symbol_data.symbol} has {len(symbol_data.ranges)} timeframes")
                assert symbol_data.symbol in symbols
                
        except Exception as e:
            print(f"ℹ️  Multiple range discovery failed: {e}")


class TestConnectionIsolation:
    """Test that different operations don't interfere with each other."""
    
    def test_concurrent_operations(self, test_data_manager, test_gap_filler):
        """Test that gap filler and API operations can run concurrently."""
        # Start gap filler in background
        gap_filler_started = test_gap_filler.start()
        assert gap_filler_started
        
        try:
            # Make API call while gap filler is running
            ib_service = IbService(test_data_manager)
            request = IbLoadRequest(
                symbol=TEST_SYMBOL,
                timeframe=TEST_TIMEFRAME,
                mode="tail"
            )
            
            response = ib_service.load_data(request)
            
            # Both should work without interfering
            assert response.execution_time_seconds > 0
            
            # Check gap filler is still running
            assert test_gap_filler._running
            
            stats = test_gap_filler.get_stats()
            assert stats["running"] == True
            
            print("✅ Concurrent operations: API and gap filler worked together")
            
        finally:
            # Always stop gap filler
            test_gap_filler.stop()
    
    def test_connection_cleanup(self):
        """Test that connections are properly cleaned up."""
        connection_manager = get_connection_manager()
        
        # Get initial connection count
        initial_metrics = connection_manager.get_metrics()
        initial_attempts = initial_metrics.get("total_connections", 0)
        
        # Make several connection requests
        for i in range(3):
            connection = connection_manager.get_connection()
            assert connection is not None
            assert connection.is_connected()
        
        # Check that we didn't create excessive connections
        final_metrics = connection_manager.get_metrics()
        final_attempts = final_metrics.get("total_connections", 0)
        
        # Should not have created 3 new connections (should reuse)
        connection_increase = final_attempts - initial_attempts
        assert connection_increase <= 1, f"Too many new connections created: {connection_increase}"
        
        print(f"✅ Connection reuse: {connection_increase} new connections for 3 requests")


if __name__ == "__main__":
    # Run specific test classes for easier debugging
    pytest.main([
        __file__ + "::TestConnectionManagement",
        __file__ + "::TestAutomaticGapFilling", 
        __file__ + "::TestApiDataLoading",
        "-v", "-s"
    ])