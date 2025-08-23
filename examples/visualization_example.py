#!/usr/bin/env python
"""
Comprehensive visualization example showcasing all chart types in KTRDR.

This example demonstrates:
1. Candlestick chart for price data
2. Line chart for indicators (overlays and separate panels)
3. Histogram chart for volume data
4. Theme configuration and customization
"""

import pandas as pd
import os
import numpy as np
from pathlib import Path

from ktrdr.visualization import Visualizer

# Set up output directory
output_dir = Path("output")
os.makedirs(output_dir, exist_ok=True)
output_path = output_dir / "visualization_example.html"


def main():
    """Run the comprehensive visualization example."""
    # Load sample data
    data_path = Path("data") / "AAPL_1d.csv"
    if not data_path.exists():
        print(f"Error: Data file not found at {data_path}")
        print("Please make sure you have AAPL_1d.csv in the data directory")
        return

    # Load data with pandas
    df = pd.read_csv(data_path)

    # Convert date strings to datetime objects
    df["date"] = pd.to_datetime(df["date"])

    # Take only last 100 days for better visualization
    df = df.tail(100)

    # Calculate some indicators for demonstration
    # Simple Moving Averages
    df["SMA20"] = df["close"].rolling(window=20).mean()
    df["SMA50"] = df["close"].rolling(window=50).mean()

    # Relative Strength Index (RSI) - simplified calculation for demo
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    df["RSI"] = 100 - (100 / (1 + rs))

    # MACD
    df["EMA12"] = df["close"].ewm(span=12, adjust=False).mean()
    df["EMA26"] = df["close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = df["EMA12"] - df["EMA26"]
    df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"] = df["MACD"] - df["Signal"]

    print(f"Loaded {len(df)} days of price data")
    print(f"Data range: {df['date'].min().date()} to {df['date'].max().date()}")

    # Create visualizer with dark theme
    visualizer = Visualizer(theme="dark")

    # Create a candlestick chart as the main panel
    chart = visualizer.create_chart(
        data=df, title="AAPL Price Analysis", chart_type="candlestick", height=350
    )

    # Add moving averages as line overlays on the price chart
    chart = visualizer.add_indicator_overlay(
        chart=chart,
        data=df,
        column="SMA20",
        color="#2962FF",  # Blue
        title="SMA 20",
        line_width=1.5,
    )

    chart = visualizer.add_indicator_overlay(
        chart=chart,
        data=df,
        column="SMA50",
        color="#FF5252",  # Red
        title="SMA 50",
        line_width=1.5,
    )

    # Add volume as a histogram panel
    chart = visualizer.add_indicator_panel(
        chart=chart,
        data=df,
        column="volume",
        panel_type="histogram",
        height=100,
        color="#26A69A",  # Green
        title="Volume",
    )

    # Add RSI as a line chart panel
    chart = visualizer.add_indicator_panel(
        chart=chart,
        data=df,
        column="RSI",
        panel_type="line",
        height=120,
        color="#7B1FA2",  # Purple
        title="RSI (14)",
    )

    # Add MACD as a line chart panel
    chart = visualizer.add_indicator_panel(
        chart=chart,
        data=df,
        column="MACD",
        panel_type="line",
        height=120,
        color="#2962FF",  # Blue
        title="MACD (12,26,9)",
    )

    # Add Signal line in the same panel
    chart = visualizer.add_indicator_panel(
        chart=chart,
        data=df,
        column="Signal",
        panel_type="line",
        height=0,  # Height of 0 will add to existing panel
        color="#FF6D00",  # Orange
        title="Signal",
    )

    # Add MACD histogram
    chart = visualizer.add_indicator_panel(
        chart=chart,
        data=df,
        column="MACD_Hist",
        panel_type="histogram",
        height=0,  # Height of 0 will add to existing panel
        color="#26A69A",  # Green for positive values
        title="MACD Histogram",
    )

    # Add range slider
    chart = visualizer.configure_range_slider(chart, height=50, show=True)

    # Save the chart
    output_file = visualizer.save(chart, output_path, overwrite=True)
    print(f"Comprehensive chart saved to {output_file}")
    print(f"Open {output_file} in your browser to view the chart")


if __name__ == "__main__":
    main()
