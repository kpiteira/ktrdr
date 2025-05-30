#!/usr/bin/env python3
"""
Simple direct test of IB connection.
"""

from ib_insync import IB, util
import asyncio

async def test_simple():
    """Test simple IB connection."""
    ib = IB()
    
    print("Attempting to connect to 127.0.0.1:4002...")
    try:
        await ib.connectAsync(host='127.0.0.1', port=4002, clientId=1)
        print("✅ Connected!")
        
        # Request current time as a simple test
        server_time = await ib.reqCurrentTimeAsync()
        print(f"✅ Server time: {server_time}")
        
        # Disconnect
        ib.disconnect()
        print("✅ Disconnected")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        if ib.isConnected():
            ib.disconnect()

if __name__ == "__main__":
    print("Testing simple IB connection...")
    util.run(test_simple())