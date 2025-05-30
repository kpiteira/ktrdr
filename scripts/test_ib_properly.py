#!/usr/bin/env python3
"""
Test IB integration properly handling event loops.
"""

import asyncio
import time
from datetime import datetime, timedelta, timezone
from ktrdr.config.ib_config import get_ib_config
from ktrdr.data.ib_connection import IbConnectionManager
from ktrdr.data.ib_data_fetcher import IbDataFetcher
from ktrdr.data.ib_cleanup import IbConnectionCleaner
from ib_insync import util

async def test_ib_properly():
    """Test IB integration with proper async handling."""
    config = get_ib_config()
    print(f"IB Config: {config.host}:{config.port}, client_id={config.client_id}")
    
    # Test 1: Basic connection
    print("\n=== Test 1: Basic Connection ===")
    conn = IbConnectionManager(config)
    try:
        await conn.connect()
        print("✅ Connected successfully")
        
        # Test connection health
        is_connected = await conn.is_connected()
        print(f"✅ Connection health check: {is_connected}")
        
        # Test 2: Data fetching (using async method directly)
        print("\n=== Test 2: Data Fetching (Async) ===")
        fetcher = IbDataFetcher(conn, config)
        
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=2)
        
        try:
            # Call the async method directly, NOT the sync wrapper
            data = await fetcher.fetch_historical_data("AAPL", "1h", start_date, end_date)
            if data is not None and len(data) > 0:
                print(f"✅ Fetched {len(data)} bars")
                print(f"   Date range: {data.index[0]} to {data.index[-1]}")
            else:
                print("❌ No data returned")
        except Exception as e:
            print(f"❌ Data fetch failed: {e}")
            
    except Exception as e:
        print(f"❌ Connection failed: {e}")
    finally:
        await conn.disconnect()
        print("✅ Disconnected")
    
    # Small delay
    await asyncio.sleep(1)
    
    # Test 3: Second connection to verify cleanup
    print("\n=== Test 3: Second Connection ===")
    conn2 = IbConnectionManager(config)
    try:
        await conn2.connect()
        print("✅ Second connection successful")
        
        # Try another data fetch
        fetcher2 = IbDataFetcher(conn2, config)
        data = await fetcher2.fetch_historical_data("MSFT", "1h", start_date, end_date)
        if data is not None and len(data) > 0:
            print(f"✅ Fetched {len(data)} bars for MSFT")
        else:
            print("❌ No data returned for MSFT")
            
    except Exception as e:
        print(f"❌ Second connection failed: {e}")
    finally:
        await conn2.disconnect()
        print("✅ Disconnected")
    
    # Final status
    print(f"\nFinal active connections: {IbConnectionManager.get_connection_count()}")

if __name__ == "__main__":
    print("Testing IB integration with proper async handling...")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Clean up any existing connections first
    IbConnectionCleaner.cleanup_all_sync()
    print("Cleaned up any existing connections")
    
    # Run the test
    util.run(test_ib_properly())
    
    print("\n✅ Test completed")