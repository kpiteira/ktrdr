#!/usr/bin/env python3
"""
Debug script to test IB Gateway connection outside of Docker.

This script tests basic IB Gateway connectivity to help isolate
whether the issue is with Docker networking or IB configuration.
"""

import asyncio
import sys
from ib_insync import IB

async def test_ib_connection():
    """Test basic IB Gateway connection"""
    ib = IB()
    
    # Test parameters
    host = "localhost"  # Test from host machine first
    port = 4002
    client_id = 999  # Use high client ID to avoid conflicts
    timeout = 10  # Shorter timeout for faster feedback
    
    print(f"🔍 Testing IB Gateway connection:")
    print(f"   Host: {host}")
    print(f"   Port: {port}")
    print(f"   Client ID: {client_id}")
    print(f"   Timeout: {timeout}s")
    print()
    
    try:
        print("🚀 Attempting connection...")
        await ib.connectAsync(
            host=host,
            port=port,
            clientId=client_id,
            timeout=timeout
        )
        
        print("✅ Connection successful!")
        print(f"   Connected: {ib.isConnected()}")
        
        # Test basic API call
        print("🧪 Testing basic API call...")
        try:
            accounts = await ib.reqManagedAcctsAsync()
            print(f"   Managed accounts: {accounts}")
            
            # Test contract details
            from ib_insync import Stock
            contract = Stock('AAPL', 'SMART', 'USD')
            details = await ib.reqContractDetailsAsync(contract)
            print(f"   Contract details for AAPL: {len(details)} results")
            
            print("✅ API calls successful!")
            
        except Exception as api_error:
            print(f"❌ API call failed: {api_error}")
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print(f"   Error type: {type(e).__name__}")
        
        # Check if it's a timeout specifically
        if "timeout" in str(e).lower() or "TimeoutError" in str(type(e).__name__):
            print("\n🔍 Timeout error detected - this suggests:")
            print("   1. TCP connection succeeded but IB handshake failed")
            print("   2. IB Gateway may not be properly configured for API access")
            print("   3. Check IB Gateway API settings and login status")
        
    finally:
        if ib.isConnected():
            print("🔌 Disconnecting...")
            ib.disconnect()
            print("✅ Disconnected")

if __name__ == "__main__":
    print("IB Gateway Connection Debug Script")
    print("=" * 40)
    
    try:
        asyncio.run(test_ib_connection())
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)
    
    print("\n✅ Debug script completed")