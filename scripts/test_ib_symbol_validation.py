#!/usr/bin/env python3
"""
Test IB symbol validation with real connection.

This script tests the IbSymbolValidator against a real IB Gateway/TWS
to verify symbol lookup functionality works correctly.
"""

import sys
import time
from datetime import datetime

from ktrdr.data.ib_connection_sync import IbConnectionSync
from ktrdr.data.ib_symbol_validator import IbSymbolValidator
from ktrdr.config.ib_config import get_ib_config


def test_symbol_validation():
    """Test symbol validation with real IB connection."""
    print("Testing IB Symbol Validation...")
    print(f"Started at: {datetime.now()}")
    print("-" * 60)
    
    # Get IB configuration
    config = get_ib_config()
    print(f"Using IB config: {config.host}:{config.port}")
    
    # Create connection
    ib_connection = IbConnectionSync(config.get_connection_config())
    
    try:
        # Ensure connection to IB
        print("\n1. Connecting to IB...")
        if not ib_connection.ensure_connection():
            print("❌ Failed to connect to IB Gateway/TWS")
            print("   Make sure IB Gateway or TWS is running")
            return False
        
        print("✓ Connected to IB")
        
        # Create validator
        validator = IbSymbolValidator(connection=ib_connection)
        
        # Test symbols with priority order
        test_symbols = [
            # Forex (should be CASH)
            "EUR.USD",
            "EUR/USD", 
            "EURUSD",
            "GBP.USD",
            "USD.JPY",
            
            # Stocks (should be STK)
            "AAPL",
            "MSFT", 
            "GOOGL",
            "TSLA",
            
            # Futures (should be FUT)
            "ES",
            "NQ",
            
            # Invalid symbols
            "INVALID123",
            "NOTREAL"
        ]
        
        print(f"\n2. Testing {len(test_symbols)} symbols...")
        print("   Priority order: CASH (forex) -> STK (stocks) -> FUT (futures)")
        
        # Test individual validation
        results = {}
        for symbol in test_symbols:
            print(f"\n   Testing: {symbol}")
            start_time = time.time()
            
            try:
                # Get contract details (includes validation)
                contract_info = validator.get_contract_details(symbol)
                duration = time.time() - start_time
                
                if contract_info:
                    results[symbol] = True
                    print(f"   ✓ Valid ({duration:.2f}s)")
                    print(f"     Type: {contract_info.asset_type}")
                    print(f"     Exchange: {contract_info.exchange}")
                    print(f"     Currency: {contract_info.currency}")
                    print(f"     Description: {contract_info.description}")
                else:
                    results[symbol] = False
                    print(f"   ❌ Invalid ({duration:.2f}s)")
                    
            except Exception as e:
                results[symbol] = False
                print(f"   ❌ Error: {e}")
        
        # Test batch validation
        print(f"\n3. Testing batch validation...")
        batch_symbols = ["EUR.USD", "AAPL", "INVALID"]
        
        start_time = time.time()
        batch_results = validator.batch_validate(batch_symbols)
        duration = time.time() - start_time
        
        print(f"   Batch validation completed in {duration:.2f}s")
        for symbol, is_valid in batch_results.items():
            status = "✓" if is_valid else "❌"
            print(f"   {status} {symbol}: {is_valid}")
        
        # Test batch contract lookup
        print(f"\n4. Testing batch contract lookup...")
        start_time = time.time()
        batch_contracts = validator.batch_get_contracts(batch_symbols)
        duration = time.time() - start_time
        
        print(f"   Batch lookup completed in {duration:.2f}s")
        for symbol, contract_info in batch_contracts.items():
            if contract_info:
                print(f"   ✓ {symbol}: {contract_info.asset_type} on {contract_info.exchange}")
            else:
                print(f"   ❌ {symbol}: Not found")
        
        # Test caching
        print(f"\n5. Testing caching performance...")
        
        # First lookup (fresh)
        start_time = time.time()
        validator.get_contract_details("EUR.USD")
        fresh_duration = time.time() - start_time
        
        # Second lookup (cached)
        start_time = time.time()
        validator.get_contract_details("EUR.USD")
        cached_duration = time.time() - start_time
        
        print(f"   Fresh lookup: {fresh_duration:.3f}s")
        print(f"   Cached lookup: {cached_duration:.3f}s")
        print(f"   Speedup: {fresh_duration/cached_duration:.1f}x")
        
        # Cache statistics
        stats = validator.get_cache_stats()
        print(f"\n6. Cache statistics:")
        print(f"   Cached symbols: {stats['cached_symbols']}")
        print(f"   Failed symbols: {stats['failed_symbols']}")
        print(f"   Total lookups: {stats['total_lookups']}")
        
        cached_symbols = validator.get_cached_symbols()
        print(f"   Cached symbol list: {', '.join(cached_symbols)}")
        
        # Test forex detection
        print(f"\n7. Testing forex detection heuristics...")
        forex_tests = [
            ("EUR.USD", True),
            ("GBP/USD", True), 
            ("EURUSD", True),
            ("AAPL", False),
            ("INVALID", False)
        ]
        
        for symbol, expected in forex_tests:
            is_forex = validator.is_forex_symbol(symbol)
            status = "✓" if is_forex == expected else "❌"
            print(f"   {status} {symbol}: {is_forex} (expected {expected})")
        
        # Summary
        print(f"\n8. Summary:")
        valid_count = sum(1 for v in results.values() if v)
        total_count = len(results)
        print(f"   Valid symbols: {valid_count}/{total_count}")
        
        forex_symbols = [s for s, info in validator._cache.items() if info.asset_type == "CASH"]
        stock_symbols = [s for s, info in validator._cache.items() if info.asset_type == "STK"]
        future_symbols = [s for s, info in validator._cache.items() if info.asset_type == "FUT"]
        
        print(f"   Forex (CASH): {len(forex_symbols)} - {', '.join(forex_symbols)}")
        print(f"   Stocks (STK): {len(stock_symbols)} - {', '.join(stock_symbols)}")
        print(f"   Futures (FUT): {len(future_symbols)} - {', '.join(future_symbols)}")
        
        print(f"\n✅ Symbol validation test completed successfully!")
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
    success = test_symbol_validation()
    sys.exit(0 if success else 1)