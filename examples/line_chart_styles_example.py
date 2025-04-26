#!/usr/bin/env python
"""
Line chart styles example for KTRDR visualization module.

This example demonstrates:
1. Different line chart styles (solid, dashed, dotted)
2. Various line widths and colors
3. Creating multiple line series in a single chart
"""

import pandas as pd
import os
import numpy as np
from pathlib import Path

from ktrdr.visualization import Visualizer

# Set up output directory
output_dir = Path("output")
os.makedirs(output_dir, exist_ok=True)
output_path = output_dir / "line_chart_styles_example.html"

def main():
    """Run the line chart styles example."""
    # Load sample data
    data_path = Path("data") / "AAPL_1d.csv"
    if not data_path.exists():
        print(f"Error: Data file not found at {data_path}")
        print("Please make sure you have AAPL_1d.csv in the data directory")
        return
    
    # Load data with pandas
    df = pd.read_csv(data_path)
    
    # Convert date strings to datetime objects
    df['date'] = pd.to_datetime(df['date'])
    
    # Take only last 100 days for better visualization
    df = df.tail(100)
    
    # Create some synthetic line data with different patterns
    df['SMA10'] = df['close'].rolling(window=10).mean()
    df['SMA20'] = df['close'].rolling(window=20).mean()
    df['SMA50'] = df['close'].rolling(window=50).mean()
    df['EMA15'] = df['close'].ewm(span=15, adjust=False).mean()
    
    # Create synthetic oscillator data (values between 0 and 100)
    df['Oscillator1'] = 50 + 25 * np.sin(np.linspace(0, 10, len(df)))
    df['Oscillator2'] = 50 + 30 * np.cos(np.linspace(0, 8, len(df)))
    
    print(f"Loaded {len(df)} days of price data")
    print(f"Data range: {df['date'].min().date()} to {df['date'].max().date()}")
    
    # Create visualizer with dark theme
    visualizer = Visualizer(theme="dark")
    
    # Create the main line chart
    chart = visualizer.create_chart(
        data=df,
        title="Line Chart Styles Example",
        chart_type="line",  # Using line chart as the main chart
        height=350
    )
    
    # Add different styled line overlays
    chart = visualizer.add_indicator_overlay(
        chart=chart,
        data=df,
        column="SMA10",
        color="#FF5252",  # Red
        title="SMA 10 - Solid",
        line_width=1.0,
        line_style="solid"
    )
    
    chart = visualizer.add_indicator_overlay(
        chart=chart,
        data=df,
        column="SMA20",
        color="#2962FF",  # Blue
        title="SMA 20 - Dashed",
        line_width=1.5,
        line_style="dashed"
    )
    
    chart = visualizer.add_indicator_overlay(
        chart=chart,
        data=df,
        column="SMA50",
        color="#00BFA5",  # Teal
        title="SMA 50 - Dotted",
        line_width=2.0,
        line_style="dotted"
    )
    
    chart = visualizer.add_indicator_overlay(
        chart=chart,
        data=df,
        column="EMA15",
        color="#FFAB00",  # Amber
        title="EMA 15 - Large Dash",
        line_width=2.5,
        line_style="large_dashed"
    )
    
    # Add a separate panel with styled oscillator lines
    chart = visualizer.add_indicator_panel(
        chart=chart,
        data=df,
        column="Oscillator1",
        panel_type="line",
        height=150,
        color="#7B1FA2",  # Purple
        title="Oscillator Panel"
    )
    
    chart = visualizer.add_indicator_overlay_to_panel(
        chart=chart,
        panel_index=-1,  # Last panel (Oscillator)
        data=df,
        column="Oscillator2",
        color="#26A69A",  # Green
        title="Second Oscillator",
        line_width=1.5,
        line_style="dashed"
    )
    
    # Add horizontal reference lines
    chart = visualizer.add_horizontal_line_to_panel(
        chart=chart,
        panel_index=-1,  # Last panel (Oscillator)
        price=70,
        color="#FF5252",  # Red
        line_width=1.0,
        line_style="dashed"
    )
    
    chart = visualizer.add_horizontal_line_to_panel(
        chart=chart,
        panel_index=-1,  # Last panel (Oscillator)
        price=30,
        color="#26A69A",  # Green
        line_width=1.0,
        line_style="dashed"
    )
    
    # Add range slider
    chart = visualizer.configure_range_slider(chart, height=50, show=True)
    
    # Save the chart
    output_file = visualizer.save(chart, output_path, overwrite=True)
    print(f"Line chart styles example saved to {output_file}")
    print(f"Open {output_file} in your browser to view the chart")

if __name__ == "__main__":
    main()