#!/usr/bin/env python3
"""
Test IB connection from Docker container to host IB Gateway.
"""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.abspath('.'))

from ktrdr.data.ib_connection_sync import IbConnectionSync, ConnectionConfig
from ktrdr.config.ib_config import get_ib_config
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(name)s | %(message)s')

def test_ib_connection_direct():
    """Test direct IB connection bypassing DataManager."""
    print("=== Testing Direct IB Connection (Docker→Host) ===")
    
    try:
        # Get config
        ib_config = get_ib_config()
        print(f"IB Config: {ib_config.host}:{ib_config.port} (client_id={ib_config.client_id})")
        
        # Create sync config
        sync_config = ConnectionConfig(
            host=ib_config.host,
            port=ib_config.port,
            client_id=ib_config.client_id,
            timeout=ib_config.timeout,
            readonly=ib_config.readonly
        )
        
        # Test connection
        print("Attempting IB connection...")
        ib_conn = IbConnectionSync(sync_config)
        
        if ib_conn.is_connected():
            print("✅ IB Connection successful!")
            print(f"Connection info: {ib_conn.get_connection_info()}")
            ib_conn.disconnect()
        else:
            print("❌ IB Connection failed")
            
    except Exception as e:
        print(f"❌ IB Connection error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_ib_connection_direct()