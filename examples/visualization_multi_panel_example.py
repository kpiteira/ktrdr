#!/usr/bin/env python
"""
Multi-panel visualization example for KTRDR.

This example demonstrates:
1. Creating multiple panels with different indicators
2. Using different chart types in each panel
3. Synchronizing time scales across panels
4. Adding overlays to each panel
"""

import os
from pathlib import Path

import pandas as pd

from ktrdr.visualization import Visualizer


def main():
    # Load data directly using pandas
    data_path = Path("examples/demo_data/DEMO_1d.csv")
    output_dir = Path("output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = output_dir / "visualization_multi_panel_example.html"

    # Read CSV with index column as first column
    data = pd.read_csv(data_path, index_col=0)

    # Reset the index to make the date a column called 'date'
    data = data.reset_index()
    data.rename(columns={"index": "date"}, inplace=True)

    # Convert date column to datetime
    data["date"] = pd.to_datetime(data["date"])

    # Create SMA 20 and SMA 50 indicators
    data["SMA_20"] = data["close"].rolling(window=20).mean()
    data["SMA_50"] = data["close"].rolling(window=50).mean()

    # Create RSI indicator
    def calculate_rsi(series, period=14):
        delta = series.diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    data["RSI_14"] = calculate_rsi(data["close"], period=14)

    # Create MACD indicators
    def calculate_macd(series, fast_period=12, slow_period=26, signal_period=9):
        fast_ema = series.ewm(span=fast_period, adjust=False).mean()
        slow_ema = series.ewm(span=slow_period, adjust=False).mean()
        macd = fast_ema - slow_ema
        signal = macd.ewm(span=signal_period, adjust=False).mean()
        histogram = macd - signal
        return macd, signal, histogram

    data["MACD"], data["MACD_SIGNAL"], data["MACD_HIST"] = calculate_macd(data["close"])

    # Create visualizer
    visualizer = Visualizer(theme="dark")

    # Create main chart with candlesticks
    chart = visualizer.create_chart(
        data=data, title="Multi-Panel Example", chart_type="candlestick"
    )

    # Add SMA overlays to main chart
    chart = visualizer.add_indicator_overlay(
        chart=chart, data=data, column="SMA_20", color="#2196F3", title="SMA 20"
    )

    chart = visualizer.add_indicator_overlay(
        chart=chart, data=data, column="SMA_50", color="#FF5722", title="SMA 50"
    )

    # Configure range slider
    chart = visualizer.configure_range_slider(chart, show=True)

    # Add volume panel
    chart = visualizer.add_indicator_panel(
        chart=chart,
        data=data,
        column="volume",
        panel_type="histogram",
        height=150,
        color="#00BCD4",
        title="Volume",
    )

    # Add RSI panel
    chart = visualizer.add_indicator_panel(
        chart=chart,
        data=data,
        column="RSI_14",
        panel_type="line",
        height=150,
        color="#9C27B0",
        title="RSI 14",
    )

    # Add MACD panel
    chart = visualizer.add_indicator_panel(
        chart=chart,
        data=data,
        column="MACD",
        panel_type="line",
        height=150,
        color="#2196F3",
        title="MACD",
    )

    # Add MACD Signal and Histogram overlays to MACD panel
    chart = visualizer.add_indicator_overlay(
        chart=chart,
        data=data,
        column="MACD_SIGNAL",
        color="#FF5722",
        title="Signal",
        panel_id="MACD",  # Specify the MACD panel
    )

    chart = visualizer.add_indicator_overlay(
        chart=chart,
        data=data,
        column="MACD_HIST",
        color="#4CAF50",
        title="Histogram",
        panel_id="MACD",  # Specify the MACD panel
    )

    # Save chart
    output_file = visualizer.save(chart, output_path, overwrite=True)
    print(f"Multi-panel visualization saved to {output_file}")


if __name__ == "__main__":
    main()
