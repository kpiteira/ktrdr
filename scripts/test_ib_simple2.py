#!/usr/bin/env python3
"""
Simple direct test of IB connection with different client ID.
"""

from ib_insync import IB, util
import asyncio
import time

async def test_with_client_id(client_id):
    """Test IB connection with specific client ID."""
    ib = IB()
    
    print(f"\nTrying client ID {client_id}...")
    try:
        await ib.connectAsync(host='127.0.0.1', port=4002, clientId=client_id)
        print(f"✅ Connected with client ID {client_id}!")
        
        # Request current time
        server_time = await ib.reqCurrentTimeAsync()
        print(f"✅ Server time: {server_time}")
        
        # Disconnect properly
        ib.disconnect()
        print("✅ Disconnected")
        return True
        
    except Exception as e:
        print(f"❌ Client ID {client_id} failed: {e}")
        if ib.isConnected():
            ib.disconnect()
        return False

async def test_multiple_client_ids():
    """Test with different client IDs."""
    # Try different client IDs
    for client_id in [1, 2, 3, 99]:
        success = await test_with_client_id(client_id)
        if success:
            print(f"\n✅ Client ID {client_id} works!")
            break
        await asyncio.sleep(1)

if __name__ == "__main__":
    print("Testing IB connection with different client IDs...")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    util.run(test_multiple_client_ids())