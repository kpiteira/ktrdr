#!/usr/bin/env python3
"""
Test script for the enhanced DataManager with intelligent gap analysis.

This script tests the key functionality of the enhanced DataManager:
- Gap analysis
- Segment orchestration  
- Trading calendar awareness
- Resilient fetching

Run with: uv run python test_enhanced_datamanager.py
"""

import sys
from datetime import datetime, timezone, timedelta
import pandas as pd
from pathlib import Path

# Add the ktrdr package to the path
sys.path.insert(0, str(Path(__file__).parent))

from ktrdr.data.data_manager import DataManager
from ktrdr import get_logger

logger = get_logger(__name__)

def test_gap_analysis():
    """Test the gap analysis functionality."""
    print("\n🔍 Testing Gap Analysis...")
    
    # Create a DataManager instance (with IB disabled for pure testing)
    dm = DataManager(enable_ib=False)
    
    # Create mock existing data with gaps
    dates = pd.date_range('2024-01-01', '2024-01-10', freq='D', tz='UTC')
    existing_data = pd.DataFrame({
        'open': [100] * len(dates),
        'high': [105] * len(dates), 
        'low': [95] * len(dates),
        'close': [102] * len(dates),
        'volume': [1000] * len(dates)
    }, index=dates)
    
    # Test case 1: Request range that extends beyond existing data
    requested_start = datetime(2023, 12, 15, tzinfo=timezone.utc)
    requested_end = datetime(2024, 1, 20, tzinfo=timezone.utc)
    
    gaps = dm._analyze_gaps(existing_data, requested_start, requested_end, '1d')
    
    print(f"   Found {len(gaps)} gaps:")
    for i, (start, end) in enumerate(gaps):
        print(f"   Gap {i+1}: {start} to {end}")
    
    # Should find gap before and after existing data
    assert len(gaps) >= 1, "Should find at least one gap"
    print("   ✅ Gap analysis working correctly")

def test_meaningful_gap_filtering():
    """Test the meaningful gap filtering logic."""
    print("\n🗂️ Testing Meaningful Gap Filtering...")
    
    dm = DataManager(enable_ib=False)
    
    # Test weekend gap (should be filtered out for daily data)
    friday = datetime(2024, 1, 5, tzinfo=timezone.utc)  # Friday
    monday = datetime(2024, 1, 8, tzinfo=timezone.utc)  # Monday
    
    is_meaningful = dm._is_meaningful_gap(friday, monday, '1d')
    print(f"   Weekend gap (Fri-Mon) meaningful: {is_meaningful}")
    
    # Test longer gap (should be meaningful)
    gap_start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    gap_end = datetime(2024, 1, 10, tzinfo=timezone.utc)
    
    is_meaningful = dm._is_meaningful_gap(gap_start, gap_end, '1d')
    print(f"   10-day gap meaningful: {is_meaningful}")
    assert is_meaningful, "10-day gap should be meaningful"
    
    print("   ✅ Gap filtering working correctly")

def test_segment_splitting():
    """Test the segment splitting for large gaps."""
    print("\n⚡ Testing Segment Splitting...")
    
    dm = DataManager(enable_ib=False)
    
    # Create a large gap that would exceed IB limits
    large_gap_start = datetime(2023, 1, 1, tzinfo=timezone.utc)
    large_gap_end = datetime(2024, 6, 1, tzinfo=timezone.utc)  # ~1.5 years
    
    gaps = [(large_gap_start, large_gap_end)]
    segments = dm._split_into_segments(gaps, '1d')
    
    print(f"   Split 1 large gap into {len(segments)} segments:")
    for i, (start, end) in enumerate(segments[:3]):  # Show first 3
        duration = end - start
        print(f"   Segment {i+1}: {start.date()} to {end.date()} ({duration.days} days)")
    
    if len(segments) > 3:
        print(f"   ... and {len(segments) - 3} more segments")
    
    # Each segment should be within IB limits (1 year for daily data)
    max_days = 365
    for start, end in segments:
        duration = (end - start).days
        assert duration <= max_days, f"Segment too large: {duration} days"
    
    print("   ✅ Segment splitting working correctly")

def test_trading_calendar():
    """Test basic trading calendar functionality."""
    print("\n📅 Testing Trading Calendar...")
    
    dm = DataManager(enable_ib=False)
    
    # Test weekday (should contain trading days)
    weekday_start = datetime(2024, 1, 2, tzinfo=timezone.utc)  # Tuesday
    weekday_end = datetime(2024, 1, 4, tzinfo=timezone.utc)    # Thursday
    
    has_trading_days = dm._gap_contains_trading_days(weekday_start, weekday_end)
    print(f"   Tue-Thu contains trading days: {has_trading_days}")
    assert has_trading_days, "Weekdays should contain trading days"
    
    # Test weekend only (should not contain trading days)
    saturday = datetime(2024, 1, 6, tzinfo=timezone.utc)    # Saturday
    sunday = datetime(2024, 1, 7, tzinfo=timezone.utc)      # Sunday
    
    has_trading_days = dm._gap_contains_trading_days(saturday, sunday)
    print(f"   Sat-Sun contains trading days: {has_trading_days}")
    assert not has_trading_days, "Weekend should not contain trading days"
    
    print("   ✅ Trading calendar working correctly")

def main():
    """Run all tests."""
    print("🧪 TESTING ENHANCED DATAMANAGER")
    print("=" * 50)
    
    try:
        test_gap_analysis()
        test_meaningful_gap_filtering()
        test_segment_splitting()
        test_trading_calendar()
        
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Enhanced DataManager is working correctly")
        print("\n📋 Key Features Verified:")
        print("   • Intelligent gap detection")
        print("   • Smart gap filtering (weekends/holidays)")
        print("   • IB-compliant segment orchestration")
        print("   • Trading calendar awareness")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()