"""
Test fixtures for visualization tests.

This module contains reusable fixtures for the visualization tests,
including sample data for different chart types and configurations.
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def sample_price_data():
    """Create a sample price DataFrame with various data patterns.

    This fixture creates a dataset with realistic price patterns:
    - Trending up (days 1-10)
    - Consolidation (days 11-20)
    - Trending down (days 21-30)
    - Gap up (day 17)
    - Gap down (day 24)
    """
    dates = [datetime.now() - timedelta(days=i) for i in range(30)]
    dates.reverse()  # Make them go forward in time

    # Generate realistic price patterns
    base_price = 100.0
    volatility = 2.0
    trend_up = np.array(
        [base_price + i * 1.5 + np.random.normal(0, volatility) for i in range(10)]
    )
    consolidation = np.array(
        [base_price + 15 + np.random.normal(0, volatility) for i in range(10)]
    )
    trend_down = np.array(
        [base_price + 15 - i * 1.0 + np.random.normal(0, volatility) for i in range(10)]
    )

    # Create price series
    closes = np.concatenate([trend_up, consolidation, trend_down])

    # Create open, high, low based on close
    opens = closes - np.random.uniform(-1.0, 1.0, size=30)
    highs = np.maximum(opens, closes) + np.random.uniform(0.1, 1.5, size=30)
    lows = np.minimum(opens, closes) - np.random.uniform(0.1, 1.5, size=30)

    # Create volume with increased volume on trend days
    volume = np.concatenate(
        [
            np.random.uniform(1000, 2000, size=10) * 1.5,  # Higher volume in trend up
            np.random.uniform(500, 1500, size=10),  # Lower volume in consolidation
            np.random.uniform(1000, 2500, size=10)
            * 1.7,  # Highest volume in trend down
        ]
    )

    # Add gaps
    closes[17] += 5.0  # Gap up
    opens[17] += 5.0
    highs[17] += 5.0
    lows[17] += 5.0

    closes[24] -= 7.0  # Gap down
    opens[24] -= 7.0
    highs[24] -= 7.0
    lows[24] -= 7.0

    # Create DataFrame
    return pd.DataFrame(
        {
            "date": dates,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volume,
        }
    )


@pytest.fixture
def sample_indicators(sample_price_data):
    """Create sample technical indicators for testing.

    Includes:
    - Moving averages (SMA and EMA)
    - RSI
    - MACD
    - Bollinger Bands
    """
    df = sample_price_data.copy()

    # Calculate SMA
    df["sma_10"] = df["close"].rolling(10).mean()
    df["sma_20"] = df["close"].rolling(20).mean()

    # Calculate EMA
    df["ema_10"] = df["close"].ewm(span=10).mean()
    df["ema_20"] = df["close"].ewm(span=20).mean()

    # Simple RSI calculation (not precisely the same as traditional RSI)
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan).fillna(gain)
    df["rsi"] = 100 - (100 / (1 + rs))

    # Simple MACD calculation
    df["macd_line"] = df["ema_12"] = (
        df["close"].ewm(span=12).mean() - df["close"].ewm(span=26).mean()
    )
    df["macd_signal"] = df["macd_line"].ewm(span=9).mean()
    df["macd_histogram"] = df["macd_line"] - df["macd_signal"]

    # Bollinger Bands
    sma_20 = df["close"].rolling(20).mean()
    std_20 = df["close"].rolling(20).std()
    df["bollinger_upper"] = sma_20 + (std_20 * 2)
    df["bollinger_middle"] = sma_20
    df["bollinger_lower"] = sma_20 - (std_20 * 2)

    return df


@pytest.fixture
def histogram_data():
    """Create sample histogram data with positive and negative values."""
    dates = [datetime.now() - timedelta(days=i) for i in range(30)]
    dates.reverse()

    # Generate alternating positive and negative values
    values = []
    for i in range(30):
        base = 1000 + i * 50
        if i % 3 == 0:
            values.append(-base * np.random.uniform(0.8, 1.2))
        else:
            values.append(base * np.random.uniform(0.8, 1.2))

    return pd.DataFrame({"date": dates, "value": values})


@pytest.fixture
def multiple_series_data():
    """Create sample data with multiple line series for testing overlay charts."""
    dates = [datetime.now() - timedelta(days=i) for i in range(30)]
    dates.reverse()

    # Generate multiple lines with different patterns
    line1 = [50 + i * 0.5 + np.random.normal(0, 1) for i in range(30)]  # Uptrend
    line2 = [80 - i * 0.2 + np.random.normal(0, 1) for i in range(30)]  # Downtrend
    line3 = [
        65 + 10 * np.sin(i / 3) + np.random.normal(0, 1) for i in range(30)
    ]  # Cyclic

    return pd.DataFrame(
        {"date": dates, "uptrend": line1, "downtrend": line2, "cyclic": line3}
    )


@pytest.fixture
def edge_case_data():
    """Create sample data with edge cases for testing robustness.

    Includes:
    - Missing values
    - Extreme values
    - Constant values
    - Very low volatility
    """
    dates = [datetime.now() - timedelta(days=i) for i in range(20)]
    dates.reverse()

    # Create base data
    df = pd.DataFrame(
        {
            "date": dates,
            "normal": [100 + i * 0.5 for i in range(20)],
            "missing_values": [100 + i for i in range(20)],
            "extreme_values": [100 + i * 0.5 for i in range(20)],
            "constant": [100 for _ in range(20)],
            "low_volatility": [100 + i * 0.01 for i in range(20)],
        }
    )

    # Add missing values
    df.loc[5:8, "missing_values"] = np.nan

    # Add extreme values
    df.loc[10, "extreme_values"] = 10000
    df.loc[15, "extreme_values"] = -5000

    return df
