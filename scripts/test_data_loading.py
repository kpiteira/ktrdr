#!/usr/bin/env python
"""
Test script to verify data loading from CSV files.

This script tests the DataManager's ability to load data from the existing CSV files
and prints information about the loaded data.
"""

import os
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime

# Add the project root to the path to allow importing from ktrdr
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from ktrdr.data import DataManager

def main():
    """Main test function."""
    # Create DataManager instance
    print("Creating DataManager...")
    data_manager = DataManager()
    
    # Test loading AAPL 1d data
    symbol = "AAPL"
    timeframe = "1d"
    print(f"\nTest 1: Loading {symbol} {timeframe} data...")
    try:
        df = data_manager.load(symbol=symbol, interval=timeframe)
        print(f"Successfully loaded {len(df)} rows")
        print(f"DataFrame info:")
        print(f" - Shape: {df.shape}")
        print(f" - Columns: {list(df.columns)}")
        print(f" - Index type: {type(df.index)}")
        print(f" - Date range: {df.index.min()} to {df.index.max()}")
        print("\nFirst 5 rows:")
        print(df.head(5))
    except Exception as e:
        print(f"Error loading {symbol} {timeframe} data: {str(e)}")
    
    # Test loading MSFT 1h data
    symbol = "MSFT"
    timeframe = "1h"
    print(f"\nTest 2: Loading {symbol} {timeframe} data...")
    try:
        df = data_manager.load(symbol=symbol, interval=timeframe)
        print(f"Successfully loaded {len(df)} rows")
        print(f"DataFrame info:")
        print(f" - Shape: {df.shape}")
        print(f" - Columns: {list(df.columns)}")
        print(f" - Index type: {type(df.index)}")
        print(f" - Date range: {df.index.min()} to {df.index.max()}")
        print("\nFirst 5 rows:")
        print(df.head(5))
    except Exception as e:
        print(f"Error loading {symbol} {timeframe} data: {str(e)}")
        
    # Test loading with direct pandas for comparison
    print("\nTest 3: Direct pandas read_csv for comparison...")
    try:
        csv_path = Path("data") / f"{symbol}_{timeframe}.csv"
        print(f"Reading directly from: {csv_path}")
        
        df = pd.read_csv(csv_path)
        print(f"Successfully loaded {len(df)} rows with pandas")
        print(f"DataFrame columns: {list(df.columns)}")
        
        # Try parsing date column
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            print(f"Successfully parsed date column")
            print(f"Date range: {df.index.min()} to {df.index.max()}")
        
        print("\nFirst 5 rows from direct pandas read:")
        print(df.head(5))
    except Exception as e:
        print(f"Error with direct pandas read: {str(e)}")

if __name__ == "__main__":
    main()