#!/usr/bin/env python3
"""
Demonstration of Enhanced Volume=-1 Handling System

This script shows how the improved system handles IB's volume=-1 indicators
correctly, distinguishing them from actual data quality issues.
"""

import pandas as pd
from ktrdr.data.data_quality_validator import DataQualityValidator
from ktrdr.logging import get_logger

logger = get_logger(__name__)

def demo_volume_handling():
    """Demonstrate the enhanced volume=-1 handling."""
    
    print("🎯 ENHANCED VOLUME=-1 HANDLING DEMONSTRATION")
    print("=" * 52)
    
    print("📖 BACKGROUND:")
    print("   IB sends volume=-1 to indicate 'volume data not available'")
    print("   This happens for forex where volume is synthetic/estimated")
    print("   The OHLC price data is still valid and accurate")
    print("   We should NOT treat this as an 'error' to be 'corrected'")
    print()
    
    # Create realistic test data mimicking what IB sends
    test_data = {
        'timestamp': pd.date_range('2024-11-05 08:00:00', periods=8, freq='1h', tz='UTC'),
        'open': [1.0870, 1.0875, 1.0880, 1.0885, 1.0890, 1.0895, 1.0900, 1.0905],
        'high': [1.0875, 1.0880, 1.0885, 1.0890, 1.0895, 1.0900, 1.0905, 1.0910], 
        'low': [1.0865, 1.0870, 1.0875, 1.0880, 1.0885, 1.0890, 1.0895, 1.0900],
        'close': [1.0873, 1.0878, 1.0883, 1.0888, 1.0893, 1.0898, 1.0903, 1.0908],
        'volume': [150, -1, -1, -1, -1, -1, -3, 200]  # Mostly IB indicators, one bad value
    }
    
    df = pd.DataFrame(test_data)
    df.set_index('timestamp', inplace=True)
    
    print("📊 SIMULATED IB RAW DATA:")
    print(f"   Total bars: {len(df)}")
    print(f"   Volume=-1 (IB indicators): {(df['volume'] == -1).sum()}")
    print(f"   Other negative volumes: {((df['volume'] < 0) & (df['volume'] != -1)).sum()}")
    print(f"   Normal volumes: {(df['volume'] > 0).sum()}")
    print()
    
    # Show a few sample bars
    print("📋 SAMPLE BARS (showing OHLC data with volume=-1):")
    for i, (timestamp, row) in enumerate(df.head(4).iterrows()):
        vol_type = "IB_INDICATOR" if row['volume'] == -1 else "NORMAL" if row['volume'] > 0 else "INVALID"
        print(f"   {timestamp}: OHLC=[{row['open']:.4f}, {row['high']:.4f}, {row['low']:.4f}, {row['close']:.4f}], Vol={row['volume']} ({vol_type})")
    print()
    
    print("🔧 ENHANCED SYSTEM BEHAVIOR:")
    print("=" * 35)
    
    # Test the enhanced system
    validator = DataQualityValidator(auto_correct=True)
    df_processed, report = validator.validate_data(df.copy(), 'EURUSD', '1h', 'demo')
    
    print(f"📈 PROCESSING RESULTS:")
    print(f"   Issues detected: {len(report.issues)}")
    print(f"   Auto-corrections made: {report.corrections_made}")
    print(f"   Data considered healthy: {report.is_healthy()}")
    print()
    
    # Show what happened to each type of volume
    volume_neg1_preserved = (df_processed['volume'] == -1).sum()
    volume_corrected_to_zero = (df_processed['volume'] == 0).sum() - (df['volume'] == 0).sum()
    
    print(f"📊 VOLUME HANDLING RESULTS:")
    print(f"   Volume=-1 preserved: {volume_neg1_preserved} (✅ Correct - these are IB indicators)")
    print(f"   Invalid negatives corrected to 0: {volume_corrected_to_zero} (✅ Correct - these were data errors)")
    print(f"   Final volumes: {df_processed['volume'].tolist()}")
    print()
    
    print("📋 DETAILED ISSUE ANALYSIS:")
    for issue in report.issues:
        icon = "ℹ️" if issue.severity == "info" else "⚠️" if issue.severity in ["medium", "high"] else "🔍"
        correction_status = "✅ Corrected" if issue.corrected else "📊 Preserved" if issue.severity == "info" else "❌ Not corrected"
        print(f"   {icon} {issue.issue_type} ({issue.severity})")
        print(f"      Description: {issue.description}")
        print(f"      Action: {correction_status}")
        if issue.metadata and issue.metadata.get('note'):
            print(f"      Note: {issue.metadata['note']}")
        print()
    
    print("✅ KEY IMPROVEMENTS:")
    print("=" * 20)
    print("   🎯 Volume=-1 is preserved (not 'corrected' to 0)")
    print("   🎯 Volume=-1 is classified as 'info' (not an error)")
    print("   🎯 Only actual invalid negatives are corrected")
    print("   🎯 Data with volume=-1 is still considered 'healthy'")
    print("   🎯 Clear distinction between IB indicators vs data corruption")
    print("   🎯 Transparent logging shows exactly what was received vs processed")
    print()
    
    print("🔍 COMPARISON WITH OLD SYSTEM:")
    print("   ❌ Old: Treated volume=-1 as an error to be corrected")
    print("   ❌ Old: Converted all volume=-1 to 0 silently") 
    print("   ❌ Old: Lost information about IB data availability")
    print("   ✅ New: Preserves volume=-1 as valuable metadata")
    print("   ✅ New: Only corrects actual data corruption")
    print("   ✅ New: Transparent about what IB sent vs what we processed")

if __name__ == "__main__":
    demo_volume_handling()