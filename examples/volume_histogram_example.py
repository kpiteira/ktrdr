#!/usr/bin/env python
"""
Volume histogram chart example for KTRDR visualization module.
"""

import pandas as pd
import os
from pathlib import Path

from ktrdr.visualization import Visualizer

# Set up output directory
output_dir = Path("output")
os.makedirs(output_dir, exist_ok=True)
output_path = output_dir / "volume_histogram_example.html"


def main():
    """Run the example to create a candlestick chart with volume histogram."""
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

    # Take only last 60 days for better visualization
    df = df.tail(60)

    print(f"Loaded {len(df)} days of price data")
    print(f"Data range: {df['date'].min().date()} to {df['date'].max().date()}")

    # Create visualizer with dark theme
    visualizer = Visualizer(theme="dark")

    # Create a candlestick chart
    chart = visualizer.create_chart(
        data=df, title="AAPL Price with Volume", chart_type="candlestick", height=400
    )

    # Add volume as a separate histogram panel
    chart = visualizer.add_indicator_panel(
        chart=chart,
        data=df,
        column="volume",
        panel_type="histogram",
        height=150,
        color="#26a69a",  # Green color for volume bars
        title="Volume",
    )

    # Add range slider for easier navigation
    chart = visualizer.configure_range_slider(chart, height=60, show=True)

    # Save the chart
    output_file = visualizer.save(chart, output_path, overwrite=True)
    print(f"Chart saved to {output_file}")
    print(f"Open {output_file} in your browser to view the chart")


if __name__ == "__main__":
    main()
