#!/usr/bin/env python
"""
Indicator line chart example with theme support for KTRDR visualization module.
"""

import os
from pathlib import Path

import pandas as pd

from ktrdr.visualization import Visualizer

# Set up output directory
output_dir = Path("output")
os.makedirs(output_dir, exist_ok=True)


def main():
    """Run the example to create line charts with different themes."""
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

    # Take only last 120 days for better visualization
    df = df.tail(120)

    # Add simple moving averages for demonstration
    df["SMA20"] = df["close"].rolling(window=20).mean()
    df["SMA50"] = df["close"].rolling(window=50).mean()

    print(f"Loaded {len(df)} days of price data")
    print(f"Data range: {df['date'].min().date()} to {df['date'].max().date()}")

    # Create visualizer with dark theme
    create_theme_chart(df, "dark", output_dir / "indicator_dark_theme.html")

    # Create visualizer with light theme
    create_theme_chart(df, "light", output_dir / "indicator_light_theme.html")

    print("Both theme examples have been created")
    print("Open the HTML files in your browser to compare the themes")


def create_theme_chart(df, theme, output_path):
    """Create a chart with the specified theme."""
    print(f"Creating {theme} theme chart...")

    # Create visualizer with specified theme
    visualizer = Visualizer(theme=theme)

    # Create a candlestick chart
    chart = visualizer.create_chart(
        data=df,
        title=f"AAPL Price with SMAs ({theme} theme)",
        chart_type="candlestick",
        height=500,
    )

    # Add SMA20 as an overlay (blue line)
    chart = visualizer.add_indicator_overlay(
        chart=chart,
        data=df,
        column="SMA20",
        color="#2962FF",
        title="SMA 20",
        line_width=2.0,
    )

    # Add SMA50 as an overlay (red line)
    chart = visualizer.add_indicator_overlay(
        chart=chart,
        data=df,
        column="SMA50",
        color="#FF5252",
        title="SMA 50",
        line_width=2.0,
    )

    # Add range slider
    chart = visualizer.configure_range_slider(chart, height=60, show=True)

    # Save the chart
    output_file = visualizer.save(chart, output_path, overwrite=True)
    print(f"{theme.capitalize()} theme chart saved to {output_file}")


if __name__ == "__main__":
    main()
