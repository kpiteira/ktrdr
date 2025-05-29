#!/usr/bin/env python3
"""
Test IB's reqHeadTimestamp API to get earliest available data directly.

This tests the native IB API for finding earliest data which is much
more efficient than binary search.
"""

import sys
import time
from datetime import datetime
from ib_insync import Stock, Contract

from ktrdr.data.ib_connection_sync import IbConnectionSync
from ktrdr.config.ib_config import get_ib_config


def test_head_timestamp():
    """Test IB's reqHeadTimestamp API."""
    print("Testing IB reqHeadTimestamp API...")
    print(f"Started at: {datetime.now()}")
    print("-" * 60)
    
    # Get IB configuration
    config = get_ib_config()
    print(f"Using IB config: {config.host}:{config.port}")
    
    # Create connection
    ib_connection = IbConnectionSync(config.get_connection_config())
    
    try:
        # Connect to IB
        print("\n1. Connecting to IB...")
        if not ib_connection.ensure_connection():
            print("❌ Failed to connect to IB Gateway/TWS")
            return False
        
        print("✓ Connected to IB")
        
        # Test symbols
        test_cases = [
            ("MSFT", "TRADES"),
            ("AAPL", "TRADES"),
            ("MSFT", "MIDPOINT"),
        ]
        
        print(f"\n2. Testing reqHeadTimestamp for {len(test_cases)} cases...")
        
        for symbol, what_to_show in test_cases:
            print(f"\n   Testing: {symbol} @ {what_to_show}")
            
            try:
                # Create contract
                contract = Stock(symbol=symbol, exchange="SMART", currency="USD")
                
                # Check if reqHeadTimestamp is available
                if hasattr(ib_connection.ib, 'reqHeadTimeStamp'):
                    print("   ✓ reqHeadTimeStamp method available")
                    
                    start_time = time.time()
                    
                    # Request head timestamp
                    # Format: reqHeadTimeStamp(reqId, contract, whatToShow, useRTH, formatDate)
                    head_timestamp = ib_connection.ib.reqHeadTimeStamp(
                        contract=contract,
                        whatToShow=what_to_show,
                        useRTH=False,  # Include all trading hours
                        formatDate=1   # Return as datetime
                    )
                    
                    duration = time.time() - start_time
                    
                    if head_timestamp:
                        print(f"   ✓ Head timestamp: {head_timestamp} ({duration:.3f}s)")
                        
                        # Convert to datetime if it's a string
                        if isinstance(head_timestamp, str):
                            try:
                                # IB returns format like "20050609  11:15:00"
                                dt = datetime.strptime(head_timestamp.strip(), "%Y%m%d  %H:%M:%S")
                                print(f"   ✓ Parsed datetime: {dt}")
                            except Exception as e:
                                print(f"   ⚠️  Could not parse timestamp: {e}")
                        else:
                            print(f"   ✓ Datetime object: {head_timestamp}")
                    else:
                        print(f"   ❌ No head timestamp returned ({duration:.3f}s)")
                        
                elif hasattr(ib_connection.ib, 'reqHeadTimestamp'):
                    print("   ✓ reqHeadTimestamp method available (different spelling)")
                    
                    start_time = time.time()
                    head_timestamp = ib_connection.ib.reqHeadTimestamp(
                        contract=contract,
                        whatToShow=what_to_show,
                        useRTH=False,
                        formatDate=1
                    )
                    duration = time.time() - start_time
                    
                    if head_timestamp:
                        print(f"   ✓ Head timestamp: {head_timestamp} ({duration:.3f}s)")
                    else:
                        print(f"   ❌ No head timestamp returned ({duration:.3f}s)")
                        
                else:
                    print("   ❌ reqHeadTimestamp method not found")
                    print("   Available methods:", [method for method in dir(ib_connection.ib) if 'head' in method.lower() or 'timestamp' in method.lower()])
                    
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
        # Test method discovery
        print(f"\n3. Discovering available methods...")
        ib_methods = [method for method in dir(ib_connection.ib) if method.startswith('req')]
        head_methods = [method for method in ib_methods if 'head' in method.lower() or 'timestamp' in method.lower()]
        
        print(f"   Total req* methods: {len(ib_methods)}")
        print(f"   Head/timestamp methods: {head_methods}")
        
        # Check for the specific method
        if 'reqHeadTimeStamp' in ib_methods:
            print("   ✓ reqHeadTimeStamp found")
        elif 'reqHeadTimestamp' in ib_methods:
            print("   ✓ reqHeadTimestamp found")
        else:
            print("   ❌ No reqHeadTime* method found")
            print("   This may be an older version of ib_insync or TWS/IB Gateway")
        
        # Test with raw IB client if available
        print(f"\n4. Testing raw IB client access...")
        if hasattr(ib_connection.ib, 'client'):
            client = ib_connection.ib.client
            print("   ✓ Raw client accessible")
            
            client_methods = [method for method in dir(client) if 'head' in method.lower() or 'timestamp' in method.lower()]
            print(f"   Client head/timestamp methods: {client_methods}")
            
            if hasattr(client, 'reqHeadTimestamp'):
                print("   ✓ client.reqHeadTimestamp available")
                # We could try calling it directly, but it's more complex with raw client
            elif hasattr(client, 'reqHeadTimeStamp'):
                print("   ✓ client.reqHeadTimeStamp available")
        else:
            print("   ❌ Raw client not accessible")
        
        print(f"\n✅ Head timestamp API exploration completed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Disconnect
        if ib_connection.is_connected():
            ib_connection.disconnect()
            print("\n🔌 Disconnected from IB")


if __name__ == "__main__":
    success = test_head_timestamp()
    sys.exit(0 if success else 1)