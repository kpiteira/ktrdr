#!/usr/bin/env python3
"""
Basic IB Gateway Connection Diagnostic Script

Simple diagnostic script to test the most fundamental IB Gateway connection
without any KTRDR architecture complexity. This is NOT part of the automated
test suite - it's a manual debugging tool for IB connection issues.

Usage: python scripts/basic_ib_connection_check.py
"""

import asyncio
import sys
import time
from pathlib import Path

# Add project root to path so we can import ib_insync
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from ib_insync import IB

    print("✅ ib_insync imported successfully")
except ImportError as e:
    print(f"❌ Failed to import ib_insync: {e}")
    sys.exit(1)


def check_sync_connection():
    """Test synchronous connection (the most basic approach)"""
    print("\n🧪 Test 1: Synchronous Connection")
    print("-" * 40)

    ib = IB()

    try:
        print("Attempting sync connection to localhost:4002 with client_id=100...")
        ib.connect("localhost", 4002, clientId=100, timeout=15)

        print("✅ Connection successful!")
        print(f"   Connected: {ib.isConnected()}")

        if ib.isConnected():
            try:
                accounts = ib.managedAccounts()
                print(f"   Managed accounts: {accounts}")
                print(f"   Account count: {len(accounts) if accounts else 0}")
            except Exception as api_e:
                print(f"   ⚠️  API call failed: {api_e}")

        ib.disconnect()
        print("✅ Disconnected successfully")
        return True

    except Exception as e:
        print(f"❌ Sync connection failed: {e}")
        print(f"   Error type: {type(e).__name__}")
        return False


async def check_async_connection():
    """Test asynchronous connection"""
    print("\n🧪 Test 2: Asynchronous Connection")
    print("-" * 40)

    ib = IB()

    try:
        print("Attempting async connection to localhost:4002 with client_id=101...")
        await ib.connectAsync("localhost", 4002, clientId=101, timeout=15)

        print("✅ Async connection successful!")
        print(f"   Connected: {ib.isConnected()}")

        if ib.isConnected():
            try:
                accounts = await ib.reqManagedAcctsAsync()
                print(f"   Managed accounts (async): {accounts}")
            except Exception as api_e:
                print(f"   ⚠️  Async API call failed: {api_e}")

        ib.disconnect()
        print("✅ Async disconnected successfully")
        return True

    except Exception as e:
        print(f"❌ Async connection failed: {e}")
        print(f"   Error type: {type(e).__name__}")
        return False


def check_different_client_ids():
    """Test with different client IDs to rule out conflicts"""
    print("\n🧪 Test 3: Different Client IDs")
    print("-" * 40)

    client_ids_to_test = [1, 2, 10, 50, 999]
    successful_ids = []

    for client_id in client_ids_to_test:
        ib = IB()
        try:
            print(f"Testing client_id={client_id}...", end=" ")
            ib.connect("localhost", 4002, clientId=client_id, timeout=10)

            if ib.isConnected():
                print("✅ SUCCESS")
                successful_ids.append(client_id)
                ib.disconnect()
            else:
                print("❌ Connected but not healthy")

        except Exception as e:
            print(f"❌ FAILED ({type(e).__name__})")

    print(f"\nSuccessful client IDs: {successful_ids}")
    return len(successful_ids) > 0


def check_port_variations():
    """Test different ports in case there's confusion"""
    print("\n🧪 Test 4: Port Variations")
    print("-" * 40)

    ports_to_test = [4002, 4001, 7497, 7496]
    successful_ports = []

    for port in ports_to_test:
        ib = IB()
        try:
            print(f"Testing port {port}...", end=" ")
            ib.connect("localhost", port, clientId=200, timeout=5)

            if ib.isConnected():
                print("✅ SUCCESS")
                successful_ports.append(port)
                ib.disconnect()
            else:
                print("❌ Connected but not healthy")

        except Exception as e:
            error_type = type(e).__name__
            if "refused" in str(e).lower():
                print("❌ CONNECTION REFUSED")
            elif "timeout" in str(e).lower():
                print("❌ TIMEOUT")
            else:
                print(f"❌ {error_type}")

    print(f"\nSuccessful ports: {successful_ports}")
    return len(successful_ports) > 0


def main():
    print("IB Gateway Basic Connection Test")
    print("=" * 50)
    print(f"Testing at: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        import ib_insync

        print(f"ib_insync version: {ib_insync.__version__}")
    except Exception:
        print("Could not determine ib_insync version")

    # Run all tests
    results = []

    # Test 1: Sync connection
    results.append(("Synchronous", check_sync_connection()))

    # Test 2: Async connection
    try:
        results.append(("Asynchronous", asyncio.run(check_async_connection())))
    except Exception as e:
        print(f"❌ Async test crashed: {e}")
        results.append(("Asynchronous", False))

    # Test 3: Different client IDs
    results.append(("Client ID variations", check_different_client_ids()))

    # Test 4: Different ports
    results.append(("Port variations", check_port_variations()))

    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)

    success_count = 0
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name:20} {status}")
        if success:
            success_count += 1

    print(f"\nOverall: {success_count}/{len(results)} tests passed")

    if success_count == 0:
        print("\n⚠️  NO TESTS PASSED - IB Gateway connection issue confirmed")
        print("Possible causes:")
        print("- IB Gateway not properly logged in")
        print("- API settings not configured correctly")
        print("- IB Gateway internal issues")
        print("- Network/firewall blocking connections")
    elif success_count > 0:
        print(f"\n✅ {success_count} test(s) passed - IB Gateway is accessible!")
        print("The issue may be with KTRDR's IB architecture implementation")

    return success_count > 0


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
