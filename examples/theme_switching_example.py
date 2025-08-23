#!/usr/bin/env python
"""
Theme switching example for KTRDR visualization module.

This example demonstrates:
1. How to create visualizations with different themes
2. Switching between light and dark themes
3. How the same data looks with different styling
"""

import pandas as pd
import os
from pathlib import Path

from ktrdr.visualization import Visualizer

# Set up output directory
output_dir = Path("output")
os.makedirs(output_dir, exist_ok=True)


def main():
    """Run the theme switching example."""
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

    # Create identical charts with different themes
    create_themed_chart(df, "dark", output_dir / "dark_theme_example.html")
    create_themed_chart(df, "light", output_dir / "light_theme_example.html")

    print("Both theme examples have been created.")
    print("Open the HTML files in your browser to compare the themes.")


def create_themed_chart(df, theme, output_path):
    """Create a chart with the specified theme."""
    print(f"Creating {theme} theme chart...")

    # Create visualizer with the specified theme
    visualizer = Visualizer(theme=theme)

    # Create a candlestick chart
    chart = visualizer.create_chart(
        data=df,
        title=f"AAPL Price Chart ({theme.capitalize()} Theme)",
        chart_type="candlestick",
        height=400,
    )

    # Add a 20-day moving average
    chart = visualizer.add_indicator_overlay(
        chart=chart,
        data=df,
        column="close",
        color="#2962FF" if theme == "dark" else "#0033CC",  # Blue (adjusted for theme)
        title="20-Day MA",
        line_width=1.5,
    )

    # Add volume as a histogram panel
    chart = visualizer.add_indicator_panel(
        chart=chart,
        data=df,
        column="volume",
        panel_type="histogram",
        height=100,
        color="#5D6D7E" if theme == "dark" else "#8395A7",  # Gray (adjusted for theme)
        title="Volume",
    )

    # Save the chart
    output_file = visualizer.save(chart, output_path, overwrite=True)
    print(f"{theme.capitalize()} theme chart saved to {output_file}")


if __name__ == "__main__":
    main()
