#!/usr/bin/env python
"""
Simple visualizer example for KTRDR visualization module.

This example shows the most concise way to create a basic chart
with the KTRDR visualization module.
"""

import os
from pathlib import Path

import pandas as pd

from ktrdr.visualization import Visualizer


def main():
    """Run the simple visualizer example."""
    # Set up paths
    data_path = Path("data") / "AAPL_1d.csv"
    output_dir = Path("output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = output_dir / "simple_visualizer_example.html"

    # Load data
    df = pd.read_csv(data_path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.tail(60)  # Use last 60 days

    # Create visualizer and chart in one go
    visualizer = Visualizer()
    chart = visualizer.create_chart(
        data=df, title="AAPL Stock Price", chart_type="candlestick"
    )

    # Save the chart
    output_file = visualizer.save(chart, output_path, overwrite=True)
    print(f"Chart saved to {output_file}")


if __name__ == "__main__":
    main()
