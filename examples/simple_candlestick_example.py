"""
Simple Candlestick Chart Example

This example demonstrates how to create a basic candlestick chart
using the KTRDR Visualizer API.
"""

import pandas as pd
from pathlib import Path
import os

from ktrdr.visualization import Visualizer


def load_sample_data():
    """Load sample OHLCV data from the data directory."""
    data_path = Path(__file__).parents[1] / "data" / "AAPL_1d.csv"
    
    if not data_path.exists():
        print(f"Sample data not found at: {data_path}")
        print("Please make sure you have the AAPL_1d.csv file in the data directory.")
        return None
    
    # Load the CSV file
    df = pd.read_csv(data_path, parse_dates=['date'])
    print(f"Loaded {len(df)} rows from AAPL daily data")
    
    # Filter to most recent 100 days for cleaner visualization
    df = df.tail(100).reset_index(drop=True)
    print(f"Filtered to most recent {len(df)} days")
    
    return df


def main():
    """Main function demonstrating a simple candlestick chart."""
    print("KTRDR Simple Candlestick Example")
    print("-" * 40)
    
    # Load sample data
    df = load_sample_data()
    if df is None:
        return
    
    # Create a Visualizer instance
    visualizer = Visualizer()
    
    # Create a simple candlestick chart
    chart = visualizer.create_chart(
        data=df,
        title="AAPL Daily Price Chart",
        chart_type="candlestick",
        height=500
    )
    
    # Add a range slider for easier navigation
    chart = visualizer.configure_range_slider(chart)
    
    # Create output directory if it doesn't exist
    output_dir = Path(__file__).parents[1] / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save the chart to an HTML file
    output_path = output_dir / "simple_candlestick_example.html"
    visualizer.save(chart, output_path, overwrite=True)
    
    print(f"\nChart saved to: {output_path}")
    print("Open this HTML file in your browser to view the interactive candlestick chart.")


if __name__ == "__main__":
    main()