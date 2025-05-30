#!/usr/bin/env python3
"""
Quick test script to verify the context-aware IB manager works correctly.
"""

import asyncio
from datetime import datetime, timezone, timedelta
from ktrdr.data.ib_connection_manager import get_connection_manager
from ktrdr.data.ib_context_manager import create_context_aware_fetcher
from ktrdr.logging import get_logger

logger = get_logger(__name__)

def test_thread_context():
    """Test context manager in thread context (normal background mode)."""
    print("Testing thread context (background thread mode)...")
    
    connection_manager = get_connection_manager()
    if not connection_manager.is_connected():
        print("IB not connected, skipping test")
        return
    
    connection = connection_manager.get_connection()
    if not connection:
        print("No connection available")
        return
    
    # Create context-aware fetcher
    context_fetcher = create_context_aware_fetcher(connection)
    
    # Test fetch in thread context
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=1)
    
    print(f"Fetching AAPL 1h data from {start_time} to {end_time}")
    data = context_fetcher.fetch_historical_data("AAPL", "1h", start_time, end_time)
    
    if data is not None:
        print(f"✅ Thread context fetch successful: {len(data)} bars")
    else:
        print("❌ Thread context fetch failed")

async def test_async_context():
    """Test context manager in async context (FastAPI mode)."""
    print("Testing async context (FastAPI mode)...")
    
    connection_manager = get_connection_manager()
    if not connection_manager.is_connected():
        print("IB not connected, skipping test")
        return
    
    connection = connection_manager.get_connection()
    if not connection:
        print("No connection available")
        return
    
    # Create context-aware fetcher
    context_fetcher = create_context_aware_fetcher(connection)
    
    # Test fetch in async context
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=1)
    
    print(f"Fetching AAPL 1h data from {start_time} to {end_time}")
    data = context_fetcher.fetch_historical_data("AAPL", "1h", start_time, end_time)
    
    if data is not None:
        print(f"✅ Async context fetch successful: {len(data)} bars")
    else:
        print("❌ Async context fetch failed")

if __name__ == "__main__":
    print("Testing context-aware IB data fetcher...")
    
    # Test 1: Thread context (simulates background gap filler)
    test_thread_context()
    
    # Test 2: Async context (simulates FastAPI force-scan)
    print("\n" + "="*50 + "\n")
    asyncio.run(test_async_context())
    
    print("\nContext testing complete!")