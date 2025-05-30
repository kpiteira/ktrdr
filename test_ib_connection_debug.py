#!/usr/bin/env python3
"""
Debug IB connection issues - standalone test outside FastAPI context.
"""

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.abspath('.'))

from ktrdr.data.data_manager import DataManager
import tempfile
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(name)s | %(message)s')

def test_sync_ib_connection():
    """Test IB connection in pure synchronous context."""
    print("=== Testing IB Connection (Sync Context) ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"1. Creating DataManager with enable_ib=True")
        
        try:
            # Create DataManager (should load config but not connect)
            dm = DataManager(data_dir=temp_dir, enable_ib=True)
            print(f"   ✓ DataManager created successfully")
            print(f"   - enable_ib: {dm.enable_ib}")
            print(f"   - ib_connection: {dm.ib_connection}")
            print(f"   - _ib_config: {dm._ib_config is not None}")
            
        except Exception as e:
            print(f"   ✗ DataManager creation failed: {e}")
            return
            
        print(f"\n2. Testing lazy IB connection")
        try:
            # This should trigger lazy initialization
            success = dm._ensure_ib_connection()
            print(f"   - Connection success: {success}")
            print(f"   - ib_connection: {dm.ib_connection}")
            print(f"   - ib_fetcher: {dm.ib_fetcher}")
            
        except Exception as e:
            print(f"   ✗ Lazy connection failed: {e}")
            import traceback
            traceback.print_exc()
            
        print(f"\n3. Testing data loading (should trigger IB if needed)")
        try:
            # This should trigger IB connection if local data doesn't cover range
            from datetime import datetime, timezone
            
            # Request recent data that likely won't be in local CSV
            recent_start = datetime(2025, 5, 29, tzinfo=timezone.utc)
            recent_end = datetime(2025, 5, 30, tzinfo=timezone.utc)
            
            print(f"   Requesting data from {recent_start} to {recent_end}")
            data = dm.load_data("AAPL", "1h", start_date=recent_start, end_date=recent_end)
            print(f"   ✓ Data loaded: {len(data) if data is not None else 0} rows")
            
        except Exception as e:
            print(f"   ✗ Data loading failed: {e}")
            import traceback
            traceback.print_exc()

def test_async_context():
    """Test what happens in async context."""
    print("\n=== Testing IB Connection (Async Context) ===")
    
    async def async_test():
        print("Inside async function...")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                dm = DataManager(data_dir=temp_dir, enable_ib=True)
                print("   ✓ DataManager created in async context")
                
                success = dm._ensure_ib_connection()
                print(f"   - Connection success: {success}")
                
            except Exception as e:
                print(f"   ✗ Failed in async context: {e}")
                import traceback
                traceback.print_exc()
    
    # Run the async test
    try:
        asyncio.run(async_test())
    except Exception as e:
        print(f"Async test failed: {e}")

def test_event_loop_detection():
    """Test event loop state detection."""
    print("\n=== Testing Event Loop State ===")
    
    try:
        loop = asyncio.get_running_loop()
        print(f"   Current loop: {loop}")
        print(f"   Loop running: {loop.is_running()}")
    except RuntimeError as e:
        print(f"   No running loop: {e}")
    
    try:
        loop = asyncio.get_event_loop()
        print(f"   Event loop: {loop}")
        print(f"   Loop running: {loop.is_running()}")
    except Exception as e:
        print(f"   Event loop error: {e}")

if __name__ == "__main__":
    print("IB Connection Debug Test")
    print("========================")
    
    # Test event loop state first
    test_event_loop_detection()
    
    # Test in sync context
    test_sync_ib_connection()
    
    # Test in async context
    test_async_context()
    
    print("\nTest completed.")