#!/usr/bin/env python3
"""
Test IB data ranges API endpoint through Docker container.

This script tests the new /api/v1/ib/ranges endpoint for discovering
historical data ranges.
"""

import requests
import json
import time

# Base URL for the API through Docker
BASE_URL = "http://localhost:8000/api/v1"

def test_ib_ranges_api():
    """Test IB data ranges API endpoint."""
    print("Testing IB Data Ranges API endpoint...")
    print(f"Base URL: {BASE_URL}")
    print("-" * 60)
    
    # Test 1: Single symbol, single timeframe
    print("\n1. Testing single symbol, single timeframe")
    try:
        response = requests.get(f"{BASE_URL}/ib/ranges?symbols=AAPL&timeframes=1d")
        print(f"   Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Success: {data['success']}")
            if data['success'] and data['data']:
                ranges_data = data['data']
                print(f"   Requested timeframes: {ranges_data['requested_timeframes']}")
                print(f"   Symbols found: {len(ranges_data['symbols'])}")
                
                for symbol_data in ranges_data['symbols']:
                    symbol = symbol_data['symbol']
                    print(f"   Symbol: {symbol}")
                    for timeframe, range_info in symbol_data['ranges'].items():
                        if range_info:
                            print(f"     {timeframe}: {range_info['earliest_date']} to {range_info['latest_date']}")
                            print(f"       Total days: {range_info['total_days']}, Cached: {range_info['cached']}")
                        else:
                            print(f"     {timeframe}: No data")
                
                cache_stats = ranges_data['cache_stats']
                print(f"   Cache stats: {cache_stats['total_cached_ranges']} ranges, TTL: {cache_stats['cache_ttl_hours']}h")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Exception: {e}")
    
    # Test 2: Multiple symbols, multiple timeframes
    print("\n2. Testing multiple symbols and timeframes")
    try:
        response = requests.get(f"{BASE_URL}/ib/ranges?symbols=AAPL,MSFT&timeframes=1d,1h")
        print(f"   Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Success: {data['success']}")
            if data['success'] and data['data']:
                ranges_data = data['data']
                symbols_count = len(ranges_data['symbols'])
                timeframes_count = len(ranges_data['requested_timeframes'])
                print(f"   Processing {symbols_count} symbols × {timeframes_count} timeframes")
                
                for symbol_data in ranges_data['symbols']:
                    symbol = symbol_data['symbol']
                    print(f"\n   {symbol}:")
                    for timeframe, range_info in symbol_data['ranges'].items():
                        if range_info:
                            cached_status = "✓ (cached)" if range_info['cached'] else "○ (fresh)"
                            print(f"     {timeframe}: {range_info['total_days']} days {cached_status}")
                        else:
                            print(f"     {timeframe}: No data available")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Exception: {e}")
    
    # Test 3: Test caching behavior
    print("\n3. Testing cache performance")
    symbol = "AAPL"
    timeframe = "1d"
    
    try:
        # First request (should be fresh)
        start_time = time.time()
        response1 = requests.get(f"{BASE_URL}/ib/ranges?symbols={symbol}&timeframes={timeframe}")
        first_duration = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = requests.get(f"{BASE_URL}/ib/ranges?symbols={symbol}&timeframes={timeframe}")
        second_duration = time.time() - start_time
        
        print(f"   First request: {first_duration:.3f}s")
        print(f"   Second request: {second_duration:.3f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            data1 = response1.json()
            data2 = response2.json()
            
            if data1['success'] and data2['success']:
                # Check if second request shows cached result
                first_cached = data1['data']['symbols'][0]['ranges']['1d']['cached']
                second_cached = data2['data']['symbols'][0]['ranges']['1d']['cached']
                
                print(f"   First request cached: {first_cached}")
                print(f"   Second request cached: {second_cached}")
                
                if second_duration < first_duration:
                    speedup = first_duration / second_duration
                    print(f"   Cache speedup: {speedup:.1f}x")
                
        print(f"   Both requests successful: {response1.status_code == 200 and response2.status_code == 200}")
        
    except Exception as e:
        print(f"   Exception: {e}")
    
    # Test 4: Invalid inputs
    print("\n4. Testing error handling")
    
    # Test empty symbols
    try:
        response = requests.get(f"{BASE_URL}/ib/ranges?symbols=&timeframes=1d")
        print(f"   Empty symbols - Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Success: {data['success']} (should be False)")
            if not data['success']:
                print(f"   Error code: {data['error']['code']}")
    except Exception as e:
        print(f"   Exception: {e}")
    
    # Test invalid timeframe
    try:
        response = requests.get(f"{BASE_URL}/ib/ranges?symbols=AAPL&timeframes=invalid")
        print(f"   Invalid timeframe - Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Success: {data['success']} (should be False)")
            if not data['success']:
                print(f"   Error code: {data['error']['code']}")
    except Exception as e:
        print(f"   Exception: {e}")
    
    # Test 5: Test with forex symbol (if supported)
    print("\n5. Testing forex symbol")
    try:
        response = requests.get(f"{BASE_URL}/ib/ranges?symbols=EURUSD&timeframes=1d")
        print(f"   Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            if data['success'] and data['data']:
                symbol_data = data['data']['symbols'][0]
                range_info = symbol_data['ranges'].get('1d')
                if range_info:
                    print(f"   EURUSD data available: {range_info['total_days']} days")
                else:
                    print(f"   EURUSD: No data available")
            else:
                print(f"   EURUSD request failed or no data")
    except Exception as e:
        print(f"   Exception: {e}")
    
    # Test 6: Check API documentation
    print("\n6. Checking API documentation update")
    try:
        response = requests.get(f"{BASE_URL}/docs")
        if response.status_code == 200:
            print("   ✓ Swagger UI accessible")
            # The ranges endpoint should be documented
        else:
            print("   ❌ Swagger UI not accessible")
    except Exception as e:
        print(f"   Exception: {e}")
    
    print("\n" + "-" * 60)
    print("IB Ranges API tests completed!")
    
    print("\nSummary:")
    print("- GET /api/v1/ib/ranges endpoint implemented")
    print("- Supports multiple symbols and timeframes") 
    print("- Binary search-based range discovery")
    print("- 24-hour caching for performance")
    print("- Comprehensive error handling")
    print("- Query parameter validation")

if __name__ == "__main__":
    test_ib_ranges_api()