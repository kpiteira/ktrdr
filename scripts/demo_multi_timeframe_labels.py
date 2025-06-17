#!/usr/bin/env python3
"""
Demo script for multi-timeframe label generation.

This script demonstrates the new MultiTimeframeLabelGenerator with
cross-timeframe validation and comprehensive label quality analysis.
"""

import sys
import numpy as np
import pandas as pd
from pathlib import Path
import warnings

# Add the project root to the path
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

from ktrdr import get_logger
from ktrdr.training.multi_timeframe_label_generator import (
    MultiTimeframeLabelGenerator,
    MultiTimeframeLabelConfig,
    TimeframeLabelConfig,
    LabelClass
)

# Set up logging
logger = get_logger(__name__)

# Suppress warnings for cleaner output
warnings.filterwarnings("ignore")


def create_sample_data() -> dict:
    """Create realistic sample multi-timeframe data."""
    print("🔄 Generating sample multi-timeframe data...")
    
    np.random.seed(42)
    
    # Create realistic price series with trends and volatility changes
    base_dates = pd.date_range('2024-01-01', periods=500, freq='1h')
    base_price = 100.0
    
    # Generate price series with regime changes
    prices = []
    current_price = base_price
    
    for i in range(500):
        # Volatility and trend regime changes
        if i < 100:
            trend, vol = 0.02, 0.5    # Bullish, low vol
        elif i < 200:
            trend, vol = -0.01, 1.0   # Bearish, medium vol
        elif i < 300:
            trend, vol = 0.0, 0.3     # Sideways, very low vol
        elif i < 400:
            trend, vol = 0.03, 2.0    # Strong bull, high vol
        else:
            trend, vol = -0.02, 1.5   # Strong bear, high vol
        
        # Generate realistic price movement
        change = np.random.normal(trend/100, vol/100)
        current_price *= (1 + change)
        prices.append(current_price)
    
    # Create multi-timeframe datasets
    data = {}
    
    # 1h data (base resolution)
    data["1h"] = pd.DataFrame({
        'open': prices,
        'high': [p * (1 + abs(np.random.normal(0, 0.1)/100)) for p in prices],
        'low': [p * (1 - abs(np.random.normal(0, 0.1)/100)) for p in prices],
        'close': prices,
        'volume': np.random.randint(1000, 50000, 500)
    }, index=base_dates)
    
    # 4h data (aggregated from 1h)
    h4_data = []
    h4_dates = base_dates[::4]
    for i in range(0, len(prices), 4):
        chunk = prices[i:i+4]
        if len(chunk) > 0:
            h4_data.append({
                'open': chunk[0],
                'high': max(chunk),
                'low': min(chunk),
                'close': chunk[-1],
                'volume': sum([1000] * len(chunk))
            })
    
    data["4h"] = pd.DataFrame(h4_data, index=h4_dates[:len(h4_data)])
    
    # 1d data (aggregated from 1h) 
    d1_data = []
    d1_dates = base_dates[::24]
    for i in range(0, len(prices), 24):
        chunk = prices[i:i+24]
        if len(chunk) > 0:
            d1_data.append({
                'open': chunk[0],
                'high': max(chunk),
                'low': min(chunk),
                'close': chunk[-1],
                'volume': sum([1000] * len(chunk))
            })
    
    data["1d"] = pd.DataFrame(d1_data, index=d1_dates[:len(d1_data)])
    
    print(f"✅ Generated data: 1h({len(data['1h'])}), 4h({len(data['4h'])}), 1d({len(data['1d'])})")
    return data


def demo_label_generation():
    """Demonstrate multi-timeframe label generation."""
    print("\n🎯 Multi-Timeframe Label Generation Demo")
    print("=" * 50)
    
    # 1. Create sample data
    price_data = create_sample_data()
    
    # 2. Configure multi-timeframe label generator
    print("\n🔧 Configuring label generator...")
    
    label_config = MultiTimeframeLabelConfig(
        timeframe_configs={
            "1h": TimeframeLabelConfig(threshold=0.02, lookahead=12, weight=0.5),  # 2%, look 12h ahead
            "4h": TimeframeLabelConfig(threshold=0.04, lookahead=6, weight=0.3),   # 4%, look 24h ahead  
            "1d": TimeframeLabelConfig(threshold=0.06, lookahead=3, weight=0.2)    # 6%, look 3d ahead
        },
        consensus_method="weighted_majority",
        consistency_threshold=0.6,
        min_confidence_score=0.5,
        label_smoothing=True
    )
    
    # 3. Generate labels
    print("📊 Generating multi-timeframe labels...")
    generator = MultiTimeframeLabelGenerator(label_config)
    
    # Try different consensus methods
    methods = ["consensus", "hierarchy", "weighted"]
    results = {}
    
    for method in methods:
        print(f"\n  📈 Testing {method} method...")
        result = generator.generate_labels(price_data, method=method)
        results[method] = result
        
        # Basic statistics
        total_labels = len(result.labels)
        buy_count = (result.labels == LabelClass.BUY.value).sum()
        hold_count = (result.labels == LabelClass.HOLD.value).sum()
        sell_count = (result.labels == LabelClass.SELL.value).sum()
        
        avg_confidence = result.confidence_scores.mean()
        avg_consistency = result.consistency_scores.mean()
        
        print(f"    Generated {total_labels} labels")
        print(f"    Distribution: BUY({buy_count}) HOLD({hold_count}) SELL({sell_count})")
        print(f"    Quality: {avg_confidence:.3f} confidence, {avg_consistency:.3f} consistency")
    
    # 4. Detailed analysis of best method
    print(f"\n🔍 Detailed Analysis - Weighted Method")
    print("-" * 40)
    
    best_result = results["weighted"]
    quality_analysis = generator.analyze_label_quality(best_result)
    
    print(f"📊 Label Quality Metrics:")
    print(f"  • Total labels: {quality_analysis['label_count']}")
    print(f"  • Average confidence: {quality_analysis['average_confidence']:.3f}")
    print(f"  • Average consistency: {quality_analysis['average_consistency']:.3f}")
    
    print(f"\n⚖️  Class Balance:")
    balance = quality_analysis['class_balance']
    print(f"  • BUY ratio: {balance['buy_ratio']:.3f}")
    print(f"  • HOLD ratio: {balance['hold_ratio']:.3f}")
    print(f"  • SELL ratio: {balance['sell_ratio']:.3f}")
    print(f"  • Balance score: {balance['balance_score']:.3f} (1.0 = perfect)")
    
    print(f"\n🔄 Temporal Quality:")
    temporal = quality_analysis['temporal_quality']
    print(f"  • Consistency: {temporal['temporal_consistency']:.3f}")
    print(f"  • Label changes: {temporal['total_label_changes']}")
    print(f"  • Change frequency: {temporal['change_frequency']:.3f}")
    print(f"  • Longest stable sequence: {temporal['longest_stable_sequence']}")
    
    print(f"\n📈 Cross-Timeframe Agreement:")
    agreement = quality_analysis['cross_timeframe_agreement']
    print(f"  • Overall agreement: {agreement['agreement_score']:.3f}")
    print(f"  • Pairwise agreements:")
    for pair, score in agreement['pairwise_agreements'].items():
        print(f"    - {pair}: {score:.3f}")
    
    # 5. Validation analysis
    print(f"\n✅ Label Validation:")
    validation_stats = best_result.metadata.get('validation_statistics', {})
    print(f"  • Validation rate: {validation_stats.get('validation_rate', 0):.1%}")
    print(f"  • Average consistency: {validation_stats.get('average_consistency', 0):.3f}")
    print(f"  • Average confidence: {validation_stats.get('average_confidence', 0):.3f}")
    
    # 6. Timeframe contributions
    print(f"\n🎯 Timeframe Contributions:")
    for timeframe, labels in best_result.timeframe_labels.items():
        distribution = best_result.label_distribution['timeframes'][timeframe]
        print(f"  • {timeframe}: {len(labels)} labels")
        print(f"    - BUY: {distribution['buy_count']} ({distribution['buy_pct']:.1f}%)")
        print(f"    - HOLD: {distribution['hold_count']} ({distribution['hold_pct']:.1f}%)")
        print(f"    - SELL: {distribution['sell_count']} ({distribution['sell_pct']:.1f}%)")
    
    # 7. Show sample of generated labels
    print(f"\n📋 Sample Labels (first 10):")
    sample_data = []
    for i in range(min(10, len(best_result.labels))):
        idx = best_result.labels.index[i]
        label = best_result.labels.iloc[i]
        confidence = best_result.confidence_scores.iloc[i]
        consistency = best_result.consistency_scores.iloc[i]
        
        label_name = {0: "BUY", 1: "HOLD", 2: "SELL"}[label]
        
        # Get timeframe labels at this index
        tf_labels = []
        for tf, tf_labels_series in best_result.timeframe_labels.items():
            if idx in tf_labels_series.index:
                tf_label = tf_labels_series[idx]
                tf_label_name = {0: "BUY", 1: "HOLD", 2: "SELL"}[tf_label]
                tf_labels.append(f"{tf}:{tf_label_name}")
        
        print(f"  {idx.strftime('%Y-%m-%d %H:%M')}: {label_name:4} "
              f"(conf:{confidence:.2f}, cons:{consistency:.2f}) "
              f"[{', '.join(tf_labels)}]")
    
    return results


def demo_temporal_consistency():
    """Demonstrate temporal consistency validation."""
    print("\n⏰ Temporal Consistency Analysis")
    print("=" * 40)
    
    # Create data with known patterns
    price_data = create_sample_data()
    
    config = MultiTimeframeLabelConfig(
        timeframe_configs={
            "1h": TimeframeLabelConfig(threshold=0.015, lookahead=8, weight=0.6),
            "4h": TimeframeLabelConfig(threshold=0.025, lookahead=4, weight=0.4)
        },
        label_smoothing=False  # Test without smoothing first
    )
    
    generator = MultiTimeframeLabelGenerator(config)
    result = generator.generate_labels(price_data, method="weighted")
    
    # Analyze temporal consistency
    temporal_metrics = generator.validate_temporal_consistency(
        result.labels, result.timeframe_labels, window_size=5
    )
    
    print(f"📊 Temporal Consistency Results:")
    print(f"  • Overall consistency: {temporal_metrics['temporal_consistency']:.3f}")
    print(f"  • Total label changes: {temporal_metrics['total_label_changes']}")
    print(f"  • Change frequency: {temporal_metrics['change_frequency']:.3f}")
    print(f"  • Longest stable sequence: {temporal_metrics['longest_stable_sequence']} bars")
    print(f"  • Window size: {temporal_metrics['window_size']}")
    
    # Test with smoothing enabled
    print(f"\n🔧 Testing with label smoothing enabled...")
    config.label_smoothing = True
    generator_smooth = MultiTimeframeLabelGenerator(config)
    result_smooth = generator_smooth.generate_labels(price_data, method="weighted")
    
    temporal_smooth = generator_smooth.validate_temporal_consistency(
        result_smooth.labels, result_smooth.timeframe_labels, window_size=5
    )
    
    print(f"📊 With Smoothing:")
    print(f"  • Overall consistency: {temporal_smooth['temporal_consistency']:.3f}")
    print(f"  • Total label changes: {temporal_smooth['total_label_changes']}")
    print(f"  • Change frequency: {temporal_smooth['change_frequency']:.3f}")
    print(f"  • Longest stable sequence: {temporal_smooth['longest_stable_sequence']} bars")
    
    improvement = temporal_smooth['temporal_consistency'] - temporal_metrics['temporal_consistency']
    print(f"  • Improvement: {improvement:+.3f}")


def main():
    """Main demo function."""
    print("🚀 Multi-Timeframe Label Generation Demo")
    print("=========================================")
    print("This demo showcases the new MultiTimeframeLabelGenerator")
    print("with cross-timeframe validation and quality analysis.\n")
    
    try:
        # Demo 1: Basic label generation
        results = demo_label_generation()
        
        # Demo 2: Temporal consistency
        demo_temporal_consistency()
        
        print(f"\n✅ Demo completed successfully!")
        print(f"\n📋 Key Features Demonstrated:")
        print(f"  ✓ Multi-timeframe label generation (1h, 4h, 1d)")
        print(f"  ✓ Three consensus methods (consensus, hierarchy, weighted)")
        print(f"  ✓ Cross-timeframe validation and agreement tracking")
        print(f"  ✓ Label quality analysis and metrics")
        print(f"  ✓ Temporal consistency validation")
        print(f"  ✓ Label smoothing for noise reduction")
        print(f"  ✓ Comprehensive metadata and statistics")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())