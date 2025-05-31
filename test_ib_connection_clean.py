#!/usr/bin/env python3
"""
Simple IB connection test after Gateway restart.
Tests the current connection implementation with minimal complexity.
"""

import time
import os
import sys
sys.path.insert(0, '/Users/karl/Documents/dev/ktrdr2')

from ktrdr.data.ib_connection_sync import IbConnectionSync, ConnectionConfig
from ktrdr.logging import get_logger

logger = get_logger(__name__)

def test_clean_connection():
    """Test IB connection with current implementation."""
    print("🧪 Testing IB connection after Gateway restart...")
    
    # Use the Docker configuration
    config = ConnectionConfig(
        host='127.0.0.1',
        port=4003,  # Port forwarding
        client_id=20,  # Use a different client ID
        timeout=30
    )
    
    print(f"📡 Connecting to {config.host}:{config.port} with client ID {config.client_id}")
    
    try:
        # Create connection
        conn = IbConnectionSync(config)
        
        # Give it time to connect
        time.sleep(5)
        
        if conn.is_connected():
            print("✅ SUCCESS: IB connection established!")
            print(f"🆔 Client ID: {conn.config.client_id}")
            print(f"📊 Metrics: {conn.metrics}")
            
            # Test basic functionality
            try:
                print("🧪 Testing basic IB functionality...")
                # This should work if connection is truly stable
                time.sleep(2)
                if conn.is_connected():
                    print("✅ Connection remains stable after 2 seconds")
                else:
                    print("❌ Connection dropped after 2 seconds")
                    
            except Exception as e:
                print(f"⚠️ Error testing functionality: {e}")
            
            # Clean disconnect
            print("🧹 Disconnecting cleanly...")
            conn.disconnect()
            print("✅ Clean disconnect completed")
            
        else:
            print("❌ FAILED: Could not establish connection")
            print(f"📊 Metrics: {conn.metrics}")
            
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_clean_connection()