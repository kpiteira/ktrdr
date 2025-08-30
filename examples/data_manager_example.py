#!/usr/bin/env python3
"""
Data Manager Example

This script demonstrates the features of the DataManager class, including:
- Loading and saving data
- Data validation and repair
- Gap detection
- Context-aware outlier detection and repair
- Data resampling
- Merging datasets

"""

import logging
import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Add the project root to the path so we can import ktrdr
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler()],
)

# Import after sys.path is configured
try:
    from ktrdr.data import DataCorruptionError, DataManager
except ImportError as e:
    print(f"Error importing ktrdr modules: {e}")
    print("Make sure you're running this from the correct directory")
    sys.exit(1)


def create_sample_data_with_outliers():
    """Create a sample dataset with intentional outliers for demonstration."""
    # Create a date range
    index = pd.date_range(start="2023-01-01", periods=100, freq="1D")

    # Create synthetic price data with a trend and some randomness
    close = np.linspace(100, 150, 100) + np.random.normal(0, 5, 100)

    # Add some fake volatility
    high = close + np.random.uniform(1, 5, 100)
    low = close - np.random.uniform(1, 5, 100)
    open_price = close.copy()
    np.random.shuffle(open_price)  # Shuffle the opens for more realistic data

    # Fix OHLC relationships
    for i in range(len(close)):
        max_val = max(open_price[i], close[i])
        min_val = min(open_price[i], close[i])
        high[i] = max(high[i], max_val)
        low[i] = min(low[i], min_val)

    # Create some volume data
    volume = np.random.uniform(1000, 10000, 100)

    # Add outliers
    # Extreme price spike (close)
    close[30] = close[30] * 1.5  # 50% price spike
    high[30] = close[30] + 5

    # Extreme price drop (close)
    close[60] = close[60] * 0.7  # 30% price drop
    low[60] = close[60] - 3

    # Volume spike
    volume[45] = volume[45] * 10  # 10x volume

    # Create the DataFrame
    data = {
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }

    df = pd.DataFrame(data, index=index)

    # Add some NaN values
    df.loc[df.index[10:15], "close"] = np.nan

    # Add some negative volumes (invalid data)
    df.loc[df.index[75:77], "volume"] = -1000

    # Create some invalid OHLC relationships
    df.loc[df.index[80:82], "low"] = df.loc[df.index[80:82], "high"] + 5

    return df


def plot_data_comparison(original, repaired, title="Data Comparison"):
    """Plot original and repaired data for comparison."""
    fig, axes = plt.subplots(2, 1, figsize=(12, 10), sharex=True)

    # Plot close prices
    axes[0].plot(original.index, original["close"], "b-", label="Original Close")
    axes[0].plot(repaired.index, repaired["close"], "r-", label="Repaired Close")
    axes[0].set_title(f"{title} - Close Prices")
    axes[0].legend()
    axes[0].grid(True)

    # Plot volumes
    axes[1].bar(
        original.index,
        original["volume"],
        width=0.8,
        alpha=0.4,
        color="blue",
        label="Original Volume",
    )
    axes[1].bar(
        repaired.index,
        repaired["volume"],
        width=0.4,
        alpha=0.6,
        color="red",
        label="Repaired Volume",
    )
    axes[1].set_title("Volume Comparison")
    axes[1].legend()
    axes[1].grid(True)

    plt.tight_layout()
    plt.savefig(os.path.join(os.path.dirname(__file__), "data_repair_example.png"))
    print("Plot saved as data_repair_example.png")
    plt.close()


def demonstrate_data_manager():
    """Main function to demonstrate DataManager features."""
    print("\n" + "=" * 80)
    print("KTRDR Data Manager Demonstration".center(80))
    print("=" * 80)

    # Create a DataManager with a clean data directory for this example
    data_dir = os.path.join(os.path.dirname(__file__), "demo_data")
    os.makedirs(data_dir, exist_ok=True)
    data_manager = DataManager(data_dir=data_dir)

    # Create sample data with outliers
    print("\n1. Creating sample data with outliers, gaps, and other issues...")
    df = create_sample_data_with_outliers()
    print(f"  - Created dataset with {len(df)} rows")

    # Save the data
    symbol = "DEMO"
    timeframe = "1d"
    data_manager.data_loader.save(df, symbol, timeframe)
    print(f"  - Saved data for {symbol} ({timeframe})")

    # 1. Basic data loading
    print("\n2. Loading data and performing basic integrity check...")
    try:
        data_manager.load_data(symbol, timeframe, validate=True, strict=True)
        print("  - Data loaded successfully")
    except DataCorruptionError as e:
        print(f"  - Data corruption detected (expected): {e}")

    # 2. Data repair with different options
    print("\n3. Demonstrating different data repair options:")

    # 2.1 Standard repair with default settings
    print("\n  a) Standard repair with default settings")
    standard_repaired = data_manager.load_data(
        symbol,
        timeframe,
        validate=True,
        repair=True,
        repair_method="ffill",
        repair_outliers=True,
    )
    print(f"    - Repaired data has {len(standard_repaired)} rows")
    print("    - Outliers were repaired using global statistics")

    # 2.2 Repair without outlier repair
    print("\n  b) Repair missing values but preserve outliers")
    no_outlier_repair = data_manager.load_data(
        symbol,
        timeframe,
        validate=True,
        repair=True,
        repair_method="ffill",
        repair_outliers=False,
    )
    print(f"    - No outlier repair data has {len(no_outlier_repair)} rows")
    print("    - Outliers were detected but preserved")

    # 2.3 Context-aware outlier repair
    print("\n  c) Context-aware outlier repair")
    context_repaired = data_manager.load_data(
        symbol,
        timeframe,
        validate=True,
        repair=True,
        repair_method="ffill",
        repair_outliers=True,
        context_window=10,
    )
    print(f"    - Context-aware repaired data has {len(context_repaired)} rows")
    print("    - Outliers were repaired based on local context (10-day window)")

    # 3. Create a plot to compare original and repaired data
    print("\n4. Creating visualization to compare original and repaired data...")
    plot_data_comparison(df, standard_repaired, "Standard Repair")

    # 4. Demonstrate resampling
    print("\n5. Demonstrating data resampling...")
    weekly_data = data_manager.resample_data(
        standard_repaired, target_timeframe="1w", source_timeframe="1d"
    )
    print(
        f"  - Resampled from daily ({len(standard_repaired)} rows) to weekly ({len(weekly_data)} rows)"
    )

    # 5. Demonstrate merging datasets
    print("\n6. Demonstrating data merging...")
    # Create new data with a different date range
    new_index = pd.date_range(start="2023-04-11", periods=20, freq="1D")
    new_data = df.iloc[-20:].copy()
    new_data.index = new_index

    merged_data = data_manager.merge_data(
        symbol, timeframe, new_data, save_result=True, overwrite_conflicts=False
    )
    print(f"  - Merged {len(new_data)} rows with existing data")
    print(f"  - Final dataset has {len(merged_data)} rows")

    # 6. Get data summary
    print("\n7. Getting data summary...")
    summary = data_manager.get_data_summary(symbol, timeframe)
    print("  - Data summary:")
    for key, value in summary.items():
        if key not in ["columns", "missing_values"]:
            print(f"    - {key}: {value}")

    print("\n" + "=" * 80)
    print("Demonstration Complete".center(80))
    print("=" * 80)


if __name__ == "__main__":
    demonstrate_data_manager()
