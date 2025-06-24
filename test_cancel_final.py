#!/usr/bin/env python3
"""
Final test of cancellation functionality - automated test that simulates Ctrl+C.
"""

import asyncio
import sys
import signal
import os
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from ktrdr.cli.api_client import get_api_client, check_api_connection

async def test_cancellation_simulation():
    """Test cancellation by starting an operation and cancelling it after a few seconds."""
    print("🧪 Testing automated cancellation simulation...")
    
    # Check API connection
    if not await check_api_connection():
        print("❌ API not available")
        return False
    
    api_client = get_api_client()
    
    try:
        # Start a long-running operation
        print("🚀 Starting data loading operation...")
        response = await api_client.load_data(
            symbol="USDJPY",  # Use a symbol that will take time
            timeframe="1m",
            mode="full",
            start_date="2020-01-01",
            end_date="2024-01-01",
            async_mode=True
        )
        
        if not response.get("success") or not response.get("data", {}).get("operation_id"):
            print("❌ Failed to start operation")
            return False
        
        operation_id = response["data"]["operation_id"]
        print(f"✅ Started operation: {operation_id}")
        
        # Wait a few seconds to let the operation get going
        print("⏳ Waiting for operation to start processing...")
        await asyncio.sleep(2)
        
        # Check status
        status_response = await api_client.get_operation_status(operation_id)
        if status_response:
            status = status_response.get("data", {}).get("status")
            current_step = status_response.get("data", {}).get("progress", {}).get("current_step", "Unknown")
            print(f"📊 Operation status: {status} - {current_step}")
        
        # Now send cancellation request directly (simulating what the CLI should do)
        print("🛑 Sending cancellation request...")
        try:
            cancel_response = await api_client.cancel_operation(
                operation_id=operation_id,
                reason="Automated test cancellation"
            )
            
            if cancel_response.get("success"):
                print("✅ Cancel request sent successfully")
                
                # Wait a moment for the cancellation to take effect
                print("⏳ Waiting for cancellation to take effect...")
                await asyncio.sleep(2)
                
                # Check final status
                final_response = await api_client.get_operation_status(operation_id)
                if final_response:
                    final_status = final_response.get("data", {}).get("status")
                    print(f"📋 Final status: {final_status}")
                    
                    if final_status == "cancelled":
                        print("✅ Operation was successfully cancelled!")
                        return True
                    else:
                        print(f"❌ Operation status is '{final_status}', expected 'cancelled'")
                        return False
                else:
                    print("❌ Could not get final status")
                    return False
            else:
                print(f"❌ Cancel request failed: {cancel_response}")
                return False
                
        except Exception as e:
            print(f"❌ Cancel request failed with exception: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

async def main():
    """Main test function."""
    print("🧪 Final Cancellation Test")
    print("=" * 50)
    
    try:
        success = await test_cancellation_simulation()
        
        if success:
            print("\n✅ CANCELLATION TEST PASSED")
            print("✅ Cancellation functionality is working correctly")
        else:
            print("\n❌ CANCELLATION TEST FAILED")
            print("❌ Cancellation is still not working properly")
            
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")

if __name__ == "__main__":
    asyncio.run(main())