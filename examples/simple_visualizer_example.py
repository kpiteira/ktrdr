"""
Simple Visualizer API Example

This example demonstrates how to use the new high-level Visualizer API
to create charts with minimal code.
"""

import pandas as pd
from pathlib import Path
import os

from ktrdr.visualization import Visualizer


def load_sample_data():
    """Load sample OHLCV data from the data directory."""
    data_path = Path(__file__).parents[1] / "data" / "MSFT_1h.csv"
    
    if not data_path.exists():
        print(f"Sample data not found at: {data_path}")
        print("Please make sure you have the MSFT_1h.csv file in the data directory.")
        return None
    
    # Load the CSV file
    df = pd.read_csv(data_path, parse_dates=['date'])
    print(f"Loaded {len(df)} rows from MSFT hourly data")
    
    # Calculate some indicators for demonstration
    df['sma20'] = df['close'].rolling(window=20).mean()
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    # Calculate RSI
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    
    rs = avg_gain / avg_loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    return df


def main():
    """Main function demonstrating the Visualizer API."""
    print("KTRDR Visualizer API Example")
    print("-" * 40)
    
    # Load sample data
    df = load_sample_data()
    if df is None:
        return
    
    # Create a Visualizer instance with a dark theme
    visualizer = Visualizer(theme="dark")
    
    # Create a basic price chart
    chart = visualizer.create_chart(df, title="MSFT Price Chart")
    
    # Add indicator overlays to the price chart
    chart = visualizer.add_indicator_overlay(chart, df, "sma20", 
                                           color="#2962FF", title="SMA 20")
    chart = visualizer.add_indicator_overlay(chart, df, "ema50", 
                                           color="#FF6D00", title="EMA 50")
    
    # Add a volume panel
    chart = visualizer.add_indicator_panel(chart, df, "volume", 
                                         panel_type="histogram", 
                                         color="#26a69a")
    
    # Add an RSI panel
    chart = visualizer.add_indicator_panel(chart, df, "rsi", 
                                         panel_type="line", 
                                         color="#9C27B0",
                                         title="RSI (14)")
    
    # Add a range slider for easier navigation
    chart = visualizer.configure_range_slider(chart, height=60)
    
    # Create output directory if it doesn't exist
    output_dir = Path(__file__).parents[1] / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save the chart to an HTML file
    output_path = output_dir / "simple_visualizer_example.html"
    visualizer.save(chart, output_path, overwrite=True)
    
    print(f"\nChart saved to: {output_path}")
    print("Open this HTML file in your browser to view the interactive chart.")


if __name__ == "__main__":
    main()