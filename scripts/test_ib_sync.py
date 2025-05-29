#!/usr/bin/env python3
"""
Test the synchronous IB implementation.
"""

import time
from datetime import datetime, timedelta, timezone
from ktrdr.data.ib_connection_sync import IbConnectionSync, ConnectionConfig
from ktrdr.data.ib_data_fetcher_sync import IbDataFetcherSync

def test_sync_implementation():
    """Test our new synchronous IB implementation."""
    print("Testing synchronous IB implementation...")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Create config
    config = ConnectionConfig(
        host="127.0.0.1",
        port=4002,
        client_id=None  # Will be randomized
    )
    
    # Test 1: Connection
    print("\n=== Test 1: Basic Connection ===")
    conn = IbConnectionSync(config)
    
    if conn.is_connected():
        print(f"✅ Connected successfully with client ID: {config.client_id}")
        
        # Test 2: Data fetching
        print("\n=== Test 2: Data Fetching ===")
        fetcher = IbDataFetcherSync(conn)
        
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=2)
        
        try:
            # Fetch stock data
            print("Fetching AAPL data...")
            data = fetcher.fetch_historical_data("AAPL", "1h", start_date, end_date)
            if not data.empty:
                print(f"✅ Fetched {len(data)} bars for AAPL")
                print(f"   Date range: {data.index[0]} to {data.index[-1]}")
            else:
                print("❌ No data returned for AAPL")
                
        except Exception as e:
            print(f"❌ Data fetch failed: {e}")
        
        # Test 3: Disconnect and reconnect
        print("\n=== Test 3: Disconnect/Reconnect ===")
        conn.disconnect()
        print("✅ Disconnected")
        
        time.sleep(1)
        
        # Create new connection with different client ID
        config2 = ConnectionConfig(host="127.0.0.1", port=4002)
        conn2 = IbConnectionSync(config2)
        
        if conn2.is_connected():
            print(f"✅ Reconnected with new client ID: {config2.client_id}")
            
            # Try another fetch
            fetcher2 = IbDataFetcherSync(conn2)
            try:
                print("Fetching MSFT data...")
                data = fetcher2.fetch_historical_data("MSFT", "1h", start_date, end_date)
                if not data.empty:
                    print(f"✅ Fetched {len(data)} bars for MSFT")
                else:
                    print("❌ No data returned for MSFT")
            except Exception as e:
                print(f"❌ Second fetch failed: {e}")
            
            conn2.disconnect()
            print("✅ Disconnected second connection")
        else:
            print("❌ Failed to reconnect")
    else:
        print("❌ Initial connection failed")
        print(f"Connection info: {conn.get_connection_info()}")
    
    print("\n✅ Test completed")

if __name__ == "__main__":
    test_sync_implementation()