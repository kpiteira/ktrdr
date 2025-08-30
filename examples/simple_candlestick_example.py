#!/usr/bin/env python
"""
Simple candlestick chart example for KTRDR visualization module.
"""

import os
from pathlib import Path

import pandas as pd

from ktrdr.visualization import Visualizer

# Set up output directory
output_dir = Path("output")
os.makedirs(output_dir, exist_ok=True)
output_path = output_dir / "simple_candlestick_example.html"


def main():
    """Run the example to create a simple candlestick chart."""
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

    # Take only last 90 days for better visualization
    df = df.tail(90)

    print(f"Loaded {len(df)} days of price data")
    print(f"Data range: {df['date'].min().date()} to {df['date'].max().date()}")

    # Create visualizer with dark theme
    visualizer = Visualizer(theme="dark")

    # Create a simple candlestick chart
    chart = visualizer.create_chart(
        data=df, title="AAPL Daily Price", chart_type="candlestick", height=500
    )

    # Save the chart
    output_file = visualizer.save(chart, output_path, overwrite=True)
    print(f"Chart saved to {output_file}")
    print(f"Open {output_file} in your browser to view the chart")


if __name__ == "__main__":
    main()
