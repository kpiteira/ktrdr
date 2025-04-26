"""
Simple Candlestick Chart Example

This example demonstrates a minimal implementation of a candlestick chart
using AAPL daily data. This is a stripped-down version to isolate and fix
rendering issues before adding more complex features.
"""

import os
import pandas as pd
from pathlib import Path

from ktrdr.visualization.data_adapter import DataAdapter
from ktrdr.visualization.config_builder import ConfigBuilder
from ktrdr.visualization.renderer import Renderer


def load_aapl_daily_data():
    """Load AAPL daily price data."""
    data_path = Path(__file__).parents[1] / "data" / "AAPL_1d.csv"
    
    if not data_path.exists():
        raise FileNotFoundError(f"AAPL data not found at: {data_path}")
    
    # Load the CSV file with date parsing
    df = pd.read_csv(data_path, parse_dates=['date'])
    print(f"Loaded {len(df)} rows of AAPL daily data")
    
    return df


def create_simple_candlestick_chart():
    """Create a simple candlestick chart with minimal configuration."""
    # Load AAPL daily data
    df = load_aapl_daily_data()
    
    # Create renderer instance
    renderer = Renderer()
    
    # Transform OHLC data for the chart
    ohlc_data = DataAdapter.transform_ohlc(df)
    
    # Create minimal chart config with just candlesticks
    chart_options = {
        "layout": {
            "background": {"color": "#151924"},
            "textColor": "#d1d4dc"
        },
        "grid": {
            "vertLines": {"color": "#2A2E39"},
            "horzLines": {"color": "#2A2E39"}
        },
        "handleScale": True,
        "handleScroll": True,
        "rightPriceScale": {
            "borderColor": "#2A2E39",
            "visible": True,
            "autoScale": True
        },
        "timeScale": {
            "borderColor": "#2A2E39",
            "visible": True,
            "timeVisible": True,
            "secondsVisible": False,
            "fixLeftEdge": True,
            "fixRightEdge": True,
            "lockVisibleTimeRangeOnResize": True,
            "barSpacing": 6
        },
        "crosshair": {
            "mode": 0,
            "vertLine": {
                "style": 0,
                "width": 1,
                "color": "#9598A1",
                "labelBackgroundColor": "#9598A1"
            },
            "horzLine": {
                "style": 0, 
                "width": 1,
                "color": "#9598A1",
                "labelBackgroundColor": "#9598A1"
            }
        }
    }
    
    # Set up candlestick series options
    series_options = {
        "upColor": "#26a69a",      # Green for up candles
        "downColor": "#ef5350",    # Red for down candles
        "borderVisible": False,    # No borders on candles
        "wickUpColor": "#26a69a",  # Green wick for up candles
        "wickDownColor": "#ef5350" # Red wick for down candles
    }
    
    # Define a single chart config for candlesticks only
    chart_configs = [
        {
            "id": "price_chart",
            "type": "price",
            "title": "AAPL Daily Candlestick Chart",
            "height": 500,
            "options": chart_options,
            "series_options": series_options
        }
    ]
    
    # Prepare the data for the chart
    chart_data = {
        "price_chart": ohlc_data
    }
    
    # Set chart title
    title = "AAPL Daily Candlestick Chart - Simple Example"
    
    # Ensure output directory exists
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Define output path
    output_path = os.path.join(output_dir, "simple_candlestick_example.html")
    
    # Generate HTML content using the renderer
    html_content = renderer.render_chart(
        title=title,
        chart_configs=chart_configs,
        chart_data=chart_data,
        theme="dark"  # Use dark theme for better visibility
    )
    
    # Save the chart to a file
    renderer.save_chart(html_content, output_path, overwrite=True)
    print(f"Simple candlestick chart saved to: {output_path}")
    
    return output_path


if __name__ == "__main__":
    print("Simple Candlestick Chart Example")
    print("-" * 40)
    
    # Create and save the candlestick chart
    chart_path = create_simple_candlestick_chart()
    
    print("\nExample created successfully!")
    print(f"Chart saved to: {chart_path}")
    print("\nOpen this HTML file in your browser to view the chart.")