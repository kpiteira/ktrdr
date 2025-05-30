#!/usr/bin/env python3
"""
Test successive IB connections to verify connection management.
"""

import asyncio
import time
from ktrdr.config.ib_config import get_ib_config
from ktrdr.data.ib_connection import IbConnectionManager
from ktrdr.data.ib_cleanup import IbConnectionCleaner
from ib_insync import util

async def test_successive_connections():
    """Test multiple successive connections."""
    config = get_ib_config()
    print(f"IB Config: {config.host}:{config.port}, client_id={config.client_id}")
    
    # Test 1: Single connection
    print("\n=== Test 1: Single Connection ===")
    conn1 = IbConnectionManager(config)
    try:
        await conn1.connect()
        print(f"✅ Connected successfully")
        is_connected = await conn1.is_connected()
        print(f"✅ Connection check: {is_connected}")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
    finally:
        await conn1.disconnect()
        print("✅ Disconnected")
    
    # Check status after first test
    print(f"\nActive connections after Test 1: {IbConnectionManager.get_connection_count()}")
    
    # Small delay between connections
    await asyncio.sleep(1)
    
    # Test 2: Another connection
    print("\n=== Test 2: Second Connection ===")
    conn2 = IbConnectionManager(config)
    try:
        await conn2.connect()
        print(f"✅ Connected successfully")
        is_connected = await conn2.is_connected()
        print(f"✅ Connection check: {is_connected}")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
    finally:
        await conn2.disconnect()
        print("✅ Disconnected")
    
    # Check final status
    print(f"\nActive connections after Test 2: {IbConnectionManager.get_connection_count()}")
    
    # Test 3: Multiple rapid connections
    print("\n=== Test 3: Rapid Successive Connections ===")
    for i in range(3):
        print(f"\nConnection attempt {i+1}:")
        conn = IbConnectionManager(config)
        try:
            await conn.connect()
            print(f"✅ Connected")
            await conn.disconnect()
            print(f"✅ Disconnected")
        except Exception as e:
            print(f"❌ Failed: {e}")
        await asyncio.sleep(0.5)
    
    # Final cleanup check
    print(f"\nFinal active connections: {IbConnectionManager.get_connection_count()}")
    
    # Run cleanup just to be sure
    await IbConnectionCleaner.cleanup_all()
    print(f"After cleanup: {IbConnectionManager.get_connection_count()}")

if __name__ == "__main__":
    print("Testing successive IB connections...")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Use ib_insync's util.run to avoid event loop issues
    util.run(test_successive_connections())
    
    print("\n✅ Test completed")