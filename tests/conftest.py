"""
Global test fixtures for the KTRDR project.

This module contains test fixtures that can be used across all test modules.
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

@pytest.fixture
def sample_ohlcv_data():
    """
    Generate sample OHLCV (Open, High, Low, Close, Volume) data for testing.
    
    Returns:
        pd.DataFrame: A DataFrame with synthetic OHLCV data.
    """
    # Create date range for the last 30 days
    end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = end_date - timedelta(days=30)
    dates = pd.date_range(start=start_date, end=end_date, freq='D')
    
    # Generate random price data with somewhat realistic behavior
    np.random.seed(42)  # For reproducible tests
    
    # Start with a base price and create movements that are somewhat correlated
    base_price = 100.0
    daily_changes = np.random.normal(0, 1, len(dates)) * 0.01  # 1% standard deviation
    
    # Compute close prices with a random walk
    closes = []
    current_price = base_price
    for change in daily_changes:
        current_price = current_price * (1 + change)
        closes.append(current_price)
    
    # Generate other OHLCV values based on close
    opens = [closes[0]] + closes[:-1]  # Previous day's close is today's open
    
    # High is max of open and close plus a random amount
    highs = [max(o, c) * (1 + abs(np.random.normal(0, 0.005))) 
             for o, c in zip(opens, closes)]
    
    # Low is min of open and close minus a random amount
    lows = [min(o, c) * (1 - abs(np.random.normal(0, 0.005))) 
            for o, c in zip(opens, closes)]
    
    # Volume is random but correlated with price movement
    volumes = [int(np.random.normal(1000000, 200000) * (1 + 5 * abs(c/o - 1))) 
               for o, c in zip(opens, closes)]
    
    # Create DataFrame
    df = pd.DataFrame({
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': volumes
    }, index=dates)
    
    return df

@pytest.fixture
def sample_ohlcv_csv(tmp_path):
    """
    Create a temporary CSV file with sample OHLCV data for testing.
    
    Args:
        tmp_path: pytest fixture that provides a temporary directory path
        
    Returns:
        Path: Path to the temporary CSV file with sample data.
    """
    # Get sample data
    df = pd.DataFrame({
        'date': pd.date_range(start=datetime.now() - timedelta(days=30), end=datetime.now(), freq='D'),
        'open': np.random.normal(100, 5, 31),
        'high': np.random.normal(105, 5, 31),
        'low': np.random.normal(95, 5, 31),
        'close': np.random.normal(102, 5, 31),
        'volume': np.random.randint(500000, 1500000, 31)
    })
    
    # Create a CSV file in the temporary directory
    csv_path = tmp_path / "sample_AAPL_1d.csv"
    
    # Save to CSV
    df.to_csv(csv_path, index=False)
    
    return csv_path

@pytest.fixture
def corrupt_ohlcv_csv(tmp_path):
    """
    Create a corrupt CSV file for testing error handling.
    
    Args:
        tmp_path: pytest fixture that provides a temporary directory path
        
    Returns:
        Path: Path to the corrupt CSV file.
    """
    # Create a CSV file with invalid content
    csv_path = tmp_path / "corrupt_AAPL_1d.csv"
    
    with open(csv_path, 'w') as f:
        f.write("date,open,high,low,close,volume\n")
        f.write("2023-01-01,100,105,95,invalid,10000\n")  # Invalid close price
        f.write("garbage data that will cause parsing error\n")
        f.write("2023-01-03,102,107,98,103,12000\n")
    
    return csv_path