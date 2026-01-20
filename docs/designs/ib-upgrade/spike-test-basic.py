#!/usr/bin/env python3
"""
Spike Test 1: Basic API Compatibility Test

This script tests whether ib_async is a drop-in replacement for ib_insync
by verifying that all the APIs we use work identically.

Run with: uv run python docs/designs/ib-upgrade/spike-test-basic.py

Requirements:
- IB Gateway or TWS running on localhost:4002
"""

import asyncio
import sys
import time
from dataclasses import is_dataclass

# Test 1: Import compatibility
print("=" * 60)
print("TEST 1: Import Compatibility")
print("=" * 60)

try:
    from ib_async import IB, Contract, Forex, Stock, Future
    print("  [PASS] Core imports work: IB, Contract, Forex, Stock, Future")
except ImportError as e:
    print(f"  [FAIL] Import error: {e}")
    sys.exit(1)

# Test 2: Dataclass check (v2.0 change)
print("\n" + "=" * 60)
print("TEST 2: Dataclass Structure (v2.0 change)")
print("=" * 60)

stock = Stock("AAPL", "SMART", "USD")
forex = Forex("EURUSD")

print(f"  Stock is dataclass: {is_dataclass(stock)}")
print(f"  Forex is dataclass: {is_dataclass(forex)}")
print(f"  Stock attributes: symbol={stock.symbol}, exchange={stock.exchange}, currency={stock.currency}")
print(f"  Forex attributes: symbol={forex.symbol}, secType={forex.secType}")

# Test 3: Contract creation matches our patterns
print("\n" + "=" * 60)
print("TEST 3: Contract Creation Patterns")
print("=" * 60)

# Pattern from data_fetcher.py
try:
    stock_contract = Stock("AAPL", "SMART", "USD")
    print(f"  [PASS] Stock('AAPL', 'SMART', 'USD') → {stock_contract}")
except Exception as e:
    print(f"  [FAIL] Stock creation: {e}")

try:
    forex_contract = Forex("EURUSD")
    print(f"  [PASS] Forex('EURUSD') → {forex_contract}")
except Exception as e:
    print(f"  [FAIL] Forex creation: {e}")

# Pattern from symbol_validator.py
try:
    forex_pair = Forex(pair="EURUSD")
    print(f"  [PASS] Forex(pair='EURUSD') → {forex_pair}")
except Exception as e:
    print(f"  [FAIL] Forex(pair=...) creation: {e}")

try:
    future_contract = Future(symbol="ES", exchange="CME")
    print(f"  [PASS] Future(symbol='ES', exchange='CME') → {future_contract}")
except Exception as e:
    print(f"  [FAIL] Future creation: {e}")


async def test_connection():
    """Test connection and API calls."""
    print("\n" + "=" * 60)
    print("TEST 4: IB Connection (requires IB Gateway on :4002)")
    print("=" * 60)

    ib = IB()

    # Test 4a: Connection
    try:
        print("  Connecting to IB Gateway...")
        await ib.connectAsync(
            host="127.0.0.1",
            port=4002,
            clientId=9999,  # Use high client ID to avoid conflicts
            timeout=10.0
        )
        print(f"  [PASS] connectAsync() succeeded")
        print(f"  [INFO] isConnected() = {ib.isConnected()}")
    except Exception as e:
        print(f"  [SKIP] Connection failed (IB Gateway not running?): {e}")
        return

    try:
        # Test 4b: managedAccounts (used in health check)
        print("\n  Testing managedAccounts()...")
        accounts = ib.managedAccounts()
        print(f"  [PASS] managedAccounts() = {accounts}")

        # Test 4c: reqContractDetails (used in symbol_validator)
        print("\n  Testing reqContractDetails()...")
        stock = Stock("AAPL", "SMART", "USD")
        details = ib.reqContractDetails(stock)
        print(f"  [PASS] reqContractDetails() returned {len(details)} results")
        if details:
            d = details[0]
            print(f"  [INFO] Contract: {d.contract.symbol}, {d.longName}")
            print(f"  [INFO] Result is dataclass: {is_dataclass(d)}")

        # Test 4d: reqHistoricalData (used in data_fetcher)
        print("\n  Testing reqHistoricalData()...")
        from datetime import datetime, timezone
        end_dt = datetime.now(timezone.utc)
        bars = ib.reqHistoricalData(
            contract=stock,
            endDateTime=end_dt,
            durationStr="1 D",
            barSizeSetting="1 hour",
            whatToShow="TRADES",
            useRTH=True,
            formatDate=1
        )
        print(f"  [PASS] reqHistoricalData() returned {len(bars)} bars")
        if bars:
            print(f"  [INFO] First bar: {bars[0]}")
            print(f"  [INFO] Bar is dataclass: {is_dataclass(bars[0])}")

        # Test 4e: reqHeadTimeStamp (used in symbol_validator)
        print("\n  Testing reqHeadTimeStamp()...")
        head_ts = ib.reqHeadTimeStamp(
            contract=stock,
            whatToShow="TRADES",
            useRTH=False,
            formatDate=1
        )
        print(f"  [PASS] reqHeadTimeStamp() = {head_ts}")

    except Exception as e:
        print(f"  [FAIL] API call error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Test 4f: Disconnect
        print("\n  Testing disconnect()...")
        ib.disconnect()
        print(f"  [PASS] disconnect() succeeded")
        print(f"  [INFO] isConnected() after disconnect = {ib.isConnected()}")


# Test 5: Event loop handling (key concern)
print("\n" + "=" * 60)
print("TEST 5: Event Loop Handling")
print("=" * 60)

try:
    # This is the pattern we use in connection.py
    import asyncio

    # Create new event loop (like we do in dedicated thread)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    print(f"  [PASS] asyncio.new_event_loop() works")
    print(f"  [INFO] Loop: {loop}")

    # Run the connection test
    loop.run_until_complete(test_connection())

    # Close loop (like we do on disconnect)
    loop.close()
    print(f"  [PASS] loop.close() succeeded")

except Exception as e:
    print(f"  [FAIL] Event loop handling error: {e}")
    import traceback
    traceback.print_exc()


print("\n" + "=" * 60)
print("SPIKE TEST COMPLETE")
print("=" * 60)
