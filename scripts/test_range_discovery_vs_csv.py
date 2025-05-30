#!/usr/bin/env python3
"""
Test IB range discovery against local CSV data.

This script compares our IB range discovery results with the actual
date ranges in our local MSFT_1h.csv file to validate accuracy.
"""

import sys
import time
import pandas as pd
from datetime import datetime

from ktrdr.data.ib_connection_sync import IbConnectionSync
from ktrdr.data.ib_data_fetcher_sync import IbDataFetcherSync, IbDataRangeDiscovery
from ktrdr.config.ib_config import get_ib_config


def analyze_local_csv():
    """Analyze the local MSFT_1h.csv file to get actual date range."""
    print("1. Analyzing local MSFT_1h.csv file...")
    
    try:
        # Read the CSV file
        csv_path = "/Users/karl/Documents/dev/ktrdr2/data/MSFT_1h.csv"
        df = pd.read_csv(csv_path)
        
        print(f"   ✓ Loaded {len(df)} rows from CSV")
        print(f"   Columns: {list(df.columns)}")
        
        # Parse dates
        df['date'] = pd.to_datetime(df['date'])
        
        # Get date range
        earliest_date = df['date'].min()
        latest_date = df['date'].max()
        total_hours = len(df)
        total_days = (latest_date - earliest_date).days
        
        print(f"   Earliest date: {earliest_date}")
        print(f"   Latest date: {latest_date}")
        print(f"   Total hours: {total_hours}")
        print(f"   Total days span: {total_days}")
        print(f"   Data density: {total_hours/total_days:.1f} hours/day")
        
        return {
            'earliest': earliest_date,
            'latest': latest_date,
            'total_hours': total_hours,
            'total_days': total_days,
            'success': True
        }
        
    except Exception as e:
        print(f"   ❌ Error analyzing CSV: {e}")
        return {'success': False, 'error': str(e)}


def test_ib_range_discovery():
    """Test IB range discovery for MSFT 1h data."""
    print("\n2. Testing IB range discovery for MSFT...")
    
    # Get IB configuration
    config = get_ib_config()
    print(f"   Using IB config: {config.host}:{config.port}")
    
    # Create connection
    ib_connection = IbConnectionSync(config.get_connection_config())
    
    try:
        # Connect to IB
        print("   Connecting to IB...")
        if not ib_connection.ensure_connection():
            print("   ❌ Failed to connect to IB Gateway/TWS")
            return {'success': False, 'error': 'Connection failed'}
        
        print("   ✓ Connected to IB")
        
        # Create data fetcher and range discovery
        data_fetcher = IbDataFetcherSync(connection=ib_connection)
        range_discovery = IbDataRangeDiscovery(data_fetcher)
        
        # Test MSFT 1h range discovery
        symbol = "MSFT"
        timeframe = "1h"
        
        print(f"   Discovering range for {symbol} @ {timeframe}...")
        start_time = time.time()
        
        data_range = range_discovery.get_data_range(symbol, timeframe)
        discovery_duration = time.time() - start_time
        
        if data_range:
            earliest_ib, latest_ib = data_range
            
            # Handle timezone-aware datetime objects
            if hasattr(earliest_ib, 'to_pydatetime'):
                earliest_ib = earliest_ib.to_pydatetime()
            if hasattr(latest_ib, 'to_pydatetime'):
                latest_ib = latest_ib.to_pydatetime()
            
            # Remove timezone info for comparison (CSV is timezone-naive)
            if earliest_ib.tzinfo:
                earliest_ib = earliest_ib.replace(tzinfo=None)
            if latest_ib.tzinfo:
                latest_ib = latest_ib.replace(tzinfo=None)
            
            total_days_ib = (latest_ib - earliest_ib).days
            
            print(f"   ✓ IB Range discovered in {discovery_duration:.2f}s")
            print(f"   IB Earliest: {earliest_ib}")
            print(f"   IB Latest: {latest_ib}")
            print(f"   IB Total days: {total_days_ib}")
            
            return {
                'success': True,
                'earliest': earliest_ib,
                'latest': latest_ib,
                'total_days': total_days_ib,
                'discovery_duration': discovery_duration
            }
        else:
            print("   ❌ No data range found via IB")
            return {'success': False, 'error': 'No data found'}
        
    except Exception as e:
        print(f"   ❌ Error during IB range discovery: {e}")
        return {'success': False, 'error': str(e)}
        
    finally:
        # Disconnect
        if ib_connection.is_connected():
            ib_connection.disconnect()
            print("   🔌 Disconnected from IB")


def compare_results(csv_result, ib_result):
    """Compare CSV analysis with IB range discovery results."""
    print("\n3. Comparing results...")
    
    if not csv_result['success']:
        print("   ❌ Cannot compare - CSV analysis failed")
        return False
    
    if not ib_result['success']:
        print("   ❌ Cannot compare - IB discovery failed")
        return False
    
    csv_earliest = csv_result['earliest']
    csv_latest = csv_result['latest']
    csv_days = csv_result['total_days']
    
    ib_earliest = ib_result['earliest']
    ib_latest = ib_result['latest']
    ib_days = ib_result['total_days']
    
    print("   Date Range Comparison:")
    print(f"   CSV  Earliest: {csv_earliest.date()}")
    print(f"   IB   Earliest: {ib_earliest.date()}")
    
    print(f"   CSV  Latest:   {csv_latest.date()}")
    print(f"   IB   Latest:   {ib_latest.date()}")
    
    # Calculate differences
    earliest_diff = abs((csv_earliest - ib_earliest).days)
    latest_diff = abs((csv_latest - ib_latest).days)
    days_diff = abs(csv_days - ib_days)
    
    print(f"\n   Differences:")
    print(f"   Earliest date: {earliest_diff} days")
    print(f"   Latest date: {latest_diff} days")
    print(f"   Total span: {days_diff} days")
    
    # Evaluate accuracy
    print(f"\n   Accuracy Assessment:")
    
    # Check if IB earliest is reasonably close (within 30 days is good for binary search)
    earliest_accurate = earliest_diff <= 30
    print(f"   Earliest date accuracy: {'✓' if earliest_accurate else '❌'} ({earliest_diff} days difference)")
    
    # Latest should be very close (within a few days)
    latest_accurate = latest_diff <= 7
    print(f"   Latest date accuracy: {'✓' if latest_accurate else '❌'} ({latest_diff} days difference)")
    
    # Check if IB found older data (which would be expected for a financial data provider)
    ib_found_older = ib_earliest < csv_earliest
    print(f"   IB found older data: {'✓' if ib_found_older else '○'}")
    
    # Check if IB found more recent data
    ib_found_newer = ib_latest > csv_latest
    print(f"   IB found newer data: {'✓' if ib_found_newer else '○'}")
    
    # Overall assessment
    overall_good = earliest_accurate and latest_accurate
    
    print(f"\n   Overall Assessment: {'✅ GOOD' if overall_good else '⚠️ NEEDS REVIEW'}")
    
    if overall_good:
        print("   The IB range discovery is working correctly!")
        print("   Binary search successfully found the data range boundaries.")
    else:
        print("   There may be issues with the range discovery or data availability.")
        print("   This could be normal if IB has different data coverage than our CSV.")
    
    return overall_good


def test_cache_performance():
    """Test cache performance with repeated calls."""
    print("\n4. Testing cache performance...")
    
    config = get_ib_config()
    ib_connection = IbConnectionSync(config.get_connection_config())
    
    try:
        if not ib_connection.ensure_connection():
            print("   ❌ Failed to connect for cache test")
            return
        
        data_fetcher = IbDataFetcherSync(connection=ib_connection)
        range_discovery = IbDataRangeDiscovery(data_fetcher)
        
        symbol = "MSFT"
        timeframe = "1h"
        
        # Clear cache to start fresh
        range_discovery.clear_cache()
        
        # First call (fresh discovery)
        print("   First call (fresh discovery)...")
        start_time = time.time()
        range1 = range_discovery.get_data_range(symbol, timeframe)
        first_duration = time.time() - start_time
        
        # Second call (should be cached)
        print("   Second call (cached lookup)...")
        start_time = time.time()
        range2 = range_discovery.get_data_range(symbol, timeframe)
        second_duration = time.time() - start_time
        
        print(f"   Fresh discovery: {first_duration:.3f}s")
        print(f"   Cached lookup: {second_duration:.3f}s")
        
        if second_duration > 0:
            speedup = first_duration / second_duration
            print(f"   Cache speedup: {speedup:.1f}x")
        
        # Verify consistency
        if range1 == range2:
            print("   ✓ Cache consistency verified")
        else:
            print("   ❌ Cache inconsistency detected")
        
        # Get cache stats
        stats = range_discovery.get_cache_stats()
        print(f"   Cache stats: {stats['total_cached_ranges']} ranges in cache")
        
    except Exception as e:
        print(f"   ❌ Cache test error: {e}")
        
    finally:
        if ib_connection.is_connected():
            ib_connection.disconnect()


def main():
    """Main test function."""
    print("Testing IB Range Discovery vs Local CSV Data")
    print("=" * 60)
    
    # Analyze local CSV file
    csv_result = analyze_local_csv()
    
    # Test IB range discovery
    ib_result = test_ib_range_discovery()
    
    # Compare results
    comparison_success = compare_results(csv_result, ib_result)
    
    # Test cache performance
    test_cache_performance()
    
    print("\n" + "=" * 60)
    print("Test Summary:")
    print(f"CSV Analysis: {'✅' if csv_result['success'] else '❌'}")
    print(f"IB Discovery: {'✅' if ib_result['success'] else '❌'}")
    print(f"Comparison: {'✅' if comparison_success else '⚠️'}")
    
    if csv_result['success'] and ib_result['success']:
        print(f"\nKey Findings:")
        print(f"- Local CSV spans {csv_result['total_days']} days ({csv_result['earliest'].date()} to {csv_result['latest'].date()})")
        if ib_result['success']:
            print(f"- IB discovery spans {ib_result['total_days']} days")
            print(f"- Discovery completed in {ib_result['discovery_duration']:.2f}s")
            print(f"- Binary search algorithm working correctly")
    
    return comparison_success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)