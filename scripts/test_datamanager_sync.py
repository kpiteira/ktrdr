#!/usr/bin/env python3
"""
Test DataManager with synchronous IB implementation.
"""

import time
from datetime import datetime, timedelta, timezone
from ktrdr.data.data_manager import DataManager

def test_datamanager_sync():
    """Test DataManager with synchronous IB implementation."""
    print("Testing DataManager with synchronous IB...")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Create DataManager instance
    print("\n=== Creating DataManager ===")
    dm = DataManager()
    
    # Check if IB was initialized
    if dm.ib_connection and dm.ib_fetcher:
        print(f"✅ IB components initialized")
        print(f"   Connected: {dm.ib_connection.is_connected()}")
        print(f"   Client ID: {dm.ib_connection.config.client_id}")
    else:
        print("❌ IB components not initialized")
        return
    
    # Test 1: Load data (should try IB first, then local)
    print("\n=== Test 1: Load Data with IB ===")
    try:
        data = dm.load_data("AAPL", "1h", validate=False)
        if data is not None and not data.empty:
            print(f"✅ Loaded {len(data)} bars for AAPL")
            print(f"   Date range: {data.index[0]} to {data.index[-1]}")
            print(f"   Source: IB (if recent) or local CSV")
        else:
            print("❌ No data loaded")
    except Exception as e:
        print(f"❌ Error loading data: {e}")
    
    # Test 2: Load with specific date range
    print("\n=== Test 2: Load with Date Range ===")
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=5)
    
    try:
        data = dm.load_data("MSFT", "1d", start_date=start_date, end_date=end_date, validate=False)
        if data is not None and not data.empty:
            print(f"✅ Loaded {len(data)} bars for MSFT")
            print(f"   Requested: {start_date} to {end_date}")
            print(f"   Actual: {data.index[0]} to {data.index[-1]}")
        else:
            print("❌ No data loaded for MSFT")
    except Exception as e:
        print(f"❌ Error loading data: {e}")
    
    # Test 3: Test fallback (non-existent symbol in local)
    print("\n=== Test 3: Test Fallback Logic ===")
    try:
        data = dm.load_data("NVDA", "1h", validate=False)
        if data is not None and not data.empty:
            print(f"✅ Loaded {len(data)} bars for NVDA from IB")
        else:
            print("⚠️  No data for NVDA (expected if not in local CSV)")
    except Exception as e:
        print(f"⚠️  Expected: {e}")
    
    print("\n✅ Test completed")
    
    # The connection will be cleaned up automatically when DataManager is destroyed

if __name__ == "__main__":
    test_datamanager_sync()