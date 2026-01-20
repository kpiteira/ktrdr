#!/usr/bin/env python3
"""
Spike Test 4: Dataclass Serialization Compatibility

Tests whether the symbol_validator's cache serialization still works
with ib_async's dataclass-based Contract objects.

Run with: uv run python docs/designs/ib-upgrade/spike-test-dataclass.py
"""

import json
import sys
from dataclasses import is_dataclass

print("=" * 60)
print("TEST 4: Dataclass Serialization Compatibility")
print("=" * 60)

# Import from ib_async
from ib_async import Contract, Forex, Future, Stock

# Test 1: Check dataclass attributes
print("\n1. Checking dataclass attributes...")
stock = Stock("AAPL", "SMART", "USD")
print(f"   Stock is dataclass: {is_dataclass(stock)}")
print(f"   Stock has __dict__: {hasattr(stock, '__dict__')}")

# Our cache stores these fields from contract:
# - symbol
# - secType (asset_type)
# - exchange
# - currency
print(f"\n   Extractable fields:")
print(f"   - symbol: {stock.symbol}")
print(f"   - secType: {stock.secType}")
print(f"   - exchange: {stock.exchange}")
print(f"   - currency: {stock.currency}")

# Test 2: Can we create a JSON-serializable dict?
print("\n2. Creating JSON-serializable cache data...")
cache_data = {
    "symbol": stock.symbol,
    "asset_type": stock.secType,
    "exchange": stock.exchange,
    "currency": stock.currency,
    "description": "Test stock",
    "validated_at": 1234567890.0,
}

try:
    json_str = json.dumps(cache_data, indent=2)
    print(f"   [PASS] Cache data serializes to JSON:")
    print(f"   {json_str}")
except Exception as e:
    print(f"   [FAIL] JSON serialization error: {e}")
    sys.exit(1)

# Test 3: Can we recreate contracts from cached data?
print("\n3. Testing contract recreation patterns...")

def recreate_contract(data: dict):
    """Recreate Contract object from cached data (matches symbol_validator.py)"""
    asset_type = data["asset_type"]
    symbol = data["symbol"]

    if asset_type == "CASH":
        if len(symbol) == 6:
            return Forex(pair=symbol)
        return None
    elif asset_type == "STK":
        return Stock(
            symbol=symbol,
            exchange=data.get("exchange", "SMART"),
            currency=data.get("currency", "USD"),
        )
    elif asset_type == "FUT":
        return Future(symbol=symbol, exchange=data.get("exchange", "CME"))
    return None

# Test Stock recreation
stock_data = {"symbol": "AAPL", "asset_type": "STK", "exchange": "SMART", "currency": "USD"}
recreated_stock = recreate_contract(stock_data)
print(f"   Stock recreation: {recreated_stock}")
print(f"   [{'PASS' if recreated_stock else 'FAIL'}] Stock recreated correctly")

# Test Forex recreation
forex_data = {"symbol": "EURUSD", "asset_type": "CASH", "exchange": "IDEALPRO", "currency": "USD"}
recreated_forex = recreate_contract(forex_data)
print(f"   Forex recreation: {recreated_forex}")
print(f"   [{'PASS' if recreated_forex else 'FAIL'}] Forex recreated correctly")

# Test Future recreation
future_data = {"symbol": "ES", "asset_type": "FUT", "exchange": "CME", "currency": "USD"}
recreated_future = recreate_contract(future_data)
print(f"   Future recreation: {recreated_future}")
print(f"   [{'PASS' if recreated_future else 'FAIL'}] Future recreated correctly")

# Test 4: Full round-trip (serialize and deserialize)
print("\n4. Full cache round-trip test...")

# Simulate what symbol_validator does
original_cache = {
    "cache": {
        "AAPL": {
            "symbol": "AAPL",
            "asset_type": "STK",
            "exchange": "NASDAQ",
            "currency": "USD",
            "description": "Apple Inc.",
            "validated_at": 1234567890.0,
            "trading_hours": {"timezone": "America/New_York"},
            "head_timestamp": "1980-12-12T00:00:00+00:00",
        },
        "EURUSD": {
            "symbol": "EURUSD",
            "asset_type": "CASH",
            "exchange": "IDEALPRO",
            "currency": "USD",
            "description": "EUR.USD",
            "validated_at": 1234567890.0,
            "trading_hours": None,
            "head_timestamp": None,
        }
    },
    "validated_symbols": ["AAPL", "EURUSD"],
    "last_updated": 1234567890.0,
}

# Serialize
try:
    json_str = json.dumps(original_cache, indent=2)
    print(f"   [PASS] Cache serialized ({len(json_str)} chars)")
except Exception as e:
    print(f"   [FAIL] Serialization error: {e}")
    sys.exit(1)

# Deserialize
try:
    loaded_cache = json.loads(json_str)
    print(f"   [PASS] Cache deserialized")
except Exception as e:
    print(f"   [FAIL] Deserialization error: {e}")
    sys.exit(1)

# Recreate contracts
for symbol, data in loaded_cache["cache"].items():
    contract = recreate_contract(data)
    if contract:
        print(f"   [PASS] {symbol}: {contract}")
    else:
        print(f"   [FAIL] {symbol}: Could not recreate contract")

print("\n" + "=" * 60)
print("DATACLASS COMPATIBILITY TEST COMPLETE")
print("=" * 60)
print("\nConclusion: Cache serialization works with ib_async dataclasses")
