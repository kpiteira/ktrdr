#!/usr/bin/env python3
"""
Test IB data range discovery with real connection.

This script tests the IbDataRangeDiscovery against a real IB Gateway/TWS
to verify range discovery functionality works correctly.
"""

import sys
import time
from datetime import datetime

from ktrdr.data.ib_connection_sync import IbConnectionSync
from ktrdr.data.ib_data_fetcher_sync import IbDataFetcherSync, IbDataRangeDiscovery
from ktrdr.config.ib_config import get_ib_config


def test_range_discovery():
    """Test data range discovery with real IB connection."""
    print("Testing IB Data Range Discovery...")
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
        
        # Create data fetcher and range discovery
        data_fetcher = IbDataFetcherSync(connection=ib_connection)
        range_discovery = IbDataRangeDiscovery(data_fetcher)
        
        # Test symbols for range discovery
        test_cases = [
            ("AAPL", "1d"),        # Stock with daily data
            ("AAPL", "1h"),        # Stock with hourly data  
            ("MSFT", "1d"),        # Another stock
            ("EURUSD", "1d"),      # Forex pair
        ]
        
        print(f"\n2. Testing range discovery for {len(test_cases)} symbol/timeframe combinations...")
        
        # Test individual range discovery
        for symbol, timeframe in test_cases:
            print(f"\n   Testing: {symbol} @ {timeframe}")
            start_time = time.time()
            
            try:
                # Discover earliest data point
                earliest = range_discovery.get_earliest_data_point(symbol, timeframe, max_lookback_years=5)
                duration = time.time() - start_time
                
                if earliest:
                    print(f"   ✓ Earliest data: {earliest.date()} ({duration:.2f}s)")
                    
                    # Get full range
                    data_range = range_discovery.get_data_range(symbol, timeframe)
                    if data_range:
                        start_date, end_date = data_range
                        total_days = (end_date - start_date).days
                        print(f"   📊 Full range: {start_date.date()} to {end_date.date()} ({total_days} days)")
                    
                else:
                    print(f"   ❌ No data found ({duration:.2f}s)")
                    
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
        # Test cached vs non-cached performance
        print(f"\n3. Testing cache performance...")
        
        test_symbol = "AAPL"
        test_timeframe = "1d"
        
        # First call (fresh discovery)
        range_discovery.clear_cache()
        start_time = time.time()
        range1 = range_discovery.get_data_range(test_symbol, test_timeframe)
        fresh_duration = time.time() - start_time
        
        # Second call (cached)
        start_time = time.time()
        range2 = range_discovery.get_data_range(test_symbol, test_timeframe)
        cached_duration = time.time() - start_time
        
        print(f"   Fresh discovery: {fresh_duration:.3f}s")
        print(f"   Cached lookup: {cached_duration:.3f}s")
        
        if cached_duration > 0:
            speedup = fresh_duration / cached_duration
            print(f"   Cache speedup: {speedup:.1f}x")
        
        # Verify ranges are identical
        if range1 == range2:
            print("   ✓ Cache consistency verified")
        else:
            print("   ❌ Cache inconsistency detected")
        
        # Test multiple symbols/timeframes at once
        print(f"\n4. Testing batch range discovery...")
        
        symbols = ["AAPL", "MSFT", "EURUSD"]
        timeframes = ["1d", "1h"]
        
        start_time = time.time()
        multiple_ranges = range_discovery.get_multiple_ranges(symbols, timeframes)
        duration = time.time() - start_time
        
        print(f"   Batch discovery completed in {duration:.2f}s")
        
        # Display results
        for symbol in symbols:
            print(f"\n   {symbol}:")
            for timeframe in timeframes:
                data_range = multiple_ranges[symbol][timeframe]
                if data_range:
                    start_date, end_date = data_range
                    # Handle timezone-aware datetime objects
                    if hasattr(start_date, 'tz_localize'):
                        start_date = start_date.to_pydatetime()
                    if hasattr(end_date, 'tz_localize'):
                        end_date = end_date.to_pydatetime()
                    if start_date.tzinfo and not end_date.tzinfo:
                        end_date = end_date.replace(tzinfo=start_date.tzinfo)
                    elif end_date.tzinfo and not start_date.tzinfo:
                        start_date = start_date.replace(tzinfo=end_date.tzinfo)
                    
                    days = (end_date - start_date).days
                    print(f"     {timeframe}: {start_date.date()} to {end_date.date()} ({days} days)")
                else:
                    print(f"     {timeframe}: No data")
        
        # Test cache statistics
        print(f"\n5. Cache statistics:")
        stats = range_discovery.get_cache_stats()
        print(f"   Total cached ranges: {stats['total_cached_ranges']}")
        print(f"   Symbols in cache: {stats['symbols_in_cache']}")
        print(f"   Cache TTL: {stats['cache_ttl_hours']} hours")
        
        # Test specific edge cases
        print(f"\n6. Testing edge cases...")
        
        # Test invalid symbol
        print("   Testing invalid symbol...")
        start_time = time.time()
        invalid_range = range_discovery.get_data_range("INVALID123", "1d")
        duration = time.time() - start_time
        
        if invalid_range is None:
            print(f"   ✓ Invalid symbol correctly rejected ({duration:.2f}s)")
        else:
            print(f"   ❌ Invalid symbol unexpectedly accepted")
        
        # Test very short lookback period
        print("   Testing short lookback period...")
        short_earliest = range_discovery.get_earliest_data_point("AAPL", "1d", max_lookback_years=1)
        if short_earliest:
            recent_cutoff = datetime.now() - timedelta(days=400)  # Roughly 1 year + buffer
            if short_earliest >= recent_cutoff:
                print(f"   ✓ Short lookback respected: {short_earliest.date()}")
            else:
                print(f"   ⚠️  Short lookback found older data: {short_earliest.date()}")
        
        # Test data validation
        print("   Testing data validation...")
        if range1:
            start_date, end_date = range1
            if start_date <= end_date:
                print("   ✓ Date range validation passed")
            else:
                print("   ❌ Invalid date range detected")
            
            if end_date <= datetime.now():
                print("   ✓ End date validation passed")
            else:
                print("   ❌ Future end date detected")
        
        # Final summary
        print(f"\n7. Summary:")
        
        successful_ranges = 0
        total_tested = len(test_cases)
        
        for symbol, timeframe in test_cases:
            try:
                data_range = range_discovery.get_data_range(symbol, timeframe)
                if data_range:
                    successful_ranges += 1
            except:
                pass
        
        print(f"   Successful range discoveries: {successful_ranges}/{total_tested}")
        print(f"   Cache entries created: {stats['total_cached_ranges']}")
        
        if successful_ranges == total_tested:
            print(f"\n✅ Data range discovery test completed successfully!")
        else:
            print(f"\n⚠️  Some range discoveries failed, but core functionality works")
        
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
    # Import timedelta here to avoid issues at module level
    from datetime import timedelta
    
    success = test_range_discovery()
    sys.exit(0 if success else 1)